"""Portable stdlib client for a local Black Stars arena training build.

No model or learning algorithm is included. One synchronous caller per client.
Transport/protocol failures discard the connection; requests are never retried.
"""
from datetime import datetime, timezone
import json
import math
from pathlib import Path
import socket
import subprocess
import time
import uuid

PROTOCOL = "blackstars-ground-arena/1"
MAX_REQUEST_BYTES = 1024 * 1024
MAX_RESPONSE_BYTES = 16 * 1024 * 1024
MAX_ENDPOINT_BYTES = 64 * 1024


class ArenaError(Exception):
    """An explicit server rejection; the connection remains usable."""
    def __init__(self, code, message):
        self.code = code
        self.message = message
        super().__init__("{}: {}".format(code, message))


class ProtocolError(Exception):
    """Invalid endpoint or response; a live connection is discarded."""


class ConnectionLost(Exception):
    """EOF, I/O failure, or timeout; reconnect and reset before continuing."""


def _positive_timeout(value, name):
    if isinstance(value, bool) or not isinstance(value, (float, int)) or not math.isfinite(value) or value <= 0:
        raise ValueError(name + " must be a finite positive number")
    return float(value)


def _integer(value, minimum, maximum, name):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError("{} must be an integer in {}..{}".format(name, minimum, maximum))
    return value


def _reference(value, name):
    if (type(value) is int and value >= 0) or (isinstance(value, str) and value):
        return value
    raise ValueError(name + " must be a nonempty string or nonnegative integer")


def _strict_json(raw):
    def constant(value):
        raise ValueError("nonfinite JSON number")
    def real(value):
        number = float(value)
        if not math.isfinite(number):
            raise ValueError("nonfinite JSON number")
        return number
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result
    try:
        return json.loads(raw.decode("utf-8", errors="strict"), parse_constant=constant,
                          parse_float=real, object_pairs_hook=pairs)
    except (UnicodeError, ValueError, RecursionError) as error:
        raise ProtocolError("Invalid strict UTF-8 JSON") from error


def _read_endpoint(path):
    with Path(path).open("rb") as stream:
        raw = stream.read(MAX_ENDPOINT_BYTES + 1)
    if len(raw) > MAX_ENDPOINT_BYTES:
        raise ProtocolError("Endpoint file exceeds size limit")
    endpoint = _strict_json(raw)
    if not isinstance(endpoint, dict) or endpoint.get("protocol") != PROTOCOL:
        raise ProtocolError("Endpoint protocol mismatch")
    if endpoint.get("host") != "127.0.0.1":
        raise ProtocolError("Endpoint must use literal loopback 127.0.0.1")
    try:
        _integer(endpoint.get("port"), 1, 65535, "port")
        _integer(endpoint.get("pid"), 1, 2**63 - 1, "pid")
    except ValueError as error:
        raise ProtocolError(str(error)) from error
    token = endpoint.get("token")
    if not isinstance(token, str) or not token.strip():
        raise ProtocolError("Endpoint token is missing")
    return endpoint


class ArenaClient:
    """Authenticated local session. Prefer a ``with`` block to release resources.

    ``connect`` never owns a process. ``launch`` owns exactly its Popen child,
    which close terminates after releasing the session. Never kills endpoint PIDs.
    ``timeout`` is the total deadline of each request, including reset and step.
    """
    def __init__(self, connection, timeout, max_response_bytes):
        self._socket = connection
        self._timeout = timeout
        self._max_response_bytes = max_response_bytes
        self._buffer = bytearray()
        self._next_id = 1
        self._process = None
        self._log = None
        self.run_directory = None
        self.endpoint_file = None

    @classmethod
    def connect(cls, endpoint_file, timeout=120.0, max_response_bytes=MAX_RESPONSE_BYTES):
        """Read/validate a local endpoint and authenticate; never starts/kills it."""
        return cls._connect(endpoint_file, timeout, max_response_bytes)

    @classmethod
    def _connect(cls, endpoint_file, timeout, max_response_bytes, expected_pid=None):
        timeout = _positive_timeout(timeout, "timeout")
        _integer(max_response_bytes, 1, MAX_RESPONSE_BYTES, "max_response_bytes")
        deadline = time.monotonic() + timeout
        endpoint = _read_endpoint(endpoint_file)
        if expected_pid is not None and endpoint["pid"] != expected_pid:
            raise ProtocolError("Endpoint PID does not match the child launched by this client")
        remaining = deadline - time.monotonic()
        if remaining <= 0:
            raise ConnectionLost("Arena connection startup timed out")
        try:
            connection = socket.create_connection(("127.0.0.1", endpoint["port"]), timeout=remaining)
        except OSError as error:
            raise ConnectionLost("Could not connect to local arena") from error
        client = cls(connection, timeout, max_response_bytes)
        client.endpoint_file = Path(endpoint_file).expanduser().resolve()
        try:
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ConnectionLost("Arena connection startup timed out")
            client._timeout = remaining
            client._request("hello", token=endpoint["token"])
            client._timeout = timeout
            return client
        except BaseException:
            client._drop_connection()
            raise

    @classmethod
    def launch(cls, executable, run_directory, *, timeout=120.0, startup_timeout=120.0,
               extra_args=(), max_response_bytes=MAX_RESPONSE_BYTES):
        """Start a build and authenticate from any current working directory.

        ``run_directory`` is a parent directory. Every call creates a fresh
        timestamp/UUID child containing endpoint.json and unity.log. The build's
        working directory is its executable directory. No shell is used.
        """
        timeout = _positive_timeout(timeout, "timeout")
        startup_timeout = _positive_timeout(startup_timeout, "startup_timeout")
        _integer(max_response_bytes, 1, MAX_RESPONSE_BYTES, "max_response_bytes")
        executable = Path(executable).expanduser().resolve(strict=True)
        if not executable.is_file():
            raise ValueError("executable must be a file")
        extra_args = list(extra_args)
        reserved = {"-groundArenaTrain", "-groundArenaPort", "-groundArenaEndpoint"}
        if any(not isinstance(arg, str) or "\x00" in arg or arg.split("=", 1)[0] in reserved for arg in extra_args):
            raise ValueError("extra_args must be strings and cannot replace training endpoint flags")
        parent = Path(run_directory).expanduser().resolve()
        parent.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        output = parent / (stamp + "-" + uuid.uuid4().hex)
        output.mkdir(exist_ok=False)
        endpoint_file = output / "endpoint.json"
        log = (output / "unity.log").open("xb")
        process = None
        client = None
        try:
            argv = [str(executable), "-groundArenaTrain", "-groundArenaPort", "0",
                    "-groundArenaEndpoint", str(endpoint_file)] + extra_args
            process = subprocess.Popen(argv, cwd=str(executable.parent), stdin=subprocess.DEVNULL,
                                       stdout=log, stderr=subprocess.STDOUT, shell=False)
            deadline = time.monotonic() + startup_timeout
            while not endpoint_file.is_file():
                if process.poll() is not None:
                    raise ConnectionLost("Arena exited before publishing an endpoint; see " + str(output / "unity.log"))
                if time.monotonic() >= deadline:
                    raise ConnectionLost("Arena startup timed out; see " + str(output / "unity.log"))
                time.sleep(min(0.05, max(0.0, deadline - time.monotonic())))
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise ConnectionLost("Arena startup timed out")
            client = cls._connect(endpoint_file, min(timeout, remaining), max_response_bytes,
                                  expected_pid=process.pid)
            client._timeout = timeout
            client._process = process
            client._log = log
            client.run_directory = output
            return client
        except BaseException:
            if client is not None:
                client._drop_connection()
            try:
                _stop_child(process)
            finally:
                log.close()
            raise

    def _drop_connection(self):
        if self._socket is not None:
            try:
                self._socket.close()
            finally:
                self._socket = None
                self._buffer.clear()

    def _request(self, command, **fields):
        if self._socket is None:
            raise ConnectionLost("Connection is closed; reconnect and reset before continuing")
        request_id = self._next_id
        request = dict(protocol=PROTOCOL, id=request_id, command=command, **fields)
        encoded = (json.dumps(request, ensure_ascii=True, allow_nan=False, separators=(",", ":")) + "\n").encode("utf-8")
        if len(encoded) - 1 > MAX_REQUEST_BYTES:
            raise ValueError("Request exceeds 1 MiB limit")
        self._next_id += 1
        deadline = time.monotonic() + self._timeout
        try:
            self._socket.settimeout(self._timeout)
            self._socket.sendall(encoded)
            while True:
                newline = self._buffer.find(b"\n")
                if newline >= 0:
                    if newline > self._max_response_bytes:
                        raise ProtocolError("Response exceeds size limit")
                    line = bytes(self._buffer[:newline])
                    del self._buffer[:newline + 1]
                    break
                if len(self._buffer) > self._max_response_bytes:
                    raise ProtocolError("Response exceeds size limit")
                remaining = deadline - time.monotonic()
                if remaining <= 0:
                    raise TimeoutError("request deadline exceeded")
                self._socket.settimeout(remaining)
                chunk = self._socket.recv(min(65536, self._max_response_bytes + 1 - len(self._buffer)))
                if not chunk:
                    raise ConnectionLost("Arena disconnected before a complete response")
                self._buffer.extend(chunk)
            response = _strict_json(line)
            if not isinstance(response, dict) or response.get("protocol") != PROTOCOL:
                raise ProtocolError("Response protocol mismatch")
            if type(response.get("id")) is not int or response["id"] != request_id:
                raise ProtocolError("Response ID does not match outstanding request")
            if type(response.get("ok")) is not bool:
                raise ProtocolError("Response ok must be a boolean")
            if response["ok"]:
                if "data" not in response:
                    raise ProtocolError("Successful response is missing data")
                return response["data"]
            error = response.get("error")
            if (not isinstance(error, dict) or not isinstance(error.get("code"), str)
                    or not error["code"] or not isinstance(error.get("message"), str)):
                raise ProtocolError("Malformed server error")
            raise ArenaError(error["code"], error["message"])
        except (OSError, TimeoutError) as error:
            self._drop_connection()
            raise ConnectionLost("Arena I/O failed or timed out; request was not retried; reconnect and reset") from error
        except (ProtocolError, ConnectionLost):
            self._drop_connection()
            raise

    def catalog(self):
        return self._request("catalog")

    def reset(self, arena=0, pair_index=0, seed=None, control="attacker", *, time_limit_seconds=None,
              keep_others=False, concurrency=None):
        """Start fresh; optional balanced-mode time limit is 0..86400 seconds.

        Omitting the limit preserves the build's scenario default. Zero disables
        the optional balanced-mode limit; mode eligibility is checked by Unity.
        Default reset invalidates all earlier episodes. To retain other arena
        slots, pass keep_others=True and an explicit concurrency limit (1..12).
        """
        _integer(arena, 0, 11, "arena")
        _integer(pair_index, 0, 2**31 - 1, "pair_index")
        if control not in ("attacker", "defender", "both"):
            raise ValueError("control must be attacker, defender, or both")
        if type(keep_others) is not bool:
            raise ValueError("keep_others must be a boolean")
        fields = dict(arena=arena, pair_index=pair_index, control=control)
        if keep_others:
            fields["keep_others"] = True
        if concurrency is not None:
            fields["concurrency"] = _integer(concurrency, 1, 12, "concurrency")
        if seed is not None:
            fields["seed"] = _integer(seed, -(2**31), 2**31 - 1, "seed")
        if time_limit_seconds is not None:
            if (isinstance(time_limit_seconds, bool) or not isinstance(time_limit_seconds, (int, float))
                    or not math.isfinite(time_limit_seconds) or not 0 <= time_limit_seconds <= 86400):
                raise ValueError("time_limit_seconds must be a finite number in 0..86400")
            fields["time_limit_seconds"] = time_limit_seconds
        return self._request("reset", **fields)

    def observe(self, episode, unit_id=None):
        fields = dict(episode=_reference(episode, "episode"))
        if unit_id is not None:
            fields["unit_id"] = _reference(unit_id, "unit_id")
        return self._request("observe", **fields)

    def terrain(self, episode):
        return self._request("terrain", episode=_reference(episode, "episode"))

    def step(self, episode, observation_id, actions, ticks=4):
        _integer(ticks, 1, 200, "ticks")
        if not isinstance(actions, (list, tuple)):
            raise ValueError("actions must be a list or tuple")
        validated = []
        for action in actions:
            if not isinstance(action, dict) or action.get("kind") not in ("hold", "move"):
                raise ValueError("action kind must be hold or move")
            expected = {"unit_id", "kind", "candidate_id"} if action["kind"] == "move" else {"unit_id", "kind"}
            if set(action) != expected:
                raise ValueError("Use only unit_id, kind, and candidate_id for moves; no world positions")
            entry = dict(unit_id=_reference(action["unit_id"], "unit_id"), kind=action["kind"])
            if action["kind"] == "move":
                entry["candidate_id"] = _reference(action["candidate_id"], "candidate_id")
            validated.append(entry)
        return self._request("step", episode=_reference(episode, "episode"),
                             observation_id=_reference(observation_id, "observation_id"),
                             actions=validated, ticks=ticks)

    def close(self):
        """Release/pause the session and terminate only a child started by launch.

        Idempotent; a connected existing build is left running. Transport failure
        during graceful close still releases local resources.
        """
        try:
            if self._socket is not None:
                try:
                    self._request("close")
                except (ArenaError, ProtocolError, ConnectionLost):
                    pass
        finally:
            self._drop_connection()
            try:
                _stop_child(self._process)
            finally:
                self._process = None
                if self._log is not None:
                    self._log.close()
                    self._log = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, traceback):
        self.close()


def _stop_child(process):
    """Receives only the Popen handle we created, never endpoint file PID data."""
    if process is None:
        return
    if process.poll() is None:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    else:
        process.wait(timeout=5)
