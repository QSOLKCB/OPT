#!/usr/bin/env python3
"""Normalize supported CommonMark syntax, then run the hardened catalog checker.

The core checker intentionally stays strict and source-oriented. This front end creates a
scratch copy, canonicalizes two rendering-equivalent forms that the core otherwise rejects
or overlooks, and runs the core against that copy:

* one-to-three spaces before ATX headings (valid CommonMark indentation), and
* optional Markdown titles on links to optimization-record Markdown files.

The repository working tree is never modified by this normalization step.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_NAME = "check_catalog_core.py"
ATX_INDENT_RE = re.compile(r"(?m)^ {1,3}(?=#{1,6}(?:[ \t]|$))")
RECORD_LINK_START_RE = re.compile(
    r"\[([^\]\r\n]+)\]\((optimizations/[^\s)#]+\.md)"
)


def _skip_whitespace(text: str, index: int) -> int:
    while index < len(text) and text[index] in " \t\r\n":
        index += 1
    return index


def _parse_title(text: str, index: int) -> int | None:
    """Return the index after a valid optional link title, before outer whitespace."""
    if index >= len(text) or text[index] not in ('"', "'", "("):
        return None
    opener = text[index]
    closer = ")" if opener == "(" else opener
    index += 1
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            index += 2
            continue
        if char == closer:
            return index + 1
        index += 1
    return None


def canonicalize_record_link_titles(text: str) -> str:
    """Drop only syntactically complete optional titles from OPT-record links."""
    out: list[str] = []
    cursor = 0
    search_from = 0

    while True:
        match = RECORD_LINK_START_RE.search(text, search_from)
        if match is None:
            out.append(text[cursor:])
            break

        after_destination = match.end()
        if after_destination >= len(text) or text[after_destination] == ")":
            search_from = after_destination
            continue
        if text[after_destination] not in " \t\r\n":
            search_from = after_destination
            continue

        title_start = _skip_whitespace(text, after_destination)
        title_end = _parse_title(text, title_start)
        if title_end is None:
            search_from = after_destination
            continue
        outer_close = _skip_whitespace(text, title_end)
        if outer_close >= len(text) or text[outer_close] != ")":
            search_from = after_destination
            continue

        out.append(text[cursor:match.start()])
        out.append(f"[{match.group(1)}]({match.group(2)})")
        cursor = outer_close + 1
        search_from = cursor

    return "".join(out)


def canonicalize_markdown(text: str) -> str:
    text = ATX_INDENT_RE.sub("", text)
    return canonicalize_record_link_titles(text)


def markdown_inputs(root: Path) -> list[Path]:
    paths = [
        root / "README.md",
        root / "CATALOG.md",
        root / "OPTIMIZATION-PROBLEM.md",
    ]
    paths.extend(sorted((root / "optimizations").glob("*.md")))
    return [path for path in paths if path.is_file()]


def main() -> int:
    with tempfile.TemporaryDirectory(prefix="opt-catalog-integrity-") as temp_dir:
        scratch = Path(temp_dir) / "repo"
        shutil.copytree(
            ROOT,
            scratch,
            symlinks=True,
            ignore=shutil.ignore_patterns(".git", "__pycache__"),
        )

        for path in markdown_inputs(scratch):
            original = path.read_text(encoding="utf-8")
            normalized = canonicalize_markdown(original)
            if normalized != original:
                path.write_text(normalized, encoding="utf-8")

        core = scratch / "scripts" / CORE_NAME
        if not core.is_file():
            raise SystemExit(f"catalog-integrity: missing hardened core checker: {CORE_NAME}")

        completed = subprocess.run([sys.executable, str(core)], cwd=scratch, check=False)
        return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
