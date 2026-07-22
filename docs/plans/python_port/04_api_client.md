# Python Port Plan: Step 04 — The API Client

**Starting point:** copy `python/03_prompt_builder/` → `python/04_api_client/`.
Then add the Client, ApiError, updated example, and new system prompt that Step 04 introduces.

---

## What's New in Step 04

| Ruby Source (new/changed) | Python Target | What It Does |
|---|---|---|
| `backends/base.rb` | `boukensha/backends/base.py` | **Already ported in Step 03** — model validation, cost helpers ✓ |
| `backends/*.rb` | `boukensha/backends/*.py` | **Already ported in Step 03** — all 7 backends with model tables ✓ |
| `errors.rb` | `boukensha/errors.py` | Add `ApiError` alongside existing `UnknownToolError` / `UnsupportedModelError` |
| `client.rb` | `boukensha/client.py` | **NEW** — HTTP POST with retry/exponential backoff, SSL, `JSON.parse` |
| `prompts/system.md` | `boukensha/prompts/system.md` | **OVERWRITE** — new Boukensha MUD player prompt |
| `tasks/base.rb` + `player.rb` | `boukensha/tasks/base.py`, `player.py` | **Already ported in Step 03** ✓ |
| `config.rb` | `boukensha/config.py` | **Already ported in Step 03** — task-based config, `PROMPTS_DIR`, `dig()` ✓ |
| `lib/boukensha.rb` | `boukensha/__init__.py` | Add imports for `Client` + `ApiError` |
| `examples/example.rb` | `examples/example.py` | **REWRITE** — uses `Client.call()` to hit the real API, prints raw response |

---

## What Stays the Same

`config.py`, `context.py`, `tool.py`, `message.py`, `registry.py`, `prompt_builder.py`, `backends/*.py`, `tasks/*.py`, `pyproject.toml` — no changes at all. Step 04 only adds the HTTP client layer and updates the example to exercise it.

---

## Architecture

```
Config → player_settings, system_prompt
                ↓
Context + Registry → messages, tools
                ↓
Backend → to_payload(), headers(), url()
                ↓
PromptBuilder → .to_api_payload(), .headers(), .url()
                ↓
Client.call() → HTTP POST → JSON response
```

### `client.rb` (78 LOC) — what to port

```ruby
class Client
  RETRYABLE_STATUS_CODES = [408, 409, 429, 500, 502, 503, 504]
  TRANSIENT_ERRORS = [EOFError, ECONNRESET, ...]
  MAX_RETRIES = 3
  BASE_RETRY_DELAY = 0.5

  def initialize(builder)       # @builder = builder
  def call(max_output_tokens:)   # → parsed JSON hash
    # 1. Build URI, Net::HTTP, enable SSL if https
    # 2. POST with builder.headers + builder.to_api_payload.to_json
    # 3. Retry loop: catch TRANSIENT_ERRORS, check retryable status codes
    # 4. Exponential backoff: BASE_RETRY_DELAY * 2^(attempt-1)
    # 5. Raise ApiError on non-2xx
    # 6. JSON.parse(response.body)
  end
end
```

**Python notes:**
- Use `urllib.request` or `http.client` from stdlib (no external dep). Ruby uses `net/http` — match with Python's `urllib.request`.
- SSL: `context = ssl.create_default_context()` when scheme is `"https"`.
- `TRANSIENT_ERRORS`: map Ruby exceptions (`EOFError`, `Errno::ECONNRESET`, `Timeout::Error`, `socket.error`, `ssl.SSLError`) to Python equivalents (`ConnectionError`, `TimeoutError`, `ssl.SSLError`, `socket.gaierror`, etc.).
- `sleep()` between retries via `time.sleep()`.
- Raise `ApiError` with message including status code and body.

### `errors.rb` change

Add `ApiError` alongside existing errors:

```ruby
class UnknownToolError < StandardError; end
class ApiError         < StandardError; end
class UnsupportedModelError < StandardError; end
```

Python: one extra line `class ApiError(Exception): pass` in `boukensha/errors.py`.

### `prompts/system.md` — new content

Overwrite `boukensha/prompts/system.md` with:

```
You are Boukensha, an autonomous player exploring a CircleMUD world.

Use available tools to observe the world, act deliberately, and explain only what matters for the current turn.
```

### `example.rb` changes (83 LOC)

The example now:
1. Same setup as Step 03 (Config, Player.system_prompt, Context, Registry, tools, messages)
2. Dispatches backend by `provider` string (already done in Step 03)
3. Creates `PromptBuilder.new(ctx, backend)`
4. Creates `Client.new(builder)`
5. Prints `builder.url` to show the endpoint
6. Calls `client.call` (with no args, defaults `max_output_tokens=1024`)
7. Prints `JSON.pretty_generate(response)`

**Key differences from Step 03's example:**
- Tools changed: now `read_file` and `list_directory` (real file system operations) instead of `look` / `move`
- Messages changed: now a single user message `"What files are in the current directory?"` instead of 3 simulated messages
- Calls `client.call` instead of just printing `builder.to_api_payload()`
- Uses the `when "opencode"` case (same as other backends, just different env var)

---

## Files to Create / Modify

| Action | File | Notes |
|---|---|---|
| UPDATE | `boukensha/errors.py` | Add `class ApiError(Exception): pass` |
| CREATE | `boukensha/client.py` | Port of `Client` — HTTP POST, retry, SSL |
| OVERWRITE | `boukensha/prompts/system.md` | New Boukensha MUD prompt |
| UPDATE | `boukensha/__init__.py` | Import `Client`, add `ApiError` to imports + `__all__` |
| REWRITE | `examples/example.py` | Use `Client.call()`, `read_file`/`list_directory` tools, print raw response |

---

## Questions

1. **Which Python HTTP lib?** Ruby uses `net/http` from stdlib. In Python we can use `urllib.request` — same level of abstraction, no external dep. Or `http.client`. Pick one for consistency. **(suggest: `urllib.request`)**

2. **SSL cert config?** Ruby has a commented-out `ca_file = OpenSSL::X509::DEFAULT_CERT_FILE` line. Python's `ssl.create_default_context()` handles system certs automatically. Leave it default. Port the comment if you want.

3. **`OpenCode` url bug?** Python's `OpenAI.url()` uses `self.BASE_URL` — correctly resolves through MRO. No workaround needed, unlike Ruby.
