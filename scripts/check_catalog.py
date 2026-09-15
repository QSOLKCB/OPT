#!/usr/bin/env python3
"""Run the catalog normalizer with definition-aware placeholder rendering."""

from __future__ import annotations

import re

import check_catalog_normalizer as normalizer

REFERENCE_DEFINITION_RE = re.compile(
    r"(?m)^ {0,3}\[(?P<label>(?:\\.|[^\[\]\\])+)]\:[ \t]+\S.*$"
)
FULL_REFERENCE_LINK_RE = re.compile(
    r"^\[(?P<label>[^\]]*)\]\[(?P<reference>[^\]]*)\]$"
)


def _normalized_reference_label(label: str) -> str:
    """Approximate CommonMark reference-label normalization for placeholder checks."""
    unescaped = re.sub(r"\\(.)", r"\1", label)
    return " ".join(unescaped.split()).casefold()


def _reference_definitions(text: str) -> set[str]:
    return {
        _normalized_reference_label(match.group("label"))
        for match in REFERENCE_DEFINITION_RE.finditer(text)
    }


def canonicalize_classification_placeholders(text: str) -> str:
    """Reject canonical placeholders hidden behind valid full/collapsed reference links."""
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
        value = match.group("value")
        rendered = normalizer._render_placeholder_candidate(value)

        reference = FULL_REFERENCE_LINK_RE.fullmatch(rendered)
        if reference is not None:
            label = reference.group("label")
            reference_label = reference.group("reference") or label
            if _normalized_reference_label(reference_label) in definitions:
                rendered = normalizer._render_placeholder_candidate(label)

        if rendered == normalizer.CLASSIFICATION_TEMPLATE_VALUES[field]:
            out.append(
                match.group("prefix")
                + normalizer.CLASSIFICATION_TEMPLATE_VALUES[field]
                + ending
            )
        else:
            out.append(raw)

    return "".join(out)


normalizer.canonicalize_classification_placeholders = canonicalize_classification_placeholders


if __name__ == "__main__":
    raise SystemExit(normalizer.main())
