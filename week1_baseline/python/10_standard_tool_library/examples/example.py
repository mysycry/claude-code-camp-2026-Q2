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

repl(
    working_dir=os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
)
