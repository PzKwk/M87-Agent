"""Real TCP tests with an explicit fake protocol peer; no Unity build is used."""
import importlib.util
import json
from pathlib import Path
import socket
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

PROTOCOL = "blackstars-ground-arena/1"
SPEC = importlib.util.find_spec("ground_arena_client")
if SPEC is not None:
    from ground_arena_client import ArenaClient, ArenaError, ProtocolError, ConnectionLost


class FakeProtocolPeer:
    """A deliberately artificial peer, not a simulator or Unity substitute."""
    def __init__(self, handler, hello_delay=0):
        self.handler = handler
        self.hello_delay = hello_delay
        self.requests = []
        self.errors = []
        self.listener = socket.socket()
        self.listener.bind(("127.0.0.1", 0))
        self.listener.listen(1)
        self.listener.settimeout(3)
        self.port = self.listener.getsockname()[1]
        self.connection = None
        self.thread = threading.Thread(target=self.run, daemon=True)

    def run(self):
        try:
            self.connection, _ = self.listener.accept()
            self.connection.settimeout(3)
            buffer = b""
            while True:
                chunk = self.connection.recv(65536)
                if not chunk:
                    break
                buffer += chunk
                while b"\n" in buffer:
                    line, buffer = buffer.split(b"\n", 1)
                    request = json.loads(line)
                    self.requests.append(request)
                    if request["command"] == "hello":
                        time.sleep(self.hello_delay)
                        self.send(request, {"interface": "custom-json-tcp", "model_required": False})
                    else:
                        self.handler(self, request)
        except (OSError, TimeoutError):
            pass
        except Exception as error:
            self.errors.append(error)

    def send(self, request, data, fragment=False):
        encoded = (json.dumps({"protocol": PROTOCOL, "id": request["id"],
                               "ok": True, "data": data}) + "\n").encode()
        if fragment:
            for offset in range(0, len(encoded), 3):
                self.connection.sendall(encoded[offset:offset + 3])
        else:
            self.connection.sendall(encoded)

    def __enter__(self):
        self.temp = tempfile.TemporaryDirectory()
        self.endpoint = Path(self.temp.name) / "endpoint.json"
        self.endpoint.write_text(json.dumps({"protocol": PROTOCOL, "host": "127.0.0.1",
                                  "port": self.port, "token": "fake-token", "pid": 1234}))
        self.thread.start()
        return self

    def __exit__(self, *args):
        if self.connection:
            self.connection.close()
        self.listener.close()
        self.thread.join(4)
        self.temp.cleanup()
        if self.errors:
            raise self.errors[0]


class ClientTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        if SPEC is None:
            raise AssertionError("Portable training client does not exist yet")

    def test_real_socket_handshake_fragmented_response_and_command_payloads(self):
        def handler(peer, request):
            peer.send(request, {"command": request["command"], "future_field": "ä"}, True)
        with FakeProtocolPeer(handler) as peer:
            with ArenaClient.connect(peer.endpoint, timeout=2) as client:
                self.assertEqual(client.catalog()["future_field"], "ä")
                client.reset(arena=2, pair_index=3, seed=42, control="both")
                client.observe(1, unit_id="arena-Blue-0")
                client.terrain(1)
                client.step(1, 2, [{"unit_id": "arena-Blue-0", "kind": "move", "candidate_id": 17}])
            self.assertEqual(peer.requests[0]["token"], "fake-token")
            self.assertEqual([r["id"] for r in peer.requests], list(range(1, 8)))
            self.assertEqual(peer.requests[2], {"protocol": PROTOCOL, "id": 3,
                "command": "reset", "arena": 2, "pair_index": 3, "seed": 42, "control": "both"})
            self.assertEqual(peer.requests[5]["ticks"], 4)
            self.assertEqual(peer.requests[-1]["command"], "close")

    def test_structured_server_error_preserves_connection(self):
        def handler(peer, request):
            if request["command"] == "catalog":
                peer.connection.sendall((json.dumps({"protocol": PROTOCOL, "id": request["id"],
                    "ok": False, "error": {"code": "wrong_state", "message": "Reset needed"}}) + "\n").encode())
            else:
                peer.send(request, {})
        with FakeProtocolPeer(handler) as peer:
            with ArenaClient.connect(peer.endpoint) as client:
                with self.assertRaises(ArenaError) as raised:
                    client.catalog()
                self.assertEqual(raised.exception.code, "wrong_state")
                self.assertEqual(client.observe(1), {})

    def test_reset_optional_time_limit_validates_finite_range_and_preserves_zero(self):
        with FakeProtocolPeer(lambda peer, request: peer.send(request, {})) as peer:
            with ArenaClient.connect(peer.endpoint) as client:
                for invalid in (float("nan"), float("inf"), float("-inf"), -0.1, 86400.1, True, "0"):
                    with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                        client.reset(time_limit_seconds=invalid)
                client.reset(time_limit_seconds=0)
                client.reset(time_limit_seconds=86400)
                client.reset()
            self.assertEqual(peer.requests[1]["time_limit_seconds"], 0)
            self.assertEqual(peer.requests[2]["time_limit_seconds"], 86400)
            self.assertNotIn("time_limit_seconds", peer.requests[3])
            self.assertEqual([r["command"] for r in peer.requests], ["hello", "reset", "reset", "reset", "close"])

    def test_oversized_request_is_not_sent_and_request_limit_is_independent_of_response_cap(self):
        with FakeProtocolPeer(lambda peer, request: peer.send(request, {})) as peer:
            with ArenaClient.connect(peer.endpoint, max_response_bytes=1024) as client:
                with self.assertRaises(ValueError):
                    client.observe(1, unit_id="x" * 1048576)
                # This valid-size request is larger than the configured response cap.
                self.assertEqual(client.observe(1, unit_id="x" * 2048), {})
            self.assertEqual([r["command"] for r in peer.requests], ["hello", "observe", "close"])
            self.assertEqual([r["id"] for r in peer.requests], [1, 2, 3])
            self.assertEqual(len(peer.requests[1]["unit_id"]), 2048)

    def test_reset_explicit_retained_arenas_validate_and_emit_bounded_concurrency(self):
        with FakeProtocolPeer(lambda peer, request: peer.send(request, {})) as peer:
            with ArenaClient.connect(peer.endpoint) as client:
                for invalid in (0, 1, None, "true"):
                    with self.subTest(keep_others=invalid), self.assertRaises(ValueError):
                        client.reset(keep_others=invalid)
                for invalid in (True, 0, 13, 1.0, "2"):
                    with self.subTest(concurrency=invalid), self.assertRaises(ValueError):
                        client.reset(concurrency=invalid)
                client.reset(keep_others=True, concurrency=2)
                client.reset(arena=1, keep_others=True, concurrency=12)
                client.reset(keep_others=False, concurrency=1)
                client.reset()
            self.assertIs(peer.requests[1]["keep_others"], True)
            self.assertEqual(peer.requests[1]["concurrency"], 2)
            self.assertEqual(peer.requests[2]["arena"], 1)
            self.assertEqual(peer.requests[2]["concurrency"], 12)
            self.assertFalse(peer.requests[3].get("keep_others", False))
            self.assertEqual(peer.requests[3]["concurrency"], 1)
            self.assertNotIn("concurrency", peer.requests[4])
            self.assertFalse(peer.requests[4].get("keep_others", False))
            self.assertEqual([r["command"] for r in peer.requests], ["hello", "reset", "reset", "reset", "reset", "close"])

    def test_rejects_invalid_envelopes_and_drops_connection(self):
        responses = [
            b'{"protocol":"other","id":2,"ok":true,"data":{}}\n',
            b'{"protocol":"blackstars-ground-arena/1","id":3,"ok":true,"data":{}}\n',
            b'{"protocol":"blackstars-ground-arena/1","id":true,"ok":true,"data":{}}\n',
            b'{"protocol":"blackstars-ground-arena/1","id":2,"ok":1,"data":{}}\n',
            b'{"protocol":"blackstars-ground-arena/1","id":2,"ok":true}\n',
            b'{"protocol":"blackstars-ground-arena/1","id":2,"ok":false,"error":{}}\n',
            b'{"protocol":"blackstars-ground-arena/1","id":2,"ok":true,"data":{"x":NaN}}\n',
            b'{"protocol":"blackstars-ground-arena/1","id":2,"ok":true,"data":{"x":1e999}}\n',
            b'{"protocol":"blackstars-ground-arena/1","id":2,"id":2,"ok":true,"data":{}}\n',
            b'\xff\n', b'[]\n', b'not json\n',
        ]
        for response in responses:
            with self.subTest(response=response):
                with FakeProtocolPeer(lambda peer, request: peer.connection.sendall(response)) as peer:
                    client = ArenaClient.connect(peer.endpoint)
                    with self.assertRaises(ProtocolError):
                        client.catalog()
                    with self.assertRaises(ConnectionLost):
                        client.catalog()
                    client.close()

    def test_bounded_response_and_eof(self):
        for response, expected_error in ((b"x" * 1025, ProtocolError), (b'{"unfinished":', ConnectionLost)):
            def handler(peer, request):
                peer.connection.sendall(response)
                peer.connection.shutdown(socket.SHUT_WR)
            with self.subTest(response=len(response)):
                with FakeProtocolPeer(handler) as peer:
                    client = ArenaClient.connect(peer.endpoint, max_response_bytes=1024)
                    with self.assertRaises(expected_error):
                        client.catalog()
                    client.close()

    def test_timeout_never_retries_step_and_disconnects(self):
        with FakeProtocolPeer(lambda peer, request: time.sleep(0.15)) as peer:
            client = ArenaClient.connect(peer.endpoint, timeout=0.05)
            with self.assertRaises(ConnectionLost):
                client.step(1, 2, [])
            with self.assertRaises(ConnectionLost):
                client.step(1, 2, [])
            client.close()
            self.assertEqual([r["command"] for r in peer.requests], ["hello", "step"])

    def test_connect_and_handshake_share_one_timeout(self):
        real_connect = socket.create_connection
        def slow_connect(*args, **kwargs):
            time.sleep(0.06)
            return real_connect(*args, **kwargs)
        with FakeProtocolPeer(lambda peer, request: peer.send(request, {}), hello_delay=0.06) as peer:
            with mock.patch("ground_arena_client.socket.create_connection", side_effect=slow_connect):
                with self.assertRaises(ConnectionLost):
                    client = ArenaClient.connect(peer.endpoint, timeout=0.09)
                    client.close()

    def test_endpoint_rejects_remote_and_invalid_fields_before_socket_connect(self):
        base = {"protocol": PROTOCOL, "host": "127.0.0.1", "port": 12345, "token": "secret", "pid": 3}
        invalid = [{"host": "localhost"}, {"host": "8.8.8.8"}, {"port": True}, {"port": 0},
                   {"port": 65536}, {"pid": False}, {"pid": -1}, {"token": ""}, {"protocol": "v2"}]
        with tempfile.TemporaryDirectory() as directory:
            endpoint = Path(directory) / "endpoint.json"
            with mock.patch("ground_arena_client.socket.create_connection") as connect:
                for values in invalid:
                    endpoint.write_text(json.dumps(dict(base, **values)))
                    with self.subTest(values=values), self.assertRaises((ValueError, ProtocolError)):
                        ArenaClient.connect(endpoint)
                connect.assert_not_called()

    def test_rejects_unbounded_responses_and_free_position_actions(self):
        with FakeProtocolPeer(lambda peer, request: peer.send(request, {})) as peer:
            with ArenaClient.connect(peer.endpoint) as client:
                with self.assertRaises(ValueError):
                    client.step(1, 2, [{"unit_id": "arena-Blue-0", "kind": "move", "position": [1, 2]}])
                with self.assertRaises(ValueError):
                    client.step(1, 2, [], ticks=201)
                with self.assertRaises(ValueError):
                    client.reset(control="human")
            self.assertEqual([r["command"] for r in peer.requests], ["hello", "close"])
        with self.assertRaises(ValueError):
            ArenaClient.connect("missing", max_response_bytes=16777217)

    def test_launch_uses_absolute_unique_output_and_cleans_up_own_child(self):
        class FakeProcess:
            pid = 3456
            def __init__(self):
                self.terminated = False
            def poll(self):
                return 0 if self.terminated else None
            def terminate(self):
                self.terminated = True
            def wait(self, timeout):
                return 0
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory)
            executable = parent / "Arena.exe"
            executable.touch()
            process = FakeProcess()
            observed = {}
            def start(argv, **kwargs):
                observed.update(argv=argv, **kwargs)
                endpoint = Path(argv[argv.index("-groundArenaEndpoint") + 1])
                observed["endpoint"] = endpoint
                # A stale/wrong endpoint must never lead to killing its advertised PID.
                endpoint.write_text(json.dumps({"protocol": PROTOCOL, "host": "127.0.0.1",
                    "port": 1, "token": "fake", "pid": 9999}))
                return process
            with mock.patch("ground_arena_client.subprocess.Popen", side_effect=start):
                with self.assertRaises(ProtocolError):
                    ArenaClient.launch(executable, parent, startup_timeout=0.1,
                                       extra_args=["-batchmode"])
            self.assertTrue(process.terminated)
            self.assertEqual(observed["argv"][0], str(executable.resolve()))
            self.assertEqual(observed["argv"][1:4], ["-groundArenaTrain", "-groundArenaPort", "0"])
            self.assertEqual(observed["argv"][-1], "-batchmode")
            self.assertTrue(observed["endpoint"].is_absolute())
            self.assertNotEqual(observed["endpoint"].parent, parent)
            self.assertEqual(observed["cwd"], str(executable.parent.resolve()))
            self.assertTrue(observed["endpoint"].parent.joinpath("unity.log").exists())

    def test_launch_success_and_close_terminate_only_owned_process(self):
        class FakeProcess:
            pid = 1234
            terminated = False
            def poll(self):
                return 0 if self.terminated else None
            def terminate(self):
                self.terminated = True
            def wait(self, timeout):
                return 0
        with FakeProtocolPeer(lambda peer, request: peer.send(request, {})) as peer:
            process = FakeProcess()
            parent = Path(peer.temp.name) / "existing runs"
            parent.mkdir()
            sentinel = parent / "unity.log"
            sentinel.write_text("previous run")
            def start(argv, **kwargs):
                Path(argv[argv.index("-groundArenaEndpoint") + 1]).write_bytes(peer.endpoint.read_bytes())
                return process
            with mock.patch("ground_arena_client.subprocess.Popen", side_effect=start):
                with ArenaClient.launch(sys.executable, parent, timeout=1) as client:
                    self.assertEqual(client.catalog(), {})
                    self.assertTrue(client.run_directory.is_absolute())
                client.close()
            self.assertTrue(process.terminated)
            self.assertEqual(sentinel.read_text(), "previous run")
            self.assertEqual(peer.requests[-1]["command"], "close")

    def test_launch_startup_timeout_terminates_own_child(self):
        class FakeProcess:
            pid = 1234
            terminated = False
            def poll(self):
                return None
            def terminate(self):
                self.terminated = True
            def wait(self, timeout):
                return 0
        with tempfile.TemporaryDirectory() as directory:
            process = FakeProcess()
            with mock.patch("ground_arena_client.subprocess.Popen", return_value=process):
                with self.assertRaises(ConnectionLost):
                    ArenaClient.launch(sys.executable, directory, startup_timeout=0.02)
            self.assertTrue(process.terminated)


class SmokeTests(unittest.TestCase):
    def test_smoke_chooses_opaque_first_candidate_or_hold_and_stops_at_cap(self):
        smoke_spec = importlib.util.find_spec("smoke_test")
        self.assertIsNotNone(smoke_spec, "Non-learning smoke runner does not exist yet")
        from smoke_test import choose_actions, run_smoke
        observation = {"episode": 1, "observation_id": 2, "terminated": False,
            "truncated": False, "result": None, "decisions": [
                {"unit_id": "arena-Blue-0", "candidates": [{"candidate_id": 17}]},
                {"unit_id": "arena-Blue-1", "candidates": []}]}
        self.assertEqual(choose_actions(observation), [
            {"unit_id": "arena-Blue-0", "kind": "move", "candidate_id": 17},
            {"unit_id": "arena-Blue-1", "kind": "hold"}])
        class FakeNonSimulatorClient:
            steps = 0
            def reset(self, **kwargs):
                return dict(observation, decisions=[{"unit_id": "arena-Blue-1", "candidates": []}])
            def step(self, episode, observation_id, actions, ticks):
                self.steps += 1
                return self.reset()
        import io
        output = io.StringIO()
        client = FakeNonSimulatorClient()
        summaries = run_smoke(client, episodes=2, max_steps=3, stream=output)
        self.assertEqual(client.steps, 6)
        self.assertTrue(all(item["step_cap_reached"] for item in summaries))
        self.assertIn("HOLD-only diagnostic", output.getvalue())
        self.assertIn("terminated=False", output.getvalue())


if __name__ == "__main__":
    unittest.main()
