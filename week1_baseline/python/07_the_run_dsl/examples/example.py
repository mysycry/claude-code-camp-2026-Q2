import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

if "BOUKENSHA_DIR" not in os.environ:
    repo_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))))
    os.environ["BOUKENSHA_DIR"] = os.path.join(repo_root, ".boukensha")

from boukensha import _get_config, run

config = _get_config()
base_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))

print("=== BOUKENSHA Step 7: The Boukensha.run DSL ===")
print()
print(f"Config: {config}")
print()

result = run(
    task="Read the README.md file and summarise what this MUD player assistant framework can do.",
    block=lambda dsl: [
        dsl.tool(
            "read_file",
            description="Read the contents of a file from disk",
            parameters={"path": {"type": "string", "description": "The file path to read"}},
            block=lambda path: open(os.path.normpath(os.path.join(base_dir, "..", "..", "ruby", "07_the_run_dsl", path))).read(),
        ),
        dsl.tool(
            "list_directory",
            description="List the files in a directory",
            parameters={"path": {"type": "string", "description": "The directory path to list"}},
            block=lambda path: ", ".join(f for f in os.listdir(os.path.normpath(os.path.join(base_dir, "..", "..", "ruby", "07_the_run_dsl", path))) if not f.startswith(".")),
        ),
    ],
)

print()
print("=== FINAL RESPONSE ===")
print(result)
