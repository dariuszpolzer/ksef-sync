from __future__ import annotations

import argparse
import re
import subprocess
import sys
from pathlib import Path

SECRET_PATTERNS = [
    ("private_key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    ("bearer_token", re.compile(r"\bBearer\s+[A-Za-z0-9._~+/=-]{16,}")),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{10,}\b")),
    (
        "secret_assignment",
        re.compile(
            r"(?i)\b(token|secret|password|passwd|api[_-]?key|ftp[_-]?password)\b\s*[:=]\s*['\"]?[^'\"\s]{8,}"
        ),
    ),
]

FORBIDDEN_NAMES = {".env", "config.json", "ftp-sync.json"}
FORBIDDEN_PARTS = {
    "data/batches",
    "data/downloads",
    "data/exports",
    "data/auth",
    "logs",
    "reports",
    "JPK/XML",
    "JPK/HTML",
}
FORBIDDEN_EXTENSIONS = {".xlsx", ".xls", ".csv"}
TEXT_EXTENSIONS = {".cmd", ".json", ".md", ".ps1", ".py", ".toml", ".txt", ".yaml", ".yml"}
ALLOWED_TRACKED_PREFIXES = {"tests/data/", "test_data/", "tests/fixtures/"}
ALLOWED_TRACKED_FILES = {"config.example.json", "ftp-sync.example.json"}


def run_git(args: list[str]) -> list[str]:
    result = subprocess.run(
        ["git", *args],
        text=True,
        encoding="utf-8",
        errors="replace",
        capture_output=True,
        check=True,
    )
    return [line for line in result.stdout.splitlines() if line]


def normalize(path: str) -> str:
    return path.replace("\\", "/")


def is_allowed_fixture(path: str) -> bool:
    path = normalize(path)
    return path in ALLOWED_TRACKED_FILES or any(
        path.startswith(prefix) for prefix in ALLOWED_TRACKED_PREFIXES
    )


def is_forbidden_tracked_path(path: str) -> str | None:
    normalized = normalize(path)
    name = Path(normalized).name

    if is_allowed_fixture(normalized):
        return None

    if name in FORBIDDEN_NAMES:
        return f"tracked private config: {name}"

    if Path(normalized).suffix.lower() == ".xml":
        return "tracked runtime XML"

    if Path(normalized).suffix.lower() in FORBIDDEN_EXTENSIONS:
        return "tracked report/data file"

    for part in FORBIDDEN_PARTS:
        if normalized == part or normalized.startswith(part + "/") or f"/{part}/" in normalized:
            return f"tracked runtime path: {part}"

    return None


def redact(value: str) -> str:
    value = re.sub(r"\b\d{10}\b", "***NIP***", value)
    value = re.sub(r"https?://[^\s\"')]+", "***URL***", value)
    value = re.sub(
        r"(?i)(token|secret|password|passwd|api[_-]?key)(\s*[:=]\s*)[^\s\"']+",
        r"\1\2***",
        value,
    )
    value = re.sub(r"\bBearer\s+[A-Za-z0-9._~+/=-]{8,}", "Bearer ***", value)
    return value


def scan_file(path: Path) -> list[str]:
    if path.suffix.lower() not in TEXT_EXTENSIONS:
        return []
    if not path.exists() or path.stat().st_size > 2_000_000:
        return []

    findings = []
    try:
        content = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return []

    for idx, line in enumerate(content.splitlines(), start=1):
        for name, pattern in SECRET_PATTERNS:
            if pattern.search(line):
                findings.append(f"{path}:{idx}: possible secret ({name})")
    return findings


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--redact", action="store_true", help="Maskuj NIP, tokeny i URL w wyniku.")
    args = parser.parse_args(argv)

    tracked = run_git(["ls-files"])
    findings = []

    for path in tracked:
        reason = is_forbidden_tracked_path(path)
        if reason:
            findings.append(f"{path}: {reason}")
        findings.extend(scan_file(Path(path)))

    if findings:
        print("SECURITY CHECK FAILED")
        for finding in findings:
            print(redact(finding) if args.redact else finding)
        return 1

    print("SECURITY CHECK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
