import warnings


class Tui:
    def __init__(self, repl):
        self._repl = repl

    def start(self):
        warnings.warn(
            "TUI not available: charm-ruby is a Go native extension with no "
            "Python equivalent. Falling back to plain REPL.",
            stacklevel=2,
        )
        self._repl.start()
