#!/usr/bin/env python3
"""Check OPT catalog/document integrity without external dependencies."""

from __future__ import annotations

import re
from collections import Counter
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
ALLOWED_V2_STATUS_CATEGORIES = {
    "Verified",
    "Verified, environment-specific",
    "Implemented reference",
    "Implemented external reference",
    "Implemented external pattern",
    "Proposed / OPT synthesis",
    "Source candidate",
}
TEMPLATE_PLACEHOLDER_LINES = {
    "- Repository / publication / article:",
    "- Release/commit/PR/DOI/date:",
    "- Exact files/sections where applicable:",
    "- Licensing/provenance boundary where code reuse may matter:",
    "What dominates runtime, latency, memory, I/O, CI cost, quality budget or optimization-evaluation cost?",
    "State exactly what must remain unchanged: output bytes, theorem targets, assertions, API, numerical tolerance, ordering, statistical guarantee, evidence boundary, trust model, etc.",
    "If the optimization changes the contract (for example exact → approximate), state the new contract explicitly instead of claiming preservation.",
    "Describe the reusable mechanism, not only the source-project patch.",
    "If no controlled benchmark exists, say so explicitly.",
    "How was equivalence, correctness, bound soundness, approximation error or other contract compliance established?",
    "Which source constants, thresholds, worker counts, bit splits, cache keys, search budgets or tolerances must be re-profiled rather than copied?",
    "What can make this optimization invalid, slower, less robust or misleading?",
    "Define the measured or semantic condition that disables/reverts the optimization.",
}
LINK_RE = re.compile(r"\[([^\]]+)\]\((optimizations/[^)#]+\.md)\)")
ID_RE = re.compile(r"^# (OPT-[A-Z]+-\d{3}) — ")
FILENAME_ID_RE = re.compile(r"^(OPT-[A-Z]+-\d{3})-")
STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(.*?)\s*$")
OPT_TOKEN_RE = re.compile(r"\bOPT-[A-Z]+-\d{3}\b")
EMPTY_LABEL_RE = re.compile(r"^-\s+[^:]+:\s*$")
README_ROW_RE = re.compile(
    r"^\|\s*\[(OPT-[A-Z]+-\d{3})\]\((optimizations/[^)#]+\.md)\)"
    r"\s*\|[^|]*\|\s*([^|]+?)\s*\|",
    re.MULTILINE,
)
CANONICAL_DEFINITION_PATTERNS = {
    "X": re.compile(r"^- `X` — \S"),
    "F": re.compile(r"^- `F(?: ⊆ X)?` — \S"),
    "f": re.compile(r"^- `f(?:\s*:[^`]*)?` — \S"),
    "d": re.compile(r"^- `d` — \S"),
    "C": re.compile(r"^- `C` — \S"),
    "B": re.compile(r"^- `B` — \S"),
    "S": re.compile(r"^- `S` — \S"),
}


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


def section_has_content(lines: list[str]) -> bool:
    """Require record-specific visible content, not stock template prompts."""
    content = "\n".join(lines)
    content = re.sub(r"<!--.*?-->", "", content, flags=re.DOTALL)
    for raw in content.splitlines():
        line = raw.strip()
        if not line:
            continue
        if line in TEMPLATE_PLACEHOLDER_LINES:
            continue
        if EMPTY_LABEL_RE.match(line):
            continue
        return True
    return False


def normalized_status_category(raw: str) -> str:
    """Normalize light Markdown emphasis, then return the category before ';'."""
    plain = re.sub(r"[*_`]", "", raw).strip()
    return plain.split(";", 1)[0].strip()


records: dict[str, Path] = {}
status_categories: dict[str, str] = {}
for path in sorted(OPT_DIR.glob("OPT-*.md")):
    text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    first = lines[0] if lines else ""
    match = ID_RE.match(first)
    if not match:
        die(f"bad record heading: {path.relative_to(ROOT)}")
    record_id = match.group(1)

    filename_match = FILENAME_ID_RE.match(path.name)
    if not filename_match:
        die(f"record filename does not begin with an OPT ID: {path.relative_to(ROOT)}")
    filename_id = filename_match.group(1)
    if filename_id != record_id:
        die(
            f"record ID mismatch: {path.relative_to(ROOT)} declares {record_id} "
            f"but filename encodes {filename_id}"
        )

    if record_id in records:
        die(f"duplicate record id {record_id}: {records[record_id]} and {path}")
    records[record_id] = path

    status_matches = [STATUS_RE.match(line) for line in lines]
    statuses = [m.group(1).strip() for m in status_matches if m is not None]
    if len(statuses) != 1:
        die(f"{path.relative_to(ROOT)} must contain exactly one Status line")
    if not statuses[0]:
        die(f"{path.relative_to(ROOT)} has empty Status")

    if record_id not in FROZEN_V1:
        status_category = statuses[0].split(";", 1)[0].strip()
        if status_category not in ALLOWED_V2_STATUS_CATEGORIES:
            die(
                f"{path.relative_to(ROOT)} uses undefined status category "
                f"'{status_category}'"
            )
        status_categories[record_id] = status_category

        headings = {line for line in lines if line.startswith("## ")}
        missing = sorted(REQUIRED_V2 - headings)
        if missing:
            die(f"{path.relative_to(ROOT)} missing sections: {', '.join(missing)}")

        for heading in sorted(REQUIRED_V2):
            if not section_has_content(section_lines(text, heading)):
                die(
                    f"{path.relative_to(ROOT)} has empty/template-only mandatory section {heading}"
                )

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

record_paths = {str(path.relative_to(ROOT)): record_id for record_id, path in records.items()}

# README is the complete human-facing record index. CATALOG may use either
# links or plain/backticked IDs, but any optimization-record link in either
# document must use the target record's stable ID as its label.
for doc_name in ("README.md", "CATALOG.md"):
    text = (ROOT / doc_name).read_text(encoding="utf-8")
    links = LINK_RE.findall(text)
    linked_ids: list[str] = []
    for label, rel in links:
        target = ROOT / rel
        if not target.is_file():
            die(f"broken record link in {doc_name}: {rel}")
        target_id = record_paths.get(rel)
        if target_id is None:
            die(f"record link in {doc_name} is not a discovered OPT record: {rel}")
        if label.strip() != target_id:
            die(
                f"record link label mismatch in {doc_name}: '{label}' points to "
                f"{target_id} ({rel})"
            )
        linked_ids.append(target_id)

    if doc_name == "README.md":
        counts = Counter(linked_ids)
        duplicates = sorted(record_id for record_id, count in counts.items() if count != 1)
        if duplicates:
            die(f"README.md must index each record exactly once; bad counts for: {', '.join(duplicates)}")
        missing_readme = sorted(records.keys() - counts.keys())
        if missing_readme:
            die(f"README.md is missing record(s): {', '.join(missing_readme)}")

        row_statuses: dict[str, str] = {}
        for row_id, rel, raw_status in README_ROW_RE.findall(text):
            if record_paths.get(rel) != row_id:
                die(f"README.md row identity mismatch for {row_id}: {rel}")
            if row_id in row_statuses:
                die(f"README.md has duplicate status row for {row_id}")
            row_statuses[row_id] = normalized_status_category(raw_status)

        for record_id, expected_status in status_categories.items():
            observed_status = row_statuses.get(record_id)
            if observed_status is None:
                die(f"README.md has no catalog status cell for post-v1 record {record_id}")
            if observed_status != expected_status:
                die(
                    f"README.md status mismatch for {record_id}: "
                    f"record='{expected_status}' README='{observed_status}'"
                )

catalog = (ROOT / "CATALOG.md").read_text(encoding="utf-8")
catalog_ids = set(OPT_TOKEN_RE.findall(catalog))
unknown_catalog_ids = sorted(catalog_ids - records.keys())
if unknown_catalog_ids:
    die(f"CATALOG.md references unknown record ID(s): {', '.join(unknown_catalog_ids)}")
for record_id, path in records.items():
    if record_id not in catalog_ids:
        die(f"{record_id} ({path.name}) is not mentioned in CATALOG.md")

problem_contract = ROOT / "OPTIMIZATION-PROBLEM.md"
if not problem_contract.is_file():
    die("OPTIMIZATION-PROBLEM.md is missing")
problem_text = problem_contract.read_text(encoding="utf-8")
problem_lines = problem_text.splitlines()
if not problem_lines or problem_lines[0] != "# Optimization Problem Contract":
    die("OPTIMIZATION-PROBLEM.md has missing/invalid title")
if "## Canonical contract" not in problem_lines:
    die("OPTIMIZATION-PROBLEM.md is missing ## Canonical contract")
canonical = section_lines(problem_text, "## Canonical contract")
canonical_text = "\n".join(canonical)
if "P = (X, F, f, d, C, B, S)" not in canonical_text:
    die("OPTIMIZATION-PROBLEM.md is missing canonical P = (X, F, f, d, C, B, S) formula")
for field, pattern in CANONICAL_DEFINITION_PATTERNS.items():
    if not any(pattern.match(line) for line in canonical):
        die(f"OPTIMIZATION-PROBLEM.md is missing canonical definition for {field}")

print(f"CATALOG_INTEGRITY_OK records={len(records)} frozen_v1={len(FROZEN_V1)}")
