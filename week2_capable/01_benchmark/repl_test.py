"""Launch Boukensha REPL with memory hooks + room inspection enabled."""
import os
import sys

root = os.path.join(os.path.dirname(__file__), os.pardir, os.pardir)
sys.path.insert(0, os.path.join(root, "week1_baseline", "python", "12_context"))
sys.path.insert(0, os.path.dirname(__file__))

from memory_hook import make_memory_hook
from boukensha import repl

memory_path = os.path.join(os.path.dirname(__file__), "memory_repl.db")
hooks = {"after_tool": make_memory_hook()}

repl(
    working_dir=os.getcwd(),
    mud=True,
    memory_path=memory_path,
    hooks=hooks,
    # To test Step 05 permissions, uncomment:
    # allow=["look", "move", {"check": {"kind": ["exits", "score"]}}],
)
