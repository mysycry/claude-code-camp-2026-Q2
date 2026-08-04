import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from agents import mudparse


class TestStripAnsi(unittest.TestCase):
    def test_strips_escapes(self):
        self.assertEqual(mudparse.strip_ansi("\x1b[31mHello\x1b[0m"), "Hello")

    def test_none_safe(self):
        self.assertEqual(mudparse.strip_ansi(None), "")


class TestParseExits(unittest.TestCase):
    def test_open_and_closed(self):
        exits = mudparse.parse_exits("n s (w) u")
        self.assertEqual(exits, [
            {"direction": "n", "open": True},
            {"direction": "s", "open": True},
            {"direction": "w", "open": False},
            {"direction": "u", "open": True},
        ])


class TestParseRoomBlock(unittest.TestCase):
    def test_basic_room(self):
        text = (
            "The Grunting Boar\n"
            "A warm smoky tavern full of noise.\n"
            "[ Exits: n e s w ]\n"
            "a brutish bouncer is standing here.\n"
            "A tankard of ale is lying here.\n"
        )
        room = mudparse.parse_room_block(text)
        self.assertIsNotNone(room)
        self.assertEqual(room["name"], "The Grunting Boar")
        self.assertEqual(len(room["exits"]), 4)
        self.assertEqual(len(room["entities"]), 2)

    def test_returns_none_without_exits(self):
        self.assertIsNone(mudparse.parse_room_block("A room with no exit line"))


class TestClassifyEntity(unittest.TestCase):
    def test_mob(self):
        self.assertEqual(mudparse.classify_entity("a rat is standing here."), "mob")

    def test_item(self):
        self.assertEqual(mudparse.classify_entity("A shiny rock is lying here."), "item")


class TestExtractHealth(unittest.TestCase):
    def test_hmv(self):
        vitals = mudparse.extract_health("38H 100M 27V [standing]")
        self.assertEqual(vitals, {"hp": 38, "mana": 100, "mv": 27})

    def test_none(self):
        self.assertIsNone(mudparse.extract_health("no vitals here"))


class TestParseScore(unittest.TestCase):
    def test_score_fields(self):
        text = (
            "Score for Dummy the Soldier (level 5)\n"
            "You are 17 years old.\n"
            "You have 30(85) hit, 100(100) mana and 16(93) movement points.\n"
            "You have 11543 exp, 0 gold.\n"
            "You need 20457 exp to reach your next level.\n"
            "Your alignment is 159.\n"
            "Your armor class is 80/10.\n"
        )
        score = mudparse.parse_score(text)
        self.assertEqual(score["level"], 5)
        self.assertEqual(score["hp"], 30)
        self.assertEqual(score["max_hp"], 85)
        self.assertEqual(score["xp"], 11543)
        self.assertEqual(score["gold"], 0)
        self.assertEqual(score["xp_next"], 20457)
        self.assertEqual(score["age"], 17)
        self.assertEqual(score["alignment"], 159)
        self.assertEqual(score["armor"], "80/10")


if __name__ == "__main__":
    unittest.main(verbosity=2)
