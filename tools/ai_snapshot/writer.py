from pathlib import Path

from tools.ai_snapshot.render import (
    write_section,
    write_snapshot_header,
    write_table_of_contents,
)
from tools.ai_snapshot.sections import build_sections


def write_snapshot(
    *,
    root: Path,
    output_path: Path,
    files: list[Path],
    skipped_dirs: list[str],
    skipped_files: list[tuple[Path, str | None]],
    total_lines: int,
    deps,
    secret_warnings,
    count_lines,
    make_tree,
    rel_posix,
    render_dependencies,
    render_domain_objects,
    render_file_metadata,
    render_module_summaries,
    render_secret_warnings,
    render_tooling_context,
    write_file_content,
):
    with output_path.open("w", encoding="utf-8") as out:
        write_snapshot_header(
            out=out,
            root=root,
            files_count=len(files),
            skipped_dirs_count=len(skipped_dirs),
            skipped_files_count=len(skipped_files),
            total_lines=total_lines,
        )

        write_table_of_contents(out)

        sections = build_sections(
            root=root,
            files=files,
            deps=deps,
            secret_warnings=secret_warnings,
            render_dependencies=render_dependencies,
            render_domain_objects=render_domain_objects,
            render_file_metadata=render_file_metadata,
            render_module_summaries=render_module_summaries,
            render_secret_warnings=render_secret_warnings,
            render_tooling_context=render_tooling_context,
        )

        for section in sections:
            write_section(out, section)

        out.write("# PROJECT TREE\n\n")
        out.write(make_tree(files))
        out.write("\n\n---\n\n")

        out.write("# INCLUDED FILES\n\n")
        for file in files:
            out.write(f"- {rel_posix(file)}\n")

        out.write("\n\n---\n\n")

        if skipped_dirs or skipped_files:
            out.write("# SKIPPED PATHS\n\n")

            for directory in skipped_dirs:
                out.write(f"- {directory} — ignored directory\n")

            for file, reason in skipped_files:
                out.write(f"- {rel_posix(file)} — {reason}\n")

            out.write("\n\n---\n\n")

        out.write("# FILE CONTENTS\n")

        for rel in files:
            write_file_content(out, root, rel)
