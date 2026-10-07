#!/usr/bin/env python3
"""Verify a file against an expected SHA-256 digest."""

import hashlib
import sys
from pathlib import Path


def main() -> None:
    if len(sys.argv) != 3:
        raise SystemExit(f"Usage: {Path(sys.argv[0]).name} <file> <expected-sha256>")

    file_path = Path(sys.argv[1])
    expected = sys.argv[2].lower()
    actual = hashlib.sha256(file_path.read_bytes()).hexdigest()
    if actual != expected:
        raise SystemExit(
            f"SHA-256 mismatch for {file_path}: expected {expected}, got {actual}"
        )


if __name__ == "__main__":
    main()
