#!/usr/bin/env python3
"""Fail closed on proof placeholders or user-declared axioms in Lean sources."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

FORBIDDEN = re.compile(r"\b(sorry|admit|axiom|unsafe)\b")


def strip_comments_and_strings(text: str) -> str:
    out: list[str] = []
    i = 0
    block_depth = 0
    in_string = False
    escaped = False

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if block_depth:
            if ch == "/" and nxt == "-":
                block_depth += 1
                out.extend("  ")
                i += 2
                continue
            if ch == "-" and nxt == "/":
                block_depth -= 1
                out.extend("  ")
                i += 2
                continue
            out.append("\n" if ch == "\n" else " ")
            i += 1
            continue

        if in_string:
            if ch == "\n":
                out.append("\n")
            else:
                out.append(" ")
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if ch == "/" and nxt == "-":
            block_depth = 1
            out.extend("  ")
            i += 2
            continue
        if ch == "-" and nxt == "-":
            while i < len(text) and text[i] != "\n":
                out.append(" ")
                i += 1
            continue
        if ch == '"':
            in_string = True
            out.append(" ")
            i += 1
            continue

        out.append(ch)
        i += 1

    if block_depth:
        raise ValueError("unterminated block comment")
    if in_string:
        raise ValueError("unterminated string literal")
    return "".join(out)


def check_file(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8")
    stripped = strip_comments_and_strings(text)
    findings: list[str] = []
    for match in FORBIDDEN.finditer(stripped):
        line = stripped.count("\n", 0, match.start()) + 1
        findings.append(f"{path}:{line}: forbidden token {match.group(1)!r}")
    return findings


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path("Lean"))
    args = parser.parse_args()

    files = sorted(args.root.rglob("*.lean"))
    if not files:
        print(f"no Lean sources found under {args.root}")
        return 2

    findings: list[str] = []
    for path in files:
        try:
            findings.extend(check_file(path))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            findings.append(f"{path}: source scan failed: {exc}")

    if findings:
        for finding in findings:
            print(finding)
        return 1

    print(f"LEAN_SOURCE_PURITY_OK files={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
