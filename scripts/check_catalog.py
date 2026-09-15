#!/usr/bin/env python3
"""Normalize supported CommonMark syntax, then run the hardened catalog checker.

The core checker intentionally stays strict and source-oriented. This front end creates a
scratch copy, canonicalizes rendering-equivalent forms that the core otherwise rejects
or overlooks, and runs the core against that copy:

* one-to-three spaces before ATX headings (valid CommonMark indentation),
* optional Markdown titles on links to optimization-record Markdown files,
* inline-code examples that resemble optimization-record links,
* block-quoted link-reference definitions that actually parse as definitions,
* classification placeholders hidden behind rendering-only inline formatting,
* generic TODO/TBD-style required-field placeholders,
* hash-shaped source text that lacks explicit commit/revision context, and
* type-7 raw-HTML tags that CommonMark keeps inside an already-open paragraph.

The repository working tree is never modified by this normalization step.
"""

from __future__ import annotations

import html
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CORE_NAME = "check_catalog_core.py"
ATX_INDENT_RE = re.compile(r"(?m)^ {1,3}(?=#{1,6}(?:[ \t]|$))")
ATX_HEADING_RE = re.compile(r"^ {0,3}#{1,6}(?:[ \t]|$)")
FENCE_LINE_RE = re.compile(r"^ {0,3}(?:`{3,}|~{3,})")
LIST_BLOCK_RE = re.compile(r"^ {0,3}(?:[-+*]|\d+[.)])[ \t]+")
THEMATIC_BREAK_RE = re.compile(
    r"^ {0,3}(?:\*(?:[ \t]*\*){2,}|-(?:[ \t]*-){2,}|_(?:[ \t]*_){2,})[ \t]*$"
)
RECORD_LINK_START_RE = re.compile(
    r"\[([^\]\r\n]+)\]\((optimizations/[^\s)#]+\.md)"
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
    r"|@"
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
        code_text = code_text.replace(
            "(optimizations/", "(__inline_code__/optimizations/"
        )
        out.append(
            text[index : index + run_len]
            + code_text
            + text[close_start : close_start + run_len]
        )
        index = close_start + run_len

    return "".join(out)


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


def canonicalize_nested_reference_definitions(text: str) -> str:
    """Expose only quoted reference definitions that CommonMark parses as definitions."""
    out: list[str] = []
    paragraph_open = False
    reference_title_expected = False

    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]
        unquoted, changed = _strip_blockquote_prefix(content)

        if not changed:
            paragraph_open = False
            reference_title_expected = False
            out.append(raw)
            continue

        stripped = unquoted.strip()
        if not stripped:
            paragraph_open = False
            reference_title_expected = False
            out.append(raw)
            continue

        if reference_title_expected and LINK_REFERENCE_TITLE_CONTINUATION_RE.fullmatch(unquoted):
            out.append(unquoted + ending)
            reference_title_expected = False
            paragraph_open = False
            continue

        if LINK_REFERENCE_DEFINITION_RE.fullmatch(stripped):
            if paragraph_open:
                out.append(raw)
                reference_title_expected = False
                paragraph_open = True
            else:
                out.append(unquoted + ending)
                reference_title_expected = True
                paragraph_open = False
            continue

        out.append(raw)
        reference_title_expected = False
        paragraph_open = _line_can_open_or_continue_paragraph(unquoted)

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
            # The core is deliberately source-strict and would otherwise start a type-7
            # raw-HTML block here. Prefix only the scratch copy so it remains paragraph
            # text, matching CommonMark's rule that type-7 blocks cannot interrupt one.
            out.append("INLINE_HTML_CONTINUATION " + content.lstrip() + ending)
            paragraph_open = True
            continue

        out.append(raw)
        paragraph_open = _line_can_open_or_continue_paragraph(content)

    return "".join(out)


def _render_placeholder_candidate(value: str) -> str:
    """Render the subset of inline Markdown relevant to template placeholders."""
    result = html.unescape(value.strip())
    changed = True
    while changed:
        changed = False
        for marker in INLINE_WRAPPERS:
            if (
                len(result) > 2 * len(marker)
                and result.startswith(marker)
                and result.endswith(marker)
            ):
                result = result[len(marker) : -len(marker)].strip()
                changed = True
                break
        if changed:
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

    result = INLINE_HTML_TAG_RE.sub("", result)
    result = re.sub(r"\\(.)", r"\1", result)
    return html.unescape(result).strip()


def canonicalize_classification_placeholders(text: str) -> str:
    """Normalize rendered-but-unselected template values back to canonical source."""
    out: list[str] = []
    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]
        match = CLASSIFICATION_FIELD_RE.fullmatch(content)
        if match is None:
            out.append(raw)
            continue

        field = match.group("field")
        value = match.group("value")
        if _render_placeholder_candidate(value) == CLASSIFICATION_TEMPLATE_VALUES[field]:
            out.append(match.group("prefix") + CLASSIFICATION_TEMPLATE_VALUES[field] + ending)
        else:
            out.append(raw)
    return "".join(out)


def canonicalize_generic_required_placeholders(text: str) -> str:
    """Turn rendered generic placeholders into empty values so the strict core rejects them."""
    out: list[str] = []
    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]
        match = REQUIRED_FIELD_RE.fullmatch(content)
        if match is None:
            out.append(raw)
            continue
        rendered = _render_placeholder_candidate(match.group("value"))
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
    text = ATX_INDENT_RE.sub("", text)
    text = canonicalize_nested_reference_definitions(text)
    text = canonicalize_type7_html_paragraph_interruptions(text)
    text = canonicalize_classification_placeholders(text)
    text = canonicalize_generic_required_placeholders(text)
    text = canonicalize_ambiguous_commit_tokens(text)
    if link_scan_document:
        text = mask_inline_code_record_destinations(text)
        text = canonicalize_record_link_titles(text)
    return text


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
