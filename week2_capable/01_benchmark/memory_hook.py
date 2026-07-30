import re
import hashlib

_ANSI_RE = re.compile(r'\x1b\[[0-9;]*[a-zA-Z]')

_MOVE_FAILURES = re.compile(
    r'^(Alas|You can\'t|You cannot|It\'s|Sorry|Maybe|Try|I don\'t see|There is no)',
    re.IGNORECASE,
)


def _strip_ansi(text):
    return _ANSI_RE.sub('', text)


def _room_id(name):
    return hashlib.md5(name.encode()).hexdigest()[:16]


_EXITS_RE = re.compile(r'(?:Obvious exits|\[ Exits):\s*(.+)', re.IGNORECASE)
_DIR_RE = re.compile(r'\b(n|s|e|w|u|d|north|south|east|west|up|down)\b', re.IGNORECASE)
_DIR_MAP = {'n': 'north', 's': 'south', 'e': 'east', 'w': 'west', 'u': 'up', 'd': 'down'}


def _record_exit(direction, dest_name, exits):
    direction = direction.strip().lower()
    direction = _DIR_MAP.get(direction, direction)
    if direction in ('north', 'south', 'east', 'west', 'up', 'down'):
        exits.append({'direction': direction, 'dest': dest_name})


def parse_room_description(text):
    text = _strip_ansi(text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    if not lines:
        return None
    room_name = None
    exits = []
    for line in lines:
        m = _EXITS_RE.search(line)
        if not m:
            continue
        exits_text = m.group(1)
        if ',' in exits_text:
            for part in exits_text.split(','):
                part = part.strip()
                if not part:
                    continue
                parts = part.split(' - ', 1)
                direction = parts[0].strip().lower()
                dest_name = parts[1].strip() if len(parts) > 1 else None
                _record_exit(direction, dest_name, exits)
        else:
            for dm in _DIR_RE.finditer(exits_text):
                direction = dm.group(1).lower()
                _record_exit(direction, None, exits)
        break
    if not lines[0].startswith('Obvious') and not lines[0].startswith('[') and not lines[0].startswith('You'):
        room_name = lines[0]
    elif exits and len(lines) > 1:
        room_name = lines[1]
    if room_name and _MOVE_FAILURES.match(room_name):
        return None
    if not room_name and not exits:
        return None
    return {
        'room_name': room_name,
        'exits': exits,
    }


def parse_exits_output(text):
    """Parse output from MUD 'exits' command (direction -> destination name pairs)."""
    text = _strip_ansi(text)
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    exits = []
    for line in lines:
        if ' - ' not in line:
            continue
        parts = line.split(' - ', 1)
        direction = parts[0].strip().lower()
        direction = _DIR_MAP.get(direction, direction)
        dest = parts[1].strip() if len(parts) > 1 else None
        if direction in ('north', 'south', 'east', 'west', 'up', 'down') and dest:
            exits.append({'direction': direction, 'dest': dest})
    return exits if exits else None


def make_memory_hook():
    def after_tool(ctx, name, args, result, err):
        if err or not result:
            return
        store = ctx.memory_store
        if not store:
            return
        if name == 'look' and not args.get('target') and not args.get('preposition'):
            parsed = parse_room_description(result)
            if parsed and parsed['room_name']:
                rid = _room_id(parsed['room_name'])
                store.record_room(rid, parsed['room_name'], current=True)
                for ex in parsed['exits']:
                    dest_rid = _room_id(ex['dest']) if ex['dest'] else None
                    store.record_exit(rid, ex['direction'], dest_rid)
                ctx.inject_here_block()
        elif name == 'move':
            parsed = parse_room_description(result)
            if parsed and parsed['room_name']:
                rid = _room_id(parsed['room_name'])
                prev = store.current_room()
                if prev == rid:
                    return
                store.record_room(rid, parsed['room_name'], current=True)
                direction = args.get('direction', '?')
                if prev and direction != '?':
                    store.record_exit(prev, direction, rid)
                    store.mark_exit_walked(prev, direction)
                for ex in parsed['exits']:
                    dest_rid = _room_id(ex['dest']) if ex['dest'] else None
                    store.record_exit(rid, ex['direction'], dest_rid)
                ctx.inject_here_block()
        elif name == 'check' and args.get('kind') == 'exits':
            parsed = parse_exits_output(result)
            if parsed:
                current = store.current_room()
                if current:
                    for ex in parsed:
                        dest_rid = _room_id(ex['dest'])
                        store.record_room(dest_rid, ex['dest'])
                        store.record_exit(current, ex['direction'], dest_rid)
                    ctx.inject_here_block()
    return after_tool
