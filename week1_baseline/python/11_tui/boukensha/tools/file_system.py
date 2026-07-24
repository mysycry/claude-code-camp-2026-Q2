import glob as glob_module
import os
import re
from pathlib import Path


class FileSystem:
    @classmethod
    def register(cls, registry, working_dir):
        root = os.path.abspath(working_dir)

        def resolve(path):
            absolute = os.path.normpath(os.path.join(root, str(path)))
            if absolute == root or absolute.startswith(root + os.sep):
                return absolute
            return f"error: path '{path}' escapes the working directory"

        def oops(msg):
            return f"error: {msg}"

        registry.tool(
            "pwd",
            description="Return the working directory — the root that all file paths are relative to.",
            parameters={},
            block=lambda: root,
        )

        registry.tool(
            "list_directory",
            description="List files and subdirectories at a path relative to the working directory. Defaults to the working directory itself.",
            parameters={"path": {"type": "string", "description": "Relative path to list (default '.')"}},
            block=lambda path=".": _list_directory(path, root, resolve, oops),
        )

        registry.tool(
            "read_file",
            description="Read and return the full contents of a file. Path is relative to the working directory.",
            parameters={"path": {"type": "string", "description": "Relative path to the file"}},
            block=lambda path: _read_file(path, resolve, oops),
        )

        registry.tool(
            "write_file",
            description="Write content to a file, creating it (and any missing parent directories) if needed, overwriting if it exists. Path is relative to the working directory.",
            parameters={
                "path": {"type": "string", "description": "Relative path to the file"},
                "content": {"type": "string", "description": "Text content to write"},
            },
            block=lambda path, content: _write_file(path, content, root, resolve, oops),
        )

        registry.tool(
            "delete_file",
            description="Delete a file. Directories are not deleted. Path is relative to the working directory.",
            parameters={"path": {"type": "string", "description": "Relative path to the file to delete"}},
            block=lambda path: _delete_file(path, resolve, oops),
        )

        registry.tool(
            "search_files",
            description="Search for a text pattern (literal string or regex) across all files in the working directory tree. Returns matching lines in 'path:line_number:content' format.",
            parameters={
                "pattern": {"type": "string", "description": "The text or regex pattern to search for"},
                "path": {"type": "string", "description": "Subdirectory or file to search within (default '.' = entire working directory)"},
                "glob": {"type": "string", "description": "File glob to restrict which files are searched, e.g. '*.py' (default '*')"},
            },
            block=lambda pattern, path=".", glob="*": _search_files(pattern, path, glob, root, resolve, oops),
        )


def _list_directory(path, root, resolve, oops):
    target = resolve(path)
    if target.startswith("error:"):
        return target
    if not os.path.isdir(target):
        return oops(f"'{path}' is not a directory")

    entries = sorted(os.listdir(target))
    result = []
    for name in entries:
        full = os.path.join(target, name)
        result.append(f"{name}/" if os.path.isdir(full) else name)
    return "(empty)" if not result else "\n".join(result)


def _read_file(path, resolve, oops):
    target = resolve(path)
    if target.startswith("error:"):
        return target
    if not os.path.isfile(target):
        return oops(f"'{path}' is not a file")
    try:
        return Path(target).read_text(encoding="utf-8", errors="replace")
    except Exception as e:
        return oops(str(e))


def _write_file(path, content, root, resolve, oops):
    target = resolve(path)
    if target.startswith("error:"):
        return target
    try:
        os.makedirs(os.path.dirname(target), exist_ok=True)
        Path(target).write_text(str(content), encoding="utf-8")
        rel = os.path.relpath(target, root)
        return f"ok: wrote {len(content.encode('utf-8'))} bytes to {rel}"
    except Exception as e:
        return oops(str(e))


def _delete_file(path, resolve, oops):
    target = resolve(path)
    if target.startswith("error:"):
        return target
    if not os.path.isfile(target):
        return oops(f"'{path}' is not a file")
    try:
        os.remove(target)
        return f"ok: deleted {path}"
    except Exception as e:
        return oops(str(e))


def _search_files(pattern, path, glob_pattern, root, resolve, oops):
    target = resolve(path)
    if target.startswith("error:"):
        return target

    try:
        regex = re.compile(pattern)
    except re.error as e:
        return oops(f"invalid pattern: {e}")

    search_root = os.path.dirname(target) if os.path.isfile(target) else target

    if os.path.isfile(target):
        file_iter = [target]
    else:
        file_iter = glob_module.glob(os.path.join(target, "**", glob_pattern), recursive=True)
        file_iter = sorted(file_iter)

    matches = []
    for filepath in file_iter:
        if not os.path.isfile(filepath):
            continue
        rel = os.path.relpath(filepath, root)
        try:
            with open(filepath, encoding="utf-8", errors="replace") as f:
                for lineno, line in enumerate(f, 1):
                    if regex.search(line.rstrip("\n")):
                        matches.append(f"{rel}:{lineno}:{line.rstrip()}")
        except Exception as e:
            matches.append(f"{rel}: error reading file: {e}")

    return "no matches" if not matches else "\n".join(matches)
