#!/usr/bin/env python3
"""Check OPT catalog/document integrity without external dependencies."""

from __future__ import annotations

import html
import ipaddress
import re
import string
from collections import Counter
from pathlib import Path
from urllib.parse import unquote, urlsplit

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
    r"^\[(OPT-[A-Z]+-\d{3})\]\(\s*(optimizations/[^)#\s]+\.md)(?:#[^)\s]*)?\s*\)$"
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
SOURCE_COMMIT_CONTEXT_RE = re.compile(
    r"(?:"
    r"\b(?:commit(?:[ \t]+sha)?|sha|revision|rev)\b[^0-9A-Za-z]{0,12}"
    r"|\b(?:pinned|inspected)[ \t]+at\b[^0-9A-Za-z]{0,12}"
    r"|@"
    r")$",
    re.IGNORECASE,
)
SOURCE_LOCAL_NOTE_RE = re.compile(r"`?(sources/[A-Za-z0-9._/-]+\.md)`?")
SOURCE_REPOSITORY_RE = re.compile(r"`[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+`")
SOURCE_PLACEHOLDER_RE = re.compile(
    r"^(?:[-*+]\s*)?(?:unknown|tbd|todo|n/?a|none|pending)\.?$", re.IGNORECASE
)
REFERENCE_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\[[^\]]*\]")
REFERENCE_LINK_RE = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")
INLINE_HTML_TAG_RE = re.compile(
    r"</?[A-Za-z][A-Za-z0-9-]*"
    r"(?:[ \t\r\n]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t\r\n]*=[ \t\r\n]*(?:\"[^\"]*\"|'[^']*'|[^ \t\r\n\"'=<>\x60]+))?)*"
    r"[ \t\r\n]*/?>"
)
HEADING_RE = re.compile(r"^#{1,6}(?:\s|$)")
SECTION_BOUNDARY_RE = re.compile(r"^#{1,2}(?:\s|$)")
SETEXT_H1_RE = re.compile(r"^ {0,3}=+[ \t]*$")
SETEXT_H2_RE = re.compile(r"^ {0,3}-+[ \t]*$")
THEMATIC_BREAK_RE = re.compile(
    r"^(?:\*(?:[ \t]*\*){2,}|-(?:[ \t]*-){2,}|_(?:[ \t]*_){2,})[ \t]*$"
)
LIST_MARKER_ONLY_RE = re.compile(r"^(?:[-+*]|\d{1,9}[.)])$")
TABLE_SEPARATOR_CELL_RE = re.compile(r"^:?-{3,}:?$")
FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
RAW_HTML_TYPE1_OPEN_RE = re.compile(
    r"^ {0,3}<(?P<tag>script|pre|style|textarea)(?:[ \t]|>|$)", re.IGNORECASE
)
RAW_HTML_DECLARATION_OPEN_RE = re.compile(r"^ {0,3}<![A-Z]")
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
    """Return whether leading whitespace reaches four CommonMark columns."""
    columns = 0
    for char in raw:
        if char == " ":
            columns += 1
        elif char == "\t":
            columns += 4 - (columns % 4)
        else:
            break
        if columns >= 4:
            return True
    return False


def blockquote_depth_and_content(raw: str) -> tuple[int, str]:
    """Return active block-quote depth and content after those markers."""
    result = raw
    depth = 0
    while True:
        match = re.match(r"^ {0,3}>[ \t]?", result)
        if match is None:
            return depth, result
        result = result[match.end() :]
        depth += 1


def strip_blockquote_prefixes(raw: str) -> str:
    """Strip active block-quote markers for block-level parsing only."""
    _depth, result = blockquote_depth_and_content(raw)
    return result


def leading_columns(value: str) -> int:
    columns = 0
    for char in value:
        if char == " ":
            columns += 1
        elif char == "\t":
            columns += 4 - (columns % 4)
        else:
            break
    return columns


def strip_indent_columns(value: str, columns: int) -> str:
    """Strip exactly the requested indentation columns, preserving tab residue."""
    current = 0
    index = 0
    while index < len(value) and current < columns:
        char = value[index]
        if char == " ":
            current += 1
            index += 1
            continue
        if char == "\t":
            width = 4 - (current % 4)
            if current + width > columns:
                residual = current + width - columns
                return (" " * residual) + value[index + 1 :]
            current += width
            index += 1
            continue
        break
    return value[index:] if current >= columns else value


def list_item_content(raw: str) -> tuple[int, str] | None:
    match = re.match(r"^ {0,3}(?P<marker>[-+*]|\d{1,9}[.)])(?P<spacing>[ \t]+)", raw)
    if match is None:
        return None
    marker_start = len(raw) - len(raw.lstrip(" "))
    marker_width = len(match.group("marker"))
    column = marker_start + marker_width
    spacing_columns = 0
    for char in match.group("spacing"):
        width = 4 - (column % 4) if char == "\t" else 1
        column += width
        spacing_columns += width
    effective_spacing = spacing_columns if 0 < spacing_columns <= 4 else 1
    content_indent = marker_start + marker_width + effective_spacing
    excess_padding = max(0, spacing_columns - effective_spacing)
    return content_indent, (" " * excess_padding) + raw[match.end() :]


CHARACTER_REFERENCE_RE = re.compile(
    r"&(?:#[xX][0-9A-Fa-f]{1,6}|#[0-9]{1,7}|[A-Za-z][A-Za-z0-9]{0,31});"
)


def decode_character_references(value: str) -> str:
    """Decode only semicolon-terminated CommonMark character references."""
    return CHARACTER_REFERENCE_RE.sub(
        lambda match: html.unescape(match.group(0)),
        value,
    )


def commonmark_unescape(value: str) -> str:
    """Unescape punctuation and strict CommonMark character references."""
    out: list[str] = []
    index = 0
    while index < len(value):
        char = value[index]
        if (
            char == "\\"
            and index + 1 < len(value)
            and value[index + 1] in string.punctuation
        ):
            out.append(value[index + 1])
            index += 2
            continue
        out.append(char)
        index += 1
    return decode_character_references("".join(out))


def inline_html_comment_end(text: str, index: int) -> int | None:
    """Return the end of a valid CommonMark inline HTML comment."""
    if not text.startswith("<!--", index) or is_backslash_escaped(text, index):
        return None
    end = text.find("-->", index + 4)
    if end < 0:
        return None
    body = text[index + 4 : end]
    if body.startswith(">") or body.startswith("->"):
        return None
    if "--" in body or body.endswith("-"):
        return None
    return end + 3


def strip_inline_html_comments(raw: str, in_comment: bool) -> tuple[str, bool]:
    """Strip valid inline HTML comments while preserving invalid/escaped openers."""
    out: list[str] = []
    cursor = 0

    if in_comment:
        end = raw.find("-->")
        if end < 0:
            if "--" in raw:
                return raw, False
            return "", True
        if "--" in raw[:end] or raw[:end].endswith("-"):
            return raw, False
        cursor = end + 3
        in_comment = False

    while cursor < len(raw):
        start = raw.find("<!--", cursor)
        if start < 0:
            out.append(raw[cursor:])
            break
        end = inline_html_comment_end(raw, start)
        if end is None:
            out.append(raw[cursor : start + 1])
            cursor = start + 1
            continue
        out.append(raw[cursor:start])
        cursor = end

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
    if re.match(r"^ {0,3}<!\[CDATA\[", raw):
        return "token", "]] >".replace(" ", "")
    if RAW_HTML_DECLARATION_OPEN_RE.match(raw):
        return "token", ">"
    if RAW_HTML_BLOCK_TAG_RE.match(raw) or RAW_HTML_COMPLETE_TAG_RE.match(raw):
        return "blank", None
    return None


def raw_html_tag_closes(raw: str, tag: str) -> bool:
    """Match CommonMark type-1 block terminators exactly (case-insensitive)."""
    return re.search(rf"</{re.escape(tag)}>", raw, re.IGNORECASE) is not None


def _line_keeps_paragraph_open(raw: str, was_open: bool = False) -> bool:
    """Approximate whether this source line leaves a paragraph open."""
    stripped = raw.strip()
    if not stripped:
        return False
    if re.match(r"^ {0,3}#{1,6}(?:[ \t]|$)", raw):
        return False
    if THEMATIC_BREAK_RE.fullmatch(stripped):
        return False
    if LINK_REFERENCE_DEFINITION_RE.fullmatch(stripped):
        return was_open
    if LIST_MARKER_ONLY_RE.fullmatch(stripped) or stripped == ">":
        return False
    return True


def visible_nonfenced_lines(
    lines: list[str],
    raw_html_text: list[str] | None = None,
    raw_html_source: list[str] | None = None,
) -> list[str]:
    """Return Markdown-visible lines used by schema validation.

    When raw_html_text is supplied, visible text nodes from raw HTML blocks are
    collected separately so callers can inspect rendered HTML text without
    treating it as Markdown structure.
    """
    visible: list[str] = []
    fence_char: str | None = None
    fence_len = 0
    fence_quote_depth = 0
    fence_list_indent = 0
    active_list_indent: int | None = None
    inline_comment = False
    html_mode: str | None = None
    html_end: str | None = None
    html_quote_depth = 0
    html_list_indent = 0
    paragraph_open = False

    def boundary() -> None:
        if not visible or visible[-1] != "":
            visible.append("")

    for raw in lines:
        quote_depth, block_raw = blockquote_depth_and_content(raw)

        if fence_char is not None:
            quote_ended = fence_quote_depth > 0 and quote_depth < fence_quote_depth
            list_ended = (
                fence_list_indent > 0
                and block_raw.strip()
                and leading_columns(block_raw) < fence_list_indent
            )
            if quote_ended or list_ended:
                fence_char = None
                fence_len = 0
                fence_quote_depth = 0
                fence_list_indent = 0
                boundary()
            else:
                paragraph_open = False
                fence_view = (
                    strip_indent_columns(block_raw, fence_list_indent)
                    if fence_list_indent > 0
                    else block_raw
                )
                close = re.fullmatch(
                    rf" {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*",
                    fence_view,
                )
                if close is not None:
                    fence_char = None
                    fence_len = 0
                    fence_quote_depth = 0
                    fence_list_indent = 0
                continue

        if html_mode is not None:
            quote_ended = html_quote_depth > 0 and quote_depth < html_quote_depth
            list_ended = (
                html_list_indent > 0
                and block_raw.strip()
                and leading_columns(block_raw) < html_list_indent
            )
            if quote_ended or list_ended:
                html_mode = None
                html_end = None
                html_quote_depth = 0
                html_list_indent = 0
                boundary()
            else:
                paragraph_open = False
                html_view = (
                    strip_indent_columns(block_raw, html_list_indent)
                    if html_list_indent > 0
                    else block_raw
                )
                if (
                    raw_html_source is not None
                    and html_mode == "tag"
                    and html_end == "pre"
                ):
                    raw_html_source.append(html_view)
                if (
                    raw_html_text is not None
                    and html_mode == "tag"
                    and html_end in {"pre", "textarea"}
                ):
                    rendered_html = strip_inline_html_constructs(html_view)
                    if rendered_html.strip():
                        raw_html_text.append(rendered_html)

                if html_mode == "tag":
                    if html_end is not None and raw_html_tag_closes(html_view, html_end):
                        html_mode = None
                        html_end = None
                        html_quote_depth = 0
                        html_list_indent = 0
                    continue
                if html_mode == "token":
                    if html_end is not None and html_end in html_view:
                        html_mode = None
                        html_end = None
                        html_quote_depth = 0
                        html_list_indent = 0
                    continue
                if html_mode == "blank":
                    if raw_html_source is not None and html_view.strip():
                        raw_html_source.append(html_view)
                    if raw_html_text is not None:
                        rendered_html = strip_inline_html_constructs(html_view)
                        if rendered_html.strip():
                            raw_html_text.append(rendered_html)
                    if html_view.strip() == "":
                        html_mode = None
                        html_end = None
                        html_quote_depth = 0
                        html_list_indent = 0
                        boundary()
                    continue

        was_paragraph_open = paragraph_open

        list_open = list_item_content(block_raw)
        block_view = block_raw
        current_list_indent = active_list_indent
        if list_open is not None:
            current_list_indent, block_view = list_open
            active_list_indent = current_list_indent
        elif active_list_indent is not None:
            if block_raw.strip() and leading_columns(block_raw) >= active_list_indent:
                block_view = strip_indent_columns(block_raw, active_list_indent)
                current_list_indent = active_list_indent
            elif block_raw.strip():
                active_list_indent = None
                current_list_indent = None
        else:
            current_list_indent = None

        if inline_comment:
            rendered, inline_comment = strip_inline_html_comments(raw, True)
            if inline_comment:
                continue
            raw_for_parse = rendered
        else:
            if is_indented_code_line(block_view):
                if not paragraph_open:
                    continue
                raw_for_parse = raw
            else:
                opener = FENCE_OPEN_RE.match(block_view)
                if opener is not None:
                    run = opener.group(1)
                    info = opener.group(2)
                    if run[0] != chr(96) or chr(96) not in info:
                        paragraph_open = False
                        fence_char = run[0]
                        fence_len = len(run)
                        fence_quote_depth = quote_depth
                        fence_list_indent = current_list_indent or 0
                        boundary()
                        continue

                html_start = raw_html_block_start(block_view)
                if html_start is not None:
                    paragraph_open = False
                    boundary()
                    html_mode, html_end = html_start
                    html_quote_depth = quote_depth
                    html_list_indent = current_list_indent or 0
                    if raw_html_source is not None and (
                        html_mode == "blank"
                        or (html_mode == "tag" and html_end == "pre")
                    ):
                        raw_html_source.append(block_view)
                    if raw_html_text is not None and (
                        html_mode == "blank"
                        or (html_mode == "tag" and html_end in {"pre", "textarea"})
                    ):
                        rendered_html = strip_inline_html_constructs(block_view)
                        if rendered_html.strip():
                            raw_html_text.append(rendered_html)
                    if (
                        html_mode == "tag"
                        and html_end is not None
                        and raw_html_tag_closes(block_view, html_end)
                    ):
                        html_mode = None
                        html_end = None
                        html_quote_depth = 0
                        html_list_indent = 0
                    elif (
                        html_mode == "token"
                        and html_end is not None
                        and html_end in block_view
                    ):
                        html_mode = None
                        html_end = None
                        html_quote_depth = 0
                        html_list_indent = 0
                    continue

                raw_for_parse, inline_comment = strip_inline_html_comments(raw, False)

        parse_view = strip_blockquote_prefixes(raw_for_parse)
        if current_list_indent is not None and list_item_content(parse_view) is None:
            if leading_columns(parse_view) >= current_list_indent:
                parse_view = strip_indent_columns(parse_view, current_list_indent)

        if (
            raw_for_parse
            and is_indented_code_line(parse_view)
            and not was_paragraph_open
        ):
            continue

        if raw_for_parse:
            visible.append(raw_for_parse)
            if is_indented_code_line(parse_view) and was_paragraph_open:
                paragraph_open = True
            else:
                paragraph_open = _line_keeps_paragraph_open(
                    parse_view, was_paragraph_open
                )
        elif not inline_comment and raw == "":
            boundary()
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


def normalized_visible_heading(line: str) -> str | None:
    """Return a rendered ATX heading identity while preserving its level."""
    match = re.match(r"^(?P<hashes>#{1,6})(?:[ \t]+|$)(?P<body>.*)$", line)
    if match is None:
        return None

    body = match.group("body")
    body = re.sub(r"[ \t]+#+[ \t]*$", "", body)
    rendered = rendered_inline_text(body).strip()
    return f"{match.group('hashes')} {rendered}" if rendered else match.group("hashes")


def section_lines(text: str, heading: str) -> list[str]:
    """Return one exact rendered level-2 Markdown section."""
    lines = visible_nonfenced_lines(markdown_source_lines(text))
    start = next(
        (
            index + 1
            for index, line in enumerate(lines)
            if normalized_visible_heading(line) == heading
        ),
        None,
    )
    if start is None:
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
        if text[i] == "<":
            html_end = inline_html_construct_end(text, i)
            if html_end is not None:
                i = html_end
                continue
        if text[i] == "[":
            depth += 1
        elif text[i] == "]":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return None


def skip_inline_link_whitespace(text: str, index: int) -> int | None:
    """Skip spaces/tabs and at most one line ending; reject blank lines."""
    i = index
    saw_newline = False
    while i < len(text):
        if text[i] in " \t":
            i += 1
            continue
        if text[i] == "\n":
            if saw_newline:
                return None
            saw_newline = True
            i += 1
            continue
        break
    return i


def parse_link_title_and_close(text: str, index: int) -> int | None:
    """Parse whitespace plus an optional CommonMark-style title and outer close."""
    skipped = skip_inline_link_whitespace(text, index)
    if skipped is None:
        return None
    i = skipped

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
            probe = i + 1
            while probe < len(text) and text[probe] in " \t":
                probe += 1
            if probe < len(text) and text[probe] == "\n":
                return None
            i += 1
            continue
        i += 1
    else:
        return None

    skipped = skip_inline_link_whitespace(text, i)
    if skipped is None:
        return None
    i = skipped
    if i < len(text) and text[i] == ")":
        return i + 1
    return None


def find_inline_link_end(text: str, open_paren: int) -> int | None:
    """Return the end of a valid inline-link destination/title, or None."""
    skipped = skip_inline_link_whitespace(text, open_paren + 1)
    if skipped is None:
        return None
    i = skipped

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


def inline_link_destination(text: str, open_paren: int) -> str | None:
    """Return a valid inline-link destination, honoring CommonMark whitespace."""
    end = find_inline_link_end(text, open_paren)
    if end is None:
        return None

    skipped = skip_inline_link_whitespace(text, open_paren + 1)
    if skipped is None:
        return None
    i = skipped

    if i >= len(text) or text[i] == ")":
        return ""

    if text[i] == "<":
        start = i + 1
        i = start
        while i < len(text):
            if text[i] == "\\" and i + 1 < len(text):
                i += 2
                continue
            if text[i] == ">":
                return text[start:i]
            i += 1
        return None

    start = i
    depth = 0
    while i < len(text):
        char = text[i]
        if char == "\\" and i + 1 < len(text):
            i += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return text[start:i]
            depth -= 1
        elif char in " \t\n" and depth == 0:
            return text[start:i]
        i += 1
    return None


def inline_html_crosses_paragraph_boundary(text: str, start: int, end: int) -> bool:
    """Return whether a candidate inline HTML construct crosses a blank line."""
    return re.search(r"(?:\r\n|\r|\n)[ \t]*(?:\r\n|\r|\n)", text[start:end]) is not None


def inline_html_construct_end(text: str, index: int) -> int | None:
    """Return end of one rendered-inline-HTML source construct within one paragraph."""
    if index >= len(text) or text[index] != "<" or is_backslash_escaped(text, index):
        return None

    end: int | None = None
    if text.startswith("<!--", index):
        end = inline_html_comment_end(text, index)
    elif text.startswith("<?", index):
        close = text.find("?>", index + 2)
        end = None if close < 0 else close + 2
    elif text.startswith("<![CDATA[", index):
        close = text.find("]]>", index + 9)
        end = None if close < 0 else close + 3
    elif re.match(r"<![A-Z]", text[index:]):
        close = text.find(">", index + 2)
        end = None if close < 0 else close + 1
    else:
        match = INLINE_HTML_TAG_RE.match(text, index)
        end = match.end() if match is not None else None

    if end is None or inline_html_crosses_paragraph_boundary(text, index, end):
        return None
    return end


def strip_inline_html_constructs(text: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        end = inline_html_construct_end(text, index)
        if end is not None:
            index = end
            continue
        out.append(text[index])
        index += 1
    return "".join(out)


def rendered_record_label(value: str) -> str:
    """Render the narrow inline subset allowed for record IDs."""
    stripped = value.strip()
    protected_text, protected = protect_code_spans(stripped)
    if len(protected_text) == 1 and protected_text in protected:
        code_text = protected[protected_text].replace("\n", " ")
        if (
            len(code_text) >= 2
            and code_text.startswith(" ")
            and code_text.endswith(" ")
            and code_text.strip()
        ):
            code_text = code_text[1:-1]
        return code_text

    return rendered_inline_text(stripped)


def visible_record_links(text: str) -> list[tuple[str, str]]:
    """Return rendered OPT-labelled inline links with parsed destinations."""
    links: list[tuple[str, str]] = []
    i = 0
    while i < len(text):
        if text[i] == "<":
            html_end = inline_html_construct_end(text, i)
            if html_end is not None:
                i = html_end
                continue
        if text[i] != "[" or is_backslash_escaped(text, i):
            i += 1
            continue
        if (
            i > 0
            and text[i - 1] == "!"
            and not is_backslash_escaped(text, i - 1)
        ):
            image_label_close = find_label_close(text, i)
            if (
                image_label_close is not None
                and image_label_close + 1 < len(text)
                and text[image_label_close + 1] == "("
            ):
                image_end = find_inline_link_end(text, image_label_close + 1)
                if image_end is not None:
                    i = image_end
                    continue
            i += 1
            continue

        label_close = find_label_close(text, i)
        if (
            label_close is None
            or label_close + 1 >= len(text)
            or text[label_close + 1] != "("
        ):
            i += 1
            continue

        raw_label = text[i + 1 : label_close]
        rendered_label = rendered_record_label(raw_label)
        if not re.fullmatch(r"OPT-[A-Z]+-\d{3}", rendered_label):
            i += 1
            continue

        destination = inline_link_destination(text, label_close + 1)
        if destination is None:
            i += 1
            continue

        links.append((rendered_label, commonmark_unescape(destination)))
        link_end = find_inline_link_end(text, label_close + 1)
        i = link_end if link_end is not None else label_close + 1

    return links


HTML_HREF_RE = re.compile(
    r"""(?:^|[ \t\r\n])href[ \t\r\n]*=[ \t\r\n]*(?:"([^"]*)"|'([^']*)'|([^ \t\r\n"'=<>\x60]+))""",
    re.IGNORECASE,
)


def html_anchor_hrefs(text: str) -> list[str]:
    """Return decoded href values from syntactically valid HTML anchor start tags."""
    hrefs: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("<", index)
        if start < 0:
            break
        tag = INLINE_HTML_TAG_RE.match(text, start)
        if tag is None:
            index = start + 1
            continue
        tag_source = tag.group(0)
        if re.match(r"<a(?:[ \t\r\n]|>)", tag_source, re.IGNORECASE):
            href_match = HTML_HREF_RE.search(tag_source)
            if href_match is not None:
                href = next(value for value in href_match.groups() if value is not None)
                hrefs.append(html.unescape(href))
        index = tag.end()
    return hrefs


def visible_html_record_links(text: str) -> list[tuple[str, str]]:
    """Return OPT-labelled visible raw-HTML anchors and decoded href targets."""
    links: list[tuple[str, str]] = []
    index = 0
    while index < len(text):
        start = text.find("<", index)
        if start < 0:
            break

        tag = INLINE_HTML_TAG_RE.match(text, start)
        if tag is None:
            index = start + 1
            continue

        tag_source = tag.group(0)
        if re.match(r"<a(?:[ \t\r\n]|>)", tag_source, re.IGNORECASE) is None:
            index = tag.end()
            continue

        href_match = HTML_HREF_RE.search(tag_source)
        if href_match is None:
            index = tag.end()
            continue
        href = next(
            value for value in href_match.groups() if value is not None
        )

        close = re.search(r"</a[ \t\r\n]*>", text[tag.end() :], re.IGNORECASE)
        if close is None:
            index = tag.end()
            continue

        label_start = tag.end()
        label_end = tag.end() + close.start()
        rendered_label = rendered_inline_text(text[label_start:label_end])
        if re.fullmatch(r"OPT-[A-Z]+-\d{3}", rendered_label):
            links.append((rendered_label, html.unescape(href)))

        index = tag.end() + close.end()

    return links


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
    """Split a GFM pipe table on every unescaped pipe delimiter."""
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

        if char == "|":
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
    value = unwrap_markdown_emphasis(cell).strip()
    if not value.startswith("["):
        die(f"{context} has invalid record-link cell: {cell}")

    label_close = find_label_close(value, 0)
    if (
        label_close is None
        or label_close + 1 >= len(value)
        or value[label_close + 1] != "("
    ):
        die(f"{context} has invalid record-link cell: {cell}")

    link_end = find_inline_link_end(value, label_close + 1)
    if link_end is None or link_end != len(value):
        die(f"{context} has invalid record-link cell: {cell}")

    rendered_label = rendered_record_label(value[1:label_close])
    if re.fullmatch(r"OPT-[A-Z]+-\d{3}", rendered_label) is None:
        die(f"{context} has invalid record-link label: {cell}")

    destination = inline_link_destination(value, label_close + 1)
    if destination is None:
        die(f"{context} has invalid record-link destination: {cell}")

    destination = commonmark_unescape(destination)
    rel, _separator, _fragment = destination.partition("#")
    if not rel.startswith("optimizations/") or not rel.endswith(".md"):
        die(f"{context} has invalid record-link destination: {cell}")
    return rendered_label, rel


def strip_paired_inline_formatting(text: str) -> str:
    """Remove paired inline formatting delimiters while preserving unmatched ones."""
    patterns = (
        re.compile(r"\*\*(?=\S)(.+?\S)\*\*"),
        re.compile(r"__(?=\S)(.+?\S)__"),
        re.compile(r"~~(?=\S)(.+?\S)~~"),
        re.compile(r"\*(?=\S)(.+?\S)\*"),
        re.compile(r"_(?=\S)(.+?\S)_"),
    )
    previous = None
    while text != previous:
        previous = text
        for pattern in patterns:
            text = pattern.sub(lambda match: match.group(1), text)
    return text


def rendered_inline_text(value: str) -> str:
    """Approximate rendered inline text for required field-value validation."""
    text, protected_code = protect_code_spans(value)
    text = strip_inline_links(text)
    text = REFERENCE_IMAGE_RE.sub(lambda m: m.group(1), text)
    text = REFERENCE_LINK_RE.sub(lambda m: m.group(1), text)
    text = strip_inline_html_constructs(text)
    text = strip_paired_inline_formatting(text)
    text = commonmark_unescape(text)
    for token, code_text in protected_code.items():
        text = text.replace(token, code_text)
    return text.strip()


def decode_visible_character_references(text: str) -> str:
    protected_text, protected_code = protect_code_spans(text)
    protected_text = decode_character_references(protected_text)
    for token, code_text in protected_code.items():
        protected_text = protected_text.replace(token, code_text)
    return protected_text


def commonmark_unescape_outside_code_spans(value: str) -> str:
    """Decode rendered escapes/references without decoding code-span contents."""
    protected_text, protected_code = protect_code_spans(value)
    rendered = commonmark_unescape(protected_text)
    for token, code_text in protected_code.items():
        rendered = rendered.replace(token, code_text)
    return rendered


def has_substantive_rendered_text(value: str) -> bool:
    return any(ch.isalnum() for ch in rendered_inline_text(value))


def _parse_reference_definition_destination(value: str) -> tuple[str, str] | None:
    source = value.lstrip(" \t")
    if not source:
        return None
    if source.startswith("<"):
        end = source.find(">", 1)
        if end < 0 or "<" in source[1:end]:
            return None
        return source[1:end], source[end + 1 :]
    index = 0
    depth = 0
    while index < len(source):
        char = source[index]
        if char == "\\" and index + 1 < len(source):
            index += 2
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                break
            depth -= 1
        elif char in " \t" and depth == 0:
            break
        elif char in "<>" or ord(char) < 0x20:
            return None
        index += 1
    if index == 0 or depth != 0:
        return None
    return source[:index], source[index:]


def _reference_title_complete(value: str) -> bool:
    value = value.strip()
    if len(value) < 2 or value[0] not in ('"', "'", "("):
        return False
    closer = ")" if value[0] == "(" else value[0]
    if value[-1] != closer:
        return False
    inner = value[1:-1]
    escaped = False
    for char in inner:
        if escaped:
            escaped = False
        elif char == "\\":
            escaped = True
        elif char == closer:
            return False
    return True


def normalized_reference_label(label: str) -> str:
    """Apply CommonMark-style case/whitespace normalization to a reference label."""
    return " ".join(commonmark_unescape(label).split()).casefold()


def reference_definition_scan(lines: list[str]) -> tuple[set[int], dict[str, str]]:
    """Return hidden definition indexes and their first rendered destinations."""
    hidden: set[int] = set()
    destinations: dict[str, str] = {}
    prefix_re = re.compile(
        r"^ {0,3}\[(?P<label>(?:\\.|[^\[\]\\])+)\]:[ \t]*(?P<rest>.*)$"
    )
    index = 0
    paragraph_open = False

    while index < len(lines):
        raw = lines[index]
        if not raw.strip():
            paragraph_open = False
            index += 1
            continue

        match = prefix_re.fullmatch(raw)
        if match is None or paragraph_open or len(match.group("label")) > 999:
            paragraph_open = _line_keeps_paragraph_open(raw, paragraph_open)
            index += 1
            continue

        rest = match.group("rest")
        consumed = 1
        hidden_indexes = [index]

        if not rest:
            if (
                index + consumed < len(lines)
                and re.match(r"^ {1,3}\S", lines[index + consumed])
            ):
                rest = lines[index + consumed].lstrip(" ")
                hidden_indexes.append(index + consumed)
                consumed += 1
            else:
                paragraph_open = True
                index += 1
                continue

        parsed = _parse_reference_definition_destination(rest)
        if parsed is None:
            paragraph_open = True
            index += 1
            continue

        destination, tail = parsed
        title = tail.strip()
        if title:
            while not _reference_title_complete(title):
                if (
                    index + consumed >= len(lines)
                    or not re.match(r"^ {1,3}\S", lines[index + consumed])
                ):
                    hidden_indexes = []
                    break
                title += "\n" + lines[index + consumed].lstrip(" ")
                hidden_indexes.append(index + consumed)
                consumed += 1
            if not hidden_indexes:
                paragraph_open = True
                index += 1
                continue
        elif (
            index + consumed < len(lines)
            and re.match(r"^ {1,3}[\"'(]", lines[index + consumed])
        ):
            title = lines[index + consumed].lstrip(" ")
            hidden_indexes.append(index + consumed)
            consumed += 1
            while not _reference_title_complete(title):
                if (
                    index + consumed >= len(lines)
                    or not re.match(r"^ {1,3}\S", lines[index + consumed])
                ):
                    hidden_indexes = []
                    break
                title += "\n" + lines[index + consumed].lstrip(" ")
                hidden_indexes.append(index + consumed)
                consumed += 1
            if not hidden_indexes:
                paragraph_open = True
                index += 1
                continue

        hidden.update(hidden_indexes)
        destinations.setdefault(
            normalized_reference_label(match.group("label")),
            commonmark_unescape(destination),
        )
        paragraph_open = False
        index += consumed

    return hidden, destinations


def reference_definition_hidden_indexes(lines: list[str]) -> set[int]:
    return reference_definition_scan(lines)[0]


def reference_definition_destinations(lines: list[str]) -> dict[str, str]:
    return reference_definition_scan(lines)[1]


def used_reference_labels(text: str) -> set[str]:
    """Return rendered reference labels used by full, collapsed, or shortcut links."""
    labels: set[str] = set()
    protected_text, _protected_code = protect_code_spans(text)
    i = 0
    while i < len(protected_text):
        if protected_text[i] == "<":
            html_end = inline_html_construct_end(protected_text, i)
            if html_end is not None:
                i = html_end
                continue
        if protected_text[i] != "[" or is_backslash_escaped(protected_text, i):
            i += 1
            continue
        if (
            i > 0
            and protected_text[i - 1] == "!"
            and not is_backslash_escaped(protected_text, i - 1)
        ):
            i += 1
            continue

        label_close = find_label_close(protected_text, i)
        if label_close is None:
            i += 1
            continue

        label = protected_text[i + 1 : label_close]
        after = label_close + 1

        if after < len(protected_text) and protected_text[after] == "(":
            link_end = find_inline_link_end(protected_text, after)
            i = link_end if link_end is not None else after + 1
            continue

        if after < len(protected_text) and protected_text[after] == "[":
            reference_close = find_label_close(protected_text, after)
            if reference_close is not None:
                reference = protected_text[after + 1 : reference_close] or label
                labels.add(normalized_reference_label(reference))
                i = reference_close + 1
                continue

        labels.add(normalized_reference_label(label))
        i = label_close + 1

    return labels


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


def source_commit_has_context(line: str, match: re.Match[str]) -> bool:
    prefix = line[max(0, match.start() - 80) : match.start()]
    cleaned = prefix.rstrip(" \t`*_~([{<")
    return SOURCE_COMMIT_CONTEXT_RE.search(cleaned) is not None


def inline_link_destinations(text: str) -> list[str]:
    """Return destinations of valid inline links, excluding images and titles."""
    destinations: list[str] = []
    i = 0
    while i < len(text):
        if text[i] == "<":
            html_end = inline_html_construct_end(text, i)
            if html_end is not None:
                i = html_end
                continue
        if text[i] != "[" or is_backslash_escaped(text, i):
            i += 1
            continue
        if (
            i > 0
            and text[i - 1] == "!"
            and not is_backslash_escaped(text, i - 1)
        ):
            i += 1
            continue

        label_close = find_label_close(text, i)
        if (
            label_close is None
            or label_close + 1 >= len(text)
            or text[label_close + 1] != "("
        ):
            i += 1
            continue

        destination = inline_link_destination(text, label_close + 1)
        link_end = find_inline_link_end(text, label_close + 1)
        if destination is not None and link_end is not None:
            destinations.append(commonmark_unescape(destination))
            i = link_end
            continue
        i += 1
    return destinations


def valid_http_source_url(value: str) -> bool:
    """Require an absolute HTTP(S) URL with a syntactically valid host."""
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
    except ValueError:
        return False

    if parsed.scheme.lower() not in {"http", "https"} or not host:
        return False

    try:
        ipaddress.ip_address(host)
        return True
    except ValueError:
        pass

    if len(host) > 253:
        return False
    labels = host.rstrip(".").split(".")
    return bool(labels) and all(
        label
        and len(label) <= 63
        and label[0].isalnum()
        and label[-1].isalnum()
        and all(char.isalnum() or char == "-" for char in label)
        for label in labels
    )


def source_text_has_identity(line: str, sources_root: Path) -> bool:
    if any(valid_http_source_url(match.group(0)) for match in SOURCE_URL_RE.finditer(line)):
        return True
    if SOURCE_DOI_RE.search(line):
        return True
    if any(
        source_commit_has_context(line, match)
        for match in SOURCE_COMMIT_RE.finditer(line)
    ):
        return True
    for match in SOURCE_LOCAL_NOTE_RE.finditer(line):
        candidate = (ROOT / match.group(1)).resolve()
        try:
            candidate.relative_to(sources_root)
        except ValueError:
            continue
        if candidate.is_file():
            return True
    return SOURCE_REPOSITORY_RE.search(line) is not None


def source_section_has_identity(lines: list[str]) -> bool:
    """Require at least one concrete, rendered provenance identity."""
    sources_root = (ROOT / "sources").resolve()
    visible = visible_nonfenced_lines(lines)
    hidden_reference_lines, destinations = reference_definition_scan(visible)

    rendered_source_lines: list[str] = []
    for index, raw in enumerate(visible):
        if index in hidden_reference_lines:
            continue

        raw_source = raw.strip()
        html_destinations = html_anchor_hrefs(raw_source)
        source = strip_inline_html_constructs(raw_source)
        destinations_inline = inline_link_destinations(source)
        visible_source = strip_inline_links(source)
        line = commonmark_unescape_outside_code_spans(visible_source)

        if not line or SOURCE_PLACEHOLDER_RE.fullmatch(line):
            continue
        rendered_source_lines.append(source)
        if source_text_has_identity(line, sources_root):
            return True
        for destination in (*html_destinations, *destinations_inline):
            rendered_destination = commonmark_unescape_outside_code_spans(destination)
            if source_text_has_identity(rendered_destination, sources_root):
                return True

    used_labels = used_reference_labels("\n".join(rendered_source_lines))
    for label in used_labels:
        destination = destinations.get(label)
        if destination is None:
            continue
        rendered_destination = commonmark_unescape_outside_code_spans(destination)
        if source_text_has_identity(rendered_destination, sources_root):
            return True

    return False


def status_category_source(raw: str) -> str:
    """Return the status category before a real caveat separator."""
    index = 0
    code_run_len: int | None = None
    while index < len(raw):
        char = raw[index]

        if char == "`" and not is_backslash_escaped(raw, index):
            run_len = backtick_run_length(raw, index)
            if code_run_len is None:
                code_run_len = run_len
            elif run_len == code_run_len:
                code_run_len = None
            index += run_len
            continue

        if code_run_len is not None:
            index += 1
            continue

        if char == "\\" and index + 1 < len(raw):
            index += 2
            continue

        if char == "&":
            reference = CHARACTER_REFERENCE_RE.match(raw, index)
            if reference is not None:
                index = reference.end()
                continue

        if char == ";":
            return raw[:index]
        index += 1
    return raw


def normalized_status_category(raw: str) -> str:
    category = status_category_source(raw).strip()
    return rendered_inline_text(category).strip()


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
            normalized_value = rendered_inline_text(value).rstrip(" \t.!?")
            rejected_value = rejected_values.get(field)
            if (
                rejected_value is not None
                and normalized_value == rejected_value.rstrip(" \t.!?")
            ):
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

    status_category = normalized_status_category(statuses[0])
    if status_category not in ALLOWED_V2_STATUS_CATEGORIES:
        die(
            f"{path.relative_to(ROOT)} uses undefined status category "
            f"'{status_category}'"
        )
    status_categories[record_id] = status_category

    headings = {
        rendered
        for line in lines
        if (rendered := normalized_visible_heading(line)) is not None
        and rendered.startswith("## ")
    }
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


HTML_ANCHOR_ID_RE = re.compile(
    r"""(?:^|[ \t\r\n])(?:id|name)[ \t\r\n]*=[ \t\r\n]*(?:"([^"]+)"|'([^']+)'|([^ \t\r\n"'=<>\x60]+))""",
    re.IGNORECASE,
)


def github_heading_slug(value: str) -> str:
    """Approximate GitHub's rendered heading fragment for repository headings."""
    value = rendered_inline_text(value).strip().casefold()
    value = re.sub(r"[^\w\- ]+", "", value, flags=re.UNICODE)
    value = re.sub(r"[ \t\r\n]+", "-", value)
    return value


def record_fragment_ids(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    anchors: set[str] = set()
    slug_counts: Counter[str] = Counter()

    for line in visible_nonfenced_lines(markdown_source_lines(text)):
        heading = normalized_visible_heading(line)
        if heading is None:
            continue
        match = re.match(r"^#{1,6}(?:[ \t]+|$)(?P<body>.*)$", heading)
        if match is None:
            continue
        slug = github_heading_slug(match.group("body"))
        if not slug:
            continue
        count = slug_counts[slug]
        slug_counts[slug] += 1
        anchors.add(slug if count == 0 else f"{slug}-{count}")

    for tag in INLINE_HTML_TAG_RE.finditer(text):
        source = tag.group(0)
        for match in HTML_ANCHOR_ID_RE.finditer(source):
            anchor = next(value for value in match.groups() if value is not None)
            anchors.add(html.unescape(anchor))

    return anchors


record_fragment_cache: dict[Path, set[str]] = {}


def validate_record_fragment(
    target: Path, fragment: str, *, doc_name: str, destination: str
) -> None:
    if not fragment:
        return
    decoded = unquote(fragment)
    anchors = record_fragment_cache.setdefault(target, record_fragment_ids(target))
    if decoded not in anchors:
        die(
            f"broken visible record fragment in {doc_name}: "
            f"{destination} (missing '#{decoded}')"
        )


for doc_name in ("README.md", "CATALOG.md"):
    text = (ROOT / doc_name).read_text(encoding="utf-8")
    raw_html_source: list[str] = []
    rendered = "\n".join(
        visible_nonfenced_lines(
            markdown_source_lines(text),
            raw_html_source=raw_html_source,
        )
    )
    record_links = visible_record_links(rendered)
    record_links.extend(visible_html_record_links(rendered))
    record_links.extend(visible_html_record_links("\n".join(raw_html_source)))
    for label, destination in record_links:
        rel, separator, fragment = destination.partition("#")
        if not rel.startswith("optimizations/") or not rel.endswith(".md"):
            die(
                f"visible record link in {doc_name} has invalid destination: "
                f"{destination}"
            )
        target = ROOT / rel
        if not target.is_file():
            die(f"broken visible record link in {doc_name}: {rel}")
        target_id = record_paths.get(rel)
        if target_id is None:
            die(f"record link in {doc_name} is not a discovered OPT record: {rel}")
        if rendered_record_label(label) != target_id:
            die(
                f"record link label mismatch in {doc_name}: '{label}' points to "
                f"{target_id} ({rel})"
            )
        if separator:
            validate_record_fragment(
                target,
                fragment,
                doc_name=doc_name,
                destination=destination,
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
catalog_html_text: list[str] = []
visible_catalog = "\n".join(
    visible_nonfenced_lines(
        markdown_source_lines(catalog),
        raw_html_text=catalog_html_text,
    )
)
visible_catalog = strip_inline_html_constructs(visible_catalog)
previous_catalog = None
while visible_catalog != previous_catalog:
    previous_catalog = visible_catalog
    visible_catalog = strip_inline_links(visible_catalog)
visible_catalog = decode_visible_character_references(visible_catalog)

visible_html_catalog = decode_visible_character_references(
    "\n".join(catalog_html_text)
)
catalog_ids = set(OPT_TOKEN_RE.findall(visible_catalog))
catalog_ids.update(OPT_TOKEN_RE.findall(visible_html_catalog))
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
canonical_text = "\n".join(rendered_inline_text(line) for line in canonical)
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
