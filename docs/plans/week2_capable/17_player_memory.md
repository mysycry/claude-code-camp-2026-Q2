# Goal: Expand player memory beyond basic vitals

## Files

| File | What It Does |
|------|-------------|
| `week2_capable/01_benchmark/memory_hook.py` | `parse_room_description()` — parses MUD `look` output; `make_memory_hook()` — factory returning after_tool hook |
| `week1_baseline/python/12_context/boukensha/memory.py` | `MemoryStore` schema — includes `entities` table for mobs/items/players but no parsers for score/inventory/equipment |

## Key Architecture Decisions

- **Room description parsing only**: The implemented parsing pipeline handles `look` output — extracting room name, exits (both `Obvious exits:` and `[ Exits]:` formats), and identifying entities by color/name in the description text.
- **No score/inventory/equipment parsers in Python**: The `entities` table in `MemoryStore` has the schema for storing mob/item/player data, but the `memory_hook.py` only records rooms and exits. Score, practice, inventory, and equipment parsers exist in the Ruby version but were not ported to Python.
- **Parsed exit formats**:
  - `Obvious exits: north - Room Name, south - Another Room` (long form)
  - `[ Exits: n s e w ]` (short form, CircleMUD/ROM)
  - `Alas...` / `You can't go that way` (move failure detection)

## Key Findings

- The `check(kind: "score")`, `check(kind: "inventory")`, and `check(kind: "equipment")` tools exist in the Ruby MudManager but no parser consumes their output into structured memory in Python.
- The `record_entity()` method in `MemoryStore` is never called by the Python memory hook — only rooms and exits are recorded.
- Move failure is detected by regex matching on error messages like `Alas, you cannot go that way` and `You can't`.

## Verification

```bash
cd week2_capable/01_benchmark
python test_memory.py
```
