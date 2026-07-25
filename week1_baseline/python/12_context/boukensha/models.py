TABLE = {
    "claude-opus-4-8": {"context_window": 200_000},
    "claude-sonnet-4-6": {"context_window": 200_000},
    "claude-haiku-4-5": {"context_window": 200_000},
}

DEFAULT_CONTEXT_WINDOW = 32_000


def context_window(model):
    entry = TABLE.get(str(model))
    if entry is not None:
        return entry["context_window"]
    return DEFAULT_CONTEXT_WINDOW
