import argparse
import ast
import hashlib
import sys
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from tools.ai_snapshot.collect import (
    collect_files,
    count_lines,
    load_gitignore,
    make_tree,
    rel_posix,
)
from tools.ai_snapshot.config import (
    MAX_TEXT_FILE_SIZE,
    OUTPUT_NAME,
    SECRET_PATTERNS,
)
from tools.ai_snapshot.writer import write_snapshot

MAX_NONPY_FILE_SIZE = 300_000
CHUNK_SIZE_LINES = 900

MAX_NONPY_FILE_SIZE = 300_000
CHUNK_SIZE_LINES = 900


@dataclass(frozen=True)
class ImportRef:
    module: str
    level: int = 0
    name: str | None = None


@dataclass
class ModuleSummary:
    path: Path
    classes: list[str]
    functions: list[str]
    imports: list[str]
    line_count: int


def read_text_safe(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def is_probably_binary(path: Path) -> bool:
    try:
        chunk = path.read_bytes()[:2048]
    except OSError:
        return True

    return b"\0" in chunk


def is_ignored_by_gitignore(rel: Path, spec) -> bool:
    if spec is None:
        return False

    return spec.match_file(rel_posix(rel))


def file_sha256(path: Path) -> str:
    h = hashlib.sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 128), b""):
            h.update(chunk)

    return h.hexdigest()


def get_file_limit(path: Path) -> int:
    if path.suffix.lower() == ".py":
        return MAX_TEXT_FILE_SIZE
    return MAX_NONPY_FILE_SIZE


def module_name_from_path(file: Path) -> str:
    if file.name == "__init__.py":
        return file.parent.as_posix().replace("/", ".")
    return file.with_suffix("").as_posix().replace("/", ".")


def package_name_from_path(file: Path) -> str:
    parent = file.parent.as_posix().replace("/", ".")
    return "" if parent == "." else parent


def resolve_relative_import(file: Path, node: ast.ImportFrom) -> str | None:
    package = package_name_from_path(file)
    if not package and node.level > 0:
        return node.module

    parts = package.split(".") if package else []

    if node.level > 0:
        keep = max(len(parts) - node.level + 1, 0)
        base_parts = parts[:keep]
    else:
        base_parts = []

    if node.module:
        base_parts.append(node.module)

    result = ".".join(part for part in base_parts if part)
    return result or None


def parse_import_refs(file_path: Path, rel_path: Path | None = None) -> list[ImportRef]:
    try:
        source = read_text_safe(file_path)
        tree = ast.parse(source)
    except Exception:
        return []

    imports: list[ImportRef] = []

    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.append(ImportRef(module=alias.name, level=0))

        elif isinstance(node, ast.ImportFrom):
            if node.level > 0 and rel_path is not None:
                module = resolve_relative_import(rel_path, node)
            else:
                module = node.module

            if module:
                imports.append(ImportRef(module=module, level=node.level))

    return imports


def resolve_import_to_file(imported_module: str, module_map: dict[str, Path]) -> Path | None:
    current = imported_module

    while current:
        if current in module_map:
            return module_map[current]

        if "." not in current:
            break

        current = current.rsplit(".", 1)[0]

    return None


def build_dependency_map(root: Path, files: list[Path]) -> dict[Path, list[Path]]:
    module_map: dict[str, Path] = {}
    deps: dict[Path, list[Path]] = {}

    for file in files:
        if file.suffix != ".py":
            continue

        module = module_name_from_path(file)
        if module:
            module_map[module] = file

        if file.name == "__init__.py":
            package_name = file.parent.as_posix().replace("/", ".")
            if package_name != ".":
                module_map[package_name] = file

    for file in files:
        if file.suffix != ".py":
            continue

        found: set[Path] = set()

        for import_ref in parse_import_refs(root / file, file):
            module_path = resolve_import_to_file(import_ref.module, module_map)
            if module_path and module_path != file:
                found.add(module_path)

        deps[file] = sorted(found, key=rel_posix)

    return deps


def render_dependencies(deps: dict[Path, list[Path]]) -> str:
    lines = ["# MODULE DEPENDENCIES", ""]
    has_any = False

    for file, imports in sorted(deps.items(), key=lambda item: rel_posix(item[0])):
        visible_imports = [
            imported_file for imported_file in imports if imported_file.name != "__init__.py"
        ]

        if not visible_imports:
            continue

        has_any = True
        lines.append(rel_posix(file))

        for imported_file in visible_imports:
            lines.append(f"  └── {rel_posix(imported_file)}")

        lines.append("")

    if not has_any:
        lines.append("No internal Python module dependencies detected.")

    return "\n".join(lines)


def parse_module_summary(root: Path, file: Path) -> ModuleSummary | None:
    if file.suffix != ".py":
        return None

    full_path = root / file

    try:
        source = read_text_safe(full_path)
        tree = ast.parse(source)
    except Exception:
        return None

    classes: list[str] = []
    functions: list[str] = []

    for node in tree.body:
        if isinstance(node, ast.ClassDef):
            classes.append(node.name)
        elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            functions.append(node.name)

    imports = [ref.module for ref in parse_import_refs(full_path, file)]

    return ModuleSummary(
        path=file,
        classes=classes,
        functions=functions,
        imports=imports,
        line_count=len(source.splitlines()),
    )


def render_module_summaries(root: Path, files: list[Path]) -> str:
    lines = ["# MODULE SUMMARY", ""]
    summaries = [parse_module_summary(root, file) for file in files]
    summaries = [summary for summary in summaries if summary is not None]

    if not summaries:
        lines.append("No Python module summaries available.")
        return "\n".join(lines)

    for summary in summaries:
        lines.append(rel_posix(summary.path))
        lines.append(f"- lines: {summary.line_count}")
        lines.append(f"- classes: {', '.join(summary.classes) if summary.classes else '-'}")
        lines.append(f"- functions: {', '.join(summary.functions) if summary.functions else '-'}")
        lines.append(f"- imports: {', '.join(summary.imports) if summary.imports else '-'}")
        lines.append("")

    return "\n".join(lines)


def render_domain_objects(root: Path, files: list[Path]) -> str:
    lines = ["# DOMAIN OBJECTS / PUBLIC SYMBOLS", ""]
    found_any = False

    for file in files:
        if file.suffix != ".py":
            continue

        try:
            source = read_text_safe(root / file)
            tree = ast.parse(source)
        except Exception:
            continue

        symbols: list[str] = []

        for node in tree.body:
            if isinstance(node, ast.ClassDef) and not node.name.startswith("_"):
                symbols.append(f"class {node.name}")
            elif isinstance(
                node, (ast.FunctionDef, ast.AsyncFunctionDef)
            ) and not node.name.startswith("_"):
                symbols.append(f"def {node.name}()")

        if symbols:
            found_any = True
            lines.append(rel_posix(file))
            for symbol in symbols:
                lines.append(f"- {symbol}")
            lines.append("")

    if not found_any:
        lines.append("No public symbols detected.")

    return "\n".join(lines)


def file_metadata(root: Path, file: Path) -> dict[str, str | int | float]:
    full_path = root / file
    stat = full_path.stat()

    return {
        "path": rel_posix(file),
        "size": stat.st_size,
        "mtime": datetime.fromtimestamp(stat.st_mtime).isoformat(timespec="seconds"),
        "sha256": file_sha256(full_path),
        "lines": count_lines(full_path),
    }


def render_file_metadata(root: Path, files: list[Path]) -> str:
    lines = ["# FILE METADATA", ""]

    for file in files:
        try:
            meta = file_metadata(root, file)
        except OSError:
            lines.append(f"- {rel_posix(file)} — metadata unavailable")
            continue

        lines.append(f"- {meta['path']}")
        lines.append(f"  size: {meta['size']}")
        lines.append(f"  lines: {meta['lines']}")
        lines.append(f"  mtime: {meta['mtime']}")
        lines.append(f"  shF256: {meta['sha256']}")

    return "\n".join(lines)


def scan_text_for_secrets(text: str) -> list[str]:
    hits: list[str] = []

    for name, pattern in SECRET_PATTERNS:
        if pattern.search(text):
            hits.append(name)

    return sorted(set(hits))


def scan_files_for_secret_warnings(root: Path, files: list[Path]) -> dict[Path, list[str]]:
    warnings: dict[Path, list[str]] = {}

    for file in files:
        try:
            text = read_text_safe(root / file)
        except OSError:
            continue

        hits = scan_text_for_secrets(text)
        if hits:
            warnings[file] = hits

    return warnings


def render_secret_warnings(secret_warnings: dict[Path, list[str]]) -> str:
    lines = ["# SECRET / SENSITIVE DATA WARNINGS", ""]

    if not secret_warnings:
        lines.append("No obvious secret patterns detected in included files.")
        return "\n".join(lines)

    lines.append("Potential sensitive patterns detected. Review before sharing externally.")
    lines.append("")

    for file, warnings in sorted(secret_warnings.items(), key=lambda item: rel_posix(item[0])):
        lines.append(f"- {rel_posix(file)}: {', '.join(warnings)}")

    return "\n".join(lines)


def render_tooling_context(root: Path) -> str:
    lines = ["# BUILD / TOOLING CONTEXT", ""]

    for filename in [
        "pyproject.toml",
        "requirements.txt",
        "pytest.ini",
        ".bandit",
        "check.ps1",
        "fix.ps1",
    ]:
        path = root / filename
        if path.exists() and path.is_file():
            try:
                lines.append(f"## {filename}")
                lines.append("")
                content = read_text_safe(path).strip()
                if content:
                    lines.append(content)
                else:
                    lines.append("[EMPTY FILE]")
                lines.append("")
            except OSError:
                lines.append(f"## {filename}")
                lines.append("[Could not read file]")
                lines.append("")

    return "\n".join(lines)


def write_file_content(out, root: Path, rel: Path):
    full_path = root / rel
    rel_name = rel_posix(rel)

    out.write(f"\n\n===== FILE START: {rel_name} =====\n\n")

    try:
        content = read_text_safe(full_path)
    except OSError as error:
        out.write(f"[Could not read file: {error}]\n")
        out.write(f"\n===== FILE END: {rel_name} =====\n")
        return

    if not content.strip():
        out.write("[EMPTY FILE]\n")
        out.write(f"\n===== FILE END: {rel_name} =====\n")
        return

    lines = content.splitlines(keepends=True)

    if len(lines) <= CHUNK_SIZE_LINES:
        out.write(content)
        if not content.endswith("\n"):
            out.write("\n")
        out.write(f"\n===== FILE END: {rel_name} =====\n")
        return

    chunks = [lines[i : i + CHUNK_SIZE_LINES] for i in range(0, len(lines), CHUNK_SIZE_LINES)]

    for idx, chunk in enumerate(chunks, start=1):
        out.write(f"===== FILE CHUNK {idx}/{len(chunks)}: {rel_name} =====\n\n")
        out.write("".join(chunk))
        if chunk and not chunk[-1].endswith("\n"):
            out.write("\n")
        out.write("\n")

    out.write(f"===== FILE END: {rel_name} =====\n")


def main():
    parser = argparse.ArgumentParser(description="Export project snapshot for AI analysis.")

    parser.add_argument(
        "--root",
        default=".",
        help="Project root directory. Default: current directory.",
    )

    parser.add_argument(
        "--include-exporter",
        action="store_true",
        help="Include this export script in the snapshot.",
    )

    parser.add_argument(
        "--output",
        default=OUTPUT_NAME,
        help=f"Output file name. Default: {OUTPUT_NAME}",
    )

    args = parser.parse_args()

    root = Path(args.root).resolve()

    if not root.exists():
        print(f"Root nie istnieje: {root}")
        sys.exit(1)

    output_path = root / args.output
    spec = load_gitignore(root)

    files, skipped_dirs, skipped_files = collect_files(
        root=root,
        spec=spec,
        output_path=output_path,
        include_exporter=args.include_exporter,
    )

    write_snapshot(
        root=root,
        output_path=output_path,
        files=files,
        skipped_dirs=skipped_dirs,
        skipped_files=skipped_files,
        total_lines=sum(count_lines(root / file) for file in files),
        deps=build_dependency_map(root, files),
        secret_warnings=scan_files_for_secret_warnings(root, files),
        count_lines=count_lines,
        make_tree=make_tree,
        rel_posix=rel_posix,
        render_dependencies=render_dependencies,
        render_domain_objects=render_domain_objects,
        render_file_metadata=render_file_metadata,
        render_module_summaries=render_module_summaries,
        render_secret_warnings=render_secret_warnings,
        render_tooling_context=render_tooling_context,
        write_file_content=write_file_content,
    )

    print(f"Snapshot zapisany do: {output_path}")
    print(f"Plików dodanych: {len(files)}")
    print(f"Katalogów pominiętych: {len(skipped_dirs)}")
    print(f"Plików pominiętych: {len(skipped_files)}")
    print(f"Łącznie pominiętych ścieżek: {len(skipped_dirs) + len(skipped_files)}")


if __name__ == "__main__":
    main()
