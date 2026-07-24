# MudManager — Testing Guide

## Architecture (three layers)

```
┌─────────────────────────────────────────────────────┐
│  Layer 3: Game Server (CircleMUD)                   │
│  Listens on port 4000 (default)                     │
│  This is the actual MUD you connect to and play     │
├─────────────────────────────────────────────────────┤
│  Layer 2: MudManager::Session (Ruby)                │
│  Manages a persistent Telnet connection to the MUD  │
│  Handles login, IAC stripping, prompt detection     │
│  Used directly by:  mud_daemon (NDJSON),            │
│                     mud_mcp (MCP), and Ruby code    │
├─────────────────────────────────────────────────────┤
│  Layer 1: Bridges to your agent                     │
│  ┌─────────────────┐  ┌──────────────────────────┐  │
│  │ mud_daemon       │  │ mud_mcp                  │  │
│  │ NDJSON over TCP  │  │ MCP over stdio           │  │
│  │ For Python/Java/ │  │ For opencode, Claude     │  │
│  │ Rust/Go clients  │  │ Desktop, any MCP host    │  │
│  └─────────────────┘  └──────────────────────────┘  │
└─────────────────────────────────────────────────────┘
```

### What to run when

| You want to... | Start this | Notes |
|---|---|---|
| Test Python client code | `mud_daemon` | Python talks to this via TCP |
| Let opencode use MUD tools | `mud_mcp` (via `opencode.json`) | opencode spawns this automatically |
| Connect to the actual game | **CircleMUD server** on `localhost:4000` | Required by both daemon and MCP server |
| Test Ruby code directly | Nothing — just `require "mud_manager"` | Ruby uses MudManager::Session directly |

**CircleMUD server must be running on port 4000 before `mud_daemon` or `mud_mcp` can connect to it.**

## Full startup sequence (in order)

### Step 0: Prerequisites (one-time)

```powershell
# Install mud_manager gem
C:\Ruby40-x64\bin\gem.cmd install --local week0_explore/mud_manager/mud_manager-0.1.0.gem --no-document

# Install Python dependencies
C:\Program` Files\PyManager\python.exe -m pip install python-dotenv pyyaml
```

### Step 1: Start the CircleMUD game server (Terminal 1)

```powershell
cd week0_explore\infrastructure
docker compose up --build
```

Wait until the container is ready (you'll see it listening on port 4000). Keep this terminal open.

> **First build takes time** — Docker downloads Debian, compiles tbaMUD from source. Subsequent starts are instant.

To verify it's running: open another terminal and run `telnet localhost 4000` — you should see the MUD's login prompt ("By what name do you wish to be known?").

### Step 2: Start the bridge you need

| If you're using... | Command (Terminal 2) |
|---|---|
| **Python client** (`MudDaemonClient`) | `C:\Ruby40-x64\bin\ruby.exe week1_baseline\ruby\10_standard_tool_library\bin\mud_daemon` |
| **opencode / MCP host** (via `opencode.json`) | No command — opencode spawns `mud_mcp` automatically when you launch it |

Both bridges auto-connect to the MUD using credentials from environment variables or `opencode.json`. Keep this terminal open.

### Step 3: Open a third terminal and test

```powershell
# From the repo root:
C:\Program` Files\PyManager\python.exe -c "
from boukensha.tools.mud_client import MudDaemonClient
c = MudDaemonClient()
print(c.connect(host='localhost', port=4000, name='YourChar', password='secret'))
print(c.send('look'))
print(c.send('score'))
"
```

Or if using opencode, just ask the AI to look around.

---

## Prerequisites

### 1. Start the daemon

```powershell
C:\Ruby40-x64\bin\ruby.exe week1_baseline\ruby\10_standard_tool_library\bin\mud_daemon
```

You should see:
```
[mud_daemon] listening on 127.0.0.1:64386 (pid 12345)
```

The port is ephemeral — it will differ each run. The daemon writes its port to `~/.mud_manager/port`.

### 2. Ping the daemon via PowerShell

```powershell
$port = Get-Content "$env:USERPROFILE\.mud_manager\port"
$sock = New-Object System.Net.Sockets.TcpClient("127.0.0.1", [int]$port)
$stream = $sock.GetStream()
$writer = New-Object System.IO.StreamWriter($stream)
$writer.WriteLine('{"cmd":"ping"}')
$writer.Flush()
$reader = New-Object System.IO.StreamReader($stream)
$reader.ReadLine()
$sock.Close()
```

Expected response:
```json
{"ok":true,"data":"pong"}
```

### 3. Test protocol edge cases (no session)

```powershell
$port = Get-Content "$env:USERPROFILE\.mud_manager\port"
$sock = New-Object System.Net.Sockets.TcpClient("127.0.0.1", [int]$port)
$stream = $sock.GetStream()
$writer = New-Object System.IO.StreamWriter($stream)
$writer.WriteLine('{"cmd":"send","command":"look"}')
$writer.Flush()
$reader = New-Object System.IO.StreamReader($stream)
$reader.ReadLine()
$sock.Close()
```

Expected:
```json
{"ok":false,"error":"not connected — call connect first"}
```

### 4. Test invalid JSON

```powershell
$sock = New-Object System.Net.Sockets.TcpClient("127.0.0.1", [int](Get-Content "$env:USERPROFILE\.mud_manager\port"))
$stream = $sock.GetStream()
$writer = New-Object System.IO.StreamWriter($stream)
$writer.WriteLine('not json at all')
$writer.Flush()
$reader = New-Object System.IO.StreamReader($stream)
$reader.ReadLine()
$sock.Close()
```

Expected:
```json
{"ok":false,"error":"invalid JSON"}
```

---

## Python client tests

Set up the Python path and encoding:

```powershell
cd week1_baseline\python\10_standard_tool_library
$env:PYTHONIOENCODING='utf-8'
```

### 5. Ping via MudDaemonClient

```powershell
C:\Program` Files\PyManager\python.exe -c "
from boukensha.tools.mud_client import MudDaemonClient
c = MudDaemonClient()
print('ping:', c.ping())
print('status:', c.status())
print('disconnect:', c.disconnect())
print('send:', c.send('look'))
"
```

### 6. Verify Mud.register warns when daemon is down

Stop the daemon (Ctrl+C), then:

```powershell
C:\Program` Files\PyManager\python.exe -c "
import sys; sys.path.insert(0, '.')
from boukensha.tools.mud import Mud
Mud.register(None, name='test', password='test')
"
```

Expected: a `UserWarning` about daemon not running, and no crash.

---

## Full MUD integration tests (requires a CircleMUD server)

### 7. End-to-end from Python

Start the daemon, then:

```powershell
C:\Program` Files\PyManager\python.exe -c "
from boukensha.tools.mud_client import MudDaemonClient
c = MudDaemonClient()
result = c.connect(host='localhost', port=4000, name='YourChar', password='secret')
print('connect:', result)
if result.get('ok'):
    print('look:', c.send('look'))
    print('score:', c.send('score'))
    print('disconnect:', c.disconnect())
"
```

### 8. End-to-end from Ruby (direct, no daemon)

```powershell
C:\Ruby40-x64\bin\ruby.exe -e "
require 'mud_manager'
s = MudManager::Session.new(host: 'localhost', port: 4000)
s.open
s.login('YourChar', 'secret')
puts s.send_command('look')
puts s.read_until_prompt
s.close
"
```

### 9. Via Boukensha Python REPL (with daemon)

First create `~/.boukensha/settings.yaml`:

```yaml
mud:
  host: localhost
  port: 4000
  username: YourChar
  password: secret
```

Start the daemon, then:

```powershell
C:\Program` Files\PyManager\python.exe -c "
import sys; sys.path.insert(0, '.')
from boukensha.tools.mud import Mud
from boukensha.registry import Registry
from boukensha.context import Context
from boukensha.tasks.player import Player as TaskPlayer
ctx = Context(task=TaskPlayer)
reg = Registry(ctx)
Mud.register(reg, host='localhost', port=4000, name='YourChar', password='secret')
tool = reg.get('look')
print('look result:', tool['block']())
"
```

---

---

## MCP Server Tests

The MCP server exposes all MUD tools via the [Model Context Protocol](https://modelcontextprotocol.io) — any MCP client (opencode, Claude Desktop, etc.) can use it directly.

### 10. Start the MCP server

```powershell
C:\Ruby40-x64\bin\ruby.exe week1_baseline\ruby\10_standard_tool_library\bin\mud_mcp
```

The MCP server reads JSON-RPC 2.0 messages from **stdin** and writes responses to **stdout** (logs go to stderr). This is the standard MCP stdio transport — configure your MCP client to spawn this process.

### 11. Manual JSON-RPC test (initialize + tools/list + tools/call)

```powershell
$ruby = "C:\Ruby40-x64\bin\ruby.exe"
$mcp_script = "week1_baseline\ruby\10_standard_tool_library\bin\mud_mcp"

$requests = @(
  '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"test","version":"0.1.0"}}}',
  '{"jsonrpc":"2.0","method":"notifications/initialized"}',
  '{"jsonrpc":"2.0","id":2,"method":"tools/list","params":{}}',
  '{"jsonrpc":"2.0","id":3,"method":"tools/call","params":{"name":"look","arguments":{}}}',
  '{"jsonrpc":"2.0","id":4,"method":"tools/call","params":{"name":"nonexistent","arguments":{}}}'
)

$psi = New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName = $ruby
$psi.Arguments = $mcp_script
$psi.RedirectStandardInput = $true
$psi.RedirectStandardOutput = $true
$psi.RedirectStandardError = $true
$psi.UseShellExecute = $false
$psi.CreateNoWindow = $true
$p = [System.Diagnostics.Process]::Start($psi)
Start-Sleep -Milliseconds 200
$requests | ForEach-Object { $p.StandardInput.WriteLine($_); Start-Sleep -Milliseconds 200 }
$p.StandardInput.Close()
$p.WaitForExit(4000)
$out = $p.StandardOutput.ReadToEnd()
$out -split "`n" | ForEach-Object { if ($_ -match '"id":') { Write-Output $_ } }
```

Expected responses:
- **id:1** — Server capabilities (protocol version, supported features)
- **id:2** — List of 27 MUD tools with full JSON Schema input definitions
- **id:3** — `{"isError":true,"content":[{"type":"text","text":"error: not connected — call mud_connect first"}]}`
- **id:4** — `{"isError":true,"content":[{"type":"text","text":"Unknown tool: nonexistent"}]}`

### 12. Auto-connect with environment variables

Set `MUD_USERNAME` and `MUD_PASSWORD` to have the server attempt auto-connect on initialize:

```powershell
$env:MUD_USERNAME = "dummy"
$env:MUD_PASSWORD = "helloworld"
C:\Ruby40-x64\bin\ruby.exe week1_baseline\ruby\10_standard_tool_library\bin\mud_mcp
```

The server will attempt to connect on startup and send a `notifications/message` event with the result.

### 13. Configure MCP in opencode

Add to your `opencode.json` (create one in the project root if missing):

```json
{
  "mcpServers": {
    "mud-manager": {
      "command": "C:\\Ruby40-x64\\bin\\ruby.exe",
      "args": [
        "week1_baseline\\ruby\\10_standard_tool_library\\bin\\mud_mcp"
      ],
      "env": {
        "MUD_HOST": "localhost",
        "MUD_PORT": "4000",
        "MUD_USERNAME": "dummy",
        "MUD_PASSWORD": "helloworld"
      }
    }
  }
}
```

## Troubleshooting

| Symptom | Likely cause |
|---------|-------------|
| `gem: command not found` | Ruby not on PATH — use `C:\Ruby40-x64\bin\gem.cmd` |
| `ruby: command not found` | Ruby not on PATH — use `C:\Ruby40-x64\bin\ruby.exe` |
| `Python was not found` | Python alias points to Microsoft Store stub — use full path `C:\Program Files\PyManager\python.exe` |
| `ModuleNotFoundError: No module named 'dotenv'` | Run `python -m pip install python-dotenv` |
| `Connection refused` | Daemon not running — start it first |
| `port file not found` | Daemon hasn't started yet — wait 1-2 seconds after launching |
| `gets: connection reset by peer` | Only one request per connection — the daemon closes after each response |

## Protocol reference

See `docs/plans/mud_manager/generic_interfacing.md` for the full NDJSON protocol spec.
