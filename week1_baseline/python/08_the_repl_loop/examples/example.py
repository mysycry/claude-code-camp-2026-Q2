import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "BOUKENSHA_DIR" not in os.environ:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    os.environ["BOUKENSHA_DIR"] = os.path.join(repo_root, ".boukensha")

from boukensha import _get_config, repl

config = _get_config()
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "ruby", "07_the_run_dsl"))

print("Config:", config)
print()

repl(block=lambda dsl: [
    dsl.tool(
        "read_file",
        description="Read the contents of a file from disk",
        parameters={"path": {"type": "string", "description": "File path (relative to the working directory)"}},
        block=lambda path: open(os.path.normpath(os.path.join(base_dir, path))).read(),
    ),
    dsl.tool(
        "list_directory",
        description="List the files in a directory",
        parameters={"path": {"type": "string", "description": "Directory path (relative to the working directory, or '.' for root)"}},
        block=lambda path: ", ".join(sorted(f for f in os.listdir(os.path.normpath(os.path.join(base_dir, path))) if not f.startswith("."))),
    ),
])
