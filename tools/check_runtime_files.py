from __future__ import annotations

import sys

from security_check import is_forbidden_tracked_path, redact, run_git


def main() -> int:
    findings = []

    for path in run_git(["ls-files"]):
        reason = is_forbidden_tracked_path(path)
        if reason:
            findings.append(f"{path}: {reason}")

    if findings:
        print("RUNTIME FILE CHECK FAILED")
        for finding in findings:
            print(redact(finding))
        return 1

    print("RUNTIME FILE CHECK OK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
