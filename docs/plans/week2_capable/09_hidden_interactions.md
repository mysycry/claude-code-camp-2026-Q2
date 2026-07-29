# Goal: Find a faster and cheaper way to detect hidden room interactions

## Files

| File | What It Does |
|------|-------------|
| Look candidates training pipeline | Extracts supervised training data from MUD world files (`.wld`, `.obj`, `.mob`) |
| BERT model artifacts | Trained int8 BERT-medium model for predicting interactable words in room descriptions |
| Evaluation pipeline | Frozen train/test splits, reachable-room filtering, model comparison framework |

## Key Architecture Decisions

- **Supervised learning from world files**: Training data was extracted from the MUD's parsed world files, which contain room descriptions and object/mob definitions. This provides ground truth for which words in a room description correspond to interactable objects.
- **Context-sensitive classification**: The same word can be interactive in one room but not another (e.g., "fountain" in Temple of Midgaard vs a generic fountain in a forest). The model uses the full room description as context, not just isolated words.
- **Multiple approaches compared**: Lexicon-based, hand-built features, BERT variants, Qwen, and Claude Haiku were benchmarked. A trained BERT-small model outperformed all LLM approaches for this task — cheaper (zero ongoing LLM cost), faster, and more accurate.

## Key Findings

- Context matters critically — the same word can be interactive in one room and decorative in another.
- Earlier evaluation had bugs: unreachable rooms in the training set (rooms the agent could never visit), data leakage (test data used during training), and incorrect model inputs.
- A trained local model (BERT) outperformed tested LLM approaches for this specific classification task.
- The BERT model output feeds into the deterministic survey pipeline (Step 10) — predicting candidate words for the `examine` command.

## Verification

```bash
# Run look_candidates model inference on a room description
# Verify predicted interactable words match actual MUD interaction results
```
