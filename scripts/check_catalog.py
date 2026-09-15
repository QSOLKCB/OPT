#!/usr/bin/env python3
"""Check OPT catalog/document integrity without external dependencies."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
OPT_DIR = ROOT / "optimizations"
FROZEN_V1 = {
    "OPT-PY-001",
    "OPT-INV-001",
    "OPT-LEAN-001",
    "OPT-PAR-001",
    "OPT-DSP-001",
}
REQUIRED_V2 = {
    "## Source evidence",
    "## Problem",
    "## Optimization problem contract",
    "## Preserved contract",
    "## Optimization",
    "## Before / after evidence",
    "## Validation",
    "## Target-repo adaptation",
    "## Failure modes",
    "## Rollback trigger",
}
REQUIRED_CONTRACT_FIELDS = ("X", "F", "f", "d", "C", "B", "S")
LINK_RE = re.compile(r"\[[^\]]+\]\((optimizations/[^)#]+\.md)\)")
ID_RE = re.compile(r"^# (OPT-[A-Z]+-\d{3}) — ")


def die(msg: str) -> None:
    raise SystemExit(f"catalog-integrity: {msg}")


def section_lines(text: str, heading: str) -> list[str]:
    """Return lines belonging to one exact level-2 Markdown section."""
    lines = text.splitlines()
    try:
        start = lines.index(heading) + 1
    except ValueError:
        return []
    end = len(lines)
    for i in range(start, len(lines)):
        if lines[i].startswith("## "):
            end = i
            break
    return lines[start:end]


records: dict[str, Path] = {}
for path in sorted(OPT_DIR.glob("OPT-*.md")):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    first = lines[0] if lines else ""
    match = ID_RE.match(first)
    if not match:
        die(f"bad record heading: {path.relative_to(ROOT)}")
    record_id = match.group(1)
    if record_id in records:
        die(f"duplicate record id {record_id}: {records[record_id]} and {path}")
    records[record_id] = path
    if "**Status:**" not in text:
        die(f"missing Status in {path.relative_to(ROOT)}")

    if record_id not in FROZEN_V1:
        headings = {line for line in lines if line.startswith("## ")}
        missing = sorted(REQUIRED_V2 - headings)
        if missing:
            die(f"{path.relative_to(ROOT)} missing sections: {', '.join(missing)}")

        contract = section_lines(text, "## Optimization problem contract")
        for field in REQUIRED_CONTRACT_FIELDS:
            prefix = f"- {field}:"
            matches = [line for line in contract if line.startswith(prefix)]
            if len(matches) != 1:
                die(
                    f"{path.relative_to(ROOT)} must contain exactly one contract field "
                    f"'{prefix}' in ## Optimization problem contract"
                )
            if not matches[0][len(prefix) :].strip():
                die(f"{path.relative_to(ROOT)} has empty contract field {field}")

missing_frozen = sorted(FROZEN_V1 - records.keys())
if missing_frozen:
    die(f"frozen v1 record(s) missing: {', '.join(missing_frozen)}")

# README is the human-facing record index and must contain real Markdown links.
# CATALOG may use either links or plain/backticked record IDs; any links it does
# contain are still validated below, while complete catalog coverage is enforced
# independently by record ID.
for doc_name in ("README.md", "CATALOG.md"):
    text = (ROOT / doc_name).read_text(encoding="utf-8")
    links = LINK_RE.findall(text)
    if doc_name == "README.md" and not links:
        die("README.md contains no optimization-record links")
    for rel in links:
        if not (ROOT / rel).is_file():
            die(f"broken record link in {doc_name}: {rel}")

catalog = (ROOT / "CATALOG.md").read_text(encoding="utf-8")
for record_id, path in records.items():
    if record_id not in catalog:
        die(f"{record_id} ({path.name}) is not mentioned in CATALOG.md")

problem_contract = ROOT / "OPTIMIZATION-PROBLEM.md"
if not problem_contract.is_file():
    die("OPTIMIZATION-PROBLEM.md is missing")

print(f"CATALOG_INTEGRITY_OK records={len(records)} frozen_v1={len(FROZEN_V1)}")
