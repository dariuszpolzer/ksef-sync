from datetime import datetime
from pathlib import Path
from typing import TextIO


def write_section(out: TextIO, content: str) -> None:
    content = (content or "").strip()
    if not content:
        return

    out.write(content)
    out.write("\n\n---\n\n")


def write_snapshot_header(
    out: TextIO,
    root: Path,
    files_count: int,
    skipped_dirs_count: int,
    skipped_files_count: int,
    total_lines: int,
) -> None:
    out.write("# PROJECT SNAPSHOT FOR AI\n\n")
    out.write(f"Generated: {datetime.now().isoformat(timespec='seconds')}\n")
    out.write(f"Root: {root.name}\n")
    out.write(f"Files included: {files_count}\n")
    out.write(f"Directories skipped: {skipped_dirs_count}\n")
    out.write(f"Files skipped: {skipped_files_count}\n")
    out.write(f"Total skipped paths: {skipped_dirs_count + skipped_files_count}\n")
    out.write(f"Total lines: {total_lines}\n\n")


def write_table_of_contents(out: TextIO) -> None:
    out.write("# TABLE OF CONTENTS\n\n")
    out.write("1. AI instructions\n")
    out.write("2. Current status\n")
    out.write("3. Project context\n")
    out.write("4. Project architecture\n")
    out.write("5. Pipeline architecture\n")
    out.write("6. Data flow\n")
    out.write("7. Security and sensitive data\n")
    out.write("8. Build and tooling context\n")
    out.write("9. Module dependencies\n")
    out.write("10. Module summaries\n")
    out.write("11. Domain objects and public symbols\n")
    out.write("12. File metadata\n")
    out.write("13. Project tree\n")
    out.write("14. Included and skipped files\n")
    out.write("15. File contents\n\n")
    out.write("---\n\n")
