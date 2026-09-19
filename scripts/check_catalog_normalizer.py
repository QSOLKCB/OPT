#!/usr/bin/env python3
"""Normalize supported CommonMark syntax, then run the hardened catalog checker.

The core checker intentionally stays strict and source-oriented. This front end creates a
scratch copy, canonicalizes rendering-equivalent forms that the core otherwise rejects
or overlooks, and runs the core against that copy:

* one-to-three spaces before top-level ATX headings (valid CommonMark indentation),
* optional Markdown titles and angle-bracket destinations on record links,
* inline-code examples that resemble optimization-record links,
* block-quoted link-reference definitions that actually parse as definitions,
* classification placeholders hidden behind rendering-only inline formatting,
* generic TODO/TBD-style required-field placeholders,
* type-7 raw-HTML tags that CommonMark keeps inside an already-open paragraph,
* thematic breaks after paragraph-interrupting blocks that are not Setext headings, and
* heading-shaped suffixes after multiline inline comments that remain paragraph text.

The repository working tree is never modified by this normalization step.
"""

from __future__ import annotations

import html
import re
import shutil
import string
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_NAME = "check_catalog_core.py"
ATX_INDENT_RE = re.compile(r"(?m)^ {1,3}(?=#{1,6}(?:[ \t]|$))")
ATX_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")
ATX_SUFFIX_RE = re.compile(r"^(?P<indent> {0,3})(?P<hashes>#{1,6})(?=[ \t]|$)")
FENCE_LINE_RE = re.compile(r"^ {0,3}(?:`{3,}|~{3,})")
LIST_BLOCK_RE = re.compile(r"^ {0,3}(?:[-+*]|\d{1,9}[.)])[ \t]+")
LIST_ITEM_RE = re.compile(
    r"^(?P<indent> *)(?P<marker>[-+*]|\d{1,9}[.)])(?P<spacing>[ \t]+)"
)
THEMATIC_BREAK_RE = re.compile(
    r"^ {0,3}(?:\*(?:[ \t]*\*){2,}|-(?:[ \t]*-){2,}|_(?:[ \t]*_){2,})[ \t]*$"
)
SETEXT_H2_LINE_RE = re.compile(r"^(?P<indent> {0,3})-{3,}[ \t]*$")
RECORD_LINK_START_RE = re.compile(
    r"\[([^\]\r\n]+)\]\((?:[ \t]*\r?\n[ \t]*|[ \t]*)(optimizations/[^\s)#]+\.md(?:#[^\s)]*)?)"
)
ANGLE_RECORD_DEST_RE = re.compile(
    r"(?P<prefix>\[[^\]\r\n]+\]\()<(?P<dest>optimizations/[^\s<>#]+\.md(?:#[^\s<>]*)?)>"
)
BLOCKQUOTE_PREFIX_RE = re.compile(r"^ {0,3}>[ \t]?")
LINK_REFERENCE_DEFINITION_RE = re.compile(
    r"^\[(?:\\.|[^\[\]\\])+\]:[ \t]+\S.*$"
)
LINK_REFERENCE_TITLE_CONTINUATION_RE = re.compile(
    r'^ {0,3}(?:"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\((?:\\.|[^)\\])*\))[ \t]*$'
)
INLINE_HTML_TAG_RE = re.compile(
    r"</?[A-Za-z][A-Za-z0-9-]*"
    r"(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t]*=[ \t]*(?:\"[^\"]*\"|'[^']*'|[^ \t\n\"'=<>`]+))?)*"
    r"[ \t]*/?>"
)
HTML_ALT_ATTR_RE = re.compile(
    r"""(?:^|[ \t\r\n])alt[ \t\r\n]*=[ \t\r\n]*(?:"([^"]*)"|'([^']*)'|([^ \t\r\n"'=<>\x60]+))""",
    re.IGNORECASE,
)
HTML_HIDDEN_ATTR_RE = re.compile(
    r"(?:^|[ \t\r\n])hidden"
    r"(?:[ \t\r\n]*=[ \t\r\n]*(?:\"[^\"]*\"|\'[^\']*\'|[^ \t\r\n\"\'=<>`]+))?"
    r"(?=[ \t\r\n/>]|$)",
    re.IGNORECASE,
)
NONRENDERING_INLINE_HTML_TAGS = {
    "script", "style", "template", "head", "title", "iframe",
}
HTML_VOID_TAGS = {
    "area", "base", "br", "col", "embed", "hr", "img", "input",
    "link", "meta", "param", "source", "track", "wbr",
}

STANDALONE_HTML_TAG_RE = re.compile(
    r"^ {0,3}(?:"
    r"</(?P<close>[A-Za-z][A-Za-z0-9-]*)[ \t]*>"
    r"|<(?P<open>[A-Za-z][A-Za-z0-9-]*)"
    r"(?:[ \t]+[A-Za-z_:][A-Za-z0-9_.:-]*"
    r"(?:[ \t]*=[ \t]*(?:\"[^\"]*\"|'[^']*'|[^ \t\n\"'=<>`]+))?)*"
    r"[ \t]*/?>"
    r")[ \t]*$"
)
INLINE_WRAPPERS = ("**", "__", "~~", "*", "_", "`")
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
CLASSIFICATION_FIELD_RE = re.compile(
    r"^(?P<prefix>- (?P<field>"
    + "|".join(re.escape(field) for field in CLASSIFICATION_TEMPLATE_VALUES)
    + r"):[ \t]*)(?P<value>.*)$"
)
REQUIRED_FIELD_NAMES = (
    "X",
    "F",
    "f",
    "d",
    "C",
    "B",
    "S",
    *CLASSIFICATION_TEMPLATE_VALUES.keys(),
)
REQUIRED_FIELD_RE = re.compile(
    r"^(?P<prefix>- (?P<field>"
    + "|".join(re.escape(field) for field in REQUIRED_FIELD_NAMES)
    + r"):[ \t]*)(?P<value>.*)$"
)
GENERIC_PLACEHOLDER_RE = re.compile(
    r"^(?:unknown|tbd|todo|n/?a|none|pending)(?:[.!?])?$", re.IGNORECASE
)
HEX_TOKEN_RE = re.compile(r"\b[0-9a-fA-F]{7,40}\b")
EXPLICIT_COMMIT_CONTEXT_RE = re.compile(
    r"(?:"
    r"\b(?:commit(?:[ \t]+sha)?|sha|revision|rev)\b[^0-9A-Za-z]{0,12}"
    r"|\b(?:pinned|inspected)[ \t]+at\b[^0-9A-Za-z]{0,12}"
    r")$",
    re.IGNORECASE,
)
HTML_BLOCK_TAGS = {
    "address", "article", "aside", "base", "basefont", "blockquote", "body",
    "caption", "center", "col", "colgroup", "dd", "details", "dialog", "dir",
    "div", "dl", "dt", "fieldset", "figcaption", "figure", "footer", "form",
    "frame", "frameset", "h1", "h2", "h3", "h4", "h5", "h6", "head",
    "header", "hr", "html", "iframe", "legend", "li", "link", "main", "menu",
    "menuitem", "nav", "noframes", "ol", "optgroup", "option", "p", "param",
    "search", "section", "summary", "table", "tbody", "td", "tfoot", "th",
    "thead", "title", "tr", "track", "ul",
}
TYPE1_HTML_TAGS = {"script", "pre", "style", "textarea"}


def _skip_link_whitespace(text: str, index: int) -> int | None:
    """Skip spaces/tabs and at most one line ending."""
    i = index
    saw_newline = False
    while i < len(text):
        if text[i] in " \t":
            i += 1
            continue
        if text.startswith("\r\n", i):
            if saw_newline:
                return None
            saw_newline = True
            i += 2
            continue
        if text[i] in "\r\n":
            if saw_newline:
                return None
            saw_newline = True
            i += 1
            continue
        break
    return i


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
        if char in "\r\n":
            return None
        index += 1
    return None


def _find_label_close(text: str, open_index: int) -> int | None:
    depth = 1
    index = open_index + 1
    while index < len(text):
        if text[index] == "\\" and index + 1 < len(text):
            index += 2
            continue
        if text[index] == "[":
            depth += 1
        elif text[index] == "]":
            depth -= 1
            if depth == 0:
                return index
        index += 1
    return None


def _find_inline_link_end(text: str, open_paren: int) -> int | None:
    """Return the index after a complete inline-link destination/title."""
    index = _skip_whitespace(text, open_paren + 1)
    if index >= len(text):
        return None
    if text[index] == ")":
        return index + 1

    if text[index] == "<":
        index += 1
        while index < len(text):
            if text[index] == "\\" and index + 1 < len(text):
                index += 2
                continue
            if text[index] == ">":
                after_title = _skip_whitespace(text, index + 1)
                if after_title < len(text) and text[after_title] == ")":
                    return after_title + 1
                title_end = _parse_title(text, after_title)
                if title_end is None:
                    return None
                outer_close = _skip_whitespace(text, title_end)
                if outer_close < len(text) and text[outer_close] == ")":
                    return outer_close + 1
                return None
            if text[index] in "\r\n<":
                return None
            index += 1
        return None

    depth = 0
    while index < len(text):
        char = text[index]
        if char == "\\" and index + 1 < len(text):
            index += 2
            continue
        if char == "(":
            depth += 1
            index += 1
            continue
        if char == ")":
            if depth == 0:
                return index + 1
            depth -= 1
            index += 1
            continue
        if char in " \t\r\n" and depth == 0:
            after_title = _skip_whitespace(text, index)
            if after_title < len(text) and text[after_title] == ")":
                return after_title + 1
            title_end = _parse_title(text, after_title)
            if title_end is None:
                return None
            outer_close = _skip_whitespace(text, title_end)
            if outer_close < len(text) and text[outer_close] == ")":
                return outer_close + 1
            return None
        if char in "<>" or ord(char) < 0x20:
            return None
        index += 1
    return None


def _is_backslash_escaped(text: str, index: int) -> bool:
    count = 0
    cursor = index - 1
    while cursor >= 0 and text[cursor] == "\\":
        count += 1
        cursor -= 1
    return count % 2 == 1


def _backtick_run_length(text: str, index: int) -> int:
    cursor = index
    while cursor < len(text) and text[cursor] == "`":
        cursor += 1
    return cursor - index


def mask_inline_code_record_destinations(text: str) -> str:
    """Prevent link-shaped inline-code examples from being treated as actual links."""
    out: list[str] = []
    index = 0
    while index < len(text):
        if text[index] != "`" or _is_backslash_escaped(text, index):
            out.append(text[index])
            index += 1
            continue

        run_len = _backtick_run_length(text, index)
        cursor = index + run_len
        close_start: int | None = None
        while cursor < len(text):
            if text[cursor] != "`":
                cursor += 1
                continue
            candidate_len = _backtick_run_length(text, cursor)
            if candidate_len == run_len:
                close_start = cursor
                break
            cursor += candidate_len

        if close_start is None:
            out.append(text[index : index + run_len])
            index += run_len
            continue

        code_text = text[index + run_len : close_start]
        code_text = re.sub(
            r"\([ \t\r\n]*optimizations/",
            "(__inline_code__/optimizations/",
            code_text,
        )
        out.append(
            text[index : index + run_len]
            + code_text
            + text[close_start : close_start + run_len]
        )
        index = close_start + run_len

    return "".join(out)


def canonicalize_angle_record_destinations(text: str) -> str:
    """Remove CommonMark angle brackets around optimization-record destinations."""
    return ANGLE_RECORD_DEST_RE.sub(
        lambda match: match.group("prefix") + match.group("dest"), text
    )


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

        title_start = _skip_link_whitespace(text, after_destination)
        if title_start is None:
            search_from = after_destination
            continue
        title_end = _parse_title(text, title_start)
        if title_end is None:
            search_from = after_destination
            continue
        outer_close = _skip_link_whitespace(text, title_end)
        if (
            outer_close is None
            or outer_close >= len(text)
            or text[outer_close] != ")"
        ):
            search_from = after_destination
            continue

        out.append(text[cursor : match.start()])
        out.append(f"[{match.group(1)}]({match.group(2)})")
        cursor = outer_close + 1
        search_from = cursor

    return "".join(out)


def _strip_blockquote_prefix(line: str) -> tuple[str, bool]:
    result = line
    changed = False
    while True:
        match = BLOCKQUOTE_PREFIX_RE.match(result)
        if match is None:
            return result, changed
        result = result[match.end() :]
        changed = True


def _standalone_html_tag_name(line: str) -> str | None:
    match = STANDALONE_HTML_TAG_RE.fullmatch(line)
    if match is None:
        return None
    return (match.group("open") or match.group("close")).lower()


def _is_type7_complete_tag_line(line: str) -> bool:
    tag = _standalone_html_tag_name(line)
    return tag is not None and tag not in HTML_BLOCK_TAGS and tag not in TYPE1_HTML_TAGS


def _line_can_open_or_continue_paragraph(line: str) -> bool:
    if not line.strip():
        return False
    if line.startswith("\t") or line.startswith("    "):
        return False
    if ATX_HEADING_RE.match(line) or FENCE_LINE_RE.match(line):
        return False
    if THEMATIC_BREAK_RE.fullmatch(line) or LIST_BLOCK_RE.match(line):
        return False
    if BLOCKQUOTE_PREFIX_RE.match(line):
        return False
    if _standalone_html_tag_name(line) is not None or line.lstrip().startswith("<"):
        return False
    return True


def _list_item_layout(line: str) -> tuple[int, int] | None:
    """Return marker/content columns for a Markdown list item."""
    match = LIST_ITEM_RE.match(line)
    if match is None:
        return None

    marker_indent = len(match.group("indent"))
    marker_width = len(match.group("marker"))
    column = marker_indent + marker_width
    spacing_columns = 0
    for char in match.group("spacing"):
        width = 4 - (column % 4) if char == "\t" else 1
        column += width
        spacing_columns += width

    if spacing_columns <= 0:
        return None
    effective_spacing = spacing_columns if spacing_columns <= 4 else 1
    return marker_indent, marker_indent + marker_width + effective_spacing


def canonicalize_top_level_atx_indentation(text: str) -> str:
    """Deindent only ATX headings that CommonMark renders outside list items."""
    out: list[str] = []
    list_content_indents: list[int] = []
    blank_count = 0
    fence_char: str | None = None
    fence_len = 0
    fence_open_re = re.compile(
        r"^ {0,3}((?:[~]{3,}|[" + chr(96) + r"]{3,}))(.*)$"
    )

    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]

        if fence_char is not None:
            close = re.fullmatch(
                rf" {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*", content
            )
            if close is not None:
                fence_char = None
                fence_len = 0
            out.append(raw)
            continue

        if not content.strip():
            blank_count += 1
            if blank_count >= 2:
                list_content_indents.clear()
            out.append(raw)
            continue

        had_blank = blank_count > 0
        blank_count = 0

        fence = fence_open_re.match(content)
        if fence is not None:
            run = fence.group(1)
            info = fence.group(2)
            if run[0] != chr(96) or chr(96) not in info:
                fence_char = run[0]
                fence_len = len(run)
                out.append(raw)
                continue

        leading_spaces = len(content) - len(content.lstrip(" "))
        if (
            had_blank
            and list_content_indents
            and leading_spaces == 0
            and _list_item_layout(content) is None
        ):
            list_content_indents.clear()

        if THEMATIC_BREAK_RE.fullmatch(content):
            while list_content_indents and leading_spaces < list_content_indents[-1]:
                list_content_indents.pop()
            out.append(raw)
            continue

        list_layout = _list_item_layout(content)
        if list_layout is not None:
            marker_indent, content_indent = list_layout
            list_match = LIST_ITEM_RE.match(content)
            item_content = (
                content[list_match.end() :] if list_match is not None else ""
            )
            item_fence = fence_open_re.match(item_content)
            if item_fence is not None:
                run = item_fence.group(1)
                info = item_fence.group(2)
                if run[0] != chr(96) or chr(96) not in info:
                    fence_char = run[0]
                    fence_len = len(run)
            while list_content_indents and marker_indent < list_content_indents[-1]:
                list_content_indents.pop()

            if not list_content_indents:
                if marker_indent <= 3:
                    list_content_indents.append(content_indent)
            elif marker_indent >= list_content_indents[-1]:
                list_content_indents.append(content_indent)

            out.append(raw)
            continue

        block_interrupt = bool(
            ATX_HEADING_RE.match(content)
            or FENCE_LINE_RE.match(content)
            or BLOCKQUOTE_PREFIX_RE.match(content)
            or _standalone_html_tag_name(content) is not None
        )
        if list_content_indents and block_interrupt:
            while list_content_indents and leading_spaces < list_content_indents[-1]:
                list_content_indents.pop()

        atx_indent = ATX_INDENT_RE.match(content)
        if atx_indent is not None and not list_content_indents:
            content = content[atx_indent.end() :]

        out.append(content + ending)

    return "".join(out)


def canonicalize_nested_reference_definitions(text: str) -> str:
    """Expose rendered reference definitions inside quote/list containers."""
    out: list[str] = []
    paragraph_open = False
    reference_title_expected = False
    reference_destination_expected = False
    active_list_indent: int | None = None
    fence_char: str | None = None
    fence_len = 0
    fence_requires_quote = False
    html_mode: str | None = None
    html_end: str | None = None
    html_requires_quote = False
    fence_open_re = re.compile(
        r"^ {0,3}((?:[~]{3,}|[" + chr(96) + r"]{3,}))(.*)$"
    )
    definition_prefix_re = re.compile(
        r"^\[(?:\\.|[^\[\]\\])+\]:[ \t]*(?P<rest>.*)$"
    )

    def html_start(view: str) -> tuple[str, str | None] | None:
        if re.match(r"^ {0,3}<!--", view):
            return "token", "-->"
        type1 = re.match(
            r"^ {0,3}<(?P<tag>script|pre|style|textarea)(?:[ \t]|>|$)",
            view,
            re.IGNORECASE,
        )
        if type1 is not None:
            return "tag", type1.group("tag").lower()
        if re.match(r"^ {0,3}<\?", view):
            return "token", "?>"
        if re.match(r"^ {0,3}<!\[CDATA\[", view):
            return "token", "]]>"
        if re.match(r"^ {0,3}<![A-Z]", view):
            return "token", ">"
        block_tag = re.match(
            r"^ {0,3}</?(?P<tag>[A-Za-z][A-Za-z0-9-]*)(?:[ \t\n/>]|$)",
            view,
        )
        if (
            block_tag is not None
            and block_tag.group("tag").lower() in HTML_BLOCK_TAGS
        ):
            return "blank", None
        return None

    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]
        unquoted, quoted = _strip_blockquote_prefix(content)

        if fence_char is not None:
            if fence_requires_quote and not quoted:
                fence_char = None
                fence_len = 0
                fence_requires_quote = False
            else:
                fence_view = unquoted if quoted else content
                if active_list_indent is not None and not quoted:
                    leading = len(content) - len(content.lstrip(" "))
                    if leading >= active_list_indent:
                        fence_view = content[active_list_indent:]
                close = re.fullmatch(
                    rf" {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*",
                    fence_view,
                )
                if close is not None:
                    fence_char = None
                    fence_len = 0
                    fence_requires_quote = False
                out.append(raw)
                continue

        view = unquoted
        exposed = quoted
        list_marker = LIST_ITEM_RE.match(view)
        if list_marker is not None:
            layout = _list_item_layout(view)
            if layout is not None:
                _marker_indent, active_list_indent = layout
            view = view[list_marker.end() :]
            exposed = True
        elif active_list_indent is not None and not quoted:
            leading = len(content) - len(content.lstrip(" "))
            if content.strip() and leading >= active_list_indent:
                view = content[active_list_indent:]
                exposed = True
            elif content.strip():
                active_list_indent = None

        if html_mode is not None:
            if html_requires_quote and not quoted:
                html_mode = None
                html_end = None
                html_requires_quote = False
            else:
                html_view = view
                if html_mode == "tag":
                    if html_end is not None and re.search(
                        rf"</{re.escape(html_end)}>", html_view, re.IGNORECASE
                    ):
                        html_mode = None
                        html_end = None
                        html_requires_quote = False
                    out.append(raw)
                    continue
                if html_mode == "token":
                    if html_end is not None and html_end in html_view:
                        html_mode = None
                        html_end = None
                        html_requires_quote = False
                    out.append(raw)
                    continue
                if html_mode == "blank":
                    if not html_view.strip():
                        html_mode = None
                        html_end = None
                        html_requires_quote = False
                    out.append(raw)
                    continue

        fence = fence_open_re.match(view)
        if exposed and fence is not None:
            run = fence.group(1)
            info = fence.group(2)
            if run[0] != chr(96) or chr(96) not in info:
                fence_char = run[0]
                fence_len = len(run)
                fence_requires_quote = quoted
                reference_title_expected = False
                reference_destination_expected = False
                paragraph_open = False
                out.append(raw)
                continue

        started_html = html_start(view) if exposed else None
        if started_html is not None:
            html_mode, html_end = started_html
            html_requires_quote = quoted
            reference_title_expected = False
            reference_destination_expected = False
            paragraph_open = False
            if html_mode == "tag" and html_end is not None and re.search(
                rf"</{re.escape(html_end)}>", view, re.IGNORECASE
            ):
                html_mode = None
                html_end = None
                html_requires_quote = False
            elif html_mode == "token" and html_end is not None and html_end in view:
                html_mode = None
                html_end = None
                html_requires_quote = False
            out.append(raw)
            continue

        if not exposed:
            paragraph_open = False
            reference_title_expected = False
            reference_destination_expected = False
            out.append(raw)
            continue

        if not view.strip():
            paragraph_open = False
            reference_title_expected = False
            reference_destination_expected = False
            out.append(raw)
            continue

        normalized_view = view
        if active_list_indent is not None and list_marker is None and not quoted:
            normalized_view = " " + view.lstrip(" ")

        if reference_destination_expected:
            if re.match(r"^ {1,3}\S", normalized_view):
                out.append(normalized_view + ending)
                reference_destination_expected = False
                reference_title_expected = True
                paragraph_open = False
                continue
            reference_destination_expected = False

        if (
            reference_title_expected
            and LINK_REFERENCE_TITLE_CONTINUATION_RE.fullmatch(normalized_view)
        ):
            out.append(normalized_view + ending)
            reference_title_expected = False
            paragraph_open = False
            continue

        definition = definition_prefix_re.fullmatch(normalized_view)
        if definition is not None:
            if paragraph_open:
                out.append(raw)
                reference_title_expected = False
                reference_destination_expected = False
                paragraph_open = True
            else:
                out.append(normalized_view + ending)
                rest = definition.group("rest")
                reference_destination_expected = not bool(rest)
                reference_title_expected = bool(rest)
                paragraph_open = False
            continue

        out.append(raw)
        reference_title_expected = False
        reference_destination_expected = False
        paragraph_open = _line_can_open_or_continue_paragraph(normalized_view)

    return "".join(out)


def canonicalize_type7_html_paragraph_interruptions(text: str) -> str:
    """Keep type-7 complete tags inline when a CommonMark paragraph is already open."""
    out: list[str] = []
    paragraph_open = False

    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]

        if not content.strip():
            paragraph_open = False
            out.append(raw)
            continue

        if paragraph_open and _is_type7_complete_tag_line(content):
            out.append("! " + content.lstrip() + ending)
            paragraph_open = True
            continue

        out.append(raw)
        paragraph_open = _line_can_open_or_continue_paragraph(content)

    return "".join(out)


ORDERED_LIST_LINE_RE = re.compile(r"^ {0,3}(?P<number>\d{1,9})[.)][ \t]+")


def _line_interrupts_open_paragraph(line: str, paragraph_open: bool) -> bool:
    if not line.strip():
        return True
    ordered = ORDERED_LIST_LINE_RE.match(line)
    if ordered is not None:
        return not paragraph_open or ordered.group("number") == "1"
    return bool(
        re.match(r"^ {0,3}[-+*][ \t]+", line)
        or BLOCKQUOTE_PREFIX_RE.match(line)
        or ATX_HEADING_RE.match(line)
        or FENCE_LINE_RE.match(line)
        or THEMATIC_BREAK_RE.fullmatch(line)
        or line.startswith("\t")
        or line.startswith("    ")
    )


def canonicalize_nonsetext_thematic_breaks(text: str) -> str:
    """Rewrite only hyphen lines whose predecessor is truly a block interrupt."""
    out: list[str] = []
    paragraph_open = False
    previous_was_interrupt = False

    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]
        match = SETEXT_H2_LINE_RE.fullmatch(content)

        if match is not None and previous_was_interrupt:
            normalized = match.group("indent") + "- - -"
            out.append(normalized + ending)
            paragraph_open = False
            previous_was_interrupt = True
            continue

        out.append(raw)

        if not content.strip():
            paragraph_open = False
            previous_was_interrupt = True
            continue

        interrupted = _line_interrupts_open_paragraph(content, paragraph_open)
        previous_was_interrupt = interrupted
        paragraph_open = not interrupted

    return "".join(out)


def canonicalize_multiline_inline_comment_context(text: str) -> str:
    """Prevent comment-closing suffixes from becoming fresh block starts mid-paragraph."""
    out: list[str] = []
    comment_from_paragraph = False
    fence_char: str | None = None
    fence_len = 0

    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]

        if fence_char is not None:
            if re.fullmatch(
                rf" {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*", content
            ):
                fence_char = None
                fence_len = 0
            out.append(raw)
            continue

        fence = re.match(r"^ {0,3}(`{3,}|~{3,})(.*)$", content)
        if fence is not None:
            run = fence.group(1)
            info = fence.group(2)
            if run[0] != "`" or "`" not in info:
                fence_char = run[0]
                fence_len = len(run)
                out.append(raw)
                continue

        if comment_from_paragraph:
            close = content.find("-->")
            if close < 0:
                out.append(raw)
                continue
            suffix_start = close + 3
            suffix = content[suffix_start:]
            heading = ATX_SUFFIX_RE.match(suffix)
            if heading is not None:
                escaped_suffix = (
                    heading.group("indent")
                    + "\\"
                    + suffix[len(heading.group("indent")) :]
                )
                content = content[:suffix_start] + escaped_suffix
            comment_from_paragraph = False
            out.append(content + ending)
            continue

        cursor = 0
        while True:
            start = content.find("<!--", cursor)
            if start < 0:
                break
            close = content.find("-->", start + 4)
            if close >= 0:
                cursor = close + 3
                continue
            if content[:start].strip():
                comment_from_paragraph = True
            break
        out.append(raw)

    return "".join(out)


def _valid_inline_comment_end(text: str, index: int) -> int | None:
    if not text.startswith("<!--", index):
        return None
    end = text.find("-->", index + 4)
    if end < 0:
        return None
    body = text[index + 4 : end]
    if body.startswith(">") or body.startswith("->") or "--" in body or body.endswith("-"):
        return None
    return end + 3


def _strip_valid_inline_comments(text: str) -> str:
    out: list[str] = []
    index = 0
    while index < len(text):
        start = text.find("<!--", index)
        if start < 0:
            out.append(text[index:])
            break
        end = _valid_inline_comment_end(text, start)
        if end is None:
            out.append(text[index : start + 1])
            index = start + 1
            continue
        out.append(text[index:start])
        index = end
    return "".join(out)


def _render_placeholder_with_following_lines(
    lines: list[str], index: int, value: str
) -> str:
    """Render a field value together with a valid multiline inline comment."""
    source = value
    comment_start = source.find("<!--")
    if comment_start >= 0 and _valid_inline_comment_end(source, comment_start) is None:
        cursor = index + 1
        while cursor < len(lines):
            continuation = lines[cursor].rstrip("\r\n")
            if not continuation.strip():
                break
            source += "\n" + continuation
            if _valid_inline_comment_end(source, comment_start) is not None:
                break
            cursor += 1
    source = _strip_valid_inline_comments(source)
    return _render_placeholder_candidate(source)


def _inline_delimiter_flanking(
    text: str, start: int, run_len: int
) -> tuple[bool, bool]:
    """Return CommonMark-style left/right flanking for one delimiter run."""
    before = text[start - 1] if start > 0 else ""
    after_index = start + run_len
    after = text[after_index] if after_index < len(text) else ""

    before_whitespace = not before or before.isspace()
    after_whitespace = not after or after.isspace()
    before_punctuation = bool(before) and before in string.punctuation
    after_punctuation = bool(after) and after in string.punctuation

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


def _valid_emphasis_delimiter(
    text: str, start: int, marker: str, *, opening: bool
) -> bool:
    left_flanking, right_flanking = _inline_delimiter_flanking(
        text, start, len(marker)
    )
    if marker.startswith("_"):
        before = text[start - 1] if start > 0 else ""
        after_index = start + len(marker)
        after = text[after_index] if after_index < len(text) else ""
        before_punctuation = bool(before) and before in string.punctuation
        after_punctuation = bool(after) and after in string.punctuation
        if opening:
            return left_flanking and (not right_flanking or before_punctuation)
        return right_flanking and (not left_flanking or after_punctuation)
    return left_flanking if opening else right_flanking


def _strip_valid_inline_formatting(text: str) -> str:
    """Remove rendered emphasis/strong/strike delimiters, including partial spans."""
    markers = ("**", "__", "~~", "*", "_")
    changed = True
    while changed:
        changed = False
        for marker in markers:
            search_from = 0
            while True:
                start = text.find(marker, search_from)
                if start < 0:
                    break
                if not _valid_emphasis_delimiter(
                    text, start, marker, opening=True
                ):
                    search_from = start + len(marker)
                    continue

                close_search = start + len(marker)
                while True:
                    end = text.find(marker, close_search)
                    if end < 0:
                        break
                    if _valid_emphasis_delimiter(
                        text, end, marker, opening=False
                    ):
                        inner = text[start + len(marker) : end]
                        text = text[:start] + inner + text[end + len(marker) :]
                        changed = True
                        break
                    close_search = end + len(marker)

                if changed:
                    break
                search_from = start + len(marker)

            if changed:
                break
    return text


def _unwrap_valid_code_span(value: str) -> str:
    """Render a complete code span only when its delimiter run actually closes."""
    if not value.startswith(chr(96)):
        return value
    run_len = _backtick_run_length(value, 0)
    marker = chr(96) * run_len
    if (
        run_len == 0
        or len(value) < 2 * run_len
        or not value.endswith(marker)
        or marker in value[run_len : len(value) - run_len]
    ):
        return value
    code_text = value[run_len : len(value) - run_len].replace("\n", " ")
    if (
        len(code_text) >= 2
        and code_text.startswith(" ")
        and code_text.endswith(" ")
        and code_text.strip()
    ):
        code_text = code_text[1:-1]
    return code_text


def _strip_nonrendering_inline_html_regions(text: str) -> str:
    """Remove inline HTML regions whose descendants are not rendered."""
    out: list[str] = []
    index = 0
    hidden_state: tuple[str, int] | None = None

    while index < len(text):
        if hidden_state is not None:
            hidden_tag, depth = hidden_state
            tag_start = text.find("<", index)
            if tag_start < 0:
                return "".join(out)

            tag = INLINE_HTML_TAG_RE.match(text, tag_start)
            if tag is None:
                index = tag_start + 1
                continue

            source = tag.group(0)
            if re.fullmatch(
                rf"</{re.escape(hidden_tag)}[ \t\r\n]*>",
                source,
                re.IGNORECASE,
            ):
                depth -= 1
                hidden_state = None if depth == 0 else (hidden_tag, depth)
                index = tag.end()
                continue

            if re.match(
                rf"<{re.escape(hidden_tag)}(?:[ \t\r\n/>]|$)",
                source,
                re.IGNORECASE,
            ):
                if hidden_tag not in HTML_VOID_TAGS:
                    depth += 1
                    hidden_state = (hidden_tag, depth)
                index = tag.end()
                continue

            index = tag.end()
            continue

        tag_start = text.find("<", index)
        if tag_start < 0:
            out.append(text[index:])
            break

        tag = INLINE_HTML_TAG_RE.match(text, tag_start)
        if tag is None:
            out.append(text[index : tag_start + 1])
            index = tag_start + 1
            continue

        source = tag.group(0)
        if source.startswith("</"):
            out.append(text[index : tag.end()])
            index = tag.end()
            continue

        name = re.match(r"<(?P<tag>[A-Za-z][A-Za-z0-9-]*)", source)
        if name is None:
            out.append(text[index : tag.end()])
            index = tag.end()
            continue

        tag_name = name.group("tag").lower()
        hidden = (
            tag_name in NONRENDERING_INLINE_HTML_TAGS
            or HTML_HIDDEN_ATTR_RE.search(source) is not None
        )
        if not hidden:
            out.append(text[index : tag.end()])
            index = tag.end()
            continue

        out.append(text[index:tag_start])
        if tag_name in HTML_VOID_TAGS:
            index = tag.end()
            continue

        hidden_state = (tag_name, 1)
        index = tag.end()

    return "".join(out)

def _preserve_html_image_alt_text(text: str) -> str:
    """Replace visible HTML image tags with decoded accessible alt text."""
    def replace(match: re.Match[str]) -> str:
        source = match.group(0)
        if re.match(r"<img(?:[ \t\r\n]|/?>)", source, re.IGNORECASE) is None:
            return source
        alt_match = HTML_ALT_ATTR_RE.search(source)
        if alt_match is None:
            return ""
        alt = next(value for value in alt_match.groups() if value is not None)
        return html.escape(html.unescape(alt), quote=False)

    return INLINE_HTML_TAG_RE.sub(replace, text)


def _render_placeholder_candidate(value: str) -> str:
    """Render the subset of inline Markdown relevant to template placeholders."""
    result = html.unescape(value.strip())
    changed = True
    while changed:
        changed = False

        code_rendered = _unwrap_valid_code_span(result)
        if code_rendered != result:
            result = code_rendered.strip()
            changed = True
            continue

        formatted = _strip_valid_inline_formatting(result)
        if formatted != result:
            result = formatted.strip()
            changed = True
            continue

        if result.startswith("!["):
            label_close = _find_label_close(result, 1)
            if (
                label_close is not None
                and label_close + 1 < len(result)
                and result[label_close + 1] == "("
            ):
                image_end = _find_inline_link_end(result, label_close + 1)
                if image_end == len(result):
                    result = result[2:label_close].strip()
                    changed = True
                    continue

        if result.startswith("["):
            label_close = _find_label_close(result, 0)
            if (
                label_close is not None
                and label_close + 1 < len(result)
                and result[label_close + 1] == "("
            ):
                link_end = _find_inline_link_end(result, label_close + 1)
                if link_end == len(result):
                    result = result[1:label_close].strip()
                    changed = True

    result = _strip_nonrendering_inline_html_regions(result)
    result = _preserve_html_image_alt_text(result)
    result = INLINE_HTML_TAG_RE.sub("", result)
    result = re.sub(r"\\(.)", r"\1", result)
    return html.unescape(result).strip()


def canonicalize_classification_placeholders(text: str) -> str:
    """Normalize rendered-but-unselected template values back to canonical source."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for index, raw in enumerate(lines):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]
        match = CLASSIFICATION_FIELD_RE.fullmatch(content)
        if match is None:
            out.append(raw)
            continue

        field = match.group("field")
        value = match.group("value")
        rendered = _render_placeholder_with_following_lines(lines, index, value)
        if rendered == CLASSIFICATION_TEMPLATE_VALUES[field]:
            out.append(match.group("prefix") + CLASSIFICATION_TEMPLATE_VALUES[field] + ending)
        else:
            out.append(raw)
    return "".join(out)


def canonicalize_generic_required_placeholders(text: str) -> str:
    """Turn rendered generic placeholders into empty values so the strict core rejects them."""
    lines = text.splitlines(keepends=True)
    out: list[str] = []
    for index, raw in enumerate(lines):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]
        match = REQUIRED_FIELD_RE.fullmatch(content)
        if match is None:
            out.append(raw)
            continue
        rendered = _render_placeholder_with_following_lines(
            lines, index, match.group("value")
        )
        if GENERIC_PLACEHOLDER_RE.fullmatch(rendered):
            out.append(match.group("prefix") + ending)
        else:
            out.append(raw)
    return "".join(out)


def _has_explicit_commit_context(prefix: str) -> bool:
    cleaned = prefix.rstrip(" \t`*_~([{<")
    return EXPLICIT_COMMIT_CONTEXT_RE.search(cleaned) is not None


def canonicalize_ambiguous_commit_tokens(text: str) -> str:
    """Break hash-shaped prose unless the token has explicit commit/revision context."""
    out: list[str] = []
    cursor = 0
    for match in HEX_TOKEN_RE.finditer(text):
        out.append(text[cursor : match.start()])
        token = match.group(0)
        prefix = text[max(0, match.start() - 80) : match.start()]
        if _has_explicit_commit_context(prefix):
            out.append(token)
        else:
            split_at = min(4, len(token) - 1)
            out.append(token[:split_at] + "-" + token[split_at:])
        cursor = match.end()
    out.append(text[cursor:])
    return "".join(out)


def canonicalize_markdown(text: str, *, link_scan_document: bool) -> str:
    text = canonicalize_top_level_atx_indentation(text)
    text = canonicalize_multiline_inline_comment_context(text)
    text = canonicalize_nested_reference_definitions(text)
    text = canonicalize_type7_html_paragraph_interruptions(text)
    text = canonicalize_nonsetext_thematic_breaks(text)
    text = canonicalize_classification_placeholders(text)
    text = canonicalize_generic_required_placeholders(text)
    if link_scan_document:
        text = canonicalize_angle_record_destinations(text)
        text = mask_inline_code_record_destinations(text)
        text = canonicalize_record_link_titles(text)
    return text


def markdown_inputs(root: Path) -> list[Path]:
    paths = [
        root / "README.md",
        root / "CATALOG.md",
        root / "OPTIMIZATION-PROBLEM.md",
    ]
    paths.extend(sorted((root / "optimizations").rglob("OPT-*.md")))
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
            normalized = canonicalize_markdown(
                original,
                link_scan_document=path.name in {"README.md", "CATALOG.md"},
            )
            if normalized != original:
                path.write_text(normalized, encoding="utf-8")

        core = scratch / "scripts" / CORE_NAME
        if not core.is_file():
            raise SystemExit(f"catalog-integrity: missing hardened core checker: {CORE_NAME}")

        completed = subprocess.run([sys.executable, str(core)], cwd=scratch, check=False)
        return completed.returncode


if __name__ == "__main__":
    raise SystemExit(main())
