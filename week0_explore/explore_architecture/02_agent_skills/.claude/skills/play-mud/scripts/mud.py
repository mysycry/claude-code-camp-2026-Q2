#!/usr/bin/env python3
"""
MUD Client — connects to tbaMUD on localhost:4000 and executes commands.

Usage:
  python3 mud.py "<command>"
  python3 mud.py "cmd1;cmd2;cmd3"
  python3 mud.py "cmd1;cmd2" --wait 2.0
  python3 mud.py "score;look;eq" --data-dir ./data
"""

import argparse
import os
import re
import select
import socket
import time

HOST = "localhost"
PORT = 4000
USERNAME = "dummy"
PASSWORD = "helloworld"
SOCKET_TIMEOUT = 15
CMD_DELAY = 0.3
RECV_TIMEOUT = 1.5


def strip_ansi(text: str) -> str:
    return re.sub(r"\x1b\[[0-9;]*m", "", text)


def load_memory(data_dir: str) -> dict:
    memory = {}
    for name in ("player", "world"):
        path = os.path.join(data_dir, f"{name}.md")
        if os.path.exists(path):
            with open(path) as f:
                memory[name] = f.read()
        else:
            memory[name] = ""
    return memory


def update_player_memory(data_dir: str, output: str, existing: str):
    """Parse score output and update player.md with current stats."""
    lines = output.split("\n")
    updates = {}

    for line in lines:
        m = re.match(r"You are (\d+) years old", line)
        if m:
            updates["age"] = m.group(1)

        m = re.match(r"You have (\d+)\((\d+)\) hit, (\d+)\((\d+)\) mana and (\d+)\((\d+)\) movement", line)
        if m:
            updates["hp_cur"], updates["hp_max"] = m.group(1), m.group(2)
            updates["mana_cur"], updates["mana_max"] = m.group(3), m.group(4)
            updates["mv_cur"], updates["mv_max"] = m.group(5), m.group(6)

        m = re.match(r"Your armor class is ([\d/]+)", line)
        if m:
            updates["ac"] = m.group(1)

        m = re.match(r"Your alignment is (-?\d+)", line)
        if m:
            updates["alignment"] = m.group(1)

        m = re.match(r"You have (\d+) exp", line)
        if m:
            updates["xp"] = m.group(1)

        m = re.match(r"You have (\d+) gold coins", line)
        if m:
            updates["gold"] = m.group(1)

        m = re.match(r"You need (\d+) exp to reach your next level", line)
        if m:
            updates["xp_next"] = m.group(1)

        m = re.match(r"This ranks you as .+ \(level (\d+)\)", line)
        if m:
            updates["level"] = m.group(1)

        m = re.match(r"You have been playing for (\d+) days and (\d+) hours", line)
        if m:
            updates["played_days"] = m.group(1)
            updates["played_hours"] = m.group(2)

    if not updates:
        return existing

    header = "## Player Memory (auto-updated from score)"
    body = existing
    if header in body:
        body = body.replace(header, "").strip()

    for key, val in updates.items():
        line_prefix = f"- {key}: "
        found = False
        for old_line in body.split("\n"):
            if old_line.startswith(line_prefix):
                body = body.replace(old_line, f"{line_prefix}{val}")
                found = True
                break
        if not found:
            body += f"\n{line_prefix}{val}"

    return f"{header}\n{body.strip()}\n"


def update_world_memory(data_dir: str, output: str, existing: str):
    """Parse look output and update current room info."""
    lines = output.split("\n")
    room_name = ""
    room_desc_lines = []
    exits_line = ""
    in_desc = False

    for line in lines:
        if line and not line.startswith(" ") and not line.startswith("[") and in_desc:
            in_desc = False
        if in_desc:
            room_desc_lines.append(line.strip())
        if re.match(r"^[A-Z][A-Za-z ]+$", line) and room_name == "":
            room_name = line.strip()
            in_desc = True
        if line.startswith("[ Exits:"):
            exits_line = line
            in_desc = False

    if not room_name:
        return existing

    header = "## World Memory (auto-updated from look)"
    room_section = f"\n### Current Room\n- name: {room_name}"

    for desc_line in room_desc_lines:
        if desc_line:
            room_section += f"\n  {desc_line}"

    if exits_line:
        room_section += f"\n- exits: {exits_line.strip()}"

    if existing and "## World Memory" in existing:
        existing = re.sub(
            r"## World Memory.*?(?=\n## |\Z)",
            f"{header}{room_section}",
            existing,
            flags=re.DOTALL,
        )
        return existing

    return f"{header}{room_section}\n"


def save_memory(data_dir: str, output: str, old_memory: dict):
    os.makedirs(data_dir, exist_ok=True)

    player = update_player_memory(data_dir, output, old_memory.get("player", ""))
    world = update_world_memory(data_dir, output, old_memory.get("world", ""))

    for name, content in [("player", player), ("world", world)]:
        path = os.path.join(data_dir, f"{name}.md")
        if content:
            with open(path, "w") as f:
                f.write(content + "\n")

    output_path = os.path.join(data_dir, "last_output.txt")
    with open(output_path, "w") as f:
        f.write(output)


class MudClient:
    def __init__(self):
        self.sock = None

    def connect(self):
        self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        self.sock.settimeout(SOCKET_TIMEOUT)
        self.sock.connect((HOST, PORT))

    def _recv(self, timeout: float = RECV_TIMEOUT) -> str:
        data = b""
        while True:
            ready, _, _ = select.select([self.sock], [], [], timeout)
            if ready:
                chunk = self.sock.recv(4096)
                if not chunk:
                    break
                data += chunk
            else:
                break
        return data.decode(errors="replace")

    def _send(self, text: str, delay: float = CMD_DELAY):
        self.sock.send((text + "\n").encode())
        time.sleep(delay)

    def login(self):
        self._recv(2)
        self._send(USERNAME)
        time.sleep(0.5)
        self._recv(1.5)
        self._send(PASSWORD)
        time.sleep(1.5)
        output = self._recv(2.5)
        if "Make your choice" in output or "PRESS RETURN" in output:
            self._send("", 0.5)
            self._recv(1.5)
            self._send("1", 1.5)
            self._recv(2.5)
        self._send("wake", 0.3)
        self._recv(1)
        self._send("stand", 0.3)
        self._recv(1)

    def execute(self, commands: str, wait: float = None) -> str:
        parts = [c.strip() for c in commands.split(";") if c.strip()]
        results = []
        for cmd in parts:
            delay = wait if wait else CMD_DELAY
            self._send(cmd, delay)
            out = self._recv(RECV_TIMEOUT if not wait else wait)
            cleaned = strip_ansi(out)
            results.append(cleaned)
        return "\n---\n".join(results)

    def close(self):
        if self.sock:
            self.sock.close()
            self.sock = None


def main():
    parser = argparse.ArgumentParser(description="MUD Client for tbaMUD")
    parser.add_argument("commands", nargs="?", default="look", help="Command(s) to execute. Use ; to separate multiple commands.")
    parser.add_argument("--wait", type=float, default=None, help="Extra wait time between commands (seconds)")
    parser.add_argument("--data-dir", type=str, default=None, help="Directory for persistent memory (player.md, world.md)")
    args = parser.parse_args()

    memory = {}
    if args.data_dir:
        memory = load_memory(args.data_dir)

    client = MudClient()
    try:
        client.connect()
        client.login()

        if memory.get("player"):
            print(f"[Memory] Player state loaded from {args.data_dir}/player.md")
        if memory.get("world"):
            print(f"[Memory] World state loaded from {args.data_dir}/world.md")

        output = client.execute(args.commands, args.wait)
        print(output)

        if args.data_dir:
            save_memory(args.data_dir, output, memory)
            print(f"[Memory] State saved to {args.data_dir}/")
    finally:
        client.close()


if __name__ == "__main__":
    main()
