import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from agents import grind_agent
from agents import mudparse


class GrindAgentHarness(grind_agent.GrindAgent):
    pass


class TestMobAlias(unittest.TestCase):
    def setUp(self):
        self.agent = GrindAgentHarness()

    def test_plain_mob(self):
        self.assertEqual(
            self.agent._mob_alias("a rat is standing here."), "rat"
        )

    def test_article_stripped(self):
        self.assertEqual(
            self.agent._mob_alias("an orc warrior is standing here."), "orc warrior"
        )

    def test_with_you_see(self):
        self.assertEqual(
            self.agent._mob_alias("You see a goblin scout is standing here."),
            "goblin scout",
        )

    def test_sitting_variant(self):
        self.assertEqual(
            self.agent._mob_alias("a cat is sitting here."), "cat"
        )

    def test_arrival_stripped(self):
        self.assertEqual(
            self.agent._mob_alias("a pawn has just arrived from the north."),
            "pawn",
        )

    def test_no_match_falls_back(self):
        alias = self.agent._mob_alias("SomeLongMobName is here")
        self.assertTrue(alias)


class TestRoomKey(unittest.TestCase):
    def setUp(self):
        self.agent = GrindAgentHarness()

    def test_key_from_exit_list(self):
        room = {"name": "Foo", "exits": [
            {"direction": "n", "open": True},
            {"direction": "w", "open": True},
        ]}
        key = self.agent._room_key(room)
        self.assertEqual(key[0], "Foo")
        self.assertIn("n", key[1])
        self.assertIn("w", key[1])

    def test_key_distinguishes_exits(self):
        a = self.agent._room_key({"name": "Foo", "exits": [{"direction": "n", "open": True}]})
        b = self.agent._room_key({"name": "Foo", "exits": [{"direction": "e", "open": True}]})
        self.assertNotEqual(a, b)

    def test_room_itself_never_equal_across_names(self):
        a = self.agent._room_key({"name": "Foo", "exits": []})
        b = self.agent._room_key({"name": "Bar", "exits": []})
        self.assertNotEqual(a, b)


class TestMobs(unittest.TestCase):
    def setUp(self):
        self.agent = GrindAgentHarness()

    def test_filters_to_mobs(self):
        room = {"name": "X", "exits": {}, "entities": [
            "a rat is standing here.",
            "a sword is lying here.",
            "A large goblin is standing here.",
        ]}
        mobs = self.agent._mobs(room, "")
        self.assertEqual(len(mobs), 2)

    def test_target_filter(self):
        room = {"name": "X", "exits": {}, "entities": [
            "a rat is standing here.",
            "an orc is standing here.",
        ]}
        mobs = self.agent._mobs(room, "orc")
        self.assertEqual(len(mobs), 1)
        self.assertIn("orc", mobs[0].lower())


class TestKillDetection(unittest.TestCase):
    def setUp(self):
        self.agent = GrindAgentHarness()

    def test_slain_detected(self):
        out = "You have slain the rat!\nYou receive 25 experience points.\n"
        self.assertTrue(any(k in out for k in ("You have slain", "for the kill", "receive")))

    def test_death_detected(self):
        out = "You are dead! Sorry...\n"
        self.assertIn("You are dead", out)

    def test_fight_room_parse(self):
        text = (
            "The Cave Entrance\n"
            "[ Exits: s ]\n"
            "a rat is standing here.\n"
        )
        room = mudparse.parse_room_block(text)
        self.assertEqual(room["name"], "The Cave Entrance")
        self.assertTrue(any("fighting" not in e and "rat" in e for e in room["entities"]))


if __name__ == "__main__":
    unittest.main(verbosity=2)
