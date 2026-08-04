import json
import os
import sys
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from agents import daemon_manager


class DaemonManagerTestCase(unittest.TestCase):
    def setUp(self):
        import tempfile
        self._tmpdir = tempfile.mkdtemp(prefix="daemon_mgr_test_")
        self._port_file = os.path.join(self._tmpdir, "port")
        self._env = {
            "MUD_MANAGER_DIR": self._tmpdir,
            "MUD_RUBY": "ruby.exe",
        }
        self._patcher = mock.patch.dict(os.environ, self._env)
        self._patcher.start()

    def tearDown(self):
        self._patcher.stop()
        import shutil
        shutil.rmtree(self._tmpdir, ignore_errors=True)

    def _write_port(self, port):
        with open(self._port_file, "w", encoding="utf-8") as f:
            f.write(str(port))

    def test_read_port_missing(self):
        self.assertIsNone(daemon_manager.read_port())

    def test_read_port_stale_content(self):
        with open(self._port_file, "w", encoding="utf-8") as f:
            f.write("not-a-number")
        self.assertIsNone(daemon_manager.read_port())

    def test_ping_daemon_no_port_file(self):
        self.assertFalse(daemon_manager.ping_daemon())

    @mock.patch("agents.daemon_manager.socket.create_connection")
    def test_ping_daemon_pong(self, create_conn):
        sock = mock.MagicMock()
        sock.recv.return_value = json.dumps({"data": "pong"}).encode("utf-8")
        create_conn.return_value = sock
        self._write_port(12345)
        self.assertTrue(daemon_manager.ping_daemon(port=12345))
        sock.close.assert_called_once()

    @mock.patch("agents.daemon_manager.socket.create_connection")
    def test_ping_daemon_refused(self, create_conn):
        create_conn.side_effect = OSError("refused")
        self._write_port(12345)
        self.assertFalse(daemon_manager.ping_daemon(port=12345))

    @mock.patch("agents.daemon_manager.subprocess.Popen")
    @mock.patch("agents.daemon_manager.find_ruby", return_value=sys.executable)
    @mock.patch("agents.daemon_manager.daemon_script", return_value=__file__)
    def test_start_daemon_writes_port_and_returns(self, daemon_script, find_ruby, popen):
        proc = mock.MagicMock()
        proc.pid = 999
        proc.poll.return_value = None
        popen.return_value = proc
        # Simulate the daemon writing its port file shortly after spawn.
        def _write_port_file(*a, **k):
            self._write_port(55555)

        with mock.patch("agents.daemon_manager.time.sleep", side_effect=_write_port_file):
            p, port = daemon_manager.start_daemon()
        self.assertEqual(p, proc)
        self.assertEqual(port, 55555)

    @mock.patch("agents.daemon_manager.subprocess.Popen")
    @mock.patch("agents.daemon_manager.find_ruby", return_value=sys.executable)
    @mock.patch("agents.daemon_manager.daemon_script", return_value=__file__)
    def test_start_daemon_raises_if_exits_early(self, daemon_script, find_ruby, popen):
        proc = mock.MagicMock()
        proc.poll.return_value = 1
        proc.returncode = 1
        popen.return_value = proc
        with self.assertRaises(RuntimeError):
            daemon_manager.start_daemon()

    @mock.patch("agents.daemon_manager.ping_daemon", return_value=True)
    def test_ensure_daemon_already_running(self, ping):
        ok, detail = daemon_manager.ensure_daemon()
        self.assertTrue(ok)
        self.assertIn("already running", detail)

    @mock.patch("agents.daemon_manager.start_daemon")
    @mock.patch("agents.daemon_manager.ping_daemon")
    def test_ensure_daemon_starts_when_down(self, ping, start):
        ping.side_effect = [False, True]  # first ping fails, then succeeds after start
        proc = mock.MagicMock()
        proc.pid = 42
        start.return_value = (proc, 55555)
        ok, detail = daemon_manager.ensure_daemon()
        self.assertTrue(ok)
        start.assert_called_once()


if __name__ == "__main__":
    unittest.main(verbosity=2)
