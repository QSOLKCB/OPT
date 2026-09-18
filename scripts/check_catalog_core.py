#!/usr/bin/env python3
"""Check OPT catalog/document integrity without external dependencies."""

from __future__ import annotations

import html
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
    "Information": "gradient available / derivative-free / black-box",
    "Evaluation cost": "cheap / moderate / expensive",
    "Constraints": "bounds / equality / inequality / semantic / resource",
    "Parallelism": "sequential / synchronous batch / asynchronous",
    "Exactness": "exact / approximation permitted under an explicit error contract",
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

LINK_RE = re.compile(
    r"\[([^\]]+)\]\((optimizations/[^)#]+\.md)(?:#[^)\s]*)?\)"
)
RECORD_LINK_CELL_RE = re.compile(
    r"^\[(OPT-[A-Z]+-\d{3})\]\((optimizations/[^)#]+\.md)(?:#[^)\s]*)?\)$"
)
ID_RE = re.compile(r"^# (OPT-[A-Z]+-\d{3}) — ")
FILENAME_ID_RE = re.compile(r"^(OPT-[A-Z]+-\d{3})-")
STATUS_RE = re.compile(r"^\*\*Status:\*\*\s*(.*?)\s*$")
OPT_TOKEN_RE = re.compile(r"\bOPT-[A-Z]+-\d{3}\b")
EMPTY_LABEL_RE = re.compile(r"^-\s+[^:]+:\s*$")
LINK_REFERENCE_DEFINITION_RE = re.compile(
    r"^\[(?:\\.|[^\[\]\\])+\]:[ \t]+\S.*$"
)
LINK_REFERENCE_TITLE_CONTINUATION_RE = re.compile(
    r"^ {0,3}(?:\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|\((?:\\.|[^)\\])*\))[ \t]*$"
)
SOURCE_URL_RE = re.compile(r"https?://\S+", re.IGNORECASE)
SOURCE_DOI_RE = re.compile(r"\b(?:doi:\s*)?10\.\d{4,9}/\S+", re.IGNORECASE)
SOURCE_COMMIT_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
SOURCE_LOCAL_NOTE_RE = re.compile(r"`?(sources/[A-Za-z0-9._/-]+\.md)`?")
SOURCE_REPOSITORY_RE = re.compile(r"`[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+`")
SOURCE_PLACEHOLDER_RE = re.compile(
    r"^(?:[-*+]\s*)?(?:unknown|tbd|todo|n/?a|none|pending)\.?$", re.IGNORECASE
)
REFERENCE_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\[[^\]]*\]")
REFERENCE_LINK_RE = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")
INLINE_HTML_TAG_RE = re.compile(
    r"</?[A-Za-z][A-Za-z0-9-]*"
    r"(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t]*=[ \t]*(?:\"[^\"]*\"|'[^']*'|[^ \t\n\"'=<>`]+))?)*"
    r"[ \t]*/?>"
)
HEADING_RE = re.compile(r"^#{1,6}(?:\s|$)")
SECTION_BOUNDARY_RE = re.compile(r"^#{1,2}(?:\s|$)")
SETEXT_H1_RE = re.compile(r"^ {0,3}=+[ \t]*$")
SETEXT_H2_RE = re.compile(r"^ {0,3}-+[ \t]*$")
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
    r"^ {0,3}(?:"
    r"</[A-Za-z][A-Za-z0-9-]*[ \t]*>"
    r"|<[A-Za-z][A-Za-z0-9-]*"
    r"(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t]*=[ \t]*(?:\"[^\"]*\"|'[^']*'|[^ \t\n\"'=<>`]+))?)*"
    r"[ \t]*/?>"
    r")[ \t]*$"
)
EMPHASIS_WRAPPERS = ("**", "__", "~~", "*", "_")
STATUS_WRAPPERS = ("**", "__", "~~", "*", "_", "`")
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


def markdown_source_lines(text: str) -> list[str]:
    """Split only on CommonMark line endings (LF, CRLF, or CR)."""
    return text.replace("\r\n", "\n").replace("\r", "\n").split("\n")


def is_indented_code_line(raw: str) -> bool:
    """Return whether a non-fenced line is an indented Markdown code line."""
    return raw.startswith("\t") or raw.startswith("    ")


def strip_inline_html_comments(raw: str, in_comment: bool) -> tuple[str, bool]:
    """Strip inline HTML comments while carrying a mid-line unmatched comment."""
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
    """Return the raw-HTML block mode for a CommonMark-style block start."""
    if re.match(r"^ {0,3}<!--", raw):
        return "token", "-->"

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
    """Match CommonMark type-1 block terminators exactly (case-insensitive)."""
    return re.search(rf"</{re.escape(tag)}>", raw, re.IGNORECASE) is not None


def _line_keeps_paragraph_open(raw: str) -> bool:
    """Approximate block starts that terminate an open CommonMark paragraph."""
    stripped = raw.strip()
    if not stripped:
        return False
    if re.match(r"^ {0,3}#{1,6}(?:[ \t]|$)", raw):
        return False
    if THEMATIC_BREAK_RE.fullmatch(stripped):
        return False
    if LINK_REFERENCE_DEFINITION_RE.fullmatch(stripped):
        return False
    if LIST_MARKER_ONLY_RE.fullmatch(stripped) or stripped == ">":
        return False
    return True


def visible_nonfenced_lines(lines: list[str]) -> list[str]:
    """Return Markdown-visible lines used by schema validation."""
    visible: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    inline_comment = False
    html_mode: str | None = None
    html_end: str | None = None
    paragraph_open = False

    for raw in lines:
        if fence_char is not None:
            paragraph_open = False
            close = re.fullmatch(
                rf" {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*", raw
            )
            if close is not None:
                fence_char = None
                fence_len = 0
            continue

        if html_mode is not None:
            paragraph_open = False
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

        was_paragraph_open = paragraph_open

        if inline_comment:
            rendered, inline_comment = strip_inline_html_comments(raw, True)
            if inline_comment:
                continue
            raw_for_parse = rendered
        else:
            if is_indented_code_line(raw):
                if not paragraph_open:
                    continue
                raw_for_parse = raw
            else:
                opener = FENCE_OPEN_RE.match(raw)
                if opener is not None:
                    run = opener.group(1)
                    info = opener.group(2)
                    if run[0] != "`" or "`" not in info:
                        paragraph_open = False
                        fence_char = run[0]
                        fence_len = len(run)
                        continue

                html_start = raw_html_block_start(raw)
                if html_start is not None:
                    paragraph_open = False
                    html_mode, html_end = html_start
                    if html_mode == "tag" and html_end is not None and raw_html_tag_closes(raw, html_end):
                        html_mode = None
                        html_end = None
                    elif html_mode == "token" and html_end is not None and html_end in raw:
                        html_mode = None
                        html_end = None
                    continue

                raw_for_parse, inline_comment = strip_inline_html_comments(raw, False)

        if raw_for_parse and is_indented_code_line(raw_for_parse) and not was_paragraph_open:
            continue

        if raw_for_parse:
            visible.append(raw_for_parse)
            if is_indented_code_line(raw_for_parse) and was_paragraph_open:
                paragraph_open = True
            else:
                paragraph_open = _line_keeps_paragraph_open(raw_for_parse)
        elif not inline_comment and raw == "":
            visible.append("")
            paragraph_open = False

    return visible


def visible_text(text: str) -> str:
    return "\n".join(visible_nonfenced_lines(markdown_source_lines(text)))


def setext_heading_start(
    lines: list[str], underline_index: int, minimum_index: int
) -> int | None:
    """Return the first source line of a Setext heading paragraph."""
    if underline_index <= minimum_index:
        return None
    underline = lines[underline_index]
    if not (
        SETEXT_H1_RE.fullmatch(underline) or SETEXT_H2_RE.fullmatch(underline)
    ):
        return None

    candidate = underline_index - 1
    if candidate < minimum_index or not lines[candidate].strip():
        return None
    if HEADING_RE.match(lines[candidate]):
        return None

    start = candidate
    while start > minimum_index:
        previous = lines[start - 1]
        if not previous.strip() or SECTION_BOUNDARY_RE.match(previous):
            break
        start -= 1
    return start


def section_lines(text: str, heading: str) -> list[str]:
    """Return one exact visible level-2 Markdown section."""
    lines = visible_nonfenced_lines(markdown_source_lines(text))
    try:
        start = lines.index(heading) + 1
    except ValueError:
        return []
    end = len(lines)
    for i in range(start, len(lines)):
        if SECTION_BOUNDARY_RE.match(lines[i]):
            end = i
            break
        setext_start = setext_heading_start(lines, i, start)
        if setext_start is not None:
            end = setext_start
            break
    return lines[start:end]


def is_backslash_escaped(text: str, index: int) -> bool:
    count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        count += 1
        cursor -= 1
    return count % 2 == 1


def backtick_run_length(text: str, index: int) -> int:
    cursor = index
    while cursor < len(text) and text[cursor] == "`":
        cursor += 1
    return cursor - index


def protect_code_spans(text: str) -> tuple[str, dict[str, str]]:
    """Replace parsed code spans with private-use sentinels and preserve their text."""
    out: list[str] = []
    protected: dict[str, str] = {}
    i = 0
    while i < len(text):
        if text[i] != "`" or is_backslash_escaped(text, i):
            out.append(text[i])
            i += 1
            continue

        run_len = backtick_run_length(text, i)
        j = i + run_len
        close_start: int | None = None
        close_end: int | None = None
        while j < len(text):
            if text[j] != "`":
                j += 1
                continue
            candidate_len = backtick_run_length(text, j)
            if candidate_len == run_len:
                close_start = j
                close_end = j + candidate_len
                break
            j += candidate_len

        if close_start is None or close_end is None:
            out.append(text[i : i + run_len])
            i += run_len
            continue

        token = chr(0xE000 + len(protected))
        protected[token] = text[i + run_len : close_start]
        out.append(token)
        i = close_end

    return "".join(out), protected


def find_label_close(text: str, open_index: int) -> int | None:
    depth = 1
    i = open_index + 1
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            i += 2
            continue
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def parse_link_title_and_close(text: str, index: int) -> int | None:
    """Parse whitespace plus an optional CommonMark-style title and outer close."""
    i = index
    while i < len(text) and text[i] in " \t\n":
        i += 1
    if i < len(text) and text[i] == ")":
        return i + 1
    if i >= len(text):
        return None

    opener = text[i]
    if opener not in ('"', "'", "("):
        return None
    closer = ")" if opener == "(" else opener
    i += 1
    while i < len(text):
        if text[i] == "\\" and i + 1 < len(text):
            i += 2
            continue
        if text[i] == closer:
            i += 1
            break
        if text[i] == "\n":
            return None
        i += 1
    else:
        return None

    while i < len(text) and text[i] in " \t\n":
        i += 1
    if i < len(text) and text[i] == ")":
        return i + 1
    return None


def find_inline_link_end(text: str, open_paren: int) -> int | None:
    """Return the end of a valid inline-link destination/title, or None."""
    i = open_paren + 1
    while i < len(text) and text[i] in " \t\n":
        i += 1
    if i >= len(text):
        return None
    if text[i] == ")":
        return i + 1

    if text[i] == "<":
        i += 1
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                i += 2
                continue
            if text[i] == ">":
                return parse_link_title_and_close(text, i + 1)
            if text[i] in "\n<":
                return None
            i += 1
        return None

    depth = 0
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            i += 2
            continue
        if char == "(":
            depth += 1
            i += 1
            continue
        if char == ")":
            if depth == 0:
                return i + 1
            depth -= 1
            i += 1
            continue
        if char in " \t\n" and depth == 0:
            return parse_link_title_and_close(text, i)
        if char in "<>" or ord(char) < 0x20:
            return None
        i += 1
    return None


def strip_inline_links(text: str) -> str:
    """Keep rendered labels while discarding valid inline-link/image destinations."""
    out: list[str] = []
    i = 0
    while i < len(text):
        image = text.startswith("![", i)
        if image:
            label_open = i + 1
        elif text[i] == "[":
            label_open = i
        else:
            out.append(text[i])
            i += 1
            continue

        label_close = find_label_close(text, label_open)
        if label_close is None or label_close + 1 >= len(text) or text[label_close + 1] != "(":
            out.append(text[i])
            i += 1
            continue
        link_end = find_inline_link_end(text, label_close + 1)
        if link_end is None:
            out.append(text[i])
            i += 1
            continue

        out.append(text[label_open + 1 : label_close])
        i = link_end
    return "".join(out)


def markdown_table_cells(line: str) -> list[str] | None:
    """Split a pipe table on unescaped delimiters outside backtick code spans."""
    if is_indented_code_line(line):
        return None
    stripped = line.strip()
    if not stripped:
        return None

    cells: list[str] = []
    current: list[str] = []
    code_run_len: int | None = None
    saw_delimiter = stripped.startswith("|")
    i = 1 if saw_delimiter else 0
    while i < len(stripped):
        char = stripped[i]
        if char == "`" and not is_backslash_escaped(stripped, i):
            run_len = backtick_run_length(stripped, i)
            if code_run_len is None:
                code_run_len = run_len
            elif run_len == code_run_len:
                code_run_len = None
            current.append(stripped[i : i + run_len])
            i += run_len
            continue

        if char == "|" and code_run_len is None:
            if is_backslash_escaped(stripped, i):
                if current and current[-1] == "\\":
                    current.pop()
                current.append("|")
            else:
                saw_delimiter = True
                cells.append("".join(current).strip())
                current = []
            i += 1
            continue

        current.append(char)
        i += 1

    if not saw_delimiter:
        return None

    trailing_pipe_is_delimiter = (
        stripped.endswith("|") and not is_backslash_escaped(stripped, len(stripped) - 1)
    )
    if current or not trailing_pipe_is_delimiter:
        cells.append("".join(current).strip())
    return cells


def extract_markdown_table(
    lines: list[str], expected_headers: tuple[str, ...], context: str
) -> list[list[str]]:
    """Extract one visible table and return validated data rows as cell lists."""
    visible = visible_nonfenced_lines(lines)
    expected = list(expected_headers)
    for i, line in enumerate(visible):
        if markdown_table_cells(line) != expected:
            continue
        if (
            i > 0
            and visible[i - 1].strip()
            and not is_structural_only_line(visible[i - 1].strip())
        ):
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


def unwrap_outer_formatting(value: str, wrappers: tuple[str, ...]) -> str:
    """Remove only balanced formatting that wraps the complete value."""
    result = value.strip()
    changed = True
    while changed:
        changed = False
        for marker in wrappers:
            if (
                len(result) > 2 * len(marker)
                and result.startswith(marker)
                and result.endswith(marker)
            ):
                result = result[len(marker) : -len(marker)].strip()
                changed = True
                break
    return result


def unwrap_markdown_emphasis(cell: str) -> str:
    return unwrap_outer_formatting(cell, EMPHASIS_WRAPPERS)


def parse_record_link_cell(cell: str, context: str) -> tuple[str, str]:
    value = unwrap_markdown_emphasis(cell)
    match = RECORD_LINK_CELL_RE.fullmatch(value)
    if match is None:
        die(f"{context} has invalid record-link cell: {cell}")
    return match.group(1), match.group(2)


def rendered_inline_text(value: str) -> str:
    """Approximate rendered inline text for required field-value validation."""
    text, protected_code = protect_code_spans(value)
    text = strip_inline_links(text)
    text = REFERENCE_IMAGE_RE.sub(lambda m: m.group(1), text)
    text = REFERENCE_LINK_RE.sub(lambda m: m.group(1), text)
    text = INLINE_HTML_TAG_RE.sub("", text)
    text = re.sub(r"[`*_~]", "", text)
    text = re.sub(r"\\(.)", r"\1", text)
    for token, code_text in protected_code.items():
        text = text.replace(token, code_text)
    return html.unescape(text).strip()


def has_substantive_rendered_text(value: str) -> bool:
    return any(ch.isalnum() for ch in rendered_inline_text(value))


def reference_definition_hidden_indexes(lines: list[str]) -> set[int]:
    """Return lines consumed by non-rendering reference definitions/titles."""
    hidden: set[int] = set()
    for i, raw in enumerate(lines):
        if not LINK_REFERENCE_DEFINITION_RE.fullmatch(raw.strip()):
            continue
        hidden.add(i)
        if (
            i + 1 < len(lines)
            and LINK_REFERENCE_TITLE_CONTINUATION_RE.fullmatch(lines[i + 1])
        ):
            hidden.add(i + 1)
    return hidden


def is_structural_only_line(line: str) -> bool:
    if HEADING_RE.match(line) or THEMATIC_BREAK_RE.fullmatch(line):
        return True
    if LIST_MARKER_ONLY_RE.fullmatch(line) or line == ">":
        return True
    if LINK_REFERENCE_DEFINITION_RE.fullmatch(line):
        return True
    cells = markdown_table_cells(line)
    return bool(cells and all(TABLE_SEPARATOR_CELL_RE.fullmatch(cell) for cell in cells))


def section_has_content(lines: list[str]) -> bool:
    visible = visible_nonfenced_lines(lines)
    hidden_reference_lines = reference_definition_hidden_indexes(visible)
    for index, raw in enumerate(visible):
        if index in hidden_reference_lines:
            continue
        line = raw.strip()
        if not line or line in TEMPLATE_PLACEHOLDER_LINES:
            continue
        if EMPTY_LABEL_RE.match(line) or is_structural_only_line(line):
            continue
        if not has_substantive_rendered_text(line):
            continue
        return True
    return False


def source_section_has_identity(lines: list[str]) -> bool:
    """Require at least one concrete, non-placeholder provenance identity."""
    sources_root = (ROOT / "sources").resolve()
    for raw in visible_nonfenced_lines(lines):
        line = raw.strip()
        if not line or SOURCE_PLACEHOLDER_RE.fullmatch(line):
            continue
        if SOURCE_URL_RE.search(line) or SOURCE_DOI_RE.search(line) or SOURCE_COMMIT_RE.search(line):
            return True
        for match in SOURCE_LOCAL_NOTE_RE.finditer(line):
            candidate = (ROOT / match.group(1)).resolve()
            try:
                candidate.relative_to(sources_root)
            except ValueError:
                continue
            if candidate.is_file():
                return True
        if SOURCE_REPOSITORY_RE.search(line):
            return True
    return False


def normalized_status_category(raw: str) -> str:
    category = raw.split(";", 1)[0].strip()
    return unwrap_outer_formatting(category, STATUS_WRAPPERS)


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
        if not has_substantive_rendered_text(value):
            die(
                f"{path.relative_to(ROOT)} has markup-only/non-substantive field "
                f"{field} in {section}: '{value}'"
            )
        if rejected_values is not None:
            normalized_value = html.unescape(
                unwrap_outer_formatting(value, STATUS_WRAPPERS)
            ).strip()
            if normalized_value == rejected_values.get(field):
                die(
                    f"{path.relative_to(ROOT)} has unselected template placeholder "
                    f"for {field} in {section}: '{value}'"
                )


records: dict[str, Path] = {}
status_categories: dict[str, str] = {}
for path in sorted(OPT_DIR.glob("*.md")):
    text = path.read_text(encoding="utf-8")
    lines = visible_nonfenced_lines(markdown_source_lines(text))
    first = lines[0] if lines else ""
    match = ID_RE.match(first)
    if not match:
        die(f"bad or hidden record heading: {path.relative_to(ROOT)}")
    record_id = match.group(1)

    filename_match = FILENAME_ID_RE.match(path.name)
    if not filename_match:
        die(
            f"record Markdown filename does not follow OPT-<KIND>-<NNN>-... convention: "
            f"{path.relative_to(ROOT)}"
        )
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
                f"{path.relative_to(ROOT)} has empty/template/structural/markup-only mandatory section {heading}"
            )

    source_evidence = section_lines(text, "## Source evidence")
    if not source_section_has_identity(source_evidence):
        die(
            f"{path.relative_to(ROOT)} ## Source evidence lacks a concrete source identity "
            "(URL, DOI, pinned commit, existing sources/*.md note, or repository identity)"
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
        if unwrap_markdown_emphasis(label) != target_id:
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
problem_visible = visible_nonfenced_lines(markdown_source_lines(problem_text))
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

classification_lines = section_lines(problem_text, "## Required classification")
if not classification_lines:
    die("OPTIMIZATION-PROBLEM.md is missing visible ## Required classification")
classification_rows = extract_markdown_table(
    classification_lines,
    ("Dimension", "Typical values"),
    "OPTIMIZATION-PROBLEM.md ## Required classification",
)
canonical_classification: dict[str, str] = {}
for row in classification_rows:
    dimension, typical_values = row
    if dimension in canonical_classification:
        die(f"OPTIMIZATION-PROBLEM.md has duplicate classification dimension {dimension}")
    canonical_classification[dimension] = typical_values

expected_dimensions = set(REQUIRED_CLASSIFICATION_FIELDS)
observed_dimensions = set(canonical_classification)
if observed_dimensions != expected_dimensions:
    missing_dimensions = sorted(expected_dimensions - observed_dimensions)
    unknown_dimensions = sorted(observed_dimensions - expected_dimensions)
    details: list[str] = []
    if missing_dimensions:
        details.append(f"missing={','.join(missing_dimensions)}")
    if unknown_dimensions:
        details.append(f"unknown={','.join(unknown_dimensions)}")
    die(
        "OPTIMIZATION-PROBLEM.md classification dimensions do not match the checker: "
        + "; ".join(details)
    )
for dimension in REQUIRED_CLASSIFICATION_FIELDS:
    canonical_value = canonical_classification[dimension]
    checker_value = CLASSIFICATION_TEMPLATE_VALUES[dimension]
    if canonical_value != checker_value:
        die(
            f"classification placeholder drift for {dimension}: "
            f"canonical='{canonical_value}' checker='{checker_value}'"
        )

print(f"CATALOG_INTEGRITY_OK records={len(records)} frozen_v1={len(FROZEN_V1)}")
