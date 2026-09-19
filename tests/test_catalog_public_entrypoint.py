from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = "optimizations/OPT-INC-001-signature-bound-incremental-execution.md"
VALID_RECORD = "optimizations/OPT-INC-001-signature-bound-incremental-execution.md"

CASES = [
    dict(id="baseline", expected=0),
    dict(
        id="F1-missing-note",
        expected=1,
        source="[note](sources/DOES-NOT-EXIST.md)",
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="F1-empty-note",
        expected=1,
        source="[note](sources/AUDIT-NOTE.md)",
        note="No provenance recorded.",
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="F2-invalid-note-target",
        expected=1,
        source="See sources/AUDIT-NOTE.md for the source.",
        note="[source](javascript:https://example.com)",
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="F2-prefix-note-target",
        expected=1,
        source="See sources/AUDIT-NOTE.md for the source.",
        note="[source](prefixhttps://example.com)",
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="F3-fenced-note",
        expected=0,
        source="See sources/AUDIT-NOTE.md for the source.",
        note="```text\nhttps://example.com/source\n```",
    ),
    dict(
        id="F4-double-decode",
        expected=1,
        source="[source](ht&amp;#x74;ps://example.com)",
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="F5-backslash-space",
        expected=0,
        readme=r"[OPT-FAKE-999](optimizations/missing\ file.md)",
    ),
    dict(
        id="F6-inline-textarea",
        expected=0,
        readme=(
            'text <textarea><a href="optimizations/does-not-exist.md">'
            "OPT-FAKE-999</a></textarea>"
        ),
    ),
    dict(
        id="F7-code-reference-label",
        expected=0,
        source="[`source`][ref]\n\n[ref]: https://example.com/source",
    ),
    dict(
        id="control-plain-reference-label",
        expected=0,
        source="[source][ref]\n\n[ref]: https://example.com/source",
    ),
    dict(
        id="control-valid-note",
        expected=0,
        source="See sources/AUDIT-NOTE.md for the source.",
        note="https://example.com/source",
    ),
    dict(
        id="control-top-level-fence",
        expected=0,
        source="```text\nhttps://example.com/source\n```",
    ),
    dict(
        id="control-invalid-top-level-target",
        expected=1,
        source="[source](javascript:https://example.com)",
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="control-single-entity-decode",
        expected=0,
        source="[source](ht&#x74;ps://example.com)",
    ),
    dict(
        id="control-encoded-missing-path",
        expected=1,
        readme="[details](optimiz%61tions/does-not-exist.md)",
        stderr_contains=(
            "broken visible record link in README.md: "
            "optimizations/does-not-exist.md"
        ),
    ),
    dict(
        id="control-space-nested-path",
        expected=0,
        readme="[OPT-FAKE-999](optimizations/(missing file.md))",
    ),
    dict(
        id="control-recovered-anchor-end",
        expected=0,
        readme=(
            '<a href="' + VALID_RECORD + '">OPT-INC-001'
            '</a class="ignored"> tail'
        ),
    ),
    dict(
        id="control-known-broken-link",
        expected=1,
        readme="[OPT-FAKE-999](optimizations/does-not-exist.md)",
        stderr_contains=(
            "broken visible record link in README.md: "
            "optimizations/does-not-exist.md"
        ),
    ),
    # Extra controls requested by the audit guidance.
    dict(
        id="control-valid-note-fragment",
        expected=0,
        source="[note](sources/AUDIT-NOTE.md#source)",
        note="https://example.com/source",
    ),
    dict(
        id="control-source-note-code-reference-label",
        expected=0,
        source="See sources/AUDIT-NOTE.md for the source.",
        note="[`source`][ref]\n\n[ref]: https://example.com/source",
    ),
    dict(
        id="control-textarea-followed-by-real-anchor",
        expected=0,
        readme=(
            'text <textarea><a href="optimizations/does-not-exist.md">'
            'OPT-FAKE-999</a></textarea> '
            '<a href="' + VALID_RECORD + '">OPT-INC-001</a>'
        ),
    ),
    dict(
        id="control-escaped-parenthesis",
        expected=0,
        readme=r"[example](notes/foo\(bar\).md)",
    ),
]


class CatalogPublicEntrypointTests(unittest.TestCase):
    maxDiff = None

    def run_case(self, case: dict[str, object]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="opt-catalog-regression-") as temporary:
            root = Path(temporary) / "repo"
            root.mkdir()

            for name in ("README.md", "CATALOG.md", "OPTIMIZATION-PROBLEM.md"):
                shutil.copy2(ROOT / name, root / name)
            for name in ("scripts", "optimizations", "sources"):
                shutil.copytree(
                    ROOT / name,
                    root / name,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )

            source = case.get("source")
            if isinstance(source, str):
                record_path = root / RECORD
                before, rest = record_path.read_text(encoding="utf-8").split(
                    "## Source evidence", 1
                )
                _old_source, after = rest.split("## Problem", 1)
                record_path.write_text(
                    before
                    + "## Source evidence\n\n"
                    + source
                    + "\n\n## Problem"
                    + after,
                    encoding="utf-8",
                )

            note = case.get("note")
            if isinstance(note, str):
                (root / "sources" / "AUDIT-NOTE.md").write_text(
                    note + "\n", encoding="utf-8"
                )

            readme = case.get("readme")
            if isinstance(readme, str):
                readme_path = root / "README.md"
                readme_path.write_text(
                    readme_path.read_text(encoding="utf-8")
                    + "\n\n"
                    + readme
                    + "\n",
                    encoding="utf-8",
                )

            return subprocess.run(
                [sys.executable, "scripts/check_catalog.py"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

    def test_astra_audit_public_entrypoint_contract(self) -> None:
        for case in CASES:
            with self.subTest(case=case["id"]):
                completed = self.run_case(case)
                self.assertEqual(
                    completed.returncode,
                    case["expected"],
                    completed.stdout + completed.stderr,
                )
                if completed.returncode == 0:
                    self.assertIn("CATALOG_INTEGRITY_OK", completed.stdout)
                stderr_contains = case.get("stderr_contains")
                if isinstance(stderr_contains, str):
                    self.assertIn(stderr_contains, completed.stderr)


if __name__ == "__main__":
    unittest.main()
