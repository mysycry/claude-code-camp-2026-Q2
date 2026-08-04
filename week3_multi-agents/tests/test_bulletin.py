import os
import sys
import tempfile
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from agents import bulletin


class BulletinTestCase(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls._orig_db = bulletin.DB_PATH
        fd, cls._tmp = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        bulletin.DB_PATH = cls._tmp

    @classmethod
    def tearDownClass(cls):
        bulletin.DB_PATH = cls._orig_db
        for suffix in ("", "-wal", "-shm"):
            p = cls._tmp + suffix
            if os.path.isfile(p):
                os.remove(p)

    def setUp(self):
        bulletin.set_state()
        # clear state rows left by other tests
        bulletin.del_state(*[k for k in bulletin.get_state()])


class TestSetGetDel(BulletinTestCase):
    def test_roundtrip(self):
        bulletin.set_state(level="5", location="A White Square")
        state = bulletin.get_state()
        self.assertEqual(state["level"], "5")
        self.assertEqual(state["location"], "A White Square")

    def test_none_values_skipped(self):
        bulletin.set_state(level="5", last_kill=None)
        self.assertNotIn("last_kill", bulletin.get_state())

    def test_overwrite(self):
        bulletin.set_state(location="A")
        bulletin.set_state(location="B")
        self.assertEqual(bulletin.get_state()["location"], "B")

    def test_delete(self):
        bulletin.set_state(location="A")
        bulletin.del_state("location")
        self.assertNotIn("location", bulletin.get_state())


class TestSnapshot(BulletinTestCase):
    def test_snapshot_fields(self):
        bulletin.post_player_snapshot(
            score={"level": 5, "hp": 30, "max_hp": 85, "xp": 11543, "xp_next": 20457},
            location="A White Square",
            kill="pawn",
            destination="any mob",
        )
        state = bulletin.get_state()
        self.assertEqual(state["score_level"], "5")
        self.assertEqual(state["location"], "A White Square")
        self.assertEqual(state["last_kill"], "pawn")
        self.assertEqual(state["destination"], "any mob")
        self.assertEqual(state["pct_hp"], "35")
        # room id is md5 of the room name, first 16 hex chars
        import hashlib
        self.assertEqual(state["current_room"], hashlib.md5(b"A White Square").hexdigest()[:16])

    def test_events_logged(self):
        bulletin.post_player_snapshot(location="X", kill="rat", destination="south")
        kinds = {e["kind"] for e in bulletin.recent_events()}
        self.assertTrue({"nav", "kill"}.issubset(kinds))


if __name__ == "__main__":
    unittest.main(verbosity=2)
