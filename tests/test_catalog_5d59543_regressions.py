"""Public-entrypoint regressions for review 5255643133, with valid controls."""
from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = "optimizations/OPT-INC-001-signature-bound-incremental-execution.md"
BROKEN = "optimizations/does-not-exist.md"
DEFINITION = "\n\n[record]: " + BROKEN + "\n"

CASES = [
    ("heading-interruption", "[outer\\\n# [record]](not-a-record)" + DEFINITION, False),
    ("heading-interruption-no-escape", "[outer\n## [record]](not-a-record)" + DEFINITION, False),
    ("list-interruption", "[outer\n- [record]](not-a-record)" + DEFINITION, False),
    ("ordered-list-interruption", "[outer\n1. [record]](not-a-record)" + DEFINITION, False),
    ("quote-interruption", "[outer\n> [record]](not-a-record)" + DEFINITION, False),
    ("soft-label-control", "[outer\ntext](not-a-record)" + DEFINITION, True),
    ("indented-continuation-control", "[outer\n    text](not-a-record)" + DEFINITION, True),
    ("list-container-heading-interruption", "- [outer\n    # [record]](not-a-record)" + DEFINITION, False),
    ("list-container-soft-control", "- [outer\n    text](not-a-record)" + DEFINITION, True),
    ("noninitial-ordered-continuation", "[outer\n2. text](not-a-record)" + DEFINITION, True),
    ("incomplete-inline-fallback", "[record](oops" + DEFINITION, False),
    ("incomplete-title-fallback", '[record](notes.md "oops' + DEFINITION, False),
    ("complete-inline-precedence", "[record](notes.md)" + DEFINITION, True),
    ("inline-image-control", "![record](notes.png)" + DEFINITION, True),
    ("reference-image-control", "![diagram][record]" + DEFINITION, True),
    ("p-details-close", '<p hidden>x<details><summary><a href="' + BROKEN + '">details</a></summary></details>', False),
    ("p-figure-close", '<p hidden>x<figure><a href="' + BROKEN + '">details</a></figure>', False),
    ("p-figcaption-close", '<p hidden>x<figcaption><a href="' + BROKEN + '">details</a></figcaption>', False),
    ("p-summary-close", '<details open><p hidden>x<summary><a href="' + BROKEN + '">details</a></summary></details>', False),
    ("li-parent-close", '<ul><li hidden>x</ul><a href="' + BROKEN + '">details</a>', False),
    ("li-ordered-parent-close", '<ol><li hidden>x</ol><a href="' + BROKEN + '">details</a>', False),
    ("dd-parent-close", '<dl><dd hidden>x</dl><a href="' + BROKEN + '">details</a>', False),
    ("nested-list-stays-hidden", '<ul><li hidden>x<ul><li>nested</li></ul><a href="' + BROKEN + '">details</a></li></ul>', True),
    ("nested-list-parent-then-visible", '<ul><li hidden>x<ul><li>nested</li></ul></ul><a href="' + BROKEN + '">details</a>', False),
    ("hidden-ancestor-stays-hidden", '<div hidden><p>x<figure><a href="' + BROKEN + '">details</a></figure></div>', True),
    ("new-sibling-also-hidden", '<p hidden>x<figure hidden><a href="' + BROKEN + '">details</a></figure>', True),
    ("p-dialog-close", '<p hidden>x<dialog open><a href="' + BROKEN + '">details</a></dialog>', False),
    ("p-list-item-close", '<ul><p hidden>x<li><a href="' + BROKEN + '">details</a></li></ul>', False),
    ("p-parent-close", '<section><p hidden>x</section><a href="' + BROKEN + '">details</a>', False),
    ("dt-parent-close", '<dl><dt hidden>x</dl><a href="' + BROKEN + '">details</a>', False),
    ("nested-definition-stays-hidden", '<dl><dd hidden><dl><dd>nested</dl><a href="' + BROKEN + '">details</a></dl>', True),
    ("multiline-nested-list-stays-hidden", '<ul><li hidden>\n<ul>\n<li>nested</li>\n</ul>\n<a href="' + BROKEN + '">details</a>\n</li></ul>', True),
    ("multiline-parent-close", '<ul><li hidden>\n<span>x</span>\n</ul>\n<a href="' + BROKEN + '">details</a>', False),
    ("hidden-raw-text-is-not-markup", '<ul><li hidden><script>"</li></ul>"</script><a href="' + BROKEN + '">details</a></li></ul>', True),
    ("hidden-textarea-is-not-markup", '<ul><li hidden><textarea></li></ul></textarea><a href="' + BROKEN + '">details</a></li></ul>', True),
    ("button-implicit-close", '<button hidden>x<button></button><a href="' + BROKEN + '">details</a>', False),
    ("template-scope-boundary", '<div hidden><template></div><a href="' + BROKEN + '">details</a>', True),
    ("template-scope-close-control", '<div hidden><template></template></div><a href="' + BROKEN + '">details</a>', False),
    ("visible-xmp-is-literal", '<xmp><a href="' + BROKEN + '">details</a></xmp>', True),
    ("xmp-following-anchor-control", '<xmp>literal</xmp><a href="' + BROKEN + '">details</a>', False),
    ("self-closing-hidden-svg", '<svg hidden/><a href="' + BROKEN + '">details</a>', False),
    ("html-self-closing-control", '<div hidden/><a href="' + BROKEN + '">details</a>', True),
    ("plaintext-eof-literal", '<plaintext><a href="' + BROKEN + '">details</a>', True),
    ("foreignobject-html-integration", '<svg><foreignObject><div hidden/><a href="' + BROKEN + '">details</a></foreignObject></svg>', True),
    ("foreignobject-nested-svg-control", '<svg><foreignObject><svg hidden/><a href="' + BROKEN + '">details</a></foreignObject></svg>', False),
    ("nested-form-start-ignored", '<form hidden>x<form></form><a href="' + BROKEN + '">details</a>', False),
    ("single-hidden-form-control", '<form hidden>x<div></div><a href="' + BROKEN + '">details</a></form>', True),
    ("nested-anchor-recovery", '<a hidden>hidden<a href="' + BROKEN + '">details</a>', False),
    ("table-foster-parented-anchor", '<table hidden><a href="' + BROKEN + '">details</a></table>', False),
    ("table-cell-hidden-control", '<table hidden><tr><td><a href="' + BROKEN + '">details</a></td></tr></table>', True),
    ("raw-block-recovered-anchor", '<div>\n<a/ href="' + BROKEN + '">details</a>\n</div>', False),
    ("raw-block-recovered-anchor-spaced-solidus", '<div>\n<a / href="' + BROKEN + '">details</a>\n</div>', False),
    ("nested-foster-hidden-anchor", '<table><div hidden><a href="' + BROKEN + '">details</a></div></table>', True),
    ("markdown-malformed-anchor-control", 'text <a/ href="' + BROKEN + '">details</a>', True),
    ("backslash-path", '<a href="optimizations\\does-not-exist.md">details</a>', False),
    ("entity-backslash-path", '<a href="optimizations&#92;does-not-exist.md">details</a>', False),
    ("valid-backslash-path", '<a href="' + RECORD.replace('/', '\\') + '">OPT-INC-001</a>', True),
    ("select-input-closes-select", '<select hidden><input><a href="' + BROKEN + '">details</a>', False),
    ("nested-select-closes-select", '<select hidden><select><a href="' + BROKEN + '">details</a>', False),
    ("heading-current-node-recovery", '<h1 hidden>x<h2><a href="' + BROKEN + '">details</a></h2>', False),
    ("noframes-is-raw-text", '<noframes><a href="' + BROKEN + '">details</a></noframes>', True),
    ("mathml-mtext-html-integration", '<math><mtext><div hidden/><a href="' + BROKEN + '">details</a></mtext></math>', True),
    ("noncurrent-form-preserves-hidden-descendant", '<form hidden><div>x<form></form><a href="' + BROKEN + '">details</a></div>', True),
    ("legacy-image-is-void-img", '<image hidden><a href="' + BROKEN + '">details</a>', False),
    ("code-span-heading-boundary", "`open\n# [OPT-FAKE-999](" + BROKEN + ")`", False),
    ("code-span-soft-line-control", "`open\n[details](" + BROKEN + ")`", True),
    ("foreign-breakout-start", '<svg hidden><div></div><a href="' + BROKEN + '">details</a></svg>', False),
    ("table-close-reprocessed-from-cell", '<table hidden><tr><td>x</table><a href="' + BROKEN + '">details</a>', False),
    ("svg-mtext-is-not-mathml-integration", '<svg hidden><mtext><div></div><a href="' + BROKEN + '">details</a></mtext></svg>', False),
    ("generated-paragraph-closes-hidden-p", '<p hidden>\n\n[details](' + BROKEN + ')', False),
    ("table-mode-form-not-ancestry", '<table><form hidden><tr><td><a href="' + BROKEN + '">details</a></td></tr></table>', False),
    ("nested-nobr-recovery", '<nobr hidden>x<nobr></nobr><a href="' + BROKEN + '">details</a>', False),
    ("foreign-cdata-is-text", '<svg><![CDATA[<a href="' + BROKEN + '">details</a>]]></svg>', True),
    ("table-only-tr-ignored-in-body", '<div><tr hidden><a href="' + BROKEN + '">details</a></div>', False),
    ("foreign-end-tag-closes-svg", '<svg hidden></svg><a href="' + BROKEN + '">details</a>', False),
    ("generated-heading-closes-hidden-p", '<p hidden>\n\n# [details](' + BROKEN + ')', False),
    ("nested-table-start-closes-active-table", '<table hidden><table><tr><td><a href="' + BROKEN + '">details</a></td></tr></table>', False),
    ("misplaced-head-start-ignored", '<head hidden><a href="' + BROKEN + '">details</a></head>', False),
    ("svg-xlink-href-record-link", '<svg><a xlink:href="' + BROKEN + '"><text>details</text></a></svg>', False),
    ("html-xlink-href-control", '<a xlink:href="' + BROKEN + '">details</a>', True),
    ("late-frameset-start-ignored", '<frameset hidden><a href="' + BROKEN + '">OPT-FAKE-999</a></frameset>', False),
    ("misnested-formatting-reconstructs-hidden-i", '<b><i hidden></b><a href="' + BROKEN + '">OPT-FAKE-999</a></i>', True),
    ("foreign-self-closing-anchor-empty-label", '<svg><a xlink:href="' + BROKEN + '"/><text>OPT-FAKE-999</text></svg>', True),
    ("raw-comment-terminator-suffix", '<!--x--><a href="' + BROKEN + '">OPT-FAKE-999</a>', False),
    ("raw-pi-terminator-suffix", '<?x?><a href="' + BROKEN + '">OPT-FAKE-999</a>', False),
    ("raw-cdata-terminator-suffix", '<![CDATA[x]]><a href="' + BROKEN + '">OPT-FAKE-999</a>', False),
    ("raw-declaration-terminator-suffix", '<!DOCTYPE html><a href="' + BROKEN + '">OPT-FAKE-999</a>', False),
    ("non-http-scheme-control", '<a href="urn:optimizations\\does-not-exist.md">details</a>', True),
]


class Catalog5d59543RegressionTests(unittest.TestCase):
    maxDiff = None

    def run_document_case(self, document: str, fragment: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="opt-catalog-5d59543-") as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            for name in ("README.md", "CATALOG.md", "OPTIMIZATION-PROBLEM.md"):
                shutil.copy2(ROOT / name, root / name)
            for name in ("scripts", "optimizations", "sources"):
                shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))
            target = root / document
            target.write_text(target.read_text(encoding="utf-8") + "\n\n" + fragment + "\n", encoding="utf-8")
            return subprocess.run(
                [sys.executable, "scripts/check_catalog.py"],
                cwd=root, capture_output=True, text=True, check=False, timeout=30,
            )

    def test_review_findings_and_controls_in_both_catalog_documents(self) -> None:
        for document in ("README.md", "CATALOG.md"):
            for name, fragment, succeeds in CASES:
                with self.subTest(document=document, case=name):
                    result = self.run_document_case(document, fragment)
                    evidence = result.stdout + result.stderr
                    self.assertEqual(result.returncode, 0 if succeeds else 1, evidence)
                    if succeeds:
                        self.assertIn("CATALOG_INTEGRITY_OK records=20 frozen_v1=5", result.stdout)
                    else:
                        if name == "code-span-heading-boundary":
                            self.assertIn(
                                "visible record link in " + document,
                                result.stderr,
                            )
                        else:
                            self.assertIn(
                                "broken visible record link in " + document,
                                result.stderr,
                            )
                        self.assertNotIn("Traceback", result.stderr)

    def run_source_evidence_case(self, source_evidence: str) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="opt-catalog-source-select-") as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            for name in ("README.md", "CATALOG.md", "OPTIMIZATION-PROBLEM.md"):
                shutil.copy2(ROOT / name, root / name)
            for name in ("scripts", "optimizations", "sources"):
                shutil.copytree(ROOT / name, root / name, ignore=shutil.ignore_patterns("__pycache__"))

            record = root / RECORD
            text = record.read_text(encoding="utf-8")
            start = text.index("## Source evidence")
            body_start = text.index("\n", start) + 1
            next_section = text.index("\n## ", body_start)
            replacement = "\n" + source_evidence.strip() + "\n"
            record.write_text(
                text[:body_start] + replacement + text[next_section:],
                encoding="utf-8",
            )
            return subprocess.run(
                [sys.executable, "scripts/check_catalog.py"],
                cwd=root, capture_output=True, text=True, check=False, timeout=30,
            )

    def test_select_ignored_anchor_cannot_supply_source_identity(self) -> None:
        rejected = self.run_source_evidence_case(
            '<select><a href="https://example.com/source">source</a></select>'
        )
        evidence = rejected.stdout + rejected.stderr
        self.assertEqual(rejected.returncode, 1, evidence)
        self.assertIn("## Source evidence lacks a concrete source identity", rejected.stderr)
        self.assertNotIn("Traceback", rejected.stderr)

        accepted = self.run_source_evidence_case(
            '<a href="https://example.com/source">source</a>'
        )
        evidence = accepted.stdout + accepted.stderr
        self.assertEqual(accepted.returncode, 0, evidence)
        self.assertIn("CATALOG_INTEGRITY_OK records=20 frozen_v1=5", accepted.stdout)


    def test_hidden_html_ancestry_crosses_raw_block_boundaries(self) -> None:
        rejected = self.run_source_evidence_case(
            "<div hidden>\n\nhttps://example.com/source\n\n</div>"
        )
        evidence = rejected.stdout + rejected.stderr
        self.assertEqual(rejected.returncode, 1, evidence)
        self.assertTrue(
            (
                "## Source evidence lacks a concrete source identity"
                in rejected.stderr
            )
            or (
                "empty/template/structural/markup-only mandatory section ## Source evidence"
                in rejected.stderr
            ),
            evidence,
        )
        self.assertNotIn("Traceback", rejected.stderr)

        accepted = self.run_source_evidence_case(
            "<div>\n\nhttps://example.com/source\n\n</div>"
        )
        evidence = accepted.stdout + accepted.stderr
        self.assertEqual(accepted.returncode, 0, evidence)
        self.assertIn("CATALOG_INTEGRITY_OK records=20 frozen_v1=5", accepted.stdout)

    def run_extra_optimization_file(
        self, name: str, content: str
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="opt-catalog-record-discovery-") as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            for filename in ("README.md", "CATALOG.md", "OPTIMIZATION-PROBLEM.md"):
                shutil.copy2(ROOT / filename, root / filename)
            for dirname in ("scripts", "optimizations", "sources"):
                shutil.copytree(
                    ROOT / dirname,
                    root / dirname,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )
            (root / "optimizations" / name).write_text(content, encoding="utf-8")
            return subprocess.run(
                [sys.executable, "scripts/check_catalog.py"],
                cwd=root, capture_output=True, text=True, check=False, timeout=30,
            )

    def test_record_heading_cannot_bypass_filename_validation(self) -> None:
        rejected = self.run_extra_optimization_file(
            "new-record.md",
            "# OPT-NEW-001 — Unindexed record\n",
        )
        evidence = rejected.stdout + rejected.stderr
        self.assertEqual(rejected.returncode, 1, evidence)
        self.assertIn(
            "record Markdown filename does not follow OPT-<KIND>-<NNN>-... convention",
            rejected.stderr,
        )
        self.assertNotIn("Traceback", rejected.stderr)

        indented = self.run_extra_optimization_file(
            "new-record.md",
            " # OPT-NEW-001 — Indented record heading\n",
        )
        evidence = indented.stdout + indented.stderr
        self.assertEqual(indented.returncode, 1, evidence)
        self.assertIn(
            "record Markdown filename does not follow OPT-<KIND>-<NNN>-... convention",
            indented.stderr,
        )
        self.assertNotIn("Traceback", indented.stderr)

        accepted = self.run_extra_optimization_file(
            "NOTES.md",
            "# Optimization notes\n\nThis is not an OPT record.\n",
        )
        evidence = accepted.stdout + accepted.stderr
        self.assertEqual(accepted.returncode, 0, evidence)
        self.assertIn("CATALOG_INTEGRITY_OK records=20 frozen_v1=5", accepted.stdout)


    def run_status_visibility_case(
        self, wrapper_start: str, wrapper_end: str
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="opt-catalog-hidden-status-") as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            for filename in ("README.md", "CATALOG.md", "OPTIMIZATION-PROBLEM.md"):
                shutil.copy2(ROOT / filename, root / filename)
            for dirname in ("scripts", "optimizations", "sources"):
                shutil.copytree(
                    ROOT / dirname,
                    root / dirname,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )

            record = root / RECORD
            text = record.read_text(encoding="utf-8")
            status_start = text.index("**Status:**")
            status_end = text.index("\n", status_start)
            status_line = text[status_start:status_end]
            replacement = (
                wrapper_start + "\n\n" + status_line + "\n\n" + wrapper_end
            )
            record.write_text(
                text[:status_start] + replacement + text[status_end:],
                encoding="utf-8",
            )
            return subprocess.run(
                [sys.executable, "scripts/check_catalog.py"],
                cwd=root, capture_output=True, text=True, check=False, timeout=30,
            )

    def test_hidden_status_cannot_satisfy_schema_without_raw_collectors(self) -> None:
        rejected = self.run_status_visibility_case("<div hidden>", "</div>")
        evidence = rejected.stdout + rejected.stderr
        self.assertEqual(rejected.returncode, 1, evidence)
        self.assertIn("must contain exactly one visible Status line", rejected.stderr)
        self.assertNotIn("Traceback", rejected.stderr)

        accepted = self.run_status_visibility_case("<div>", "</div>")
        evidence = accepted.stdout + accepted.stderr
        self.assertEqual(accepted.returncode, 0, evidence)
        self.assertIn("CATALOG_INTEGRITY_OK records=20 frozen_v1=5", accepted.stdout)


        body_rejected = self.run_status_visibility_case("<body hidden></body>", "")
        evidence = body_rejected.stdout + body_rejected.stderr
        self.assertEqual(body_rejected.returncode, 1, evidence)
        self.assertIn("must contain exactly one visible Status line", body_rejected.stderr)
        self.assertNotIn("Traceback", body_rejected.stderr)

        body_accepted = self.run_status_visibility_case("<body></body>", "")
        evidence = body_accepted.stdout + body_accepted.stderr
        self.assertEqual(body_accepted.returncode, 0, evidence)
        self.assertIn("CATALOG_INTEGRITY_OK records=20 frozen_v1=5", body_accepted.stdout)


    def run_mandatory_section_case(
        self, body: str
    ) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="opt-catalog-section-content-") as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()
            for filename in ("README.md", "CATALOG.md", "OPTIMIZATION-PROBLEM.md"):
                shutil.copy2(ROOT / filename, root / filename)
            for dirname in ("scripts", "optimizations", "sources"):
                shutil.copytree(
                    ROOT / dirname,
                    root / dirname,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )

            record = root / RECORD
            text = record.read_text(encoding="utf-8")
            start = text.index("## Validation")
            body_start = text.index("\n", start) + 1
            next_section = text.index("\n## ", body_start)
            record.write_text(
                text[:body_start] + "\n" + body.rstrip() + "\n" + text[next_section:],
                encoding="utf-8",
            )
            return subprocess.run(
                [sys.executable, "scripts/check_catalog.py"],
                cwd=root, capture_output=True, text=True, check=False, timeout=30,
            )

    def test_literal_code_must_be_substantive_in_mandatory_sections(self) -> None:
        for name, body in (
            ("fenced-punctuation", "```text\n---\n```"),
            ("indented-punctuation", "    ---"),
        ):
            with self.subTest(case=name):
                rejected = self.run_mandatory_section_case(body)
                evidence = rejected.stdout + rejected.stderr
                self.assertEqual(rejected.returncode, 1, evidence)
                self.assertIn(
                    "empty/template/structural/markup-only mandatory section ## Validation",
                    rejected.stderr,
                )
                self.assertNotIn("Traceback", rejected.stderr)

        accepted = self.run_mandatory_section_case(
            "```text\nvalidate output bytes\n```"
        )
        evidence = accepted.stdout + accepted.stderr
        self.assertEqual(accepted.returncode, 0, evidence)
        self.assertIn("CATALOG_INTEGRITY_OK records=20 frozen_v1=5", accepted.stdout)


if __name__ == "__main__":
    unittest.main()
