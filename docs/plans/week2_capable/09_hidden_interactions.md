# Goal: Find a faster and cheaper way to detect hidden room interactions

- Extracted supervised training data from the MUD's world files.
- Built frozen train/test splits and reachable-room filtering.
- Compared lexicons, hand-built features, BERT variants, Qwen, and Haiku.
- Discovered that context matters because the same word can be interactive in one room but not another.
- Found and corrected evaluation problems involving unreachable rooms, data leakage, and model inputs.
- Determined that a trained local model outperformed the tested LLM approaches for this task.
- Built a reproducible model-training and evaluation pipeline.
- Documented the dataset, experiments, results, and model design.
