#!/usr/bin/env python3
"""Run the catalog normalizer with definition-aware rendered validation."""

from __future__ import annotations

import re

import check_catalog_normalizer as normalizer

REFERENCE_DEFINITION_RE = re.compile(
    r"(?m)^ {0,3}\[(?P<label>(?:\\.|[^\[\]\\])+)]\:[ \t]+\S.*$"
)
REFERENCE_DEFINITION_DEST_RE = re.compile(
    r"^ {0,3}\[(?P<label>(?:\\.|[^\[\]\\])+)]\:[ \t]+"
    r"(?P<destination><[^>\r\n]+>|[^ \t\r\n]+)"
)
REFERENCE_FENCE_OPEN_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})(.*)$")
FULL_REFERENCE_LINK_RE = re.compile(
    r"^\[(?P<label>[^\]]*)\]\[(?P<reference>[^\]]*)\]$"
)
REFERENCE_RECORD_LINK_RE = re.compile(
    r"(?<!!)\[(?P<label>OPT-[A-Z]+-\d{3})\]\[(?P<reference>[^\]]*)\]"
)
SHORT_REFERENCE_RECORD_LINK_RE = re.compile(
    r"(?<!!)\[(?P<label>OPT-[A-Z]+-\d{3})\](?![\[(])"
)
ATX_LEVEL_1_OR_2_RE = re.compile(r"^#{1,2}(?:[ \t]|$)")
GENERIC_SECTION_PLACEHOLDER_RE = re.compile(
    r"^(?:[-*+]\s*)?(?:unknown|tbd|todo|n/?a|none|pending)(?:[.!?])?$",
    re.IGNORECASE,
)
STATUS_LINE_RE = re.compile(r"^(?P<prefix>\*\*Status:\*\*)[ \t]*(?P<payload>.*)$")
BACKTICK_SLASH_IDENTIFIER_RE = re.compile(
    r"`(?P<left>[A-Za-z0-9_.-]+)/(?P<right>[A-Za-z0-9_.-]+)`"
)
REPOSITORY_CONTEXT_RE = re.compile(r"\brepo(?:sitory)?\b", re.IGNORECASE)
MANDATORY_SECTION_HEADINGS = {
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
MANDATORY_HEADING_WITH_CLOSER_RE = re.compile(
    r"^(?P<indent> {0,3})##[ \t]+(?P<title>"
    + "|".join(
        re.escape(heading.removeprefix("## "))
        for heading in sorted(MANDATORY_SECTION_HEADINGS)
    )
    + r")[ \t]+#+[ \t]*$"
)
INVALID_REFERENCE_DESTINATION = "optimizations/__invalid_reference_destination__.md"
STATUS_WRAPPERS = ("**", "__", "~~", "*", "_", "`")


def _normalized_reference_label(label: str) -> str:
    """Approximate CommonMark reference-label normalization for integrity checks."""
    unescaped = re.sub(r"\\(.)", r"\1", label)
    return " ".join(unescaped.split()).casefold()


def _reference_definition_source_lines(text: str) -> list[str]:
    """Return source lines outside fenced code while retaining continuations."""
    lines: list[str] = []
    fence_char: str | None = None
    fence_len = 0

    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    for raw in normalized.split("\n"):
        if fence_char is not None:
            close = re.fullmatch(
                rf" {{0,3}}{re.escape(fence_char)}{{{fence_len},}}[ \t]*", raw
            )
            if close is not None:
                fence_char = None
                fence_len = 0
            continue

        if not (raw.startswith("\t") or raw.startswith("    ")):
            opener = REFERENCE_FENCE_OPEN_RE.match(raw)
            if opener is not None:
                run = opener.group(1)
                info = opener.group(2)
                if run[0] != chr(96) or chr(96) not in info:
                    fence_char = run[0]
                    fence_len = len(run)
                    continue

        lines.append(raw)

    return lines


def _parse_reference_title(value: str) -> bool:
    """Return whether value is exactly one CommonMark-style reference title."""
    value = value.strip()
    if len(value) < 2:
        return False
    opener = value[0]
    if opener not in ('"', "'", "("):
        return False
    closer = ")" if opener == "(" else opener
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


def _parse_reference_destination_and_tail(value: str) -> tuple[str, str] | None:
    """Parse one reference destination and return destination plus trailing source."""
    source = value.lstrip(" \t")
    if not source:
        return None

    if source.startswith("<"):
        escaped = False
        for index in range(1, len(source)):
            char = source[index]
            if escaped:
                escaped = False
                continue
            if char == "\\":
                escaped = True
                continue
            if char == ">":
                return source[1:index], source[index + 1 :]
            if char == "<":
                return None
        return None

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


def _reference_entries(text: str) -> list[tuple[str, str]]:
    """Parse rendered CommonMark reference definitions in source order."""
    lines = _reference_definition_source_lines(text)
    entries: list[tuple[str, str]] = []
    prefix_re = re.compile(
        r"^ {0,3}\[(?P<label>(?:\\.|[^\[\]\\])+)\]:[ \t]*(?P<rest>.*)$"
    )
    index = 0

    while index < len(lines):
        match = prefix_re.fullmatch(lines[index])
        if match is None:
            index += 1
            continue

        label = match.group("label")
        rest = match.group("rest")
        consumed = 1

        if not rest:
            if index + 1 >= len(lines):
                index += 1
                continue
            continuation = lines[index + 1]
            if not re.match(r"^ {1,3}\S", continuation):
                index += 1
                continue
            rest = continuation.lstrip(" ")
            consumed += 1

        parsed = _parse_reference_destination_and_tail(rest)
        if parsed is None:
            index += consumed
            continue

        destination, tail = parsed
        tail = tail.strip()
        if tail:
            if not _parse_reference_title(tail):
                index += consumed
                continue
        elif index + consumed < len(lines):
            possible_title = lines[index + consumed]
            if re.match(r"^ {1,3}\S", possible_title) and _parse_reference_title(
                possible_title.strip()
            ):
                consumed += 1

        entries.append((label, re.sub(r"\\(.)", r"\1", destination)))
        index += consumed

    return entries


def _reference_definitions(text: str) -> set[str]:
    return {
        _normalized_reference_label(label)
        for label, _destination in _reference_entries(text)
    }


def _reference_destinations(text: str) -> dict[str, str]:
    """Collect the first rendered destination for each normalized label."""
    destinations: dict[str, str] = {}
    for label, destination in _reference_entries(text):
        destinations.setdefault(_normalized_reference_label(label), destination)
    return destinations


def _record_destination_path(destination: str) -> str | None:
    """Return a record path while allowing an optional URL fragment."""
    path, _separator, _fragment = destination.partition("#")
    if path.startswith("optimizations/") and path.endswith(".md"):
        return path
    return None


def _render_reference_aware_candidate(value: str, definitions: set[str]) -> str:
    """Render the placeholder-relevant subset including reference-style links."""
    rendered = normalizer._render_placeholder_candidate(value)

    reference = FULL_REFERENCE_LINK_RE.fullmatch(rendered)
    if reference is not None:
        label = reference.group("label")
        reference_label = reference.group("reference") or label
        if _normalized_reference_label(reference_label) in definitions:
            return normalizer._render_placeholder_candidate(label)

    shortcut = re.fullmatch(r"\[(?P<label>[^\]]*)\]", rendered)
    if shortcut is not None:
        label = shortcut.group("label")
        if _normalized_reference_label(label) in definitions:
            return normalizer._render_placeholder_candidate(label)

    return rendered


def _unwrap_balanced_formatting(value: str) -> str:
    """Remove only formatting markers that wrap the complete status category."""
    result = value.strip()
    changed = True
    while changed:
        changed = False
        for marker in STATUS_WRAPPERS:
            if (
                len(result) > 2 * len(marker)
                and result.startswith(marker)
                and result.endswith(marker)
            ):
                result = result[len(marker) : -len(marker)].strip()
                changed = True
                break
    return result


def canonicalize_classification_placeholders(text: str) -> str:
    """Reject canonical placeholders hidden behind valid reference links."""
    definitions = _reference_definitions(text)
    out: list[str] = []

    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]
        match = normalizer.CLASSIFICATION_FIELD_RE.fullmatch(content)
        if match is None:
            out.append(raw)
            continue

        field = match.group("field")
        rendered = _render_reference_aware_candidate(match.group("value"), definitions)
        if rendered == normalizer.CLASSIFICATION_TEMPLATE_VALUES[field]:
            out.append(
                match.group("prefix")
                + normalizer.CLASSIFICATION_TEMPLATE_VALUES[field]
                + ending
            )
        else:
            out.append(raw)

    return "".join(out)


def canonicalize_required_heading_closers(text: str) -> str:
    """Normalize optional ATX closing hashes on mandatory level-two headings."""
    out: list[str] = []
    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]
        match = MANDATORY_HEADING_WITH_CLOSER_RE.fullmatch(content)
        if match is None:
            out.append(raw)
            continue
        out.append(f"{match.group('indent')}## {match.group('title')}{ending}")
    return "".join(out)


def canonicalize_record_status_categories(text: str) -> str:
    """Normalize balanced Markdown around rendered record status categories."""
    if re.search(r"(?m)^# OPT-[A-Z]+-\d{3} — ", text) is None:
        return text

    out: list[str] = []
    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]
        match = STATUS_LINE_RE.fullmatch(content)
        if match is None:
            out.append(raw)
            continue

        payload = match.group("payload")
        category, separator, suffix = payload.partition(";")
        normalized_category = _unwrap_balanced_formatting(category)
        if separator:
            out.append(
                f"{match.group('prefix')} {normalized_category};{suffix}{ending}"
            )
        else:
            out.append(f"{match.group('prefix')} {normalized_category}{ending}")
    return "".join(out)


def canonicalize_uncontextualized_repository_tokens(text: str) -> str:
    """Prevent arbitrary slash-shaped code spans from satisfying source identity."""
    if re.search(r"(?m)^# OPT-[A-Z]+-\d{3} — ", text) is None:
        return text

    out: list[str] = []
    in_source_evidence = False
    repository_continuation_indent: int | None = None

    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]

        if content == "## Source evidence":
            in_source_evidence = True
            repository_continuation_indent = None
            out.append(raw)
            continue
        if ATX_LEVEL_1_OR_2_RE.match(content):
            in_source_evidence = False
            repository_continuation_indent = None
            out.append(raw)
            continue

        if not in_source_evidence:
            out.append(raw)
            continue

        if not content.strip():
            repository_continuation_indent = None
            out.append(raw)
            continue

        leading = len(content) - len(content.lstrip(" "))
        has_repository_context = REPOSITORY_CONTEXT_RE.search(content) is not None
        continuation_has_context = (
            repository_continuation_indent is not None
            and leading >= repository_continuation_indent
        )

        if has_repository_context:
            repository_continuation_indent = (
                leading + 2 if content.rstrip().endswith(":") else None
            )
            out.append(raw)
            continue

        if continuation_has_context:
            out.append(raw)
            continue

        repository_continuation_indent = None
        content = BACKTICK_SLASH_IDENTIFIER_RE.sub(
            lambda match: f"'{match.group('left')}/{match.group('right')}'",
            content,
        )
        out.append(content + ending)

    return "".join(out)


def canonicalize_mandatory_section_placeholders(text: str) -> str:
    """Make generic rendered placeholders non-substantive in required record sections."""
    if re.search(r"(?m)^# OPT-[A-Z]+-\d{3} — ", text) is None:
        return text

    definitions = _reference_definitions(text)
    out: list[str] = []
    active_required_section = False

    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]

        if content in MANDATORY_SECTION_HEADINGS:
            active_required_section = True
            out.append(raw)
            continue
        if ATX_LEVEL_1_OR_2_RE.match(content):
            active_required_section = False
            out.append(raw)
            continue

        if active_required_section:
            rendered = _render_reference_aware_candidate(content.strip(), definitions)
            if GENERIC_SECTION_PLACEHOLDER_RE.fullmatch(rendered):
                out.append(ending)
                continue

        out.append(raw)

    return "".join(out)


def canonicalize_reference_record_links(text: str) -> str:
    """Resolve reference-style OPT links so the core validates their destinations."""
    destinations = _reference_destinations(text)

    def destination_for(label: str, reference: str) -> str | None:
        reference_label = reference or label
        return destinations.get(_normalized_reference_label(reference_label))

    def replace_full(match: re.Match[str]) -> str:
        label = match.group("label")
        destination = destination_for(label, match.group("reference"))
        if destination is None:
            return match.group(0)
        if _record_destination_path(destination) is None:
            destination = INVALID_REFERENCE_DESTINATION
        return f"[{label}]({destination})"

    text = REFERENCE_RECORD_LINK_RE.sub(replace_full, text)

    def replace_short(match: re.Match[str]) -> str:
        label = match.group("label")
        destination = destinations.get(_normalized_reference_label(label))
        if destination is None:
            return match.group(0)
        if _record_destination_path(destination) is None:
            destination = INVALID_REFERENCE_DESTINATION
        return f"[{label}]({destination})"

    text = SHORT_REFERENCE_RECORD_LINK_RE.sub(replace_short, text)
    return normalizer.mask_inline_code_record_destinations(text)


normalizer.canonicalize_classification_placeholders = canonicalize_classification_placeholders
_base_canonicalize_markdown = normalizer.canonicalize_markdown


def canonicalize_markdown(text: str, *, link_scan_document: bool) -> str:
    normalized = _base_canonicalize_markdown(
        text, link_scan_document=link_scan_document
    )
    normalized = canonicalize_required_heading_closers(normalized)
    normalized = canonicalize_record_status_categories(normalized)
    normalized = canonicalize_uncontextualized_repository_tokens(normalized)
    normalized = canonicalize_mandatory_section_placeholders(normalized)
    if link_scan_document:
        normalized = canonicalize_reference_record_links(normalized)
    return normalized


normalizer.canonicalize_markdown = canonicalize_markdown


if __name__ == "__main__":
    raise SystemExit(normalizer.main())
