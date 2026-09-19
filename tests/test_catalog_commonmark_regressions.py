from __future__ import annotations

import sys
import unittest
from pathlib import Path, PureWindowsPath

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "scripts"))

import check_catalog_core as core  # noqa: E402


class CatalogCommonMarkRegressionTests(unittest.TestCase):
    def test_html_url_backslashes_only_normalize_http_path(self) -> None:
        for source, expected in (
            (r"optimizations\record.md?q=\value#\fragment",
             r"optimizations/record.md?q=\value#\fragment"),
            (r"HTTPS:\\example.com\record.md", "HTTPS://example.com/record.md"),
            (r"urn:optimizations\record.md", r"urn:optimizations\record.md"),
            (r"optimizations&#92;record.md", "optimizations/record.md"),
            (r"optimizations&amp;#92;record.md", "optimizations&#92;record.md"),
            (r"optimizations%5Crecord.md", r"optimizations%5Crecord.md"),
        ):
            with self.subTest(source=source):
                self.assertEqual(core.decoded_html_url_attribute(source), expected)

    def test_fenced_source_identity_counts_as_visible_literal_content(self) -> None:
        url = "https://github.com/QSOLKCB/OPT/commit/0123456789abcdef0123456789abcdef01234567"
        document = f"""# OPT-TEST-001 — Example

## Source evidence

```text
{url}
```

## Problem

Rendered prose.
"""
        fenced: list[str] = []
        section = core.section_lines(
            document,
            "## Source evidence",
            rendered_fenced_text=fenced,
        )

        self.assertNotIn(url, "\n".join(section))
        self.assertIn(url, "\n".join(fenced))
        self.assertTrue(core.fenced_rendered_text_has_content(fenced))
        self.assertTrue(
            core.source_section_has_identity(
                section,
                rendered_fenced_text=fenced,
            )
        )

    def test_percent_encoded_unreserved_record_path_is_classified(self) -> None:
        destination = "optimiz%61tions/does-not-exist.md"
        self.assertEqual(
            core.normalize_repository_relative_path(destination),
            "optimizations/does-not-exist.md",
        )
        self.assertEqual(
            core.visible_record_links(f"[details]({destination})"),
            [("details", destination)],
        )

    def test_encoded_separator_and_traversal_are_rejected(self) -> None:
        self.assertIsNone(
            core.normalize_repository_relative_path(
                "optimizations%2FOPT-INC-001-signature-bound-incremental-execution.md"
            )
        )
        self.assertIsNone(
            core.normalize_repository_relative_path(
                "prefix/%2e%2e/optimizations/OPT-INC-001-signature-bound-incremental-execution.md"
            )
        )

    def test_space_inside_nested_bare_destination_is_not_a_link(self) -> None:
        text = "[OPT-FAKE-999](optimizations/(missing file.md))"
        open_paren = text.index("(")
        self.assertIsNone(core.find_inline_link_end(text, open_paren))
        self.assertIsNone(core.inline_link_destination(text, open_paren))
        self.assertEqual(core.visible_record_links(text), [])

    def test_recovered_html_end_tag_closes_anchor(self) -> None:
        destination = (
            "optimizations/OPT-INC-001-signature-bound-incremental-execution.md"
        )
        text = (
            f'<a href="{destination}">OPT-INC-001</a class="ignored"> tail'
        )
        self.assertEqual(
            core.html_anchor_links(text),
            [("OPT-INC-001", destination)],
        )

    def test_repository_relative_key_is_posix_on_windows_paths(self) -> None:
        root = PureWindowsPath(r"C:\\repo")
        record = root / "optimizations" / "OPT-INC-001-example.md"
        self.assertEqual(
            core.repository_relative_posix(record, root),
            "optimizations/OPT-INC-001-example.md",
        )

    def test_source_link_destination_must_be_complete_identity(self) -> None:
        self.assertFalse(
            core.source_section_has_identity(
                ["[source](javascript:https://example.com)"]
            )
        )
        self.assertFalse(
            core.source_section_has_identity(
                ["[source](prefixhttps://example.com)"]
            )
        )
        self.assertTrue(
            core.source_section_has_identity(
                ["[source](https://example.com/source)"]
            )
        )
        self.assertTrue(
            core.source_section_has_identity(
                ["[source](10.5281/zenodo.1234567)"]
            )
        )
        self.assertTrue(
            core.source_section_has_identity(
                ["[source](QSOLKCB/OPT)"]
            )
        )


if __name__ == "__main__":
    unittest.main()
