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
                          host="localhost", port=4000, quiet=False):
    root, boukensha_dir, settings = _resolve_boukensha()

    mud_cfg = settings.get("mud", {})
    reset_cfg = settings.get("reset", {})

    host = host or mud_cfg.get("host", "localhost")
    port = port or mud_cfg.get("port", 4000)
    player_name = player_name or mud_cfg.get("username")
    admin_name = admin_name or reset_cfg.get("admin", {}).get("username")
    admin_password = admin_password or reset_cfg.get("admin", {}).get("password")
    start_room = start_room or reset_cfg.get("start_room", "3001")

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

    admin = MudDaemonClient(session="reset_admin")

    if not quiet:
        print(f"  reset: connecting admin ({admin_name}) to MUD {host}:{port} via daemon port {admin._port}...", file=sys.stderr)
    result = admin.connect(host=host, port=port, name=admin_name, password=admin_password)
    if not result.get("ok"):
        raise ConnectionError(f"admin login failed: {result.get('error', 'unknown')}")

    from memory_hook import parse_room_description

    # Check where we are
    resp = admin.send("look")
    current = parse_room_description(resp.get("data", ""))
    current_name = current["room_name"] if current else "?"
    if not quiet:
        print(f"  reset: admin is at [{current_name}]", file=sys.stderr)

    # Try goto — if it fails, try @goto (alternate CircleMUD syntax)
    goto_resp = admin.send(f"goto {start_room}")
    goto_text = goto_resp.get("data", "")
    if "go there" not in goto_text.lower() and "transfer" not in goto_text.lower():
        if not quiet:
            print(f"  reset: goto failed (\"{goto_text.strip()[:60]}\"), trying @goto...", file=sys.stderr)
        # @goto is an alternate immortal syntax in some CircleMUD builds
        admin.send(f"@{start_room}")

    # Transfer the player to us
    transfer_resp = admin.send(f"transfer {player_name}")
    transfer_text = transfer_resp.get("data", "")
    if "you transfer" not in transfer_text.lower() and "arrives" not in transfer_text.lower():
        if not quiet:
            print(f"  reset: transfer response: {transfer_text.strip()[:80]}", file=sys.stderr)

    # Ensure character position is saved by quitting properly
    admin.send("quit")
    admin.disconnect()

    if not quiet:
        print(f"  reset: {player_name} moved to room {start_room}", file=sys.stderr)

    return True


def admin_connected(host="localhost", port=4000):
    try:
        from boukensha.tools.mud_client import MudDaemonClient
        c = MudDaemonClient(session="reset_check")
        result = c.ping()
        return result.get("ok") is True
    except Exception:
        return False
