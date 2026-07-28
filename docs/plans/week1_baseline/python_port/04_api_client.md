# Python Port Plan: Step 04 — The API Client

**Starting point:** copy `python/03_prompt_builder/` → `python/04_api_client/`.
Then add the `Client` class that POSTs the payload assembled by `PromptBuilder`, handles retries, and returns parsed JSON.

---

## What's New in Ruby Step 04

| Ruby Source | Python Target | What It Does |
|---|---|---|
| `lib/boukensha/client.rb` (new) | `boukensha/client.py` (CREATE) | `Client` — HTTP POST via urllib, retry with backoff, `ApiError` |
| `lib/boukensha/errors.rb` | `boukensha/errors.py` (UPDATE) | Add `ApiError(Exception)` |
| `lib/boukensha.rb` (line 15) | `boukensha/__init__.py` (UPDATE) | Import `Client`, add `ApiError` |
| `lib/boukensha/tasks/base.rb` (private `fetch`) | `boukensha/tasks/base.py` (UPDATE) | Add nil guard: `return None unless isinstance(settings, dict)` |
| `prompts/system.md` | `boukensha/prompts/system.md` (OVERWRITE) | "Boukensha, autonomous player exploring a CircleMUD world" |
| `examples/example.rb` | `examples/example.py` (OVERWRITE) | `read_file`/`list_directory` tools, `Client.call` |

## What Stays the Same (Copied from Step 03)

`config.py`, `context.py`, `message.py`, `tool.py`, `registry.py`, `prompt_builder.py`, `pyproject.toml`, `tasks/player.py`, all `backends/` — no changes.

---

## Ruby `Client` → Python Mapping

| Ruby | Python |
|---|---|
| `Net::HTTP` | `urllib.request` (stdlib) |
| `Net::HTTP::Post.new(uri, headers)` | `urllib.request.Request(url, data, headers, method="POST")` |
| `http.use_ssl = uri.scheme == "https"` | Auto-detected by `urlopen` when scheme is `https` |
| `OpenSSL::SSL::VERIFY_PEER` | `ssl.create_default_context()` |
| `rescue *TRANSIENT_ERRORS` | `except tuple(TRANSIENT_ERRORS)` |
| `sleep retry_delay(attempt)` | `time.sleep(delay)` |
| `JSON.parse(response.body)` | `json.loads(resp.read().decode("utf-8"))` |

### Transient errors mapping

| Ruby Exception | Python Equivalent |
|---|---|
| `EOFError` | `ConnectionError` |
| `Errno::ECONNRESET` | `ConnectionResetError` (subclass of `ConnectionError`) |
| `Errno::ECONNREFUSED` | `ConnectionRefusedError` (subclass of `ConnectionError`) |
| `Net::OpenTimeout` | `TimeoutError` |
| `Net::ReadTimeout` | `TimeoutError` |
| `OpenSSL::SSL::SSLError` | `ssl.SSLError` |
| `SocketError` | `OSError` (socket.error is OSError in Python 3) |
| `Timeout::Error` | `TimeoutError` |

Also need `urllib.error.HTTPError` handled separately (raised by `urlopen` for non-2xx status).

## Retry Logic (Porting Recipe)

```ruby
loop do
  attempts += 1
  begin
    response = http.request(request)
  rescue *TRANSIENT_ERRORS => e
    raise ApiError if attempts > MAX_RETRIES
    sleep retry_delay(attempts)
    next
  end
  if retryable_response?(response) && attempts <= MAX_RETRIES
    sleep retry_delay(attempts)
    next
  end
  break
end
unless response.is_a?(Net::HTTPSuccess)
  raise ApiError
end
JSON.parse(response.body)
```

Python equivalent:
- `HTTPError` caught before other transient errors (because it has `.code` for status-based retry)
- Transient network errors caught as a tuple
- After loop, non-2xx status raises `ApiError`

---

## Files to Create / Modify

| Action | File |
|---|---|
| CREATE | `boukensha/client.py` |
| UPDATE | `boukensha/errors.py` — add `ApiError` |
| UPDATE | `boukensha/__init__.py` — add `Client`, `ApiError` |
| UPDATE | `boukensha/tasks/base.py` — nil guard in `_fetch` |
| OVERWRITE | `examples/example.py` — `read_file`/`list_directory`, `Client.call` |
| OVERWRITE | `boukensha/prompts/system.md` — new system prompt |

## Questions

1. **User-Agent header** — Ruby's `net/http` defaults to `"Ruby"` which is typically allowed. Python's `urllib.request` defaults to `"Python-urllib/3.x"` which OpenCode blocks with 403. Should we set a custom User-Agent like `"boukensha/0.1.0"` in the Client? It's cleaner to set it per-backend (each backend's `headers()` already includes `Content-Type`), but the User-Agent should be set at the Client level or in each backend.
   - Decision: Set `User-Agent: boukensha/0.1.0` in each backend's `headers()` dict since that's where HTTP headers are defined. Or set it in the Client itself as a fallback. **Set in the Client's `call()` method as a default header** — overridable by backend headers.

2. **`config.rb` PROMPTS_DIR path change** — Ruby 04 changed `PROMPTS_DIR` from `../../prompts` to `../../../prompts` relative to `config.rb`. This is a Ruby-specific path quirk. Python's `PROMPTS_DIR = Path(__file__).resolve().parent / "prompts"` already resolves to `boukensha/prompts/` inside the package, which is correct for both steps. **No action needed.**
