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
REQUIRED_CLASSIFICATION_FIELDS = (
    "Variables",
    "Search scope",
    "Objective behavior",
    "Information",
    "Evaluation cost",
    "Constraints",
    "Parallelism",
    "Exactness",
)
CLASSIFICATION_TEMPLATE_VALUES = {
    "Variables": "continuous / integer / categorical / conditional / mixed",
    "Search scope": "local / global",
    "Objective behavior": "deterministic / noisy / stochastic",
    "Information": "gradient / derivative-free / black-box",
    "Evaluation cost": "cheap / moderate / expensive",
    "Constraints": "bounds / equality / inequality / semantic / resource",
    "Parallelism": "sequential / synchronous batch / asynchronous",
    "Exactness": "exact / approximation permitted under explicit error contract",
}
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
RECORD_LINK_CELL_RE = re.compile(
    r"^\[(OPT-[A-Z]+-\d{3})\]\((optimizations/[^)#]+\.md)\)$"
)
ID_RE = re.compile(r"^# (OPT-[A-Z]+-\d{3}) — ")
FILENAME_ID_RE = re.compile(r"^(OPT-[A-Z]+-\d{3})-")
STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(.*?)\s*$")
OPT_TOKEN_RE = re.compile(r"\bOPT-[A-Z]+-\d{3}\b")
EMPTY_LABEL_RE = re.compile(r"^-\s+[^:]+:\s*$")
HEADING_RE = re.compile(r"^#{1,6}(?:\s|$)")
THEMATIC_BREAK_RE = re.compile(
    r"^(?:\*(?:[ \t]*\*){2,}|-(?:[ \t]*-){2,}|_(?:[ \t]*_){2,})[ \t]*$"
)
LIST_MARKER_ONLY_RE = re.compile(r"^(?:[-+*]|\d+[.)])$")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
RAW_HTML_TYPE1_OPEN_RE = re.compile(
    r"^ {0,3}<(?P<tag>script|pre|style|textarea)(?:[ \t]|>|$)", re.IGNORECASE
)
RAW_HTML_DECLARATION_OPEN_RE = re.compile(r"^ {0,3}<![A-Z]", re.IGNORECASE)
RAW_HTML_BLOCK_TAG_RE = re.compile(
    r"^ {0,3}</?(?:address|article|aside|base|basefont|blockquote|body|caption|center|col|colgroup|dd|details|dialog|dir|div|dl|dt|fieldset|figcaption|figure|footer|form|frame|frameset|h[1-6]|head|header|hr|html|iframe|legend|li|link|main|menu|menuitem|nav|noframes|ol|optgroup|option|p|param|search|section|summary|table|tbody|td|tfoot|th|thead|title|tr|track|ul)(?:[ \t\n/>]|$)",
    re.IGNORECASE,
)
RAW_HTML_COMPLETE_TAG_RE = re.compile(
    r"^ {0,3}</?[A-Za-z][A-Za-z0-9-]*(?:[ \t]+[^<>]*)?/?>[ \t]*$"
)
EMPHASIS_WRAPPERS = ("**", "__", "~~", "*", "_")
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


def strip_html_comments_from_visible_line(
    raw: str, in_comment: bool
) -> tuple[str, bool]:
    """Remove HTML comments from a non-fenced line, carrying unmatched state."""
    out: list[str] = []
    cursor = 0

    if in_comment:
        end = raw.find("-->")
        if end < 0:
            return "", True
        cursor = end + 3
        in_comment = False

    while cursor < len(raw):
        start = raw.find("<!--", cursor)
        if start < 0:
            out.append(raw[cursor:])
            break
        out.append(raw[cursor:start])
        end = raw.find("-->", start + 4)
        if end < 0:
            in_comment = True
            break
        cursor = end + 3

    return "".join(out), in_comment


def raw_html_block_start(raw: str) -> tuple[str, str | None] | None:
    """Return a raw-HTML block mode for CommonMark-style block starts.

    Markdown inside a raw HTML block is not parsed as Markdown, so it must not
    satisfy schema headings or fields. Modes are: tag (until matching close),
    token (until literal terminator), and blank (until the first blank line).
    """
    type1 = RAW_HTML_TYPE1_OPEN_RE.match(raw)
    if type1 is not None:
        return "tag", type1.group("tag").lower()
    if re.match(r"^ {0,3}<\?", raw):
        return "token", "?>"
    if re.match(r"^ {0,3}<!\[CDATA\[", raw, re.IGNORECASE):
        return "token", "]] >".replace(" ", "")
    if RAW_HTML_DECLARATION_OPEN_RE.match(raw):
        return "token", ">"
    if RAW_HTML_BLOCK_TAG_RE.match(raw) or RAW_HTML_COMPLETE_TAG_RE.match(raw):
        return "blank", None
    return None


def raw_html_tag_closes(raw: str, tag: str) -> bool:
    return re.search(rf"</{re.escape(tag)}[ \t]*>", raw, re.IGNORECASE) is not None


def visible_nonfenced_lines(lines: list[str]) -> list[str]:
    """Return rendered-ish Markdown lines, excluding non-Markdown constructs.

    Fence state is determined from the original Markdown line before HTML comments
    are removed, so a fence-looking line with trailing comment text cannot become
    a valid closer after preprocessing. Raw HTML blocks are also excluded because
    Markdown-looking source inside them is not rendered as Markdown headings,
    fields, links, or tables.
    """
    visible: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    in_comment = False
    html_mode: str | None = None
    html_end: str | None = None

    for raw in lines:
        if fence_char is not None:
            close = re.fullmatch(
                rf" {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*", raw
            )
            if close is not None:
                fence_char = None
                fence_len = 0
            continue

        if html_mode is not None:
            if html_mode == "tag":
                if html_end is not None and raw_html_tag_closes(raw, html_end):
                    html_mode = None
                    html_end = None
                continue
            if html_mode == "token":
                if html_end is not None and html_end in raw:
                    html_mode = None
                    html_end = None
                continue
            if html_mode == "blank":
                if raw.strip() == "":
                    html_mode = None
                    html_end = None
                    visible.append("")
                continue

        if in_comment:
            rendered, in_comment = strip_html_comments_from_visible_line(raw, True)
            if in_comment:
                continue
            raw_for_parse = rendered
        else:
            # A fence opener is recognized from the original line. This matters
            # because HTML comment syntax in a fence info string is literal text.
            opener = FENCE_OPEN_RE.match(raw)
            if opener is not None:
                run = opener.group(1)
                info = opener.group(2)
                if run[0] != "`" or "`" not in info:
                    fence_char = run[0]
                    fence_len = len(run)
                    continue

            html_start = raw_html_block_start(raw)
            if html_start is not None:
                html_mode, html_end = html_start
                if html_mode == "tag" and html_end is not None and raw_html_tag_closes(raw, html_end):
                    html_mode = None
                    html_end = None
                elif html_mode == "token" and html_end is not None and html_end in raw:
                    html_mode = None
                    html_end = None
                continue

            raw_for_parse, in_comment = strip_html_comments_from_visible_line(raw, False)

        if raw_for_parse:
            visible.append(raw_for_parse)
        elif not in_comment and raw == "":
            visible.append("")

    return visible


def visible_text(text: str) -> str:
    return "\n".join(visible_nonfenced_lines(text.splitlines()))


def section_lines(text: str, heading: str) -> list[str]:
    """Return one exact visible level-2 Markdown section."""
    lines = visible_nonfenced_lines(text.splitlines())
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


def markdown_table_cells(line: str) -> list[str] | None:
    stripped = line.strip()
    if not stripped.startswith("|"):
        return None
    return [cell.strip() for cell in stripped.strip("|").split("|")]


def extract_markdown_table(
    lines: list[str], expected_headers: tuple[str, ...], context: str
) -> list[list[str]]:
    """Extract one visible table and return validated data rows as cell lists."""
    visible = visible_nonfenced_lines(lines)
    expected = list(expected_headers)
    for i, line in enumerate(visible):
        if markdown_table_cells(line) != expected:
            continue
        if i + 1 >= len(visible):
            die(f"{context} table has no separator row")
        separator = markdown_table_cells(visible[i + 1])
        if (
            separator is None
            or len(separator) != len(expected)
            or not all(TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in separator)
        ):
            die(f"{context} table has an invalid separator row")

        rows: list[list[str]] = []
        for row in visible[i + 2 :]:
            cells = markdown_table_cells(row)
            if cells is None:
                break
            if len(cells) != len(expected):
                die(
                    f"{context} table row has {len(cells)} column(s); "
                    f"expected {len(expected)}: {row.strip()}"
                )
            if any(not cell for cell in cells):
                die(f"{context} table row contains an empty required cell: {row.strip()}")
            rows.append(cells)
        return rows
    die(f"{context} is missing the expected Markdown table")


def unwrap_markdown_emphasis(cell: str) -> str:
    """Remove balanced outer emphasis wrappers; do not unwrap code spans."""
    value = cell.strip()
    changed = True
    while changed:
        changed = False
        for marker in EMPHASIS_WRAPPERS:
            if (
                len(value) > 2 * len(marker)
                and value.startswith(marker)
                and value.endswith(marker)
            ):
                value = value[len(marker) : -len(marker)].strip()
                changed = True
                break
    return value


def parse_record_link_cell(cell: str, context: str) -> tuple[str, str]:
    value = unwrap_markdown_emphasis(cell)
    match = RECORD_LINK_CELL_RE.fullmatch(value)
    if match is None:
        die(f"{context} has invalid record-link cell: {cell}")
    return match.group(1), match.group(2)


def is_structural_only_line(line: str) -> bool:
    if HEADING_RE.match(line) or THEMATIC_BREAK_RE.fullmatch(line):
        return True
    if LIST_MARKER_ONLY_RE.fullmatch(line) or line == ">":
        return True
    cells = markdown_table_cells(line)
    return bool(cells and all(TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells))


def section_has_content(lines: list[str]) -> bool:
    for raw in visible_nonfenced_lines(lines):
        line = raw.strip()
        if not line or line in TEMPLATE_PLACEHOLDER_LINES:
            continue
        if EMPTY_LABEL_RE.match(line) or is_structural_only_line(line):
            continue
        return True
    return False


def normalized_status_category(raw: str) -> str:
    plain = re.sub(r"[*_`]", "", raw).strip()
    return plain.split(";", 1)[0].strip()


def require_prefixed_fields(
    path: Path,
    lines: list[str],
    fields: tuple[str, ...],
    section: str,
    rejected_values: dict[str, str] | None = None,
) -> None:
    visible = visible_nonfenced_lines(lines)
    for field in fields:
        prefix = f"- {field}:"
        matches = [line for line in visible if line.startswith(prefix)]
        if len(matches) != 1:
            die(
                f"{path.relative_to(ROOT)} must contain exactly one visible field "
                f"'{prefix}' in {section}"
            )
        value = matches[0][len(prefix) :].strip()
        if not value:
            die(f"{path.relative_to(ROOT)} has empty field {field} in {section}")
        if rejected_values is not None and value == rejected_values.get(field):
            die(
                f"{path.relative_to(ROOT)} has unselected template placeholder "
                f"for {field} in {section}: '{value}'"
            )


records: dict[str, Path] = {}
status_categories: dict[str, str] = {}
for path in sorted(OPT_DIR.glob("OPT-*.md")):
    text = path.read_text(encoding="utf-8")
    lines = visible_nonfenced_lines(text.splitlines())
    first = lines[0] if lines else ""
    match = ID_RE.match(first)
    if not match:
        die(f"bad or hidden record heading: {path.relative_to(ROOT)}")
    record_id = match.group(1)

    filename_match = FILENAME_ID_RE.match(path.name)
    if not filename_match:
        die(f"record filename does not begin with an OPT ID: {path.relative_to(ROOT)}")
    if filename_match.group(1) != record_id:
        die(
            f"record ID mismatch: {path.relative_to(ROOT)} declares {record_id} "
            f"but filename encodes {filename_match.group(1)}"
        )
    if record_id in records:
        die(f"duplicate record id {record_id}: {records[record_id]} and {path}")
    records[record_id] = path

    statuses = [m.group(1).strip() for line in lines if (m := STATUS_RE.match(line))]
    if len(statuses) != 1:
        die(f"{path.relative_to(ROOT)} must contain exactly one visible Status line")
    if not statuses[0]:
        die(f"{path.relative_to(ROOT)} has empty Status")

    if record_id in FROZEN_V1:
        continue

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
        die(f"{path.relative_to(ROOT)} missing visible sections: {', '.join(missing)}")

    for heading in sorted(REQUIRED_V2):
        if not section_has_content(section_lines(text, heading)):
            die(
                f"{path.relative_to(ROOT)} has empty/template/structural-only mandatory section {heading}"
            )

    contract = section_lines(text, "## Optimization problem contract")
    require_prefixed_fields(
        path, contract, REQUIRED_CONTRACT_FIELDS, "## Optimization problem contract"
    )
    require_prefixed_fields(
        path,
        contract,
        REQUIRED_CLASSIFICATION_FIELDS,
        "## Optimization problem contract",
        rejected_values=CLASSIFICATION_TEMPLATE_VALUES,
    )

missing_frozen = sorted(FROZEN_V1 - records.keys())
if missing_frozen:
    die(f"frozen v1 record(s) missing: {', '.join(missing_frozen)}")

record_paths = {str(path.relative_to(ROOT)): record_id for record_id, path in records.items()}

for doc_name in ("README.md", "CATALOG.md"):
    text = (ROOT / doc_name).read_text(encoding="utf-8")
    rendered = visible_text(text)
    for label, rel in LINK_RE.findall(rendered):
        target = ROOT / rel
        if not target.is_file():
            die(f"broken visible record link in {doc_name}: {rel}")
        target_id = record_paths.get(rel)
        if target_id is None:
            die(f"record link in {doc_name} is not a discovered OPT record: {rel}")
        if re.sub(r"[*_~]", "", label).strip() != target_id:
            die(
                f"record link label mismatch in {doc_name}: '{label}' points to "
                f"{target_id} ({rel})"
            )

    if doc_name != "README.md":
        continue

    catalog_lines = section_lines(text, "## Catalog")
    if not catalog_lines:
        die("README.md is missing a non-empty visible ## Catalog section")
    catalog_rows = extract_markdown_table(
        catalog_lines,
        ("ID", "Optimization", "Status", "Core idea"),
        "README.md ## Catalog",
    )

    parsed_rows: list[tuple[str, str, str]] = []
    for cells in catalog_rows:
        row_id, rel = parse_record_link_cell(cells[0], "README.md ## Catalog")
        parsed_rows.append((row_id, rel, cells[2]))

    counts = Counter(row_id for row_id, _rel, _status in parsed_rows)
    bad_counts = sorted(record_id for record_id, count in counts.items() if count != 1)
    if bad_counts:
        die(
            "README.md ## Catalog table must index each record exactly once; "
            f"bad row counts for: {', '.join(bad_counts)}"
        )
    missing_readme = sorted(records.keys() - counts.keys())
    if missing_readme:
        die(f"README.md ## Catalog table is missing record(s): {', '.join(missing_readme)}")
    unknown_rows = sorted(counts.keys() - records.keys())
    if unknown_rows:
        die(f"README.md ## Catalog table references unknown record(s): {', '.join(unknown_rows)}")

    row_statuses: dict[str, str] = {}
    for row_id, rel, raw_status in parsed_rows:
        if record_paths.get(rel) != row_id:
            die(f"README.md ## Catalog row identity mismatch for {row_id}: {rel}")
        if row_id in row_statuses:
            die(f"README.md ## Catalog has duplicate status row for {row_id}")
        row_statuses[row_id] = normalized_status_category(raw_status)

    for record_id, expected_status in status_categories.items():
        observed_status = row_statuses.get(record_id)
        if observed_status is None:
            die(f"README.md ## Catalog has no status cell for post-v1 record {record_id}")
        if observed_status != expected_status:
            die(
                f"README.md status mismatch for {record_id}: "
                f"record='{expected_status}' README='{observed_status}'"
            )

catalog = (ROOT / "CATALOG.md").read_text(encoding="utf-8")
visible_catalog = visible_text(catalog)
catalog_ids = set(OPT_TOKEN_RE.findall(visible_catalog))
unknown_catalog_ids = sorted(catalog_ids - records.keys())
if unknown_catalog_ids:
    die(f"CATALOG.md references unknown visible record ID(s): {', '.join(unknown_catalog_ids)}")
for record_id, path in records.items():
    if record_id not in catalog_ids:
        die(f"{record_id} ({path.name}) is not visibly mentioned in CATALOG.md")

decision_lines = section_lines(catalog, "## Quick decision table")
if not decision_lines:
    die("CATALOG.md is missing a non-empty visible ## Quick decision table section")
decision_rows = extract_markdown_table(
    decision_lines,
    ("Bottleneck / problem shape", "First record to inspect", "Core idea"),
    "CATALOG.md ## Quick decision table",
)

parsed_decisions: list[tuple[str, str]] = []
for cells in decision_rows:
    row_id, rel = parse_record_link_cell(
        cells[1], "CATALOG.md ## Quick decision table"
    )
    parsed_decisions.append((row_id, rel))

decision_counts = Counter(record_id for record_id, _rel in parsed_decisions)
bad_decision_counts = sorted(
    record_id for record_id, count in decision_counts.items() if count != 1
)
if bad_decision_counts:
    die(
        "CATALOG.md ## Quick decision table must index each record exactly once; "
        f"bad row counts for: {', '.join(bad_decision_counts)}"
    )
missing_decision = sorted(records.keys() - decision_counts.keys())
if missing_decision:
    die(
        "CATALOG.md ## Quick decision table is missing record(s): "
        f"{', '.join(missing_decision)}"
    )
unknown_decision = sorted(decision_counts.keys() - records.keys())
if unknown_decision:
    die(
        "CATALOG.md ## Quick decision table references unknown record(s): "
        f"{', '.join(unknown_decision)}"
    )
for row_id, rel in parsed_decisions:
    if record_paths.get(rel) != row_id:
        die(f"CATALOG.md ## Quick decision table row identity mismatch for {row_id}: {rel}")

problem_contract = ROOT / "OPTIMIZATION-PROBLEM.md"
if not problem_contract.is_file():
    die("OPTIMIZATION-PROBLEM.md is missing")
problem_text = problem_contract.read_text(encoding="utf-8")
problem_visible = visible_nonfenced_lines(problem_text.splitlines())
if not problem_visible or problem_visible[0] != "# Optimization Problem Contract":
    die("OPTIMIZATION-PROBLEM.md has missing/hidden/invalid title")
if "## Canonical contract" not in problem_visible:
    die("OPTIMIZATION-PROBLEM.md is missing visible ## Canonical contract")
canonical = section_lines(problem_text, "## Canonical contract")
canonical_text = "\n".join(canonical)
if "P = (X, F, f, d, C, B, S)" not in canonical_text:
    die("OPTIMIZATION-PROBLEM.md is missing visible canonical P = (X, F, f, d, C, B, S) formula")
for field, pattern in CANONICAL_DEFINITION_PATTERNS.items():
    if not any(pattern.match(line) for line in canonical):
        die(f"OPTIMIZATION-PROBLEM.md is missing visible canonical definition for {field}")

print(f"CATALOG_INTEGRITY_OK records={len(records)} frozen_v1={len(FROZEN_V1)}")
