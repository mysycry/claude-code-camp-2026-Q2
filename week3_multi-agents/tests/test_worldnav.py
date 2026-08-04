import os
import sys
import unittest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir))

from agents import worldnav


class WorldNavTestCase(unittest.TestCase):
    def test_vnums_by_name(self):
        cands = worldnav.vnums_by_name("The Temple Of Midgaard")
        self.assertIn(3001, cands)

    def test_vnums_by_name_empty(self):
        self.assertEqual(worldnav.vnums_by_name(""), [])
        self.assertEqual(worldnav.vnums_by_name("No Such Room 12345"), [])

    def test_route_temple_to_hunt(self):
        route, target = worldnav.route_to_nearest_hunt(3001, player_level=5)
        self.assertIsNotNone(route)
        self.assertIsNotNone(target)
        self.assertTrue(len(route) >= 1)
        # route must be a chain of direction steps
        for step in route:
            self.assertIn(step["direction"], ("north", "south", "east", "west", "up", "down"))

    def test_route_target_is_huntable(self):
        route, target = worldnav.route_to_nearest_hunt(3001, player_level=5)
        targets = worldnav.hunting_rooms(2, 8)
        self.assertIn(target, targets)

    def test_unreachable_returns_none(self):
        # A vnum that doesn't exist at all should yield None (not crash).
        route, target = worldnav.route_to_nearest_hunt(999999, player_level=5)
        self.assertIsNone(route)
        self.assertIsNone(target)

    def test_bfs_route_no_move_when_already_target(self):
        targets = worldnav.hunting_rooms(0, 50)
        # If start is itself a target, return empty list (no steps needed).
        for v in list(targets)[:1]:
            route = worldnav.bfs_route(v, targets)
            self.assertEqual(route, [])


if __name__ == "__main__":
    unittest.main(verbosity=2)
