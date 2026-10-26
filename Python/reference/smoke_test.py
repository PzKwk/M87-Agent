"""Finite NON-LEARNING protocol/build smoke test. No policy training occurs."""
import argparse
import json
from pathlib import Path
import sys

from ground_arena_client import ArenaClient, ArenaError, ConnectionLost, ProtocolError


def choose_actions(observation):
    """Use first supplied candidate, otherwise HOLD; IDs remain opaque."""
    actions = []
    for decision in observation.get("decisions", []):
        candidates = decision.get("candidates", [])
        action = {"unit_id": decision["unit_id"], "kind": "hold"}
        if candidates:
            action.update(kind="move", candidate_id=candidates[0]["candidate_id"])
        actions.append(action)
    return actions


def run_smoke(client, episodes=1, max_steps=500, *, ticks=4, arena=0, pair_index=0,
              seed=None, control="attacker", stream=None):
    """Bounded exercise of reset/step. Return per-episode diagnostics."""
    if type(episodes) is not int or episodes < 1 or type(max_steps) is not int or max_steps < 1:
        raise ValueError("episodes and max_steps must be positive integers")
    stream = sys.stdout if stream is None else stream
    summaries = []
    for episode_index in range(episodes):
        observation = client.reset(arena=arena, pair_index=pair_index, seed=seed, control=control)
        moves = holds = steps = 0
        while not observation["terminated"] and not observation["truncated"] and steps < max_steps:
            actions = choose_actions(observation)
            moves += sum(action["kind"] == "move" for action in actions)
            holds += sum(action["kind"] == "hold" for action in actions)
            observation = client.step(observation["episode"], observation["observation_id"], actions, ticks=ticks)
            steps += 1
        cap = not observation["terminated"] and not observation["truncated"] and steps >= max_steps
        summary = {"episode_index": episode_index, "episode": observation["episode"],
                   "steps": steps, "move_actions": moves, "hold_actions": holds,
                   "terminated": observation["terminated"], "truncated": observation["truncated"],
                   "step_cap_reached": cap, "scores": observation.get("scores"),
                   "rewards": observation.get("rewards"), "result": observation.get("result")}
        summaries.append(summary)
        print("episode={} steps={} terminated={} truncated={} step_cap_reached={} result={}".format(
            summary["episode"], steps, summary["terminated"], summary["truncated"], cap,
            json.dumps(summary["result"], ensure_ascii=True)), file=stream, flush=True)
        if not moves and steps:
            print("HOLD-only diagnostic: no move candidates were selected (HOLD actions: {}). "
                  "Inspect decisions, ghost_lock_seconds, geometry readiness and movement eligibility; "
                  "this is not evidence of a learning policy.".format(holds), file=stream, flush=True)
    return summaries


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--build", type=Path, help="Arena executable to launch (absolute path recommended)")
    source.add_argument("--endpoint", type=Path, help="Connect to a running local training build")
    parser.add_argument("--runs", type=Path, default=Path("arena-runs"), help="Parent for unique launch run folders")
    parser.add_argument("--results", type=Path, help="New JSONL result file; refuses to overwrite")
    parser.add_argument("--episodes", type=int, default=1)
    parser.add_argument("--max-steps", type=int, default=500)
    parser.add_argument("--ticks", type=int, default=4)
    parser.add_argument("--arena", type=int, default=0)
    parser.add_argument("--pair-index", type=int, default=0)
    parser.add_argument("--seed", type=int)
    parser.add_argument("--control", choices=("attacker", "defender", "both"), default="attacker")
    parser.add_argument("--timeout", type=float, default=120.0, help="Per-request total timeout in seconds")
    parser.add_argument("--startup-timeout", type=float, default=120.0)
    parser.add_argument("--build-arg", action="append", default=[], help="Extra Unity arg, e.g. --build-arg=-batchmode")
    options = parser.parse_args(argv)
    if options.episodes < 1 or options.max_steps < 1 or not 1 <= options.ticks <= 200:
        parser.error("episodes/max-steps must be positive; ticks must be 1..200")
    if options.endpoint and options.build_arg:
        parser.error("--build-arg requires --build")
    results_stream = None
    try:
        # Reserve a requested output before touching a live session.
        if options.results:
            results_stream = options.results.expanduser().resolve().open("x", encoding="utf-8")
        client = (ArenaClient.launch(options.build, options.runs, timeout=options.timeout,
                                    startup_timeout=options.startup_timeout, extra_args=options.build_arg)
                  if options.build else ArenaClient.connect(options.endpoint, timeout=options.timeout))
        with client:
            print("NON-LEARNING smoke test; first candidate or HOLD. No weights are trained.", flush=True)
            if client.run_directory:
                print("Run directory: " + str(client.run_directory), flush=True)
                if results_stream is None:
                    results_stream = (client.run_directory / "smoke-results.jsonl").open("x", encoding="utf-8")
            catalog = client.catalog()
            print("Catalog received ({}).".format(type(catalog).__name__), flush=True)
            summaries = run_smoke(client, options.episodes, options.max_steps, ticks=options.ticks,
                                  arena=options.arena, pair_index=options.pair_index, seed=options.seed,
                                  control=options.control)
            # Exercise read APIs too; observations do not produce another terminal reward.
            client.observe(summaries[-1]["episode"])
            terrain = client.terrain(summaries[-1]["episode"])
            print("Observe and terrain received ({}).".format(type(terrain).__name__), flush=True)
            if results_stream:
                for summary in summaries:
                    results_stream.write(json.dumps(summary, ensure_ascii=True, allow_nan=False) + "\n")
                results_stream.flush()
            return 2 if any(summary["step_cap_reached"] for summary in summaries) else 0
    except (ArenaError, ConnectionLost, ProtocolError, OSError, ValueError) as error:
        print("Smoke test failed: {}: {}".format(type(error).__name__, error), file=sys.stderr)
        return 1
    finally:
        if results_stream:
            results_stream.close()


if __name__ == "__main__":
    raise SystemExit(main())
