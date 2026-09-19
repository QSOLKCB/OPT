#!/usr/bin/env python3
"""Check OPT catalog/document integrity without external dependencies."""

from __future__ import annotations

import html
import ipaddress
from html.entities import html5 as HTML5_ENTITIES
import posixpath
import re
import string
import unicodedata
from collections import Counter
from pathlib import Path, PurePath
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
ID_RE = re.compile(r"^# (OPT-[A-Z]+-\d{3}) — (?P<title>.*)$")
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
SOURCE_URL_RE = re.compile(r"https?://[^\s<>]+", re.IGNORECASE)
SOURCE_DOI_RE = re.compile(r"\b(?:doi:\s*)?10\.\d{4,9}/\S+", re.IGNORECASE)
SOURCE_COMMIT_RE = re.compile(r"\b[0-9a-f]{7,40}\b", re.IGNORECASE)
SOURCE_COMMIT_CONTEXT_RE = re.compile(
    r"(?:"
    r"\b(?:commit(?:[ \t]+sha)?|sha|revision|rev)\b[^0-9A-Za-z]{0,12}"
    r"|\b(?:pinned|inspected)[ \t]+at\b[^0-9A-Za-z]{0,12}"
    r")$",
    re.IGNORECASE,
)
SOURCE_LOCAL_NOTE_RE = re.compile(
    r"(?<![A-Za-z0-9_./-])`?(sources/[A-Za-z0-9._/-]+\.md)`?"
    r"(?![A-Za-z0-9_./-])"
)
SOURCE_REPOSITORY_RE = re.compile(
    r"`(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)`"
)
SOURCE_REPOSITORY_CONTEXT_RE = re.compile(
    r"\brepository\s*:\s*"
    r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)\b",
    re.IGNORECASE,
)
SOURCE_REPOSITORY_PLACEHOLDERS = {
    "n/a",
    "na",
    "none",
    "unknown",
    "tbd",
    "todo",
    "pending",
}
SOURCE_PLACEHOLDER_RE = re.compile(
    r"^(?:[-*+]\s*)?(?:unknown|tbd|todo|n/?a|none|pending)(?:[.!?])?$",
    re.IGNORECASE,
)
REFERENCE_IMAGE_RE = re.compile(r"!\[([^\]]*)\]\[[^\]]*\]")
REFERENCE_LINK_RE = re.compile(r"\[([^\]]*)\]\[[^\]]*\]")
HTML_ALT_ATTR_RE = re.compile(
    r"""(?:^|[ \t\r\n])alt[ \t\r\n]*=[ \t\r\n]*(?:"([^"]*)"|'([^']*)'|([^ \t\r\n"'=<>\x60]+))""",
    re.IGNORECASE,
)
INLINE_HTML_TAG_RE = re.compile(
    r"</?[A-Za-z][A-Za-z0-9-]*"
    r"(?:[ \t\r\n]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t\r\n]*=[ \t\r\n]*(?:\"[^\"]*\"|'[^']*'|[^ \t\r\n\"'=<>\x60]+))?)*"
    r"[ \t\r\n]*/?>"
)
NONRENDERING_HTML_OPEN_RE = re.compile(
    r"<(?P<tag>script|style|template|head|title|iframe)(?:[ \t\r\n/>]|$)",
    re.IGNORECASE,
)
HTML_HIDDEN_ATTR_RE = re.compile(
    r"(?:^|[ \t\r\n])hidden"
    r"(?:[ \t\r\n]*=[ \t\r\n]*(?:\"[^\"]*\"|'[^']*'|[^ \t\r\n\"'=<>\x60]+))?"
    r"(?=[ \t\r\n/>]|$)",
    re.IGNORECASE,
)
NONRENDERING_HTML_TAGS = {
    "script", "style", "template", "head", "title", "iframe",
}
HTML_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

# HTML in-body start tags whose processing closes a p in button scope.
HTML_IMPLICIT_CLOSE_STARTS = {
    "p": {
        "address", "article", "aside", "blockquote", "center", "details",
        "dialog", "dir", "div", "dl", "fieldset", "figcaption", "figure",
        "footer", "form", "h1", "h2", "h3", "h4", "h5", "h6", "header",
        "hgroup", "hr", "li", "dt", "dd", "listing", "main", "menu", "nav",
        "ol", "p", "plaintext", "pre", "search", "section", "summary",
        "table", "ul", "xmp",
    },
    "li": {"li"},
    "dt": {"dt", "dd"},
    "dd": {"dt", "dd"},
    "rt": {"rt", "rp"},
    "rp": {"rt", "rp"},
    "option": {"option", "optgroup"},
    "optgroup": {"optgroup"},
    "thead": {"tbody", "tfoot"},
    "tbody": {"tbody", "tfoot"},
    "tfoot": {"tbody"},
    "tr": {"tr"},
    "td": {"td", "th"},
    "th": {"td", "th"},
}
HTML_SCOPE_BOUNDARIES = {
    "applet", "caption", "html", "table", "td", "th", "marquee",
    "object", "template",
}
HTML_RAW_TEXT_ELEMENTS = {"script", "style", "title", "iframe", "textarea", "xmp"}


def html_start_tag_name(source: str) -> str | None:
    match = re.match(r"<(?P<tag>[A-Za-z][A-Za-z0-9-]*)", source)
    return match.group("tag").lower() if match is not None else None


def html_start_implicitly_closes(open_tag: str, source: str) -> bool:
    """Return whether this parsed start tag implicitly closes the open element."""
    new_tag = html_start_tag_name(source)
    return bool(
        new_tag is not None
        and new_tag in HTML_IMPLICIT_CLOSE_STARTS.get(open_tag, set())
    )


class HTMLVisibilityState:
    """Keep element ancestry across chunks, including visible scope boundaries.

    A parent close removes only its own subtree. In particular, an inner ul/ol
    cannot close an outer hidden li, and closing a p cannot remove a hidden div.
    """

    def __init__(self) -> None:
        self.elements: list[tuple[str, bool]] = []

    @property
    def hidden(self) -> bool:
        return any(hidden for _tag, hidden in self.elements)

    def close_for_start(self, source: str) -> None:
        new_tag = html_start_tag_name(source)
        if new_tag is None:
            return

        # A button start tag closes an earlier button when that button is in
        # scope before the new element is inserted.
        if new_tag == "button":
            for index in range(len(self.elements) - 1, -1, -1):
                tag, _hidden = self.elements[index]
                if tag == "button":
                    del self.elements[index:]
                    break
                if tag in HTML_SCOPE_BOUNDARIES:
                    break

        # More than one optional element can close, e.g. p inside an old li.
        while True:
            changed = False
            for index in range(len(self.elements) - 1, -1, -1):
                tag, _hidden = self.elements[index]
                if not html_start_implicitly_closes(tag, source):
                    continue
                above = {name for name, _ in self.elements[index + 1 :]}
                boundaries = set(HTML_SCOPE_BOUNDARIES)
                if tag == "p":
                    boundaries.add("button")
                elif tag in {"li", "dt", "dd"}:
                    boundaries.update({"ul", "ol", "menu", "dl"})
                elif tag in {"option", "optgroup"}:
                    boundaries.add("select")
                elif tag in {"rt", "rp"}:
                    boundaries.add("ruby")
                if above & boundaries:
                    continue
                del self.elements[index:]
                changed = True
                break
            if not changed:
                return

    def close(self, tag: str) -> None:
        for index in range(len(self.elements) - 1, -1, -1):
            current_tag = self.elements[index][0]
            if current_tag == tag:
                del self.elements[index:]
                return
            if current_tag in HTML_SCOPE_BOUNDARIES:
                return


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
    "X": re.compile(r"^- `X` — (?P<body>.*)$"),
    "F": re.compile(r"^- `F(?: ⊆ X)?` — (?P<body>.*)$"),
    "f": re.compile(r"^- `f(?:\s*:[^`]*)?` — (?P<body>.*)$"),
    "d": re.compile(r"^- `d` — (?P<body>.*)$"),
    "C": re.compile(r"^- `C` — (?P<body>.*)$"),
    "B": re.compile(r"^- `B` — (?P<body>.*)$"),
    "S": re.compile(r"^- `S` — (?P<body>.*)$"),
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


def strip_nonrendering_html_regions(
    text: str,
    hidden_state: HTMLVisibilityState | None,
    *,
    honor_backslash_escapes: bool,
) -> tuple[str, HTMLVisibilityState | None]:
    """Filter hidden subtrees while retaining ancestry needed for implicit closes."""
    state = hidden_state if hidden_state is not None else HTMLVisibilityState()
    out: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("<", index)
        if start < 0:
            if not state.hidden:
                out.append(text[index:])
            break
        if not state.hidden:
            out.append(text[index:start])
        token = INLINE_HTML_TAG_RE.match(text, start)
        if token is None:
            if not state.hidden:
                out.append("<")
            index = start + 1
            continue
        source = token.group(0)
        index = token.end()
        if honor_backslash_escapes and is_backslash_escaped(text, start):
            if not state.hidden:
                out.append(source)
            continue
        end = re.match(r"</([A-Za-z][A-Za-z0-9-]*)(?:[ \t\r\n/>]|$)", source)
        end_tag = end.group(1).lower() if end is not None else None
        if state.elements and state.elements[-1][0] in HTML_RAW_TEXT_ELEMENTS:
            raw_tag = state.elements[-1][0]
            if end_tag == raw_tag:
                was_hidden = state.hidden
                state.elements.pop()
                if not was_hidden:
                    out.append(source)
            elif not state.hidden:
                out.append(
                    source.replace("<", "&lt;").replace(">", "&gt;")
                )
            continue
        if end_tag is not None:
            was_hidden = state.hidden
            state.close(end_tag)
            if not was_hidden or not state.hidden:
                out.append(source)
            continue
        tag = html_start_tag_name(source)
        if tag is None:
            if not state.hidden:
                out.append(source)
            continue
        state.close_for_start(source)
        own_hidden = (
            tag in NONRENDERING_HTML_TAGS
            or HTML_HIDDEN_ATTR_RE.search(source) is not None
        )
        if not state.hidden and not own_hidden:
            out.append(source)
        self_closing = re.search(r"/[ \t\r\n]*>$", source) is not None
        in_foreign_content = (
            tag in {"svg", "math"}
            or any(
                ancestor in {"svg", "math"}
                for ancestor, _hidden in state.elements
            )
        )
        if (
            tag not in HTML_VOID_TAGS
            and not (self_closing and in_foreign_content)
        ):
            state.elements.append((tag, own_hidden))
    return "".join(out), state if state.elements else None


def textarea_literal_parts(
    value: str, *, opening_line: bool
) -> tuple[str, str, bool]:
    """Return textarea literal body, following raw HTML, and recovered-close state."""
    source = value
    body_start = 0
    if opening_line:
        start = source.lower().find("<textarea")
        if start < 0:
            return "", "", False
        opener = INLINE_HTML_TAG_RE.match(source, start)
        if opener is None:
            return "", "", False
        body_start = opener.end()

    cursor = body_start
    while cursor < len(source):
        tag_start = source.find("<", cursor)
        if tag_start < 0:
            literal = source[body_start:]
            return (
                literal.replace("<", "&lt;").replace(">", "&gt;"),
                "",
                False,
            )

        tag = INLINE_HTML_TAG_RE.match(source, tag_start)
        if tag is None:
            cursor = tag_start + 1
            continue

        tag_source = tag.group(0)
        if re.match(r"</textarea(?:[ \t\r\n/>]|$)", tag_source, re.IGNORECASE):
            literal = source[body_start:tag_start]
            return (
                literal.replace("<", "&lt;").replace(">", "&gt;"),
                source[tag.end() :],
                True,
            )
        cursor = tag.end()

    literal = source[body_start:]
    return literal.replace("<", "&lt;").replace(">", "&gt;"), "", False


def textarea_literal_content(
    value: str, *, opening_line: bool
) -> str:
    """Compatibility wrapper returning only rendered textarea literal content."""
    return textarea_literal_parts(value, opening_line=opening_line)[0]


def render_raw_html_text_node(value: str) -> str:
    """Render raw HTML text while preserving heading-only structure."""
    stripped = value.strip()
    opener = INLINE_HTML_TAG_RE.match(stripped)
    if opener is not None:
        opener_source = opener.group(0)
        heading = re.match(
            r"<h(?P<level>[1-6])(?:[ \t\r\n/>]|$)",
            opener_source,
            re.IGNORECASE,
        )
        if heading is not None:
            level = int(heading.group("level"))
            close = re.search(
                rf"</h{level}[ \t\r\n]*>",
                stripped[opener.end() :],
                re.IGNORECASE,
            )
            if close is not None:
                close_start = opener.end() + close.start()
                close_end = opener.end() + close.end()
                if not stripped[close_end:].strip():
                    body = strip_inline_html_constructs(
                        stripped[opener.end() : close_start]
                    ).strip()
                    return f"{'#' * level} {body}" if body else "#" * level

    return strip_inline_html_constructs(value)


def visible_nonfenced_lines(
    lines: list[str],
    raw_html_text: list[str] | None = None,
    raw_html_source: list[str] | None = None,
    visible_events: list[tuple[int, str]] | None = None,
    raw_html_events: list[tuple[int, str]] | None = None,
    raw_html_source_events: list[tuple[int, str]] | None = None,
    fenced_events: list[tuple[int, str]] | None = None,
    indented_code_events: list[tuple[int, str]] | None = None,
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
    html_textarea_open = False
    raw_html_comment = False
    raw_html_source_comment = False
    raw_html_hidden_tag: HTMLVisibilityState | None = None
    raw_html_source_hidden_tag: HTMLVisibilityState | None = None
    paragraph_open = False

    def append_visible(source_index: int, value: str) -> None:
        visible.append(value)
        if visible_events is not None:
            visible_events.append((source_index, value))

    def boundary(source_index: int) -> None:
        if not visible or visible[-1] != "":
            append_visible(source_index, "")

    def append_raw_html_source(
        source_index: int, value: str, *, literal: bool = False
    ) -> None:
        nonlocal raw_html_source_comment, raw_html_source_hidden_tag
        if raw_html_source is None and raw_html_source_events is None:
            return
        if literal:
            rendered = value
        else:
            rendered, raw_html_source_comment = strip_inline_html_comments(
                value, raw_html_source_comment
            )
            rendered, raw_html_source_hidden_tag = strip_nonrendering_html_regions(
                rendered,
                raw_html_source_hidden_tag,
                honor_backslash_escapes=False,
            )
        if rendered.strip():
            if raw_html_source is not None:
                raw_html_source.append(rendered)
            if raw_html_source_events is not None:
                raw_html_source_events.append((source_index, rendered))

    def append_raw_html_text(
        source_index: int, value: str, *, literal: bool = False
    ) -> None:
        nonlocal raw_html_comment, raw_html_hidden_tag
        if raw_html_text is None and raw_html_events is None:
            return
        if literal:
            rendered = value
        else:
            rendered, raw_html_comment = strip_inline_html_comments(
                value, raw_html_comment
            )
            rendered, raw_html_hidden_tag = strip_nonrendering_html_regions(
                rendered,
                raw_html_hidden_tag,
                honor_backslash_escapes=False,
            )
            rendered = render_raw_html_text_node(rendered)
        if rendered.strip():
            if raw_html_text is not None:
                raw_html_text.append(rendered)
            if raw_html_events is not None:
                raw_html_events.append((source_index, rendered))

    for source_index, raw in enumerate(lines):
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
                boundary(source_index)
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
                elif fenced_events is not None:
                    fenced_events.append((source_index, fence_view))
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
                raw_html_comment = False
                raw_html_source_comment = False
                raw_html_hidden_tag = None
                raw_html_source_hidden_tag = None
                boundary(source_index)
            else:
                paragraph_open = False
                html_view = (
                    strip_indent_columns(block_raw, html_list_indent)
                    if html_list_indent > 0
                    else block_raw
                )
                if html_mode == "tag" and html_end == "textarea":
                    if html_textarea_open:
                        literal, remainder, recovered_close = textarea_literal_parts(
                            html_view, opening_line=False
                        )
                        if raw_html_source is not None or raw_html_source_events is not None:
                            append_raw_html_source(
                                source_index, literal, literal=True
                            )
                            if remainder:
                                append_raw_html_source(source_index, remainder)
                        if raw_html_text is not None or raw_html_events is not None:
                            append_raw_html_text(
                                source_index, literal, literal=True
                            )
                            if remainder:
                                append_raw_html_text(source_index, remainder)
                        if recovered_close:
                            html_textarea_open = False
                    else:
                        if raw_html_source is not None or raw_html_source_events is not None:
                            append_raw_html_source(source_index, html_view)
                        if raw_html_text is not None or raw_html_events is not None:
                            append_raw_html_text(source_index, html_view)
                elif html_mode == "tag" and html_end == "pre":
                    if raw_html_source is not None or raw_html_source_events is not None:
                        append_raw_html_source(source_index, html_view)
                    if raw_html_text is not None or raw_html_events is not None:
                        append_raw_html_text(source_index, html_view)

                if html_mode == "tag":
                    if html_end is not None and raw_html_tag_closes(html_view, html_end):
                        html_mode = None
                        html_end = None
                        html_quote_depth = 0
                        html_list_indent = 0
                        raw_html_comment = False
                        raw_html_source_comment = False
                        raw_html_hidden_tag = None
                        raw_html_source_hidden_tag = None
                    continue
                if html_mode == "token":
                    if html_end is not None and html_end in html_view:
                        html_mode = None
                        html_end = None
                        html_quote_depth = 0
                        html_list_indent = 0
                        raw_html_comment = False
                        raw_html_source_comment = False
                        raw_html_hidden_tag = None
                        raw_html_source_hidden_tag = None
                    continue
                if html_mode == "blank":
                    if (raw_html_source is not None or raw_html_source_events is not None) and html_view.strip():
                        append_raw_html_source(source_index, html_view)
                    if raw_html_text is not None or raw_html_events is not None:
                        append_raw_html_text(source_index, html_view)
                    if html_view.strip() == "":
                        html_mode = None
                        html_end = None
                        html_quote_depth = 0
                        html_list_indent = 0
                        raw_html_comment = False
                        raw_html_source_comment = False
                        raw_html_hidden_tag = None
                        raw_html_source_hidden_tag = None
                        boundary(source_index)
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
                    if indented_code_events is not None:
                        literal = strip_indent_columns(block_view, 4)
                        indented_code_events.append((source_index, literal))
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
                        boundary(source_index)
                        continue

                html_start = raw_html_block_start(block_view)
                if html_start is not None:
                    paragraph_open = False
                    boundary(source_index)
                    html_mode, html_end = html_start
                    html_quote_depth = quote_depth
                    html_list_indent = current_list_indent or 0
                    html_textarea_open = (
                        html_mode == "tag" and html_end == "textarea"
                    )
                    if html_mode == "tag" and html_end == "textarea":
                        literal, remainder, recovered_close = textarea_literal_parts(
                            block_view, opening_line=True
                        )
                        if raw_html_source is not None or raw_html_source_events is not None:
                            append_raw_html_source(
                                source_index, literal, literal=True
                            )
                            if remainder:
                                append_raw_html_source(source_index, remainder)
                        if raw_html_text is not None or raw_html_events is not None:
                            append_raw_html_text(
                                source_index, literal, literal=True
                            )
                            if remainder:
                                append_raw_html_text(source_index, remainder)
                        if recovered_close:
                            html_textarea_open = False
                    else:
                        if (raw_html_source is not None or raw_html_source_events is not None) and (
                            html_mode == "blank"
                            or (html_mode == "tag" and html_end == "pre")
                        ):
                            append_raw_html_source(source_index, block_view)
                        if (raw_html_text is not None or raw_html_events is not None) and (
                            html_mode == "blank"
                            or (html_mode == "tag" and html_end == "pre")
                        ):
                            append_raw_html_text(source_index, block_view)
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
                        raw_html_comment = False
                        raw_html_source_comment = False
                        raw_html_hidden_tag = None
                        raw_html_source_hidden_tag = None
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
            append_visible(source_index, raw_for_parse)
            if is_indented_code_line(parse_view) and was_paragraph_open:
                paragraph_open = True
            else:
                paragraph_open = _line_keeps_paragraph_open(
                    parse_view, was_paragraph_open
                )
        elif not inline_comment and raw == "":
            boundary(source_index)
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


def normalized_setext_heading(
    lines: list[str], underline_index: int, minimum_index: int = 0
) -> tuple[int, str] | None:
    """Return the start index and rendered identity of a Setext heading."""
    if not (
        SETEXT_H1_RE.fullmatch(lines[underline_index])
        or SETEXT_H2_RE.fullmatch(lines[underline_index])
    ):
        return None
    start = setext_heading_start(lines, underline_index, minimum_index)
    if start is None:
        return None
    body = " ".join(
        part.strip()
        for part in lines[start:underline_index]
        if part.strip()
    )
    rendered = rendered_inline_text(body).strip()
    if not rendered:
        return None
    hashes = "#" if SETEXT_H1_RE.fullmatch(lines[underline_index]) else "##"
    return start, f"{hashes} {rendered}"


def visible_level12_headings(lines: list[str]) -> list[str]:
    """Return rendered ATX/Setext level-one and level-two heading identities."""
    headings: list[str] = []
    for index, line in enumerate(lines):
        atx = normalized_visible_heading(line)
        if atx is not None and (atx.startswith("# ") or atx.startswith("## ")):
            headings.append(atx)
            continue
        setext = normalized_setext_heading(lines, index, 0)
        if setext is not None:
            _start, identity = setext
            headings.append(identity)
    return headings


def normalized_visible_heading(line: str) -> str | None:
    """Return a rendered ATX heading identity while preserving its level."""
    match = re.match(r"^(?P<hashes>#{1,6})(?:[ \t]+|$)(?P<body>.*)$", line)
    if match is None:
        return None

    body = match.group("body")
    body = re.sub(r"[ \t]+#+[ \t]*$", "", body)
    rendered = rendered_inline_text(body).strip()
    return f"{match.group('hashes')} {rendered}" if rendered else match.group("hashes")


def section_lines(
    text: str,
    heading: str,
    *,
    include_raw_html_text: bool = False,
    include_raw_html_source: bool = False,
    rendered_fenced_text: list[str] | None = None,
    rendered_indented_text: list[str] | None = None,
) -> list[str]:
    """Return one exact rendered level-2 Markdown section."""
    source_lines = markdown_source_lines(text)
    visible_events: list[tuple[int, str]] = []
    raw_html_events: list[tuple[int, str]] = []
    raw_html_source_events: list[tuple[int, str]] = []
    fenced_events: list[tuple[int, str]] = []
    indented_code_events: list[tuple[int, str]] = []
    visible_nonfenced_lines(
        source_lines,
        visible_events=visible_events,
        raw_html_events=raw_html_events if include_raw_html_text else None,
        raw_html_source_events=(
            raw_html_source_events if include_raw_html_source else None
        ),
        fenced_events=fenced_events if rendered_fenced_text is not None else None,
        indented_code_events=(
            indented_code_events if rendered_indented_text is not None else None
        ),
    )

    visible_values = [line for _source_index, line in visible_events]
    target_pos: int | None = None
    start_source: int | None = None
    for index, (source_index, line) in enumerate(visible_events):
        if normalized_visible_heading(line) == heading:
            target_pos = index
            start_source = source_index
            break
        setext = normalized_setext_heading(visible_values, index, 0)
        if setext is not None and setext[1] == heading:
            target_pos = index
            start_source = source_index
            break

    if target_pos is None or start_source is None:
        return []

    end_source = len(source_lines)

    for index in range(target_pos + 1, len(visible_events)):
        source_index, line = visible_events[index]
        if SECTION_BOUNDARY_RE.match(line):
            end_source = source_index
            break
        setext = normalized_setext_heading(
            visible_values, index, target_pos + 1
        )
        if setext is not None:
            end_source = visible_events[setext[0]][0]
            break

    section = [
        line
        for source_index, line in visible_events
        if start_source < source_index < end_source
    ]
    if include_raw_html_text:
        section.extend(
            rendered
            for source_index, rendered in raw_html_events
            if start_source < source_index < end_source
        )
    if include_raw_html_source:
        section.extend(
            source
            for source_index, source in raw_html_source_events
            if start_source < source_index < end_source
        )
    if rendered_fenced_text is not None:
        rendered_fenced_text.extend(
            rendered
            for source_index, rendered in fenced_events
            if start_source < source_index < end_source
        )
    if rendered_indented_text is not None:
        rendered_indented_text.extend(
            rendered
            for source_index, rendered in indented_code_events
            if start_source < source_index < end_source
        )
    return section


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


def inline_paragraph_limit(text: str, start: int) -> int:
    """Return the first blank-line boundary after start, or len(text)."""
    boundary = re.search(
        r"(?:\r\n|\r|\n)[ \t]*(?:\r\n|\r|\n)",
        text[start:],
    )
    return len(text) if boundary is None else start + boundary.start()


def protect_code_spans(text: str) -> tuple[str, dict[str, str]]:
    """Replace parsed code spans with collision-free private-use sentinels."""
    out: list[str] = []
    protected: dict[str, str] = {}
    private_ranges = (
        (0xE000, 0xF8FF),
        (0xF0000, 0xFFFFD),
        (0x100000, 0x10FFFD),
    )
    range_index = 0
    codepoint = private_ranges[0][0]

    def allocate_token() -> str:
        nonlocal range_index, codepoint
        while range_index < len(private_ranges):
            start, end = private_ranges[range_index]
            if codepoint < start:
                codepoint = start
            while codepoint <= end:
                token = chr(codepoint)
                codepoint += 1
                if token not in text and token not in protected:
                    return token
            range_index += 1
            if range_index < len(private_ranges):
                codepoint = private_ranges[range_index][0]
        raise ValueError("no collision-free private-use sentinel available")

    i = 0
    while i < len(text):
        if text[i] == "<" and not is_backslash_escaped(text, i):
            html_end = inline_html_construct_end(text, i)
            if html_end is not None:
                out.append(text[i:html_end])
                i = html_end
                continue

        if text[i] != "`" or is_backslash_escaped(text, i):
            out.append(text[i])
            i += 1
            continue

        run_len = backtick_run_length(text, i)
        j = i + run_len
        paragraph_end = inline_paragraph_limit(text, j)
        close_start: int | None = None
        close_end: int | None = None
        while j < paragraph_end:
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

        token = allocate_token()
        protected[token] = text[i + run_len : close_start]
        out.append(token)
        i = close_end

    return "".join(out), protected


def find_label_close(text: str, open_index: int) -> int | None:
    depth = 1
    i = open_index + 1
    paragraph_end = inline_paragraph_limit(text, i)
    while i < paragraph_end:
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
            if text[i + 1] in string.punctuation:
                i += 2
            else:
                i += 1
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
        if char in " \t\n":
            if depth != 0:
                return None
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
            if text[i + 1] in string.punctuation:
                i += 2
            else:
                i += 1
            continue
        if char == "(":
            depth += 1
        elif char == ")":
            if depth == 0:
                return text[start:i]
            depth -= 1
        elif char in " \t\n":
            if depth != 0:
                return None
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


def normalized_code_span_text(value: str) -> str:
    """Return the visible text of one CommonMark code-span payload."""
    code_text = value.replace("\n", " ")
    if (
        len(code_text) >= 2
        and code_text.startswith(" ")
        and code_text.endswith(" ")
        and code_text.strip()
    ):
        code_text = code_text[1:-1]
    return code_text


def restore_protected_code_text(
    value: str, protected_code: dict[str, str] | None
) -> str:
    """Restore protected code-span payloads as literal rendered text."""
    if not protected_code:
        return value
    for token, code_text in protected_code.items():
        value = value.replace(token, normalized_code_span_text(code_text))
    return value


def rendered_record_label(
    value: str, protected_code: dict[str, str] | None = None
) -> str:
    """Render the narrow inline subset allowed for record IDs."""
    stripped = value.strip()
    protected_text, local_protected = protect_code_spans(stripped)
    rendered = rendered_inline_text(protected_text)
    rendered = restore_protected_code_text(rendered, local_protected)
    rendered = restore_protected_code_text(rendered, protected_code)
    return rendered.strip()


URI_UNRESERVED = frozenset(string.ascii_letters + string.digits + "-._~")
PERCENT_ESCAPE_RE = re.compile(r"%([0-9A-Fa-f]{2})")


def decode_safe_repository_path_escapes(path: str) -> str | None:
    """Decode unreserved URI escapes while rejecting encoded separators/traversal."""
    if re.search(r"%(?:2[fF]|5[cC])", path):
        return None

    decoded_segments: list[str] = []
    for segment in path.split("/"):
        def replace_escape(match: re.Match[str]) -> str:
            char = chr(int(match.group(1), 16))
            return char if char in URI_UNRESERVED else match.group(0)

        decoded = PERCENT_ESCAPE_RE.sub(replace_escape, segment)
        if decoded in {".", ".."} and decoded != segment:
            return None
        decoded_segments.append(decoded)

    return "/".join(decoded_segments)


def normalize_repository_relative_path(path: str) -> str | None:
    """Normalize a repository-relative POSIX path without allowing root escape."""
    decoded = decode_safe_repository_path_escapes(path)
    if decoded is None or not decoded or decoded.startswith("/"):
        return None
    normalized = posixpath.normpath(decoded)
    if normalized in {"", "."} or normalized == ".." or normalized.startswith("../"):
        return None
    return normalized


def visible_record_links(
    text: str, protected_code: dict[str, str] | None = None
) -> list[tuple[str, str]]:
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

        destination = inline_link_destination(text, label_close + 1)
        link_end = find_inline_link_end(text, label_close + 1)
        if destination is None:
            i += 1
            continue

        raw_label = text[i + 1 : label_close]
        if inline_link_destination_pairs(raw_label):
            i += 1
            continue

        decoded_destination = commonmark_unescape(destination)
        rel, _separator, _fragment = decoded_destination.partition("#")
        normalized_rel = normalize_repository_relative_path(rel)
        rendered_label = rendered_record_label(raw_label, protected_code)
        if (
            (
                normalized_rel is not None
                and normalized_rel.startswith("optimizations/")
            )
            or re.fullmatch(r"OPT-[A-Z]+-\d{3}", rendered_label) is not None
        ):
            links.append((rendered_label, decoded_destination))

        i = link_end if link_end is not None else label_close + 1

    return links


def decode_html_attribute_references(value: str) -> str:
    """Decode character references using HTML attribute-value state rules."""
    out: list[str] = []
    index = 0

    while index < len(value):
        if value[index] != "&":
            out.append(value[index])
            index += 1
            continue

        numeric = re.match(r"&#(?:[xX][0-9A-Fa-f]+|[0-9]+);?", value[index:])
        if numeric is not None:
            token = numeric.group(0)
            out.append(html.unescape(token))
            index += len(token)
            continue

        run = re.match(r"&(?P<name>[A-Za-z0-9]+)(?P<semi>;?)", value[index:])
        if run is None:
            out.append("&")
            index += 1
            continue

        name = run.group("name")
        matched_key: str | None = None
        matched_len = 0
        if run.group("semi"):
            key = name + ";"
            if key in HTML5_ENTITIES:
                matched_key = key
                matched_len = len(name) + 1

        if matched_key is None:
            for length in range(len(name), 0, -1):
                key = name[:length]
                if key in HTML5_ENTITIES:
                    matched_key = key
                    matched_len = length
                    break

        if matched_key is None:
            out.append("&")
            index += 1
            continue

        consumed_end = index + 1 + matched_len
        if not matched_key.endswith(";"):
            next_char = value[consumed_end : consumed_end + 1]
            if next_char and (next_char.isalnum() or next_char == "="):
                out.append("&")
                index += 1
                continue

        out.append(HTML5_ENTITIES[matched_key])
        index = consumed_end

    return "".join(out)


HTML_ATTRIBUTE_RE = re.compile(
    r"""(?:^|[ \t\r\n])(?P<name>[A-Za-z_:][A-Za-z0-9_.:-]*)"""
    r"""(?:[ \t\r\n]*=[ \t\r\n]*(?:"(?P<double>[^"]*)"|'(?P<single>[^']*)'|(?P<bare>[^ \t\r\n"'=<>\x60]+)))?""",
    re.IGNORECASE,
)


def first_html_attribute_value(source: str, attribute: str) -> str | None:
    """Return the first duplicate attribute value; valueless means empty."""
    target = attribute.casefold()
    for match in HTML_ATTRIBUTE_RE.finditer(source):
        if match.group("name").casefold() != target:
            continue
        for group in ("double", "single", "bare"):
            value = match.group(group)
            if value is not None:
                return value
        return ""
    return None


def strip_preformatted_html_scan_contents(
    text: str,
    *,
    honor_backslash_escapes: bool = False,
    recover_end_tags: bool = False,
) -> str:
    """Remove textarea contents from scans that look for active HTML markup."""
    out: list[str] = []
    index = 0

    while index < len(text):
        tag_start = text.find("<", index)
        if tag_start < 0:
            out.append(text[index:])
            break

        tag = INLINE_HTML_TAG_RE.match(text, tag_start)
        if tag is None:
            out.append(text[index : tag_start + 1])
            index = tag_start + 1
            continue
        if honor_backslash_escapes and is_backslash_escaped(text, tag_start):
            out.append(text[index : tag.end()])
            index = tag.end()
            continue

        source = tag.group(0)
        opener = re.match(
            r"<(?P<tag>textarea)(?:[ \t\r\n/>]|$)",
            source,
            re.IGNORECASE,
        )
        if opener is None or source.startswith("</"):
            out.append(text[index : tag.end()])
            index = tag.end()
            continue

        out.append(text[index : tag.end()])
        raw_tag = opener.group("tag")
        cursor = tag.end()
        closed = False

        while cursor < len(text):
            candidate_start = text.find("<", cursor)
            if candidate_start < 0:
                index = len(text)
                closed = True
                break

            candidate = INLINE_HTML_TAG_RE.match(text, candidate_start)
            if candidate is None:
                cursor = candidate_start + 1
                continue

            candidate_source = candidate.group(0)
            closes = (
                re.match(
                    rf"</{re.escape(raw_tag)}(?:[ \t\r\n/>]|$)",
                    candidate_source,
                    re.IGNORECASE,
                )
                if recover_end_tags
                else re.fullmatch(
                    rf"</{re.escape(raw_tag)}[ \t\r\n]*>",
                    candidate_source,
                    re.IGNORECASE,
                )
            )
            if closes is not None:
                out.append(candidate_source)
                index = candidate.end()
                closed = True
                break

            cursor = candidate.end()

        if not closed:
            index = len(text)

    return "".join(out)


def html_anchor_label_extent(
    text: str, content_start: int
) -> tuple[int, int] | None:
    """Return rendered label end and next scan index for one HTML anchor.

    A nested anchor start implicitly closes the current anchor. Only parsed HTML
    tokens participate, so '</a>' text inside quoted attributes is ignored.
    """
    cursor = content_start
    while cursor < len(text):
        tag_start = text.find("<", cursor)
        if tag_start < 0:
            return len(text), len(text)

        tag = INLINE_HTML_TAG_RE.match(text, tag_start)
        if tag is None:
            cursor = tag_start + 1
            continue

        source = tag.group(0)
        if re.match(r"<a(?:[ \t\r\n]|>)", source, re.IGNORECASE):
            return tag_start, tag_start

        if re.match(r"</a(?:[ \t\r\n/>]|$)", source, re.IGNORECASE):
            return tag_start, tag.end()

        cursor = tag.end()

    return len(text), len(text)


ASCII_URL_EDGE_CHARS = "".join(chr(value) for value in range(0x21))


def decoded_html_url_attribute(value: str) -> str:
    """Preprocess an href in this repository's HTTP(S) document context.

    Literal backslashes are separators in special-URL paths, not in query or
    fragment data. Encoded separators and non-HTTP schemes remain untouched.
    """
    decoded = decode_html_attribute_references(value).strip(ASCII_URL_EDGE_CHARS)
    decoded = decoded.replace("\t", "").replace("\r", "").replace("\n", "")
    scheme = re.match(r"^([A-Za-z][A-Za-z0-9+.-]*):", decoded)
    if scheme is not None and scheme.group(1).lower() not in {"http", "https"}:
        return decoded
    boundary = len(decoded)
    for delimiter in ("?", "#"):
        position = decoded.find(delimiter)
        if position >= 0:
            boundary = min(boundary, position)
    return decoded[:boundary].replace("\\", "/") + decoded[boundary:]


def html_anchor_links(text: str) -> list[tuple[str, str]]:
    """Return rendered anchor labels paired with decoded href destinations."""
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

        href = first_html_attribute_value(tag_source, "href")
        if href is None:
            index = tag.end()
            continue

        extent = html_anchor_label_extent(text, tag.end())
        if extent is None:
            index = tag.end()
            continue
        label_end, next_index = extent

        label = rendered_inline_text(text[tag.end():label_end])
        links.append((label, decoded_html_url_attribute(href)))
        index = next_index

    return links


def html_anchor_hrefs(text: str) -> list[str]:
    """Return decoded hrefs for anchors with substantive rendered labels."""
    return [
        destination
        for label, destination in html_anchor_links(text)
        if has_substantive_rendered_text(label)
    ]


def rendered_raw_html_text(value: str) -> str:
    """Render raw-HTML text nodes without interpreting Markdown delimiters."""
    text, _hidden_state = strip_nonrendering_html_regions(
        value,
        None,
        honor_backslash_escapes=False,
    )
    text = preserve_html_image_alt_text(text)
    text = strip_inline_html_constructs(text)
    return html.unescape(text).strip()


def visible_html_record_links(
    text: str,
    *,
    markdown_contents: bool,
    protected_code: dict[str, str] | None = None,
) -> list[tuple[str, str]]:
    """Return visible HTML record links with origin-aware label rendering."""
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
        if markdown_contents and is_backslash_escaped(text, start):
            index = tag.end()
            continue

        tag_source = tag.group(0)
        if re.match(r"<a(?:[ \t\r\n]|>)", tag_source, re.IGNORECASE) is None:
            index = tag.end()
            continue

        href = first_html_attribute_value(tag_source, "href")
        if href is None:
            index = tag.end()
            continue

        extent = html_anchor_label_extent(text, tag.end())
        if extent is None:
            index = tag.end()
            continue
        label_end, next_index = extent

        decoded_href = decoded_html_url_attribute(href)
        rel, _separator, _fragment = decoded_href.partition("#")
        normalized_rel = normalize_repository_relative_path(rel)
        label_source = text[tag.end():label_end]
        rendered_label = (
            restore_protected_code_text(
                rendered_inline_text(label_source), protected_code
            )
            if markdown_contents
            else rendered_raw_html_text(label_source)
        )
        if (
            (
                normalized_rel is not None
                and normalized_rel.startswith("optimizations/")
            )
            or re.fullmatch(r"OPT-[A-Z]+-\d{3}", rendered_label) is not None
        ):
            links.append((rendered_label, decoded_href))

        index = next_index

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
            if any(not has_substantive_rendered_text(cell) for cell in cells):
                die(
                    f"{context} table row contains an empty/non-substantive "
                    f"rendered cell: {row.strip()}"
                )
            rows.append(cells)
        return rows
    die(f"{context} is missing the expected Markdown table")


def core_inline_delimiter_flanking(
    text: str, start: int, run_len: int
) -> tuple[bool, bool]:
    before = text[start - 1] if start > 0 else ""
    after_index = start + run_len
    after = text[after_index] if after_index < len(text) else ""

    before_whitespace = not before or before.isspace()
    after_whitespace = not after or after.isspace()
    before_punctuation = bool(before) and unicodedata.category(before).startswith("P")
    after_punctuation = bool(after) and unicodedata.category(after).startswith("P")

    left_flanking = (
        not after_whitespace
        and (
            not after_punctuation
            or before_whitespace
            or before_punctuation
        )
    )
    right_flanking = (
        not before_whitespace
        and (
            not before_punctuation
            or after_whitespace
            or after_punctuation
        )
    )
    return left_flanking, right_flanking


def core_valid_emphasis_delimiter(
    text: str, start: int, marker: str, *, opening: bool
) -> bool:
    left_flanking, right_flanking = core_inline_delimiter_flanking(
        text, start, len(marker)
    )
    if marker.startswith("_"):
        before = text[start - 1] if start > 0 else ""
        after_index = start + len(marker)
        after = text[after_index] if after_index < len(text) else ""
        before_punctuation = bool(before) and unicodedata.category(before).startswith("P")
        after_punctuation = bool(after) and unicodedata.category(after).startswith("P")
        if opening:
            return left_flanking and (not right_flanking or before_punctuation)
        return right_flanking and (not left_flanking or after_punctuation)
    return left_flanking if opening else right_flanking


def unwrap_outer_formatting(value: str, wrappers: tuple[str, ...]) -> str:
    """Remove only complete formatting whose delimiters are valid Markdown."""
    result = value.strip()
    changed = True
    while changed:
        changed = False
        for marker in wrappers:
            if (
                len(result) > 2 * len(marker)
                and result.startswith(marker)
                and result.endswith(marker)
                and core_valid_emphasis_delimiter(
                    result, 0, marker, opening=True
                )
                and core_valid_emphasis_delimiter(
                    result, len(result) - len(marker), marker, opening=False
                )
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


def preserve_html_image_alt_text(text: str) -> str:
    """Replace visible HTML image tags with their decoded accessible alt text."""
    def replace(match: re.Match[str]) -> str:
        source = match.group(0)
        if re.match(r"<img(?:[ \t\r\n]|/?>)", source, re.IGNORECASE) is None:
            return source
        alt_match = HTML_ALT_ATTR_RE.search(source)
        if alt_match is None:
            return ""
        alt = next(value for value in alt_match.groups() if value is not None)
        return html.escape(
            decode_html_attribute_references(alt),
            quote=False,
        )

    return INLINE_HTML_TAG_RE.sub(replace, text)


def rendered_inline_text(value: str) -> str:
    """Approximate rendered inline text for required field-value validation."""
    text, protected_code = protect_code_spans(value)
    text = strip_inline_links(text)
    text = REFERENCE_IMAGE_RE.sub(lambda m: m.group(1), text)
    text = REFERENCE_LINK_RE.sub(lambda m: m.group(1), text)
    text, _hidden_tag = strip_nonrendering_html_regions(
        text,
        None,
        honor_backslash_escapes=True,
    )
    text = preserve_html_image_alt_text(text)
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


def used_reference_links(text: str) -> list[tuple[str, str]]:
    """Return normalized reference keys paired with rendered link labels."""
    links: list[tuple[str, str]] = []
    protected_text, protected_code = protect_code_spans(text)
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
        is_image = (
            i > 0
            and protected_text[i - 1] == "!"
            and not is_backslash_escaped(protected_text, i - 1)
        )

        label_close = find_label_close(protected_text, i)
        if label_close is None:
            i += 1
            continue

        label_source = protected_text[i + 1 : label_close]
        rendered_label = restore_protected_code_text(
            rendered_inline_text(label_source), protected_code
        )
        after = label_close + 1

        if is_image:
            if after < len(protected_text) and protected_text[after] == "(":
                link_end = find_inline_link_end(protected_text, after)
                i = link_end if link_end is not None else label_close + 1
                continue
            if after < len(protected_text) and protected_text[after] == "[":
                reference_close = find_label_close(protected_text, after)
                if reference_close is not None:
                    i = reference_close + 1
                    continue
            i = label_close + 1
            continue

        if after < len(protected_text) and protected_text[after] == "(":
            link_end = find_inline_link_end(protected_text, after)
            i = link_end if link_end is not None else after + 1
            continue

        if after < len(protected_text) and protected_text[after] == "[":
            reference_close = find_label_close(protected_text, after)
            if reference_close is not None:
                reference = protected_text[after + 1 : reference_close] or label_source
                links.append(
                    (normalized_reference_label(reference), rendered_label)
                )
                i = reference_close + 1
                continue

        links.append(
            (normalized_reference_label(label_source), rendered_label)
        )
        i = label_close + 1

    return links


def used_reference_labels(text: str) -> set[str]:
    return {reference for reference, _label in used_reference_links(text)}


def is_structural_only_line(
    line: str, *, reference_definition: bool = True
) -> bool:
    if HEADING_RE.match(line) or THEMATIC_BREAK_RE.fullmatch(line):
        return True
    if LIST_MARKER_ONLY_RE.fullmatch(line) or line == ">":
        return True
    if reference_definition and LINK_REFERENCE_DEFINITION_RE.fullmatch(line):
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
        if EMPTY_LABEL_RE.match(line) or is_structural_only_line(
            line, reference_definition=False
        ):
            continue
        if not has_substantive_rendered_text(line):
            continue
        return True
    return False


def fenced_rendered_text_has_content(lines: list[str]) -> bool:
    """Treat fenced-code bodies as visible literal content, not Markdown structure."""
    return any(
        line.strip() and line.strip() not in TEMPLATE_PLACEHOLDER_LINES
        for line in lines
    )


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



def inline_link_destination_pairs(text: str) -> list[tuple[str, str]]:
    """Return rendered labels paired with valid inline-link destinations."""
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
        if destination is None or link_end is None:
            i += 1
            continue

        label = rendered_inline_text(text[i + 1 : label_close])
        links.append((label, commonmark_unescape(destination)))
        i = link_end

    return links


def valid_http_source_url(value: str) -> bool:
    """Require an absolute HTTP(S) URL with a syntactically valid host."""
    try:
        parsed = urlsplit(value)
        host = parsed.hostname
        _port = parsed.port
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


def valid_repository_identity(owner: str, repo: str) -> bool:
    token = f"{owner}/{repo}".lower()
    if token in SOURCE_REPOSITORY_PLACEHOLDERS:
        return False

    placeholder_parts = {"none", "unknown", "tbd", "todo", "pending"}
    if owner.lower() in placeholder_parts or repo.lower() in placeholder_parts:
        return False

    if re.fullmatch(
        r"[A-Za-z0-9](?:[A-Za-z0-9-]{0,37}[A-Za-z0-9])?",
        owner,
    ) is None:
        return False

    if (
        repo in {".", ".."}
        or re.fullmatch(r"[A-Za-z0-9._-]+", repo) is None
        or not any(char.isalnum() for char in repo)
    ):
        return False

    return True


def source_url_candidate(line: str, match: re.Match[str]) -> str:
    """Trim prose punctuation and wrappers without stripping balanced URL syntax."""
    result = match.group(0).rstrip(".,;:!?")
    opening_quote = line[match.start() - 1] if match.start() > 0 else ""
    closing_pairs = {")": "(", "]": "[", "}": "{"}

    while result:
        closer = result[-1]
        if closer in {'"', "'"} and opening_quote == closer:
            result = result[:-1].rstrip(".,;:!?")
            continue

        opener = closing_pairs.get(closer)
        if opener is not None and result.count(closer) > result.count(opener):
            result = result[:-1].rstrip(".,;:!?")
            continue

        break

    return result


def source_text_has_direct_identity(line: str) -> bool:
    """Return whether rendered text contains concrete provenance without local-note indirection."""
    if any(
        valid_http_source_url(source_url_candidate(line, match))
        for match in SOURCE_URL_RE.finditer(line)
    ):
        return True
    if SOURCE_DOI_RE.search(line):
        return True
    if any(
        source_commit_has_context(line, match)
        for match in SOURCE_COMMIT_RE.finditer(line)
    ):
        return True
    if any(
        valid_repository_identity(match.group("owner"), match.group("repo"))
        for match in SOURCE_REPOSITORY_RE.finditer(line)
    ):
        return True
    return any(
        valid_repository_identity(match.group("owner"), match.group("repo"))
        for match in SOURCE_REPOSITORY_CONTEXT_RE.finditer(line)
    )


def source_note_has_identity(path: Path, sources_root: Path) -> bool:
    """Require an existing local source note to contain its own concrete provenance."""
    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return False

    raw_html_source: list[str] = []
    fenced_source: list[tuple[int, str]] = []
    indented_source: list[tuple[int, str]] = []
    visible = visible_nonfenced_lines(
        markdown_source_lines(text),
        raw_html_source=raw_html_source,
        fenced_events=fenced_source,
        indented_code_events=indented_source,
    )
    hidden_reference_lines, destinations = reference_definition_scan(visible)
    rendered_visible = [
        raw
        for index, raw in enumerate(visible)
        if index not in hidden_reference_lines
    ]
    if any(
        rendered.strip() and source_text_has_direct_identity(rendered)
        for _source_index, rendered in (*fenced_source, *indented_source)
    ):
        return True

    raw_source = "\n".join((*rendered_visible, *raw_html_source))
    source, _hidden_tag = strip_nonrendering_html_regions(
        raw_source,
        None,
        honor_backslash_escapes=True,
    )

    html_links = html_anchor_links(source)
    inline_links = inline_link_destination_pairs(source)
    rendered = commonmark_unescape_outside_code_spans(
        strip_inline_links(strip_inline_html_constructs(source))
    )

    if source_text_has_direct_identity(rendered):
        return True

    if any(
        has_substantive_rendered_text(label)
        and source_link_destination_has_identity(
            destination, sources_root, allow_local_note=False
        )
        for label, destination in (*html_links, *inline_links)
    ):
        return True

    for reference, label in used_reference_links(source):
        if not has_substantive_rendered_text(label):
            continue
        destination = destinations.get(reference)
        if destination is None:
            continue
        if source_link_destination_has_identity(
            destination, sources_root, allow_local_note=False
        ):
            return True

    return False


def source_text_has_identity(line: str, sources_root: Path) -> bool:
    if source_text_has_direct_identity(line):
        return True

    for match in SOURCE_LOCAL_NOTE_RE.finditer(line):
        candidate = (ROOT / match.group(1)).resolve()
        try:
            candidate.relative_to(sources_root)
        except ValueError:
            continue
        if candidate.is_file() and source_note_has_identity(candidate, sources_root):
            return True

    return False


def source_link_destination_has_identity(
    value: str,
    sources_root: Path,
    *,
    allow_local_note: bool = True,
    base_dir: Path = ROOT,
) -> bool:
    """Require a parsed link destination to be one complete provenance identity."""
    candidate = value.strip()
    if not candidate:
        return False

    local_note, _separator, _fragment = candidate.partition("#")
    decoded_local_note = decode_safe_repository_path_escapes(local_note)
    if (
        decoded_local_note is not None
        and decoded_local_note.endswith(".md")
        and ":" not in decoded_local_note
    ):
        if not allow_local_note:
            return False
        note_path = (base_dir / decoded_local_note).resolve()
        try:
            note_path.relative_to(sources_root)
        except ValueError:
            return False
        return note_path.is_file() and source_note_has_identity(note_path, sources_root)

    if valid_http_source_url(candidate):
        return True

    if re.fullmatch(r"(?:doi:\s*)?10\.\d{4,9}/\S+", candidate, re.IGNORECASE):
        return True

    repository = re.fullmatch(
        r"(?P<owner>[A-Za-z0-9_.-]+)/(?P<repo>[A-Za-z0-9_.-]+)",
        candidate,
    )
    return bool(
        repository is not None
        and valid_repository_identity(
            repository.group("owner"), repository.group("repo")
        )
    )


def source_section_has_identity(
    lines: list[str],
    document_reference_definitions: dict[str, str] | None = None,
    rendered_fenced_text: list[str] | None = None,
    source_path: Path | None = None,
) -> bool:
    """Require at least one concrete, rendered provenance identity."""
    sources_root = (ROOT / "sources").resolve()

    if any(
        raw.strip()
        and not SOURCE_PLACEHOLDER_RE.fullmatch(raw.strip())
        and source_text_has_identity(raw, sources_root)
        for raw in (rendered_fenced_text or [])
    ):
        return True

    visible = list(lines)
    hidden_reference_lines, local_destinations = reference_definition_scan(visible)
    destinations = (
        document_reference_definitions
        if document_reference_definitions is not None
        else local_destinations
    )

    rendered_source_lines = [
        raw
        for index, raw in enumerate(visible)
        if index not in hidden_reference_lines
    ]
    raw_source = "\n".join(rendered_source_lines)

    # Remove non-rendering inline HTML before collecting hrefs, while honoring
    # Markdown escapes in the visible prose stream. Raw-block source has already
    # been filtered using raw-HTML (non-escape) semantics.
    source, _hidden_tag = strip_nonrendering_html_regions(
        raw_source,
        None,
        honor_backslash_escapes=True,
    )
    html_links = html_anchor_links(source)
    source = strip_inline_html_constructs(source)
    inline_links = inline_link_destination_pairs(source)
    visible_source = strip_inline_links(source)
    rendered_source = commonmark_unescape_outside_code_spans(visible_source)

    if (
        rendered_source.strip()
        and not SOURCE_PLACEHOLDER_RE.fullmatch(rendered_source.strip())
        and source_text_has_identity(rendered_source, sources_root)
    ):
        return True

    for label, destination in (*html_links, *inline_links):
        if not has_substantive_rendered_text(label):
            continue
        if source_link_destination_has_identity(
            destination,
            sources_root,
            base_dir=source_path.parent if source_path is not None else ROOT,
        ):
            return True

    for reference, label in used_reference_links(source):
        if not has_substantive_rendered_text(label):
            continue
        destination = destinations.get(reference)
        if destination is None:
            continue
        if source_link_destination_has_identity(
            destination,
            sources_root,
            base_dir=source_path.parent if source_path is not None else ROOT,
        ):
            return True

    return False


def render_resolved_reference_links(
    text: str, definitions: set[str]
) -> str:
    """Render only reference links whose definitions actually resolve."""
    out: list[str] = []
    i = 0
    while i < len(text):
        if text[i] != "[" or is_backslash_escaped(text, i):
            out.append(text[i])
            i += 1
            continue

        label_close = find_label_close(text, i)
        if label_close is None:
            out.append(text[i])
            i += 1
            continue

        label = text[i + 1 : label_close]
        after = label_close + 1

        if after < len(text) and text[after] == "[":
            reference_close = find_label_close(text, after)
            if reference_close is not None:
                reference = text[after + 1 : reference_close] or label
                if normalized_reference_label(reference) in definitions:
                    out.append(label)
                    i = reference_close + 1
                    continue

        shortcut = normalized_reference_label(label)
        if shortcut in definitions:
            out.append(label)
            i = label_close + 1
            continue

        out.append(text[i : label_close + 1])
        i = label_close + 1

    return "".join(out)


def status_category_source(
    raw: str, reference_definitions: set[str] | None = None
) -> str:
    """Return the rendered status category before its visible caveat separator."""
    rendered, protected_code = protect_code_spans(raw)
    rendered = strip_inline_links(rendered)
    rendered = render_resolved_reference_links(
        rendered, reference_definitions or set()
    )
    rendered, _hidden_tag = strip_nonrendering_html_regions(
        rendered,
        None,
        honor_backslash_escapes=True,
    )
    rendered = strip_inline_html_constructs(rendered)
    rendered = strip_paired_inline_formatting(rendered)
    rendered = commonmark_unescape(rendered)

    separator = rendered.find(";")
    category = rendered if separator < 0 else rendered[:separator]
    for token, code_text in protected_code.items():
        category = category.replace(token, code_text)
    return category


def normalized_status_category(
    raw: str, reference_definitions: set[str] | None = None
) -> str:
    return status_category_source(raw, reference_definitions).strip()


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
            normalized_value = rendered_inline_text(value).rstrip(" \t.!?,;:")
            rejected_value = rejected_values.get(field)
            if (
                rejected_value is not None
                and normalized_value == rejected_value.rstrip(" \t.!?,;:")
            ):
                die(
                    f"{path.relative_to(ROOT)} has unselected template placeholder "
                    f"for {field} in {section}: '{value}'"
                )


records: dict[str, Path] = {}
status_categories: dict[str, str] = {}
for path in sorted(OPT_DIR.rglob("OPT-*.md")):
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

    record_title = match.group("title")
    rendered_title = rendered_inline_text(record_title).strip()
    normalized_title = rendered_title.rstrip(" \t.!?,;:")
    if (
        not has_substantive_rendered_text(record_title)
        or SOURCE_PLACEHOLDER_RE.fullmatch(normalized_title) is not None
        or normalized_title.casefold() == "optimization name"
    ):
        die(
            f"{path.relative_to(ROOT)} has empty/template/markup-only Optimization Name "
            f"in its record heading"
        )

    _hidden_status_definitions, status_definitions = reference_definition_scan(lines)
    status_category = normalized_status_category(
        statuses[0], set(status_definitions)
    )
    if status_category not in ALLOWED_V2_STATUS_CATEGORIES:
        die(
            f"{path.relative_to(ROOT)} uses undefined status category "
            f"'{status_category}'"
        )
    status_categories[record_id] = status_category

    heading_counts = Counter(
        rendered
        for rendered in visible_level12_headings(lines)
        if rendered.startswith("## ")
    )
    missing = sorted(
        heading for heading in REQUIRED_V2 if heading_counts[heading] == 0
    )
    if missing:
        die(f"{path.relative_to(ROOT)} missing visible sections: {', '.join(missing)}")
    duplicated = sorted(
        heading for heading in REQUIRED_V2 if heading_counts[heading] > 1
    )
    if duplicated:
        die(
            f"{path.relative_to(ROOT)} has duplicate mandatory sections: "
            f"{', '.join(duplicated)}"
        )

    for heading in sorted(REQUIRED_V2):
        rendered_fenced_text: list[str] = []
        rendered_indented_text: list[str] = []
        section = section_lines(
            text,
            heading,
            include_raw_html_text=True,
            rendered_fenced_text=rendered_fenced_text,
            rendered_indented_text=rendered_indented_text,
        )
        if not (
            section_has_content(section)
            or fenced_rendered_text_has_content(rendered_fenced_text)
            or fenced_rendered_text_has_content(rendered_indented_text)
        ):
            die(
                f"{path.relative_to(ROOT)} has empty/template/structural/markup-only mandatory section {heading}"
            )

    source_fenced_text: list[str] = []
    source_indented_text: list[str] = []
    source_evidence = section_lines(
        text,
        "## Source evidence",
        include_raw_html_source=True,
        rendered_fenced_text=source_fenced_text,
        rendered_indented_text=source_indented_text,
    )
    if not source_section_has_identity(
        source_evidence,
        status_definitions,
        rendered_fenced_text=(*source_fenced_text, *source_indented_text),
        source_path=path,
    ):
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

def repository_relative_posix(path: PurePath, root: PurePath = ROOT) -> str:
    """Return a stable repository-relative key independent of host separators."""
    return path.relative_to(root).as_posix()


record_paths = {
    repository_relative_posix(path): record_id
    for record_id, path in records.items()
}



def collect_explicit_html_anchors(
    text: str, *, honor_backslash_escapes: bool
) -> set[str]:
    """Collect explicit id/name fragments from one visible HTML-origin stream."""
    anchors: set[str] = set()
    for tag in INLINE_HTML_TAG_RE.finditer(text):
        if (
            honor_backslash_escapes
            and is_backslash_escaped(text, tag.start())
        ):
            continue

        source = tag.group(0)
        if source.startswith("</"):
            continue

        anchor = first_html_attribute_value(source, "id")
        if anchor:
            anchors.add(decode_html_attribute_references(anchor))

        if re.match(r"<a(?:[ \t\r\n]|>)", source, re.IGNORECASE):
            anchor = first_html_attribute_value(source, "name")
            if anchor:
                anchors.add(decode_html_attribute_references(anchor))
    return anchors


def heading_slug_reference_source(
    value: str, reference_definitions: set[str]
) -> str:
    """Collapse resolved full references; preserve unresolved visible reference text."""
    pattern = re.compile(
        r"\[(?P<label>[^\]]*)\]\[(?P<reference>[^\]]*)\]"
    )

    def replace(match: re.Match[str]) -> str:
        label = match.group("label")
        reference = match.group("reference") or label
        if normalized_reference_label(reference) in reference_definitions:
            return label
        return label + match.group("reference")

    return pattern.sub(replace, value)


def github_heading_slug(
    value: str, reference_definitions: set[str] | None = None
) -> str:
    """Approximate GitHub's rendered heading fragment for repository headings."""
    value = heading_slug_reference_source(
        value, reference_definitions or set()
    )
    value = rendered_inline_text(value).strip().lower()
    value = "".join(
        char
        for char in value
        if (
            char == "-"
            or char == "_"
            or char.isspace()
            or char.isalnum()
            or unicodedata.category(char).startswith("M")
        )
    )
    value = re.sub(r"[ \t\r\n]+", "-", value)
    return value


def record_fragment_ids(path: Path) -> set[str]:
    text = path.read_text(encoding="utf-8")
    anchors: set[str] = set()
    allocated_slugs: set[str] = set()
    raw_html_source: list[str] = []

    visible_lines = visible_nonfenced_lines(
        markdown_source_lines(text),
        raw_html_source=raw_html_source,
    )
    _hidden_reference_lines, heading_definitions = reference_definition_scan(
        visible_lines
    )
    heading_definition_keys = set(heading_definitions)

    def allocate_heading_slug(body: str) -> None:
        base = github_heading_slug(body, heading_definition_keys)
        if not base:
            return
        candidate = base
        suffix = 1
        while candidate in allocated_slugs:
            candidate = f"{base}-{suffix}"
            suffix += 1
        allocated_slugs.add(candidate)
        anchors.add(candidate)

    for index, line in enumerate(visible_lines):
        match = re.match(
            r"^#{1,6}(?:[ \t]+|$)(?P<body>.*)$", line
        )
        if match is not None:
            body = re.sub(
                r"[ \t]+#+[ \t]*$", "", match.group("body")
            )
            allocate_heading_slug(body)
            continue

        if SETEXT_H1_RE.fullmatch(line) or SETEXT_H2_RE.fullmatch(line):
            start = setext_heading_start(visible_lines, index, 0)
            if start is not None:
                body = " ".join(
                    part.strip()
                    for part in visible_lines[start:index]
                    if part.strip()
                )
                allocate_heading_slug(body)

    inline_html_source = "\n".join(visible_lines)
    inline_html_source, _protected_code = protect_code_spans(inline_html_source)
    inline_html_source, _hidden_tag = strip_nonrendering_html_regions(
        inline_html_source,
        None,
        honor_backslash_escapes=True,
    )
    anchors.update(
        collect_explicit_html_anchors(
            inline_html_source,
            honor_backslash_escapes=True,
        )
    )

    raw_block_html_source = strip_preformatted_html_scan_contents(
        "\n".join(raw_html_source)
    )
    anchors.update(
        collect_explicit_html_anchors(
            raw_block_html_source,
            honor_backslash_escapes=False,
        )
    )

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
    doc_visible_lines = visible_nonfenced_lines(
        markdown_source_lines(text),
        raw_html_source=raw_html_source,
    )
    _hidden_doc_definitions, doc_reference_definitions = reference_definition_scan(
        doc_visible_lines
    )
    rendered = "\n".join(doc_visible_lines)
    rendered_code_scan, _protected_link_code = protect_code_spans(rendered)
    rendered_link_scan, _hidden_link_state = strip_nonrendering_html_regions(
        rendered_code_scan,
        None,
        honor_backslash_escapes=True,
    )
    record_links = visible_record_links(
        rendered_link_scan, _protected_link_code
    )
    rendered_html_link_scan = strip_preformatted_html_scan_contents(
        rendered_link_scan,
        honor_backslash_escapes=True,
    )
    record_links.extend(
        visible_html_record_links(
            rendered_html_link_scan,
            markdown_contents=True,
            protected_code=_protected_link_code,
        )
    )
    raw_html_link_scan = strip_preformatted_html_scan_contents(
        "\n".join(raw_html_source),
        recover_end_tags=True,
    )
    record_links.extend(
        visible_html_record_links(
            raw_html_link_scan, markdown_contents=False
        )
    )
    for label, destination in record_links:
        rel, separator, fragment = destination.partition("#")
        normalized_rel = normalize_repository_relative_path(rel)
        if (
            normalized_rel is None
            or not normalized_rel.startswith("optimizations/")
            or not normalized_rel.endswith(".md")
        ):
            die(
                f"visible record link in {doc_name} has invalid destination: "
                f"{destination}"
            )
        rel = normalized_rel
        target = ROOT / rel
        if not target.is_file():
            die(f"broken visible record link in {doc_name}: {rel}")
        target_id = record_paths.get(rel)
        if target_id is None:
            die(f"record link in {doc_name} is not a discovered OPT record: {rel}")
        if label != target_id:
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
        row_statuses[row_id] = normalized_status_category(
            raw_status, set(doc_reference_definitions)
        )

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
catalog_visible_lines = visible_nonfenced_lines(
    markdown_source_lines(catalog),
    raw_html_text=catalog_html_text,
)
hidden_catalog_definitions = reference_definition_hidden_indexes(
    catalog_visible_lines
)
visible_catalog = "\n".join(
    line
    for index, line in enumerate(catalog_visible_lines)
    if index not in hidden_catalog_definitions
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
    matches = [
        match
        for line in canonical
        if (match := pattern.fullmatch(line)) is not None
    ]
    if not any(
        has_substantive_rendered_text(match.group("body"))
        for match in matches
    ):
        die(
            "OPTIMIZATION-PROBLEM.md is missing visible substantive canonical "
            f"definition for {field}"
        )

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
