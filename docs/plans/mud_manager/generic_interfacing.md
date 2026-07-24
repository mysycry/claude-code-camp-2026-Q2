Our MudManager is written in Ruby.
In our Bootcamp, Bootcampers want to ouse their own langauge eg. Java, Python, Rust, Go.

What is the solution?
- We have to create wrapper per lang
- We make MudManager a command line tool, and other langs execute shell commands in their langs
- We implement a communication protcol
- We implement MCP as a layer.

Consider that the MudManager is managing the sessions for the MUD.





# Technical Exploration: Multi-Language MudManager Access

## Problem

MudManager is written in Ruby. It manages persistent Telnet sessions to CircleMUD —
opening connections, sending commands, reading responses until the prompt sentinel (`> `),
and keeping the session alive across multiple tool calls. Bootcampers want to write their
agent code in other languages (Python, Java, Rust, Go, etc.) while still using MudManager's
session management from Ruby.

## Constraints

1. **Session persistence** — A MUD session must survive across many command/respose cycles.
   Opening a new TCP connection per command is unacceptable (slow, breaks auto-login,
   loses character state).

2. **Prompt sentinel detection** — The key feature of MudManager is `read_until_prompt()`
   which drains the socket until the MUD's `> ` prompt appears. Reimplementing this in
   every language is fragile (each MUD codebase uses a different prompt).

3. **Doesn't need to be fast** — Single-user tool called at most once per LLM round trip
   (multiple seconds apart). Microsecond latency is irrelevant.

4. **Cross-platform** — Must work on Windows (bootcampers' machines) and Unix.

## Approaches

### Approach A: Per-language wrapper

Write native bindings in each target language. Ruby's C extension API (`mkmf`) would
need FFI bridges for each language.

| Pros | Cons |
|------|------|
| No network overhead | N developers must learn N FFI systems |
| Tight integration | MudManager API changes require N updates |
| No new deployment surface | Gem distribution doesn't help non-Ruby users |

**Verdict:** Too much maintenance for a bootcamp. Rejected.

### Approach B: CLI subprocess

MudManager exposes a command-line interface. Each language shells out:

```bash
mud_manager --host localhost --port 4000 --name Gandalf send "look"
```

| Pros | Cons |
|------|------|
| Trivial to call from any language | Process spawn per command (50–200ms on Windows) |
| No server to manage | Session state must be serialized between calls (file, env, or DB) |
| No new protocol to design | Maintaining a persistent Telnet session across process boundaries is the hard part |

The session persistence problem is fatal for this approach. The Telnet connection lives
inside the process; when it exits, the session dies. You'd need to keep a daemon process
alive anyway — at which point you've reinvented Approach C with extra steps.

**Verdict:** Simple to understand, but doesn't solve persistence. Rejected.

### Approach C: Persistent daemon with line-based protocol

MudManager runs as a long-lived daemon process. Other languages connect via TCP or
Unix socket and send text commands, receiving text responses.

```
> connect localhost 4000 Gandalf secret
ok: connected, welcome text follows...

> send look
ok: The dungeon room description...

> send move north
ok: You move north into a corridor...
```

| Pros | Cons |
|------|------|
| Session persists inside the daemon | Must design, implement, and document a protocol |
| Any language with TCP sockets can talk to it | Need to handle concurrent access (or forbid it) |
| Line-based = trivially debuggable (`nc`, `telnet`) | Port allocation, daemon lifecycle management |
| MudManager's prompt parsing stays in Ruby | Windows named pipes vs Unix sockets vs TCP |

**Key design decisions:**

- **Transport:** TCP on `127.0.0.1` (works cross-platform, no named-pipe pain on Windows).
  Pick an ephemeral port, write it to a well-known path (e.g., `~/.mud_manager/port`).
- **Protocol:** Newline-delimited JSON (NDJSON) or simple line-based text. NDJSON is
  easier for structured responses; plain text is easier to debug.
- **Session identity:** Only one session per daemon instance. Multi-session would need
  session IDs in each command.
- **Concurrency:** Single-threaded, one-request-at-a-time. Queue requests if needed later.

**Implementation sketch (Ruby daemon):**

```ruby
require "socket"

server = TCPServer.new("127.0.0.1", 0)  # ephemeral port
port = server.addr[1]
File.write(File.expand_path("~/.mud_manager/port"), port)

loop do
  client = server.accept
  # Read one line, parse command, dispatch, write response, close.
  # Session state (Telnet socket) lives in the daemon process between requests.
end
```

Each target language writes a thin ~50-line client:

```python
class MudManagerClient:
    def __init__(self):
        port = int(Path("~/.mud_manager/port").expanduser().read_text())
        self._sock = socket.create_connection(("127.0.0.1", port))

    def send(self, command):
        self._sock.sendall((command + "\n").encode())
        return self._sock.recv(65536).decode()
```

**Verdict:** Workable. Moderate implementation effort (~200 lines daemon + 50 lines per
language client). Requires a protocol spec.

### Approach D: Model Context Protocol (MCP)

Run MudManager as an MCP server using the [Model Context Protocol](https://modelcontextprotocol.io).
Each tool (look, move, attack, etc.) is an MCP tool. The LLM host (opencode, Claude Desktop,
etc.) calls them directly. No per-language client needed — the host handles protocol.

| Pros | Cons |
|------|------|
| No per-language client libraries needed | MCP is designed for LLM hosts, not arbitrary programs |
| Standardized tool definitions | Session lifecycle is tricky (MCP is stateless by design) |
| Would integrate with opencode, Claude Desktop, etc. | Most bootcampers won't be using MCP hosts directly |
| Growing ecosystem | Still young/evolving protocol |

**Verdict:** Promising for AI-agent consumption, but doesn't solve "my Python agent code
needs to call the MUD" problem unless they run an MCP host. Secondary/optional layer.

## Recommended Approach: Hybrid (C + optional MCP)

**Primary: Persistent daemon with NDJSON protocol (Approach C).**

This solves the core problem directly:

1. MudManager becomes a daemon (single Ruby process, long-lived)
2. Protocol: NDJSON over TCP on `127.0.0.1` with ephemeral port file at `~/.mud_manager/port`
3. Each session gets an ID; multiple concurrent sessions supported
4. Commands: `connect`, `send`, `disconnect`, `status`
5. Each language gets a ~50-line client class
6. Bootcampers only need to copy the client into their project

**Secondary: Optional MCP wrapper (Approach D).**

An MCP server wraps the daemon protocol for AI-host integration. Not required for the
bootcamp, but available for students who want to connect via opencode or Claude Desktop.

### Protocol Specification (NDJSON)

```
Request:  {"cmd": "connect", "session": "default", "host": "localhost", "port": 4000, "name": "Gandalf", "password": "secret"}
Response: {"ok": true, "data": "connected\nWelcome to the MUD!\n> "}

Request:  {"cmd": "send", "session": "default", "command": "look"}
Response: {"ok": true, "data": "The dungeon room...\n> "}

Request:  {"cmd": "send", "session": "default", "command": "move north"}
Response: {"ok": true, "data": "You move north...\n> "}

Request:  {"cmd": "disconnect", "session": "default"}
Response: {"ok": true, "data": "disconnected"}

Request:  {"cmd": "status", "session": "default"}
Response: {"ok": true, "data": {"connected": true, "host": "localhost", "port": 4000, "name": "Gandalf"}}

Request:  {"cmd": "ping"}
Response: {"ok": true, "data": "pong"}
```

Error response:
```
{"ok": false, "error": "not connected — call connect first"}
```

### Implementation Plan

| Step | What | Who |
|------|------|-----|
| 1 | Refactor MudManager::Session into a standalone class usable without the full tool registry | Existing Ruby code |
| 2 | Write daemon: TCPServer, NDJSON dispatch, session map | New Ruby file |
| 3 | Write protocol spec document | Doc |
| 4 | Write Python client (~50 lines) | Python port |
| 5 | Write Java client (~80 lines) | Bootcamper exercise? |
| 6 | Write Rust client (~100 lines) | Bootcamper exercise? |
| 7 | Write Go client (~80 lines) | Bootcamper exercise? |
| 8 | Optional: MCP server wrapper | Future |

### Open Questions

1. **Auto-reconnect on disconnect?** Yes — the daemon should auto-reconnect if the MUD
   drops the connection (CircleMUD has a 15-minute idle timeout).
2. **Authentication for the daemon itself?** Bind only to `127.0.0.1` — no external auth
   needed in a bootcamp context.
3. **Daemon lifecycle?** Start via `mud_manager daemon`, stop via `mud_manager stop` or
   signal. Could also use a systemd user service or Windows task.
4. **Port file race condition?** Use file locking (`flock` on Unix, `LockFile` on Windows)
   when reading/writing the port file, or put the port in a predictable location
   (`~/.mud_manager/port` with a fixed port fallback).
5. **Command timeout?** MUD commands can hang (combat lag, sleep). Add a per-command
   timeout (default 30s) configurable in the request.
