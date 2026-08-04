"""Parse CircleMUD world files and load data into MemoryStore."""
import glob, os, sys

PARSER_DIR = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                          "week0_explore", "circlemud-world-parser")
sys.path.insert(0, PARSER_DIR)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), os.pardir, os.pardir,
                                "week1_baseline", "python", "12_context"))
sys.path.insert(0, os.path.dirname(__file__))

DATA_DIR = os.path.join(PARSER_DIR, "assets")
DB_PATH = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir,
    "week3_multi-agents", "memory", "memory_bench.db",
)

from boukensha.memory import MemoryStore
from circlemud_world_parser.utils import parse_from_file
from circlemud_world_parser.room import Room
from circlemud_world_parser.mobile import Mobile
from circlemud_world_parser.object import Object
from circlemud_world_parser.zone import Zone
from circlemud_world_parser.shop import Shop


def _flag_names(flags):
    if not flags:
        return ""
    if isinstance(flags, list):
        parts = []
        for f in flags:
            if hasattr(f, "note") and f.note:
                parts.append(f.note)
            elif hasattr(f, "value"):
                parts.append(str(f.value))
            else:
                parts.append(str(f))
        return ",".join(parts)
    return str(flags)


def _flatten_exit(exit_model):
    return {
        "direction": exit_model.dir,
        "room_linked": exit_model.room_linked,
        "door_flag": exit_model.door_flag.value,
    }


def _load():
    print(f"Loading world data from {DATA_DIR} into {DB_PATH}")
    store = MemoryStore(path=DB_PATH)

    # --- Zones ---
    zones = []
    for f in sorted(glob.glob(os.path.join(DATA_DIR, "zon", "*.zon"))):
        payload, errors = parse_from_file(f, Zone.from_text)
        for z in payload:
            zones.append({
                "vnum": z.id,
                "name": z.name,
                "bottom_room": z.bottom_room,
                "top_room": z.top_room,
            })
    if zones:
        store.load_world_data(zones=zones)
        print(f"  zones: {len(zones)}")

    # --- Rooms ---
    rooms = []
    room_exits = []
    for f in sorted(glob.glob(os.path.join(DATA_DIR, "wld", "*.wld"))):
        payload, errors = parse_from_file(f, Room.from_text)
        for rm in payload:
            rooms.append({
                "vnum": rm.id,
                "name": rm.name,
                "zone_number": rm.zone_number,
                "sector_type": rm.sector_type.note if rm.sector_type and rm.sector_type.note else str(rm.sector_type.value) if rm.sector_type else None,
                "flags": _flag_names(rm.flags),
            })
            for ex in rm.exits:
                flat = _flatten_exit(ex)
                flat["from_room"] = rm.id
                room_exits.append(flat)
    store.load_world_data(rooms=rooms, exits=room_exits)
    print(f"  rooms: {len(rooms)}, exits: {len(room_exits)}")

    # --- Mobs ---
    mobs = []
    for f in sorted(glob.glob(os.path.join(DATA_DIR, "mob", "*.mob"))):
        payload, errors = parse_from_file(f, Mobile.from_text)
        for m in payload:
            flags_str = _flag_names(m.flags)
            mobs.append({
                "vnum": m.id,
                "aliases": ",".join(m.aliases) if m.aliases else "",
                "short_desc": m.short_desc,
                "long_desc": m.long_desc,
                "level": m.level,
                "thac0": m.thac0,
                "armor_class": m.armor_class,
                "hp_dice": str(m.max_hit_points) if m.max_hit_points else "",
                "damage_dice": str(m.bare_hand_damage) if m.bare_hand_damage else "",
                "gold": m.gold,
                "xp": m.xp,
                "alignment": m.alignment,
                "flags": flags_str,
            })
    store.load_world_data(mobs=mobs)
    print(f"  mobs: {len(mobs)}")

    # --- Objects ---
    objects = []
    for f in sorted(glob.glob(os.path.join(DATA_DIR, "obj", "*.obj"))):
        payload, errors = parse_from_file(f, Object.from_text)
        for o in payload:
            objects.append({
                "vnum": o.id,
                "aliases": ",".join(o.aliases) if o.aliases else "",
                "short_desc": o.short_desc,
                "long_desc": o.long_desc,
                "obj_type": _flag_names([o.type]) if o.type else "",
                "wear_flags": _flag_names(o.wear),
                "weight": o.weight,
                "cost": o.cost,
                "rent": o.rent,
                "values_str": ",".join(str(v) for v in (o.values or [])),
                "affects": _flag_names(o.affects) if hasattr(o, 'affects') else "",
            })
    store.load_world_data(objects=objects)
    print(f"  objects: {len(objects)}")

    # --- Zone mob spawns ---
    spawns = []
    for f in sorted(glob.glob(os.path.join(DATA_DIR, "zon", "*.zon"))):
        payload, errors = parse_from_file(f, Zone.from_text)
        for z in payload:
            for zm in z.mobs:
                spawns.append({
                    "zone_vnum": z.id,
                    "mob_vnum": zm.mob,
                    "room_vnum": zm.room,
                    "max_count": zm.max,
                })
    if spawns:
        store.load_world_data(spawns=spawns)
        print(f"  mob spawns: {len(spawns)}")

    # --- Shops ---
    shops = []
    for f in sorted(glob.glob(os.path.join(DATA_DIR, "shp", "*.shp"))):
        payload, errors = parse_from_file(f, Shop.from_text)
        for s in payload:
            shops.append({
                "vnum": s.id,
                "shopkeeper_mob": s.shopkeeper,
                "objects": ",".join(str(o) for o in s.objects),
                "sell_rate": s.sell_rate,
                "buy_rate": s.buy_rate,
                "buy_types": ",".join(str(b) for b in s.buy_types) if s.buy_types else "",
                "rooms": ",".join(str(r) for r in s.rooms) if s.rooms else "",
                "trades_with": _flag_names(s.trades_with) if hasattr(s, 'trades_with') else "",
            })
    if shops:
        store.load_world_data(shops=shops)
        print(f"  shops: {len(shops)}")

    store.close()
    summary = _summarize(DB_PATH)
    print(f"\nWorld data loaded successfully:")
    print(f"  {summary['rooms']} rooms, {summary['exits']} exits, {summary['mobs']} mobs, "
          f"{summary['objects']} objects, {summary['zones']} zones, {summary['shops']} shops")


def _summarize(db_path):
    import sqlite3
    conn = sqlite3.connect(db_path)
    counts = {}
    for table in ("world_rooms", "world_exits", "world_mobs", "world_objects", "world_zones", "world_shops"):
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
        counts[table.replace("world_", "")] = row[0] if row else 0
    conn.close()
    return counts


if __name__ == "__main__":
    _load()
