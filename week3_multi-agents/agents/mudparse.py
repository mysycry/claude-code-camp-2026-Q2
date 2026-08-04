import re

_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def strip_ansi(text):
    return _ANSI_RE.sub("", text or "")


_PROMPT_RE = re.compile(r"^\s*\d+H\s+\d+M\s+\d+V\b|^\s*[<>]\s*$")


def _is_prompt(line):
    stripped = line.strip()
    if not stripped:
        return False
    if re.match(r"^\d+H\s+\d+M\s+\d+V", stripped):
        return True
    if re.match(r"^(\d+/\d+H\s+)?(\d+/\d+M\s+)?\d+V?\s*>", stripped):
        return True
    if stripped in (">", "<", "> ", "(hit)") or stripped.endswith("> "):
        return True
    return False


def parse_exits(exits_text):
    exits = []
    for tok in exits_text.split():
        tok = tok.strip()
        if not tok:
            continue
        closed = tok.startswith("(") and tok.endswith(")")
        token = tok.strip("()")
        for ch in token:
            exits.append({"direction": ch, "open": not closed})
    return exits


def parse_room_block(text):
    """Parse a look/move room dump into name, description, exits, entities.

    Returns None if the text does not look like a room block.
    """
    lines = [strip_ansi(l).rstrip() for l in (text or "").splitlines()]
    exits_idx = None
    for i, l in enumerate(lines):
        if "Exits:" in l:
            exits_idx = i
            break
    if exits_idx is None:
        return None

    exits_line = lines[exits_idx]
    m = re.search(r"\[ Exits: (.*?) \]", exits_line)
    exits = parse_exits(m.group(1)) if m else []

    entities = []
    for l in lines[exits_idx + 1:]:
        stripped = l.strip()
        if not stripped:
            continue
        if _is_prompt(l):
            break
        entities.append(stripped)

    title = ""
    title_idx = exits_idx
    for idx in range(exits_idx):
        l = lines[idx].strip()
        if not l:
            continue
        if l.startswith("You ") or l.startswith("("):
            continue
        title = l
        title_idx = idx
        break

    desc_lines = []
    for l in lines[title_idx + 1:exits_idx]:
        l = l.strip()
        if l:
            desc_lines.append(l)
    description = " ".join(desc_lines)

    return {
        "name": title,
        "description": description,
        "exits": exits,
        "entities": entities,
    }


def classify_entity(line):
    """Return 'mob', 'item', or 'other' for a room entity line."""
    low = line.lower()
    if "lying here" in low:
        return "item"
    if any(marker in low for marker in (
        "standing here", "sitting here", "resting here",
        "sleeping here", "crouching here", "is here",
    )):
        return "mob"
    if "has arrived" in low or "has just arrived" in low:
        return "mob"
    return "other"


def extract_health(text):
    """Pull H/M/V from a prompt line like '38H 100M 27V ...'."""
    m = re.search(r"(\d+)H\s+(\d+)M\s+(\d+)V", strip_ansi(text or ""))
    if not m:
        return None
    return {"hp": int(m.group(1)), "mana": int(m.group(2)), "mv": int(m.group(3))}


def parse_score(text):
    """Extract level, gold, xp from a `score` dump.

    Returns a dict with keys: level, title, hp, max_hp, mana, max_mana,
    mv, max_mv, xp, xp_next, gold, alignment, armor, age.
    """
    text = strip_ansi(text or "")
    result = {}

    m = re.search(r"([\d]+)\(([\d]+)\) hit,?\s+([\d]+)\(([\d]+)\) mana\s+and\s+([\d]+)\(([\d]+)\) movement", text, re.IGNORECASE)
    if m:
        result["hp"], result["max_hp"] = int(m.group(1)), int(m.group(2))
        result["mana"], result["max_mana"] = int(m.group(3)), int(m.group(4))
        result["mv"], result["max_mv"] = int(m.group(5)), int(m.group(6))

    m = re.search(r"You have ([\d,]+) exp,\s*([\d,]+) gold", text, re.IGNORECASE)
    if m:
        result["xp"] = int(m.group(1).replace(",", ""))
        result["gold"] = int(m.group(2).replace(",", ""))

    m = re.search(r"You need ([\d,]+) exp to reach your next level", text, re.IGNORECASE)
    if m:
        result["xp_next"] = int(m.group(1).replace(",", ""))

    m = re.search(r"\(level ([\d]+)\)", text, re.IGNORECASE)
    if m:
        result["level"] = int(m.group(1))

    m = re.search(r"([\w\s]+)\s+\(level ([\d]+)\)\.", text, re.IGNORECASE)
    if m:
        result["title"] = m.group(1).strip()

    m = re.search(r"alignment is ([\d-]+)", text, re.IGNORECASE)
    if m:
        result["alignment"] = int(m.group(1))

    m = re.search(r"armor class is ([\d/]+)", text, re.IGNORECASE)
    if m:
        result["armor"] = m.group(1)

    m = re.search(r"You are ([\d]+) years old", text, re.IGNORECASE)
    if m:
        result["age"] = int(m.group(1))

    return result
