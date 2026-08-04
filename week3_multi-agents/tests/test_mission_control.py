import json
import os
import sys
import unittest
import urllib.error
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from agents import mission_control


class _FakeResp:
    def __init__(self, payload):
        self._body = json.dumps(payload).encode("utf-8")

    def read(self):
        return self._body

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _fake_urlopen(responses):
    """Return a urlopen patcher that returns canned responses keyed by path."""

    def _handler(req, *a, **k):
        path = req.full_url.replace(req.full_url.split("/api/")[0], "")
        payload = responses.get(path)
        if payload is None:
            raise RuntimeError(f"unexpected request: {req.full_url}")
        return _FakeResp(payload)

    return mock.patch("urllib.request.urlopen", side_effect=_handler)


class MissionControlClientTestCase(unittest.TestCase):
    def test_register_parses_agent_id(self):
        with _fake_urlopen({
            "/api/agents?limit=100": {"agents": []},
            "/api/agents/register": {"agent": {"id": 7, "name": "grind_agent"}, "registered": True},
        }):
            c = mission_control.MissionControlClient(url="http://localhost:3001",
                                                     api_key="k", enabled=True)
            self.assertEqual(c.register("grind_agent", role="agent"), 7)
            self.assertEqual(c._agent_name, "grind_agent")

    def test_register_reuses_existing_agent(self):
        """Already-registered names should be adopted via GET, not POSTed."""
        calls = []

        def _handler(req, *a, **k):
            calls.append((req.get_method(), req.full_url))
            return _FakeResp({"agents": [{"id": 3, "name": "grind_agent"}]})

        with mock.patch("urllib.request.urlopen", side_effect=_handler):
            c = mission_control.MissionControlClient(url="http://localhost:3001",
                                                     api_key="k", enabled=True)
            self.assertEqual(c.register("grind_agent", role="agent"), 3)
        self.assertEqual(c._agent_name, "grind_agent")
        methods = [m for m, _ in calls]
        self.assertNotIn("POST", methods)

    def test_heartbeat_requires_registration(self):
        c = mission_control.MissionControlClient(url="http://localhost:3001",
                                                 api_key="k", enabled=True)
        # No agent registered -> no request, returns None.
        self.assertIsNone(c.heartbeat(status="idle"))

    def test_heartbeat_sends_version_and_token_usage(self):
        seen = {}

        class _FakeResp:
            def read(self):
                return b'{"success": true}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def _handler(req, *a, **k):
            body = json.loads(req.data.decode("utf-8"))
            seen["body"] = body
            seen["auth"] = req.get_header("Authorization")
            return _FakeResp()

        with mock.patch("urllib.request.urlopen", side_effect=_handler):
            c = mission_control.MissionControlClient(url="http://localhost:3001",
                                                     api_key="secret", enabled=True)
            c._agent_id = 3
            c.heartbeat(status="busy", version="abc1234",
                        task="grind_agent(target=rat, steps=3)",
                        token_usage={"model": "deepseek", "inputTokens": 10, "outputTokens": 2})
        self.assertEqual(seen["body"]["status"], "busy")
        self.assertEqual(seen["body"]["version"], "abc1234")
        self.assertEqual(seen["body"]["token_usage"]["inputTokens"], 10)
        self.assertEqual(seen["auth"], "Bearer secret")

    def test_disabled_client_never_posts(self):
        calls = []
        with mock.patch("urllib.request.urlopen", side_effect=lambda *a, **k: calls.append(a)):
            c = mission_control.MissionControlClient(url="http://localhost:3001",
                                                     api_key="k", enabled=False)
            self.assertIsNone(c.register("x"))
            self.assertIsNone(c.heartbeat())
        self.assertEqual(calls, [])


class AgentStateTestCase(unittest.TestCase):
    def test_snapshot_reflects_set(self):
        s = mission_control.AgentState()
        self.assertEqual(s.snapshot()["status"], "idle")
        s.set(status="busy", task="grind")
        snap = s.snapshot()
        self.assertEqual(snap["status"], "busy")
        self.assertEqual(snap["task"], "grind")
        s.set(status="idle")
        self.assertEqual(s.snapshot()["status"], "idle")
        # task persists after status-only update
        self.assertEqual(s.snapshot()["task"], "grind")


class SquadVersionTestCase(unittest.TestCase):
    def test_env_override(self):
        with mock.patch.dict(os.environ, {"BOUKENSHA_VERSION": "v1.2.3"}):
            self.assertEqual(mission_control.squad_version(), "v1.2.3")

    def test_falls_back_to_something(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            v = mission_control.squad_version()
            self.assertTrue(v)


class ManagedAgentTestCase(unittest.TestCase):
    @mock.patch.dict(os.environ, {"MC_ENABLED": "false"})
    def test_disabled_start_returns_none(self):
        m = mission_control.ManagedAgent("grind_agent")
        self.assertIsNone(m.start())

    @mock.patch.dict(os.environ, {"MC_ENABLED": "true", "MC_URL": "http://localhost:3001",
                                  "MC_API_KEY": "k"})
    def test_start_registers_and_returns_id(self):
        responses = {
            "/api/agents?limit=100": {"agents": []},
            "/api/agents/register": {"agent": {"id": 4, "name": "grind_agent"}, "registered": True},
            "/api/agents/4/heartbeat": {"success": True},
        }
        with _fake_urlopen(responses):
            m = mission_control.ManagedAgent("grind_agent")
            agent_id = m.start(version="abc")
            self.assertEqual(agent_id, 4)
            m.stop()


class RetryTestCase(unittest.TestCase):
    def _client(self):
        return mission_control.MissionControlClient(url="http://localhost:3001",
                                                    api_key="k", enabled=True)

    @staticmethod
    def _empty_list_resp():
        return _FakeResp({"agents": []})

    def test_retries_transient_connection_error(self):
        """A URLError (connection refused) on POST should be retried, then return None."""
        calls = {"n": 0}

        def _boom(req, *a, **k):
            if req.get_method() == "GET":
                return self._empty_list_resp()
            calls["n"] += 1
            raise urllib.error.URLError("connection refused")

        with mock.patch("urllib.request.urlopen", side_effect=_boom):
            c = self._client()
            self.assertIsNone(c.register("x"))
        self.assertEqual(calls["n"], mission_control.MissionControlClient.MAX_RETRIES)

    def test_retries_5xx_but_not_401(self):
        """500 is retryable; 401 (bad key) is not — must not hammer the server."""
        counts = {"n": 0}

        class _Err(urllib.error.HTTPError):
            def __init__(self, code):
                super().__init__("url", code, "err", {}, None)

        def _boom(req, *a, **k):
            if req.get_method() == "GET":
                return self._empty_list_resp()
            counts["n"] += 1
            raise _Err(500)

        with mock.patch("urllib.request.urlopen", side_effect=_boom):
            c = self._client()
            self.assertIsNone(c.register("x"))
        self.assertEqual(counts["n"], mission_control.MissionControlClient.MAX_RETRIES)

        counts["n"] = 0

        def _unauth(req, *a, **k):
            if req.get_method() == "GET":
                return self._empty_list_resp()
            counts["n"] += 1
            raise _Err(401)

        with mock.patch("urllib.request.urlopen", side_effect=_unauth):
            c = self._client()
            self.assertIsNone(c.register("x"))
        self.assertEqual(counts["n"], 1)

    def test_recovers_after_transient_failure(self):
        """A 500 followed by success should return the parsed body."""
        attempts = {"n": 0}

        class _FakeResp:
            def read(self):
                return b'{"agent":{"id":9,"name":"x"},"registered":true}'

            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        class _Err(urllib.error.HTTPError):
            def __init__(self):
                super().__init__("url", 503, "err", {}, None)

        def _flaky(req, *a, **k):
            if req.get_method() == "GET":
                return self._empty_list_resp()
            attempts["n"] += 1
            if attempts["n"] == 1:
                raise _Err()
            return _FakeResp()

        with mock.patch("urllib.request.urlopen", side_effect=_flaky):
            c = self._client()
            self.assertEqual(c.register("x"), 9)
        self.assertEqual(attempts["n"], 2)


if __name__ == "__main__":
    unittest.main(verbosity=2)
