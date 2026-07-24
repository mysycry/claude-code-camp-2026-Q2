import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "BOUKENSHA_DIR" not in os.environ:
    repo_root = os.path.dirname(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
    )
    os.environ["BOUKENSHA_DIR"] = os.path.join(repo_root, ".boukensha")

from boukensha import repl, _get_config

cfg = _get_config()
print(f"Config: {cfg}")
print()

# --no-tui is handled by the bin script (sets BOUKENSHA_NO_TUI env var).
# Pass tui=False here since there's no Python TUI library installed.
repl(
    working_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
    tui=False,
)
