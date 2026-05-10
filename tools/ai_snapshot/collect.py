from pathlib import Path

import pathspec

from tools.ai_snapshot.config import (
    ALWAYS_IGNORE_DIRS,
    EXTRA_IGNORE_FILES,
    MAX_TEXT_FILE_SIZE,
    PRIORITY_FILES,
    SECRET_FILES,
    TEXT_EXTENSIONS,
    TEXT_FILENAMES,
)

MAX_NONPY_FILE_SIZE = 300_000


# TODO: przenieś ze snapshot.py:
# - is_text_file
# - should_ignore
# - load_gitignore
# - rel_posix
# - sort_files
# - collect_files
# - count_lines
# - make_tree
def is_text_file(path: Path) -> bool:
    if path.name in TEXT_FILENAMES:
        return True

    return path.suffix.lower() in TEXT_EXTENSIONS


def rel_posix(path: Path) -> str:
    return path.as_posix()


def read_text_safe(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def is_ignored_by_gitignore(rel: Path, spec) -> bool:
    if spec is None:
        return False

    return spec.match_file(rel_posix(rel))


def get_file_limit(path: Path) -> int:
    if path.suffix.lower() == ".py":
        return MAX_TEXT_FILE_SIZE

    return MAX_NONPY_FILE_SIZE


def should_skip_file(path: Path, rel: Path, spec, output_path: Path) -> tuple[bool, str | None]:
    try:
        if path.resolve() == output_path.resolve():
            return True, "output file"
    except OSError:
        return True, "unreadable"

    suffix = path.suffix.lower()

    if suffix == ".xsd":
        return True, "schema file"

    if suffix == ".xml":
        return True, "invoice/xml data file"

    if path.name in SECRET_FILES:
        return True, "secret/sensitive file"

    if path.name in EXTRA_IGNORE_FILES:
        return True, "extra ignored file"

    if is_ignored_by_gitignore(rel, spec):
        return True, ".gitignore"

    try:
        size = path.stat().st_size
    except OSError:
        return True, "unreadable"

    limit = get_file_limit(path)
    if size > limit:
        return True, f"too large: {size} bytes > {limit} bytes"

    if not is_text_file(path):
        return True, "binary file"

    return False, None


def load_gitignore(root: Path):
    gitignore = root / ".gitignore"
    if not gitignore.exists():
        return None

    patterns = read_text_safe(gitignore).splitlines()
    return pathspec.PathSpec.from_lines("gitwildmatch", patterns)


def sort_files(files: list[Path]) -> list[Path]:
    priority_index = {name: idx for idx, name in enumerate(PRIORITY_FILES)}

    def key(path: Path):
        rel = rel_posix(path)
        return (
            0 if rel in priority_index else 1,
            priority_index.get(rel, 9999),
            rel.lower(),
        )

    return sorted(files, key=key)


def collect_files(root: Path, spec, output_path: Path, include_exporter: bool):
    files: list[Path] = []
    skipped_files: list[tuple[Path, str | None]] = []
    skipped_dirs: set[str] = set()

    exporter_path = Path(__file__).resolve()

    def walk(directory: Path):
        try:
            children = sorted(directory.iterdir(), key=lambda p: p.name.lower())
        except OSError:
            skipped_dirs.add(rel_posix(directory.relative_to(root)) + "/")
            return

        for path in children:
            try:
                rel = path.relative_to(root)
                rel_str = rel_posix(rel)
            except ValueError:
                continue

            try:
                is_dir = path.is_dir()
                is_file = path.is_file()
            except OSError:
                skipped_files.append((rel, "unreadable"))
                continue

            if is_dir:
                if (
                    path.name in ALWAYS_IGNORE_DIRS
                    or path.name.endswith(".egg-info")
                    or path.name in {"__pypackages__"}
                ):
                    skipped_dirs.add(rel_str + "/")
                    continue

                if is_ignored_by_gitignore(rel, spec):
                    skipped_dirs.add(rel_str + "/")
                    continue

                walk(path)
                continue

            if not is_file:
                continue

            try:
                if not include_exporter and path.resolve() == exporter_path:
                    skipped_files.append((rel, "exporter script"))
                    continue
            except OSError:
                skipped_files.append((rel, "unreadable"))
                continue

            skip, reason = should_skip_file(path, rel, spec, output_path)
            if skip:
                skipped_files.append((rel, reason))
                continue

            files.append(rel)

    walk(root)

    return (
        sort_files(files),
        sorted(skipped_dirs),
        sorted(skipped_files, key=lambda x: rel_posix(x[0])),
    )


def count_lines(path: Path) -> int:
    try:
        return len(read_text_safe(path).splitlines())
    except OSError:
        return 0


def make_tree(files: list[Path]) -> str:
    lines = ["."]
    dirs: set[Path] = set()

    for file in files:
        for parent in file.parents:
            if str(parent) != ".":
                dirs.add(parent)

    all_paths = sorted(dirs | set(files), key=lambda p: rel_posix(p).lower())

    for path in all_paths:
        depth = len(path.parts) - 1
        prefix = "│   " * depth + "├── "
        suffix = "/" if path in dirs else ""
        lines.append(f"{prefix}{path.name}{suffix}")

    return "\n".join(lines)
