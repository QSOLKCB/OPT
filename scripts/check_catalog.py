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


def _reference_definitions(text: str) -> set[str]:
    return {
        _normalized_reference_label(match.group("label"))
        for match in REFERENCE_DEFINITION_RE.finditer(text)
    }


def _reference_destinations(text: str) -> dict[str, str]:
    """Collect simple reference destinations used by OPT record links."""
    destinations: dict[str, str] = {}
    for raw in text.splitlines():
        if raw.startswith("\t") or raw.startswith("    "):
            continue
        match = REFERENCE_DEFINITION_DEST_RE.match(raw)
        if match is None:
            continue
        destination = match.group("destination")
        if destination.startswith("<") and destination.endswith(">"):
            destination = destination[1:-1]
        destination = re.sub(r"\\(.)", r"\1", destination)
        destinations[_normalized_reference_label(match.group("label"))] = destination
    return destinations


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
    for raw in text.splitlines(keepends=True):
        content = raw.rstrip("\r\n")
        ending = raw[len(content) :]

        if content == "## Source evidence":
            in_source_evidence = True
            out.append(raw)
            continue
        if ATX_LEVEL_1_OR_2_RE.match(content):
            in_source_evidence = False
            out.append(raw)
            continue

        if in_source_evidence and not REPOSITORY_CONTEXT_RE.search(content):
            content = BACKTICK_SLASH_IDENTIFIER_RE.sub(
                lambda match: f"'{match.group('left')}/{match.group('right')}'",
                content,
            )
            out.append(content + ending)
            continue

        out.append(raw)

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
        if not (destination.startswith("optimizations/") and destination.endswith(".md")):
            destination = INVALID_REFERENCE_DESTINATION
        return f"[{label}]({destination})"

    text = REFERENCE_RECORD_LINK_RE.sub(replace_full, text)

    def replace_short(match: re.Match[str]) -> str:
        label = match.group("label")
        destination = destinations.get(_normalized_reference_label(label))
        if destination is None:
            return match.group(0)
        if not (destination.startswith("optimizations/") and destination.endswith(".md")):
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
