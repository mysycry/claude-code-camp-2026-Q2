from boukensha.tools.mud_client import MudDaemonClient, PORT_FILE


class Mud:
    _warned = False

    @classmethod
    def register(cls, registry, host="localhost", port=4000, name=None, password=None):
        if registry is None:
            return
        if not PORT_FILE.exists():
            if not cls._warned:
                import warnings
                warnings.warn(
                    "MUD daemon not running (no port file at ~/.mud_manager/port) — "
                    "start `ruby mud_daemon.rb` first, or MUD tools will be unavailable"
                )
                cls._warned = True
            return

        client = MudDaemonClient()

        def guard():
            result = client.status()
            if not result.get("ok") or not result.get("data", {}).get("connected"):
                return "error: not connected — call mud_connect first"
            return None

        send_cmd = lambda cmd: client.send(cmd)

        registry.tool(
            "mud_connect",
            description="Open the connection to the MUD server and log in with the configured "
                        "character name and password. Safe to call when already connected "
                        "(returns current status instead of reconnecting).",
            parameters={},
            block=lambda: _mud_connect(client, host, port, name, password),
        )

        registry.tool(
            "mud_disconnect",
            description="Close the connection to the MUD server gracefully.",
            parameters={},
            block=lambda: _mud_disconnect(client),
        )

        registry.tool(
            "mud_status",
            description="Return whether the MUD session is currently connected.",
            parameters={},
            block=lambda: _mud_status(client),
        )

        registry.tool(
            "look",
            description="Look at the current room or at a specific target. "
                        "Call with NO arguments to describe the current room (do NOT pass target: 'room'). "
                        "Pass a target to inspect a specific item, mob, or player (e.g. target: 'sword'). "
                        "Use preposition 'in' to look inside a container, 'at' to inspect something, "
                        "or a direction (north/east/south/west/up/down) to peek into an adjacent room.",
            parameters={
                "target": {"type": "string", "description": "Item, mob, or player name to inspect. Omit entirely to describe the current room."},
                "preposition": {"type": "string", "description": "Preposition: in, at, north, east, south, west, up, down (optional)"},
            },
            block=lambda target=None, preposition=None: _send_guarded(send_cmd, guard, f"look {target or ''} {preposition or ''}".strip()),
        )

        registry.tool(
            "examine",
            description="Examine a target in detail (more verbose than look).",
            parameters={
                "target": {"type": "string", "description": "The item, mob, or player to examine"},
            },
            block=lambda target: _send_guarded(send_cmd, guard, f"examine {target}"),
        )

        registry.tool(
            "check",
            description="Query information about your character or surroundings. "
                        "Kinds: score, inventory, equipment, gold, exits, time, weather, "
                        "levels, wimpy, toggle, where.",
            parameters={
                "kind": {"type": "string", "description": "What to check: score | inventory | equipment | gold | exits | time | weather | levels | wimpy | toggle | where"},
            },
            block=lambda kind: _send_guarded(send_cmd, guard, kind),
        )

        registry.tool(
            "move",
            description="Move in a compass direction or up/down.",
            parameters={
                "direction": {"type": "string", "description": "Direction: north | east | south | west | up | down"},
            },
            block=lambda direction: _send_guarded(send_cmd, guard, direction),
        )

        registry.tool(
            "flee",
            description="Attempt to flee from combat in a random available direction.",
            parameters={},
            block=lambda: _send_guarded(send_cmd, guard, "flee"),
        )

        registry.tool(
            "set_position",
            description="Change body position. Use 'rest' or 'sleep' between fights to recover "
                        "HP and mana. Must be standing to move or fight.",
            parameters={
                "position": {"type": "string", "description": "Position: stand | sit | rest | sleep | wake"},
            },
            block=lambda position: _send_guarded(send_cmd, guard, position),
        )

        registry.tool(
            "track",
            description="Attempt to track a mob or player by name, revealing which direction "
                        "they are in. Requires the Track skill.",
            parameters={
                "target": {"type": "string", "description": "Name of the mob or player to track"},
            },
            block=lambda target: _send_guarded(send_cmd, guard, f"track {target}"),
        )

        registry.tool(
            "attack",
            description="Attack a target. Style 'kill' is the standard approach; "
                        "'murder' bypasses the mercy check; 'hit' is a one-off strike.",
            parameters={
                "target": {"type": "string", "description": "Name of the mob or player to attack"},
                "style": {"type": "string", "description": "Attack style: kill | hit | murder (default: kill)"},
            },
            block=lambda target, style="kill": _send_guarded(send_cmd, guard, f"{style} {target}"),
        )

        registry.tool(
            "skill_strike",
            description="Use a combat skill against a target.",
            parameters={
                "skill": {"type": "string", "description": "Skill: bash | kick | backstab | rescue | assist"},
                "target": {"type": "string", "description": "Name of the mob or player"},
            },
            block=lambda skill, target: _send_guarded(send_cmd, guard, f"{skill} {target}"),
        )

        registry.tool(
            "consider",
            description="Assess a mob's relative strength before engaging in combat. "
                        "Returns a phrase such as 'You could kill it easily' or "
                        "'Death awaits you'. Always consider before attacking an unknown mob.",
            parameters={
                "target": {"type": "string", "description": "Name of the mob to consider"},
            },
            block=lambda target: _send_guarded(send_cmd, guard, f"consider {target}"),
        )

        registry.tool(
            "say",
            description="Speak or emote in the current room.",
            parameters={
                "text": {"type": "string", "description": "What to say or emote"},
                "mode": {"type": "string", "description": "Mode: say | emote | reply (default: say)"},
            },
            block=lambda text, mode="say": _send_guarded(send_cmd, guard, f"{mode} {text}"),
        )

        registry.tool(
            "tell",
            description="Send a private message to a specific player.",
            parameters={
                "target": {"type": "string", "description": "Player name to message"},
                "text": {"type": "string", "description": "The message"},
                "mode": {"type": "string", "description": "Mode: tell | whisper | ask (default: tell)"},
            },
            block=lambda target, text, mode="tell": _send_guarded(send_cmd, guard, f"{mode} {target} {text}"),
        )

        registry.tool(
            "channel_say",
            description="Broadcast a message over a global channel.",
            parameters={
                "channel": {"type": "string", "description": "Channel: shout | gossip | auction | grats | holler"},
                "text": {"type": "string", "description": "The message to broadcast"},
            },
            block=lambda channel, text: _send_guarded(send_cmd, guard, f"{channel} {text}"),
        )

        registry.tool(
            "get_item",
            description="Pick up an item from the room or from a container.",
            parameters={
                "item": {"type": "string", "description": "Name of the item to get"},
                "container": {"type": "string", "description": "Container to get it from (optional)"},
                "count": {"type": "integer", "description": "Number of items to get (optional)"},
            },
            block=lambda item, container=None, count=None: _get_item(send_cmd, guard, item, container, count),
        )

        registry.tool(
            "drop_item",
            description="Drop, donate, or junk an item.",
            parameters={
                "item": {"type": "string", "description": "Name of the item"},
                "mode": {"type": "string", "description": "Mode: drop | donate | junk (default: drop)"},
                "count": {"type": "integer", "description": "Number of items (optional)"},
            },
            block=lambda item, mode="drop", count=None: _send_guarded(send_cmd, guard, f"{mode} {item}"),
        )

        registry.tool(
            "put_item",
            description="Put an item into a container.",
            parameters={
                "item": {"type": "string", "description": "Name of the item to put"},
                "container": {"type": "string", "description": "Name of the container"},
                "count": {"type": "integer", "description": "Number of items (optional)"},
            },
            block=lambda item, container, count=None: _put_item(send_cmd, guard, item, container, count),
        )

        registry.tool(
            "equip_item",
            description="Wear, wield, hold, grab, or remove an item.",
            parameters={
                "item": {"type": "string", "description": "Name of the item"},
                "action": {"type": "string", "description": "Action: wear | wield | hold | grab | remove"},
                "body_loc": {"type": "string", "description": "Body location to wear on (optional, e.g. 'head', 'finger')"},
            },
            block=lambda item, action, body_loc=None: _equip_item(send_cmd, guard, action, item, body_loc),
        )

        registry.tool(
            "consume_item",
            description="Eat, drink, taste, or sip a consumable item.",
            parameters={
                "item": {"type": "string", "description": "Name of the item to consume"},
                "mode": {"type": "string", "description": "Mode: eat | drink | taste | sip (default: eat)"},
            },
            block=lambda item, mode="eat": _send_guarded(send_cmd, guard, f"{mode} {item}"),
        )

        registry.tool(
            "cast_spell",
            description="Cast a spell, optionally at a target.",
            parameters={
                "spell": {"type": "string", "description": "Full spell name (e.g. 'cure light wounds', 'magic missile')"},
                "target": {"type": "string", "description": "Target mob, player, or object (optional)"},
            },
            block=lambda spell, target=None: _cast_spell(send_cmd, guard, spell, target),
        )

        registry.tool(
            "use_magic_item",
            description="Activate a magic item: quaff a potion, recite a scroll, or use a wand/staff.",
            parameters={
                "item": {"type": "string", "description": "Name of the item to activate"},
                "mode": {"type": "string", "description": "Mode: quaff | recite | use"},
                "target_args": {"type": "string", "description": "Optional target arguments (e.g. mob name for a wand)"},
            },
            block=lambda item, mode, target_args=None: _use_magic_item(send_cmd, guard, mode, item, target_args),
        )

        registry.tool(
            "shop",
            description="Interact with a shop NPC: list stock, buy, sell, or get the value of an item.",
            parameters={
                "action": {"type": "string", "description": "Action: list | buy | sell | value | offer"},
                "args": {"type": "string", "description": "Item name or number (optional)"},
            },
            block=lambda action, args=None: _shop(send_cmd, guard, action, args),
        )

        registry.tool(
            "practice",
            description="List your known skills at a guildmaster, or practice a specific skill.",
            parameters={
                "skill": {"type": "string", "description": "Skill name to practice (omit to list all)"},
            },
            block=lambda skill=None: _practice(send_cmd, guard, skill),
        )

        registry.tool(
            "save_character",
            description="Save your character to disk so progress is not lost on disconnect.",
            parameters={},
            block=lambda: _send_guarded(send_cmd, guard, "save"),
        )

        registry.tool(
            "send_raw",
            description="Send an arbitrary command string to the MUD and return the response. "
                        "Use this as an escape hatch when no structured tool fits.",
            parameters={
                "command": {"type": "string", "description": "The raw command to send (e.g. 'who', 'help backstab')"},
            },
            block=lambda command: _send_guarded(send_cmd, guard, command),
        )

        # Auto-connect at startup
        _mud_connect(client, host, port, name, password)


def _mud_connect(client, host, port, name, password):
    result = client.connect(host=host, port=port, name=name, password=password)
    if result.get("ok"):
        return result["data"]
    return f"error: {result.get('error', 'unknown error')}"


def _mud_disconnect(client):
    result = client.disconnect()
    if result.get("ok"):
        return result["data"]
    return f"error: {result.get('error', 'unknown error')}"


def _mud_status(client):
    result = client.status()
    if result.get("ok"):
        data = result["data"]
        if data.get("connected"):
            return f"connected to {data['host']}:{data['port']}"
        return "disconnected"
    return f"error: {result.get('error', 'unknown error')}"


def _send_guarded(send_cmd, guard_fn, command):
    g = guard_fn()
    if g:
        return g
    result = send_cmd(command)
    if result.get("ok"):
        return result["data"]
    return f"error: {result.get('error', 'unknown error')}"


def _get_item(send_cmd, guard_fn, item, container, count):
    g = guard_fn()
    if g:
        return g
    parts = ["get"]
    if count is not None:
        parts.append(str(count))
    parts.append(item)
    if container:
        parts.append(container)
    return _send_guarded(send_cmd, guard_fn, " ".join(parts))


def _put_item(send_cmd, guard_fn, item, container, count):
    g = guard_fn()
    if g:
        return g
    parts = ["put"]
    if count is not None:
        parts.append(str(count))
    parts.extend([item, container])
    return _send_guarded(send_cmd, guard_fn, " ".join(parts))


def _equip_item(send_cmd, guard_fn, action, item, body_loc):
    g = guard_fn()
    if g:
        return g
    parts = [action, item]
    if body_loc:
        parts.append(body_loc)
    return _send_guarded(send_cmd, guard_fn, " ".join(parts))


def _cast_spell(send_cmd, guard_fn, spell, target):
    g = guard_fn()
    if g:
        return g
    parts = [f"cast '{spell}'"]
    if target:
        parts.append(target)
    return _send_guarded(send_cmd, guard_fn, " ".join(parts))


def _use_magic_item(send_cmd, guard_fn, mode, item, target_args):
    g = guard_fn()
    if g:
        return g
    parts = [mode, item]
    if target_args:
        parts.append(target_args)
    return _send_guarded(send_cmd, guard_fn, " ".join(parts))


def _shop(send_cmd, guard_fn, action, args):
    g = guard_fn()
    if g:
        return g
    parts = [action]
    if args:
        parts.append(args)
    return _send_guarded(send_cmd, guard_fn, " ".join(parts))


def _practice(send_cmd, guard_fn, skill):
    g = guard_fn()
    if g:
        return g
    if skill:
        return _send_guarded(send_cmd, guard_fn, f"practice {skill}")
    return _send_guarded(send_cmd, guard_fn, "practice")
