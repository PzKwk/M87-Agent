# Ground Arena External Training Implementation Plan

> **For agentic workers:** Use `superpowers:executing-plans` to implement this plan task by task. Checkboxes describe future work, not completed validation. The user requested PLAN first; do not treat this document as evidence of a successful Unity run.

**Goal:** Validate the supplied Unity Arena, establish reproducible deterministic-opponent baselines, and incrementally train a local movement policy, with a separate Jev-off/Jev-on benchmark launcher.

**Architecture:** Keep Unity authoritative and use its supplied synchronous JSON/TCP client. Python discovers scenarios, models and legal candidates at runtime, records valid trajectories, trains locally and evaluates frozen checkpoints. Jev assistance belongs exclusively to a separate benchmark workflow and must match the existing Black Stars assistance behavior.

**Tech stack:** Windows, existing Python 3.13.2, standard library for validation/baselines; a workspace-local environment and a compatible pinned local learning library for the learning stage. No cloud model or TypeSafe API dependency in training. PyTorch with a small candidate-scoring actor/critic is the proposed learning implementation; verify compatibility before installing it.

**Spec:** User instructions of 2026-10-26, including the follow-up: training uses deterministic AI without TypeSafe API; separate benchmark executable compares deterministic AI alone with the existing Jev-assisted deterministic AI.

## Constraints and paths

- Game reference root: `C:/Users/lrt71/Black Stars - The M87 Conflict`. Read only; no edits, imports that write bytecode, builds, dependency installation or output there.
- Training root: `C:/Users/lrt71/Desktop/Agent M87`. All authored code, dependencies, caches, datasets, logs and model artifacts stay here.
- Actual training build: `TrainingsArena/GroundArenaServer.exe`. The existing directory is spelled **TrainingsArena**, not TrainingArena. Preserve that name.
- Player test build: `TestArena/GroundArena.exe`. Preserve the full Unity directories and companion files.
- All Python sources and Python dependency environments go under `Python/`; trained weights and accompanying checkpoint records go under `Models/`.
- Training launches the Arena executable directly, not `BlackStarsLauncher.exe`, whose packaged MAIN workflow starts a TypeSafe service.
- No TypeSafe/Jev calls, credentials or service imports in the training workflow. Seeded stochastic exploration during learning is separate from the deterministic opponent; frozen evaluation uses deterministic action selection.
- Preserve shared game accounts, prices, upkeep, navigation, combat, ghost locks and finite scenario resources. No new game actions or AI-rule changes are proposed.
- Keep scenario scores, raw server rewards, learner rewards, natural endings, server time limits and local cutoffs distinct.
- A trained file does not install inference in MAIN or enable human-vs-model play. Such integration is outside this plan.

## Inspection evidence and limits

The game `AGENTS.md`, `Markdown/GroundArenaTraining.md`, kit `README.md` and `PROTOCOL.md`, `Markdown/GroundArena.md`, and training validation report were read. The complete Python client and smoke test were inspected, along with selected transport tests and targeted Arena host/session/rules/build-hook source.

`Markdown/KI.md` contains 6,394 lines / 567,570 bytes. Current Arena, shared hit/upkeep, fairness and ground-AI material was inspected; some broad reads were truncated. A complete, continuous review is not claimed. Finish that read in preflight; in particular, never propose AI-rule changes on the basis of these excerpts. This plan changes no AI/game rules.

Observed locally:

- Both build folders contain an executable, matching data folder, UnityPlayer and Mono runtime. This is structural inspection, not proof of a complete or compatible working build.
- Neither build folder contains the documented `GroundArenaTraining` kit. Its authored source exists in the read-only game project and can be copied into `Python/reference/`.
- `Python/` and `Models/` are empty. The training root is not currently a Git repository.
- Python reports `3.13.2`.
- Training build GUID in `boot.config`: `679b43b7ff514609a52047d6b0fe19e0`.
- Training EXE SHA-256: `246EB2CC741F8B9E93381272C356F4A5C99F01F48440E83B69EE1280DD933CC5`.
- Training `Assembly-CSharp.dll` SHA-256: `468C7A938A48949B7C67AF336562B83DBFB0E46D87A9D57398D1F376A1FA2680`.
- Source client SHA-256: `6A2EEB8B5EC9CF0D4E443956371C056CBE293246B6DE2FC5EA6E75A83F07DFF3`.
- Source smoke-test SHA-256: `B12196197089D3AB340B25200355C48CEF384133F25A197EC410B1F410EC0FB1`.

No build has been launched, smoke test run, dependency installed or model trained during planning. No reference-project access restriction was encountered. File timestamps and hashes do not prove that these binaries match the inspected source.

## Interface established from documentation and source

| Area | Contract to verify against the real build |
| --- | --- |
| Transport | `blackstars-ground-arena/1`; authenticated `127.0.0.1` TCP; one strict UTF-8 JSON object per line; serial requests per connection. Not an ML-Agents adapter. |
| Discovery | `catalog` lists scenario slots, modes, pairings and rosters. `terrain(episode)` supplies tiles, adjacency and model statistics. No fixed observation size is specified. |
| Observations | Variable unit and decision arrays, `planet_local` positions, HP, prices, ghosts and locks. Join model data by `model_id`. Source also exposes `moving` and `upkeep_unpaid`; confirm live before using them. |
| Actions | HOLD preserves an existing order. MOVE uses only a candidate ID from the current observation for that unit. `action_results[].accepted/reason` is authoritative about acceptance. |
| Scheduling | Normally one decision unit per controlled side. `observe(unit_id=...)` creates a fresh observation and invalidates prior candidates. Do not combine candidates from separate observations. |
| Time | A tick is 0.05 simulation seconds, 1–200 ticks per step; default 4. Idle requests do not advance simulation. Shared game work budgets remain in force. |
| Reset | Ordinary reset invalidates all prior episodes. Retention requires explicit `keep_others` and bounded concurrency; start with one episode/process. |
| Failure | Explicit `ArenaError` preserves the connection, but the affected episode may require reset. Timeout/transport/protocol failure discards the connection; never replay an uncertain step. Reconnect and reset. |
| Rewards | Scores are scenario values. Raw terminal reward is the once-only score difference divided by reward scale. A later observe does not repeat it. Save the step response before any extra observe. |
| Endings | Elimination and overwhelming-mode 900-second survival are natural terminations. Optional balanced-mode time limit is `truncated`. A Python step/wall-clock cap is a separate local cutoff. |
| Ownership | `launch` owns only its child process; `connect` owns no process. Never terminate a PID merely because it appears in an endpoint file. |

The source has its own 120-second pending reset/step deadline. Increasing only Python's timeout must not be presented as removing that server deadline.

## Proposed approach

Use a small local candidate scorer after transport and trajectory validation. This follows the variable legal-action interface and offers a quick learning diagnostic. A fixed-width action index based on invented observation dimensions is unsuitable. A large recurrent/graph policy and self-play may become later experiments, after measured baseline limitations justify them.

Initial opponents remain the existing deterministic AI. Do not reimplement or alter its game rules. Jev-assisted benchmarking is a separate dependency, not a condition for starting API-free training.

## Files and ownership

| Path | Responsibility |
| --- | --- |
| `Python/reference/` | Exact copied client, smoke test, documentation and authored tests; exclude source caches. |
| `Python/arena_training/provenance.py` | Build/client hashes, runtime/config/schema versions, reproducibility manifests. |
| `Python/arena_training/session.py` | Client lifecycle, fresh observations, outcome classification and error recovery. |
| `Python/arena_training/baselines.py` | HOLD, existing first-candidate policy and seeded legal-random policies. |
| `Python/arena_training/features.py` | Runtime schema/model joins, entity/candidate encoding and masks. |
| `Python/arena_training/policy.py`, `train.py`, `evaluate.py` | Local learning, checkpoint restore and frozen evaluation. |
| `Python/arena_training/benchmark.py` | Separate paired benchmark orchestration; no import from the training entry point. |
| `Python/tests/` | Focused lifecycle, feature, learning and evaluation tests. |
| `Python/configs/`, `Python/.venv/`, `Python/.cache/`, `Python/tmp/` | Configurations and all Python dependencies/caches/temp files. |
| `Runs/<run-id>/`, `Datasets/<dataset-id>/` | Immutable run evidence and optional versioned trajectories. |
| `Models/<experiment>/<checkpoint>/` | Weights, optimizer/RNG state, configuration, seed splits, manifest and evaluation results together. |
| `BenchmarkArena.exe` | Separate benchmark launcher, built entirely inside this workspace. |

## Review focus

1. Stale candidates after observe/reset, including repeated numeric candidate IDs: bind choices to episode, observation and unit (Task 2).
2. A timed-out step may already have executed: no replay or fabricated transition (Task 2).
3. A successful response can contain rejected moves: measure acceptance and preserve the actual state transition (Tasks 1–2).
4. Local cutoffs, balanced time limits and survival wins have different semantics: separate metrics and learning boundaries (Tasks 2 and 4).
5. Jev unavailable or silently falling back must not be reported as Jev-on: require assistance evidence, identical benchmark settings and explicit failure status (Task 6).

## Task 1 — Native build preflight and existing smoke test

**Deliverable:** A reproducible real Unity smoke report, or an exact runtime blocker with logs. This is the first execution milestone.

- [ ] Finish the untruncated `KI.md` read, keeping current rules distinct from historical entries. No rule changes are needed.
- [ ] Copy only the authored kit files into `Python/reference/`; compare source/destination hashes. Do not copy `.env`, `__pycache__` or game dependencies.
- [ ] Inventory the full training build and record hashes of runtime assemblies, configuration/data files and runtime libraries, not just the generic Unity EXE. Record the source/protocol hashes separately; do not assert source/binary equivalence without evidence.
- [ ] Reserve a new workspace run folder. Set Python temp/cache paths inside the workspace. Arrange Unity logging into the run output rather than its default user-profile log, and verify that arrangement.
- [ ] Run the existing smoke test unchanged against `TrainingsArena/GroundArenaServer.exe`: initial `--episodes 2 --max-steps 500 --ticks 4 --seed 87 --control attacker`, with explicit absolute `--build` and `--runs` paths. Launch the Arena directly, leaving the TypeSafe launcher/service unused.
- [ ] Capture command, exit code, stdout/stderr, Unity log, endpoint metadata without publishing its token, and both smoke/server result files. `0` means server-ended episodes; `1` means failure; `2` means at least one local cap, not a completed battle. At 4 ticks, 500 steps is at most 100 simulation seconds.
- [ ] After catalog inspection, repeat with discovered valid selections for defender and both controls. Extend a bounded run to seek a real natural ending; initially allow 6,000 steps, recording unresolved stalemates as local cutoffs. Do not require endless execution to obtain a win.
- [ ] Inspect real observations and `action_results`: the supplied smoke test counts attempted moves, not accepted moves. Add a separate diagnostic runner only after the original smoke attempt. Require an accepted MOVE, actual simulation progress, a returned ending/reward and a subsequent fresh reset before calling the full native path verified.
- [ ] Run the copied 15-test socket suite as a separate client regression check. Label it as a synthetic-peer test, never native evidence.

If launch, geometry, endpoint, reset or combat fails, preserve evidence and report the exact executable/path, error and restriction. Diagnose read-only source as needed. Do not repair or rebuild the game project. Missing kit is recoverable by the authorized copy; missing runtime functionality requires a compatible supplied build.

## Task 2 — Validated rollout recording

**Files:** `provenance.py`, `session.py`, `Python/tests/test_session.py`, `Python/tests/test_provenance.py`.

**Interfaces:** `capture_manifest(build_path, config, seed_split) -> dict`; `run_episode(client, scenario, policy, limits, recorder) -> dict`. Policies consume the latest complete observation plus episode terrain and return only legal action dictionaries.

- [ ] Write focused tests for stale IDs after observe/reset, explicit move rejection, terminal reward once-only, transport loss after send, failed replacement reset, and separate outcome categories. Verify they fail before implementing the wrapper.
- [ ] Preserve raw responses and provenance. A normal accepted step with rejected actions still has a real resulting state; mark its rejection data. An ambiguous transport failure has no trustworthy transition and must not become a training sample.
- [ ] Use the automatically offered decision units first. If later adding explicit unit selection, act only on the final freshly returned observation.
- [ ] Record natural end, server time limit, local step cutoff, local wall-clock cutoff, reset/setup failure and transport failure independently. No cutoff is silently converted into a loss, draw or zero reward.
- [ ] Verify idle time, tick advancement, episode invalidation, disconnect/reconnect and sequential reset on the real build. Multiple retained slots and parallel processes remain off until single-session results are reliable.
- [ ] Run the focused unit tests and one instrumented native trajectory. Store manifest and captured catalog/terrain snapshots with its schema fingerprint.

## Task 3 — Reproducible non-learning baseline

**Files:** `baselines.py`, `evaluate.py`, `Python/configs/baseline.json`, `Python/configs/seeds.json`, `Python/tests/test_evaluation.py`.

- [ ] Freeze a seed manifest before model selection: smoke seeds 87/88; proposed training pool 1,000–9,999; validation pool 100,000–100,015; sealed test pool 200,000–200,031. These pools are disjoint. Assign policy RNG seeds separately.
- [ ] Test that scenario enumeration derives from catalog, splits do not overlap, paired policies receive the same scenarios/seeds, and no failed/capped case disappears from denominators.
- [ ] Run HOLD, first-current-candidate and seeded legal-random baselines against deterministic AI. Use both attacker and defender controls over catalog-supported pairings; do not invent reverse pairings or alter asymmetric armies.
- [ ] Begin with a small coverage sweep across discovered worlds, modes and sides. Measure setup time, simulated seconds/wall second, steps/second, acceptance/rejection, missing candidates, memory and completed-episode rate before estimating a full matrix.
- [ ] Expand to every catalog-supported faction pairing/world/mode, retaining per-cell coverage. Documentation describes 180 configurations, but runtime discovery determines the actual matrix.
- [ ] Report wins/draws/losses, score difference, raw reward, survivors/value, duration, rejection and failure/cutoff rates separately. Stratify by faction, terrain/world, mode and controlled side; compare scores within compatible scenarios rather than treating their scales as interchangeable.
- [ ] Save repeated-seed results. Seeds reproduce initial conditions; bit-identical simulation across frame schedules, hardware or concurrency is not promised.

## Task 4 — First local learning experiment

**Files:** `features.py`, `policy.py`, `train.py`, `Python/configs/train-pilot.json`, focused feature/learner tests.

- [ ] Inspect hardware and verified data, then pin a compatible learning-library version in the workspace environment and dependency lock. Keep package caches and downloads inside `Python/`.
- [ ] Build shared entity and candidate encoders with pooling/masks for variable counts. Define and version explicit selected features from observed fields and terrain model statistics. Never use opaque IDs as ordinal numerical features, infer tactical cover from generic points, or silently drop surplus units.
- [ ] Score HOLD and each current MOVE candidate. Map the sampled choice back to that observation's candidate ID immediately. Missing candidates must still allow HOLD.
- [ ] Begin with a small actor/critic and PPO, training one controlled side against fixed deterministic AI. Use server terminal rewards first; any later observation-derived shaping is versioned separately and evaluated on unchanged game scores. No reward for merely submitting moves or for protocol failures.
- [ ] Test variable army/candidate sizes, model joins, masks, feature normalization, finite loss/gradients, weight changes and checkpoint reload. A tiny training-seed overfit is a diagnostic, not evidence of held-out quality.
- [ ] Model server termination/time-limit boundaries explicitly. Do not blindly bootstrap every field called `truncated`: the balanced server limit awards a task-ending draw. A valid nonterminal rollout/local cutoff may use the recorded next-state value under the declared learner objective; an uncertain failed step must not.
- [ ] Run a bounded pilot: initially at most 30 wall-clock minutes or 10,000 valid decisions, whichever comes first. Save partial results and a local-cutoff reason if reached. Assess throughput and learning signal before longer runs.
- [ ] Save weights, optimizer, normalization/schema, RNG states, environment manifest, complete config and training history under `Models/<experiment>/<checkpoint>/`. Resume starts a fresh Arena episode; exact restoration of Unity mid-episode is not promised.

## Task 5 — Held-out evaluation and incremental expansion

- [ ] Freeze learning, normalization and deterministic policy action selection during evaluation.
- [ ] Select checkpoints using validation seeds only. Compare against all recorded baselines on paired cases, including both sides, all available factions and terrain/world groups.
- [ ] Start with a limited validation seed subset, then expand coverage based on measured cost. Run the sealed test split only after model/configuration selection; never use it to tune the same reported candidate.
- [ ] Report sample counts, paired uncertainty intervals and per-stratum outcomes; distinguish incomplete coverage and cutoffs. A pooled win rate alone is insufficient, particularly across balanced and overwhelming modes.
- [ ] Promote a checkpoint only with complete provenance, clean action/lifecycle handling and held-out improvement with stated uncertainty. Otherwise preserve the unsuccessful run and adjust one hypothesis at a time.
- [ ] Add concurrency, wider curricula, richer state/history or larger networks only after measured limitations motivate them. Re-run comparison under matched timing and opponent settings.

## Task 6 — Separate Jev-off / Jev-on benchmark executable

**Files:** `Python/arena_training/benchmark.py`, `Python/configs/benchmark.json`, `Python/tests/test_benchmark.py`; launcher source/build artifacts confined to this workspace; output `BenchmarkArena.exe`.

**Required meaning:** Jev assists the existing deterministic AI exactly as in Black Stars. It is not a battle judge, substitute LLM-only policy or training-data generator.

**Current prerequisite:** The inspected Arena session constructs the shared deterministic `PrototypeGroundTactics` context without MAIN's TypeSafe assistance integration. MAIN has a separate `PrototypeMainFactionAi.TypeSafe` path. The documented Arena protocol exposes no Jev setting, and local SI inference remains a separate integration. A packaged `AgentService` folder alone does not establish that the Arena uses it.

- [ ] Verify the supplied `TestArena` build's actual benchmark capabilities. Resolve Jev assistance and model-control access independently; do not assume a command-line flag can add them.
- [ ] If the current build lacks the existing assistance path, report a precise requirement for a separately supplied benchmark-capable game build. Do not edit the game project, patch its compiled assemblies, or approximate Jev with a different Python policy while calling it the existing behavior. Continue deterministic training independently.
- [ ] Build an external launcher offering explicit **Jev off** and **Jev on** benchmark profiles only when supported. Training and benchmark configurations, imports, services and outputs remain separated. The off profile must not start the provider service.
- [ ] Use the same frozen learned checkpoint, catalog scenario, seed, controlled side, armies, timing and deterministic opponent configuration for paired off/on trials. Jev adds assistance to that opponent; all ordinary game action checks and AI budgets remain intact.
- [ ] Record provider/model/configuration identity, request/response outcomes, assistance actually applied, latency, usage/cost when available, failures and fallback behavior. Mark unavailable or fallback-only runs explicitly; never count them as successful Jev-on validation.
- [ ] Match MAIN's real-time cadence and stale-intent rejection; do not grant Jev extra simulation pauses or privileged actions. Report both game outcomes and wall-clock cost, with repeated trials where provider outputs are nondeterministic.
- [ ] Keep existing credentials local and out of copied manifests/logs. Use only the user-authorized benchmark service path. Do not enable TypeSafe in training or feed Jev benchmark trajectories into training by default.
- [ ] Package and exercise the separate executable from an arbitrary working directory. Verify process ownership, output containment, profile separation and no false on/off results.

## Completion gates and handoff

1. **Native validation:** real Unity launch, discovery, valid movement, combat ending/reward and fresh reset evidenced. Failed or capped runs remain visible.
2. **Baseline:** discovered scenario matrix, immutable splits, deterministic-opponent measurements and repeatable command/config records.
3. **Learning pilot:** local checkpoint can reload, produces legal actions and has an honest validation comparison; no promised win rate.
4. **Evaluation:** held-out and per-faction/world/side evidence alongside the checkpoint, with incomplete coverage explicit.
5. **Benchmark:** separate launcher and genuine existing Jev assistance comparison, or a precise supplied-build blocker. This gate never relaxes the read-only game restriction.

Execution is proposed inline, with bounded real-build tests and focused regressions at each stage. Do not initialize version control or create commits in the game project. Main-game inference integration remains a separate future task.
