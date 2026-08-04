import os
import sys
import tempfile
import unittest
from unittest import mock

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from agents.base import load_env


class LoadEnvTestCase(unittest.TestCase):
    def test_loads_keys_and_ignores_comments(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8") as f:
            f.write("# comment\n\nKEY_ONE=value1\nKEY_TWO=\"quoted\"\nexport KEY_THREE='single'\nBADLINE\n")
            path = f.name
        try:
            with mock.patch.dict(os.environ, {}, clear=True):
                load_env(path)
                self.assertEqual(os.environ.get("KEY_ONE"), "value1")
                self.assertEqual(os.environ.get("KEY_TWO"), "quoted")
                self.assertEqual(os.environ.get("KEY_THREE"), "single")
                self.assertNotIn("BADLINE", os.environ)
        finally:
            os.remove(path)

    def test_existing_env_wins(self):
        with tempfile.NamedTemporaryFile("w", suffix=".env", delete=False, encoding="utf-8") as f:
            f.write("DUP_KEY=from_file\n")
            path = f.name
        try:
            with mock.patch.dict(os.environ, {"DUP_KEY": "from_shell"}, clear=False):
                load_env(path)
                self.assertEqual(os.environ.get("DUP_KEY"), "from_shell")
        finally:
            os.remove(path)

    def test_missing_file_is_noop(self):
        with mock.patch.dict(os.environ, {}, clear=True):
            load_env(os.path.join(tempfile.gettempdir(), "does-not-exist-xyz.env"))
        # no exception raised; nothing to assert beyond that


if __name__ == "__main__":
    unittest.main(verbosity=2)
