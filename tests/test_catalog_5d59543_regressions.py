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
    ("backslash-path", '<a href="optimizations\\does-not-exist.md">details</a>', False),
    ("entity-backslash-path", '<a href="optimizations&#92;does-not-exist.md">details</a>', False),
    ("valid-backslash-path", '<a href="' + RECORD.replace('/', '\\') + '">OPT-INC-001</a>', True),
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
                        self.assertIn("broken visible record link in " + document, result.stderr)
                        self.assertNotIn("Traceback", result.stderr)


if __name__ == "__main__":
    unittest.main()
