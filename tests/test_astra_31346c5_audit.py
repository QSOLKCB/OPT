from __future__ import annotations

import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RECORD = "optimizations/OPT-INC-001-signature-bound-incremental-execution.md"
PYRECORD = "optimizations/OPT-PY-001-deterministic-test-execution.md"
BROKEN = "optimizations/does-not-exist.md"

CASES = [
    dict(id="baseline", expected=0),
    dict(id="F1-image-across-paragraph", expected=1, readme="![alt\n\nx][record]\n\n[record]: " + BROKEN),
    dict(id="F1-control-valid-image", expected=0, readme="![alt][record]\n\n[record]: " + BROKEN),
    dict(id="F1-empty-alt-image", expected=0, readme="![][record]\n\n[record]: " + BROKEN),
    dict(id="F1-blank-line-spaces", expected=1, readme="![alt\n  \nx][record]\n\n[record]: " + BROKEN),
    dict(id="F1-control-soft-line-image", expected=0, readme="![alt\nx][record]\n\n[record]: " + BROKEN),
    dict(id="F2-textarea-recovered-end", expected=1, readme='<textarea>x</textarea class="ignored"><a href="' + BROKEN + '">details</a>'),
    dict(id="F2-textarea-end-slash", expected=1, readme='<textarea>x</textarea/><a href="' + BROKEN + '">details</a>'),
    dict(id="F2-control-textarea-normal-end", expected=1, readme='<textarea>x</textarea><a href="' + BROKEN + '">details</a>'),
    dict(id="F2-control-inert-textarea", expected=0, readme='<textarea><a href="' + BROKEN + '">details</a></textarea>'),
    dict(id="F2-control-inline-invalid-end-is-literal", expected=0, readme='text <textarea>x</textarea class="ignored"><a href="' + BROKEN + '">details</a>'),
    dict(id="F2-control-inline-normal-end", expected=1, readme='text <textarea>x</textarea><a href="' + BROKEN + '">details</a>'),
    dict(id="F3-embedded-tab", expected=1, readme='<a href="optimi&#x9;zations/does-not-exist.md">details</a>'),
    dict(id="F3-embedded-lf", expected=1, readme='<a href="optimi&#10;zations/does-not-exist.md">details</a>'),
    dict(id="F3-embedded-cr", expected=1, readme='<a href="optimi&#13;zations/does-not-exist.md">details</a>'),
    dict(id="F3-control-edge-space", expected=1, readme='<a href=" ' + BROKEN + ' ">details</a>'),
    dict(id="F3-control-real-space", expected=0, readme='<a href="optimi zations/does-not-exist.md">details</a>'),
    dict(id="F3-valid-source-tab", expected=0, source='<a href="ht&#9;tps://example.com/source">source</a>'),
    dict(id="F4-inline-destination-rewrite", expected=1, readme="[details](optimizations/[OPT-INC-001].md)\n\n[OPT-INC-001]: " + RECORD),
    dict(id="F4-control-no-definition", expected=1, readme="[details](optimizations/[OPT-INC-001].md)"),
    dict(id="F4-control-real-shortcut", expected=0, readme="[OPT-INC-001]\n\n[OPT-INC-001]: " + RECORD),
    dict(id="F4-inline-title-rewrite", expected=0, readme='[OPT-INC-001](' + RECORD + ' "[record]")\n\n[record]: ' + BROKEN),
    dict(id="F4-code-span-rewrite", expected=0, readme="`[record]`\n\n[record]: " + BROKEN),
    dict(id="F4-html-attribute-rewrite", expected=0, readme='<span title="[record]">text</span>\n\n[record]: ' + BROKEN),
    dict(
        id="old-code-label-entities",
        expected=1,
        replace_readme=[
            "[OPT-PY-001](" + PYRECORD + ")",
            "[`OPT&#45;PY&#45;001`](" + PYRECORD + ")",
        ],
    ),
    dict(id="old-semicolonless-entity", expected=1, readme="[OPT-PY-001](optimizations/OPT&#45PY&#45;001-deterministic-test-execution.md)"),
    dict(id="old-invalid-inline-comment", expected=1, readme="Text <!-- invalid -- comment [OPT-FAKE-999](" + BROKEN + ") -->"),
    dict(id="old-definition-shaped-prose", expected=0, validation="!\n[ref]: visible-text"),
    dict(id="old-unused-definition-source", expected=1, source="Evidence exists.\n\n[hidden]: https://example.com/source"),
    dict(id="old-list-excess-padding", expected=1, readme="-     ~~~\n  [details](" + BROKEN + ")"),
    dict(id="old-multiline-inline-html", expected=0, readme='Text <span\n title="[OPT-FAKE-999](' + BROKEN + ')">visible</span>'),
    dict(id="old-multiline-reference-title", expected=1, readme='[OPT-PY-001][multiline-ref]\n\n[multiline-ref]: ' + BROKEN + ' "first\n second"'),
    dict(id="old-list-fenced-definition", expected=1, readme="- ```\n  [shadow-list]: " + PYRECORD + "\n  ```\n\n[shadow-list]: " + BROKEN + "\n\n[details][shadow-list]"),
    dict(id="control-note-valid-relative", expected=0, source="[note](../sources/AUDIT-NOTE.md)", note="https://example.com/source"),
    dict(id="control-note-wrong-relative", expected=1, source="[note](sources/AUDIT-NOTE.md)", note="https://example.com/source"),
    dict(id="control-hidden-recovered-end", expected=1, readme='<div hidden>x</div class="ignored"><a href="' + BROKEN + '">details</a>'),
    dict(id="control-reference-image-source", expected=1, source="![diagram][ref]\n\n[ref]: https://example.com/source"),
    dict(id="control-broken-inline", expected=1, readme="[details](" + BROKEN + ")"),
]


class Astra31346c5AuditTests(unittest.TestCase):
    maxDiff = None

    def run_case(self, case: dict[str, object]) -> subprocess.CompletedProcess[str]:
        with tempfile.TemporaryDirectory(prefix="opt-pr3-astra-31346c5-") as temporary:
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

            for key, heading, following in (
                ("source", "Source evidence", "Problem"),
                ("validation", "Validation", "Target-repo adaptation"),
            ):
                value = case.get(key)
                if isinstance(value, str):
                    record_path = root / RECORD
                    before, rest = record_path.read_text(encoding="utf-8").split(
                        "## " + heading, 1
                    )
                    _old, after = rest.split("## " + following, 1)
                    record_path.write_text(
                        before
                        + "## "
                        + heading
                        + "\n\n"
                        + value
                        + "\n\n## "
                        + following
                        + after,
                        encoding="utf-8",
                    )

            note = case.get("note")
            if isinstance(note, str):
                (root / "sources" / "AUDIT-NOTE.md").write_text(
                    note + "\n", encoding="utf-8"
                )

            replacement = case.get("replace_readme")
            if isinstance(replacement, list) and len(replacement) == 2:
                old, new = replacement
                readme_path = root / "README.md"
                readme = readme_path.read_text(encoding="utf-8")
                self.assertIn(old, readme)
                readme_path.write_text(readme.replace(old, new), encoding="utf-8")

            readme_append = case.get("readme")
            if isinstance(readme_append, str):
                readme_path = root / "README.md"
                readme_path.write_text(
                    readme_path.read_text(encoding="utf-8")
                    + "\n\n"
                    + readme_append
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
                env=dict(os.environ, PYTHONDONTWRITEBYTECODE="1"),
            )

    def test_full_astra_31346c5_matrix(self) -> None:
        self.assertEqual(len(CASES), 38)
        for case in CASES:
            with self.subTest(case=case["id"]):
                completed = self.run_case(case)
                expected = case["expected"]
                self.assertEqual(
                    completed.returncode,
                    expected,
                    completed.stdout + completed.stderr,
                )
                if expected == 0:
                    self.assertIn("CATALOG_INTEGRITY_OK", completed.stdout)
                else:
                    self.assertIn("catalog-integrity:", completed.stderr)


if __name__ == "__main__":
    unittest.main()
