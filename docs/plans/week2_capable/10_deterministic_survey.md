# Goal: Replace slow agentic room inspection with a deterministic survey pipeline

- Shipped an int8 BERT-medium model for look_candidates.
- Exported the model to ONNX and ran it directly from Ruby.
- Verified Ruby/Python token and score parity.
- Stored the model threshold and metadata in a manifest.
- Added model download, verification, and status tasks.
- Replaced the Room Inspector subagent with one deterministic InspectRoom implementation.
- Added fixed poll, look, exits, consider, and examine sequencing.
- Added colour-based mob/object classification, deduplication, keyword verification, and retries.
- Reduced the warm inspection path to zero LLM calls.
- Confirmed the TUI-not the model-was creating much of the observed latency.
