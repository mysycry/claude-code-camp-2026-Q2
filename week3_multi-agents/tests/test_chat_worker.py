import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from agents import chat_worker, mission_control  # noqa: E402


class _FakeProc:
    pid = 4242


class ChatWorkerLifecycleTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self._old_dir = os.environ.get("MUD_MANAGER_DIR")
        os.environ["MUD_MANAGER_DIR"] = self._tmp.name

    def tearDown(self):
        if self._old_dir is None:
            os.environ.pop("MUD_MANAGER_DIR", None)
        else:
            os.environ["MUD_MANAGER_DIR"] = self._old_dir
        self._tmp.cleanup()

    def test_start_writes_pid_file(self):
        with mock.patch.object(chat_worker.subprocess, "Popen", return_value=_FakeProc()):
            proc = chat_worker.start_chat_worker()
        self.assertEqual(proc.pid, 4242)
        with open(chat_worker._worker_pid_file(), encoding="utf-8") as f:
            self.assertEqual(f.read().strip(), "4242")

    def test_ensure_spawns_when_not_running(self):
        with mock.patch.object(chat_worker, "_chat_worker_alive", return_value=False), \
             mock.patch.object(chat_worker, "start_chat_worker", return_value=_FakeProc()):
            ok, detail = chat_worker.ensure_chat_worker()
        self.assertTrue(ok)
        self.assertIn("started", detail)

    def test_ensure_skips_when_already_running(self):
        with mock.patch.object(chat_worker, "_chat_worker_alive", return_value=True), \
             mock.patch.object(chat_worker, "start_chat_worker") as spawn:
            ok, detail = chat_worker.ensure_chat_worker()
        self.assertTrue(ok)
        self.assertIn("already running", detail)
        spawn.assert_not_called()

    def test_ensure_skips_when_mc_disabled(self):
        with mock.patch.object(mission_control, "enabled", return_value=False), \
             mock.patch.object(chat_worker, "start_chat_worker") as spawn:
            ok, detail = chat_worker.ensure_chat_worker()
        self.assertFalse(ok)
        self.assertIn("disabled", detail)
        spawn.assert_not_called()

    def test_ensure_reports_spawn_failure(self):
        with mock.patch.object(chat_worker, "_chat_worker_alive", return_value=False), \
             mock.patch.object(
                 chat_worker, "start_chat_worker", side_effect=RuntimeError("boom")
             ):
            ok, detail = chat_worker.ensure_chat_worker()
        self.assertFalse(ok)
        self.assertIn("could not start", detail)


class StatusReplyTestCase(unittest.TestCase):
    def test_reply_includes_live_fields(self):
        text = chat_worker.status_reply("grind_agent", prompt="where are we now?")
        self.assertIn("[grind_agent]", text)
        self.assertIn('Re: "where are we now?"', text)
        self.assertIn("Player:", text)
        self.assertIn("MUD daemon:", text)
        self.assertIn("Squad:", text)


if __name__ == "__main__":
    unittest.main()
