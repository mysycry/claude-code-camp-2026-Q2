# Goal: Replace slow agentic room inspection with a deterministic survey pipeline

## Files

| File | What It Does |
|------|-------------|
| `week1_baseline/ruby/12_context/lib/boukensha/inspection/` | Deterministic `InspectRoom` implementation |
| Look candidates ONNX model | int8 BERT-medium exported to ONNX, runs from Ruby via ONNX Runtime |
| Model manifest | Threshold and metadata stored alongside the model |

## Key Architecture Decisions

- **Zero LLM calls per room**: The entire room inspection pipeline runs deterministically — no model calls for room surveying. The warm inspection path (poll → look → exits → consider → examine) is hardcoded.
- **Fixed inspection sequence**: poll (wait for MUD state to settle) → look (get room description) → exits (get destination names) → consider (assess mob difficulty) → examine (get details on interactable words).
- **Colour-based classification**: Mobs and objects are classified by their ANSI color codes in the MUD output — a fast, no-cost signal that doesn't require parsing.
- **BERT model for candidate prediction**: The look_candidates model (from Step 09) predicts which words in the room description are interactable. The survey pipeline passes these predictions to the `examine` command and cross-references the results.
- **Deduplication and retries**: Same entity isn't inspected twice. If a command produces no output, it's retried.

## Key Findings

- The TUI (terminal UI rendering) — not the model — was creating much of the observed 30-35 second latency. On slow terminals (e.g., WSL2), rendering each intermediate step in full took significant time.
- ONNX export with int8 quantization made the BERT model fast enough to run in-process during an agent turn without noticeable latency.
- Ruby/Python token and score parity was verified — the ONNX model produces identical results regardless of host language.

## Verification

```ruby
# Run InspectRoom on a MUD room, verify zero LLM calls
inspection = InspectRoom.call(connection: mud, room_id: "3001")
assert inspection.room_name == "The Temple Of Midgaard"
assert inspection.exits.any? { |e| e.direction == "south" }
```
