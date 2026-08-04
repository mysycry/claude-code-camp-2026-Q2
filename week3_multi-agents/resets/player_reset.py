import os
import sys
import yaml


def _resolve_boukensha():
    root = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
    sys.path.insert(0, os.path.join(root, "week1_baseline", "python", "12_context"))

    boukensha_dir = os.environ.get("BOUKENSHA_DIR") or os.path.join(root, ".boukensha")
    settings_file = os.path.join(boukensha_dir, "settings.yaml")

    os.environ.setdefault("BOUKENSHA_DIR", boukensha_dir)
    os.environ.setdefault("MUD_MANAGER_DIR", os.path.join(root, ".mud_manager"))

    settings = {}
    if os.path.isfile(settings_file):
        with open(settings_file, encoding="utf-8") as f:
            settings = yaml.safe_load(f) or {}

    return root, boukensha_dir, settings


def reset_player_to_start(admin_name=None, admin_password=None,
                          player_name=None, start_room="3001",
                          start_room_name=None, max_attempts=3,
                          host="localhost", port=4000, quiet=False):
    root, boukensha_dir, settings = _resolve_boukensha()

    mud_cfg = settings.get("mud", {})
    reset_cfg = settings.get("reset", {})

    host = host or mud_cfg.get("host", "localhost")
    port = port or mud_cfg.get("port", 4000)
    player_name = player_name or mud_cfg.get("username")
    admin_name = admin_name or reset_cfg.get("admin", {}).get("username")
    admin_password = admin_password or reset_cfg.get("admin", {}).get("password")
    start_room = start_room or os.environ.get("RESET_START_ROOM") or reset_cfg.get("start_room", "3001")
    start_room_name = start_room_name or os.environ.get("RESET_START_ROOM_NAME") or reset_cfg.get("start_room_name")
    if max_attempts is None:
        max_attempts = int(os.environ.get("RESET_MAX_ATTEMPTS") or reset_cfg.get("max_attempts", 3))

    if not admin_name or not admin_password:
        raise ValueError(
            "Admin credentials required. Set reset.admin.username and "
            "reset.admin.password in .boukensha/settings.yaml"
        )
    if not player_name:
        raise ValueError(
            "Player name required. Set mud.username in "
            ".boukensha/settings.yaml or pass player_name= to this function"
        )

    from boukensha.tools.mud_client import MudDaemonClient
    from boukensha.tools.mud_client import PORT_FILE

    # Disconnect any stale session first, then connect fresh
    if PORT_FILE.is_file():
        try:
            stale = MudDaemonClient(session="reset_admin")
            stale.disconnect()
        except (ConnectionRefusedError, ConnectionError, OSError):
            pass

    from memory_hook import parse_room_description

    def _room_name(client, command="look"):
        resp = client.send(command)
        parsed = parse_room_description(resp.get("data", ""))
        return parsed["room_name"] if parsed and parsed["room_name"] else None

    last_room = None
    for attempt in range(1, max_attempts + 1):
        admin = MudDaemonClient(session="reset_admin")

        if not quiet:
            print(f"  reset: attempt {attempt}/{max_attempts}: connecting admin ({admin_name}) "
                  f"to MUD {host}:{port} via daemon port {admin._port}...", file=sys.stderr)
        result = admin.connect(host=host, port=port, name=admin_name, password=admin_password)
        if not result.get("ok"):
            raise ConnectionError(f"admin login failed: {result.get('error', 'unknown')}")

        # Try goto — if it fails, try @goto (alternate CircleMUD syntax)
        goto_resp = admin.send(f"goto {start_room}")
        goto_text = goto_resp.get("data", "")
        if "go there" not in goto_text.lower() and "transfer" not in goto_text.lower():
            if not quiet:
                print(f"  reset: goto returned (\"{goto_text.strip()[:60]}\"), trying @goto...", file=sys.stderr)
            # @goto is an alternate immortal syntax in some CircleMUD builds
            admin.send(f"@{start_room}")

        # Verify the admin actually arrived at the intended room before transfer.
        admin_room = _room_name(admin)
        if not quiet:
            print(f"  reset: admin is at [{admin_room}]", file=sys.stderr)

        # Transfer the player to the admin (player lands in the admin's room).
        transfer_resp = admin.send(f"transfer {player_name}")
        transfer_text = transfer_resp.get("data", "")
        if "you transfer" not in transfer_text.lower() and "arrives" not in transfer_text.lower():
            if not quiet:
                print(f"  reset: transfer response: {transfer_text.strip()[:80]}", file=sys.stderr)

        # Confirm where the player actually ended up (same room as admin).
        player_room = _room_name(admin)
        admin.send("quit")
        admin.disconnect()

        last_room = player_room or admin_room
        if start_room_name:
            if last_room and last_room.strip().lower() == start_room_name.strip().lower():
                if not quiet:
                    print(f"  reset: verified {player_name} at [{last_room}] (attempt {attempt})", file=sys.stderr)
                return last_room
            if not quiet:
                print(f"  reset: mismatch — player at [{last_room}], expected [{start_room_name}]", file=sys.stderr)
            continue

        # No expected name configured: still report the actual room for the caller.
        if not quiet:
            print(f"  reset: {player_name} moved to room {start_room} (actual: [{last_room}])", file=sys.stderr)
        return last_room

    raise RuntimeError(
        f"reset failed after {max_attempts} attempts: player at [{last_room}], "
        f"expected [{start_room_name}] (start_room={start_room}). "
        "Live-server room vnums may differ from the offline world DB; "
        "set reset.start_room / reset.start_room_name in .boukensha/settings.yaml."
    )


def admin_connected(host="localhost", port=4000):
    try:
        from boukensha.tools.mud_client import MudDaemonClient
        c = MudDaemonClient(session="reset_check")
        result = c.ping()
        return result.get("ok") is True
    except Exception:
        return False
