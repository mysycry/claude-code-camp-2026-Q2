import os
import sys

from agents.base import SubAgent, ROOT


class ResetAgent(SubAgent):
    name = "reset_agent"
    description = (
        "Moves the player to a start room (default 3001, the Temple) using an "
        "admin character, so a benchmark or fresh exploration begins from a known place."
    )
    parameters = {
        "start_room": {
            "type": "string",
            "description": "Room vnum to reset to (default: 3001)",
        },
        "start_room_name": {
            "type": "string",
            "description": "Expected room name for verification (optional; defaults to settings.yaml)",
        },
    }

    def run(self, **kwargs):
        start_room = kwargs.get("start_room") or "3001"
        start_room_name = kwargs.get("start_room_name") or None

        reset_path = os.path.join(ROOT, "week3_multi-agents", "resets", "player_reset.py")
        for p in (
            os.path.join(ROOT, "week3_multi-agents", "resets"),
            os.path.join(ROOT, "week3_multi-agents", "memory"),
        ):
            if p not in sys.path:
                sys.path.insert(0, p)
        spec_path = reset_path
        import importlib.util

        spec = importlib.util.spec_from_file_location("squad_player_reset", spec_path)
        module = importlib.util.module_from_spec(spec)
        sys.modules["squad_player_reset"] = module
        spec.loader.exec_module(module)

        try:
            actual_room = module.reset_player_to_start(
                start_room=start_room,
                start_room_name=start_room_name,
                quiet=True,
            )
        except Exception as e:
            return self._summary(
                "Reset",
                [("reset player", False, str(e))],
            )

        return self._summary(
            "Reset",
            [("reset player", True, f"player moved to room {start_room} (verified at [{actual_room}])")],
        )


def register(registry):
    from agents.base import register_subagents

    register_subagents(registry, [ResetAgent()])
