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
        source="[note](../sources/AUDIT-NOTE.md#source)",
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
    # Codex follow-up: HTML keeps the first duplicate attribute, even if valueless.
    dict(
        id="codex-valueless-first-href",
        expected=1,
        source='<a href href="https://example.com/source">source</a>',
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="control-valued-first-href",
        expected=0,
        source='<a href="https://example.com/source" href>source</a>',
    ),
    dict(
        id="control-empty-first-href",
        expected=1,
        source='<a href="" href="https://example.com/source">source</a>',
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="codex-valueless-first-record-href",
        expected=1,
        readme=(
            '<a href href="' + VALID_RECORD + '">OPT-INC-001</a>'
        ),
        stderr_contains="visible record link in README.md has invalid destination",
    ),
    dict(
        id="control-valued-first-record-href",
        expected=0,
        readme=(
            '<a href="' + VALID_RECORD + '" href>OPT-INC-001</a>'
        ),
    ),
    # Placeholder-only mandatory sections remain empty after ordinary punctuation.
    dict(
        id="codex-punctuated-placeholder",
        expected=1,
        validation="TODO;",
        stderr_contains=(
            "empty/template/structural/markup-only mandatory section ## Validation"
        ),
    ),
    dict(
        id="control-placeholder-with-substance",
        expected=0,
        validation="TODO; replace the temporary benchmark before release.",
    ),
    # Nested OPT-shaped Markdown must enter the same record/schema gate.
    dict(
        id="codex-nested-record",
        expected=1,
        nested_record=(
            "# OPT-NEW-999 — Nested unvalidated record\n\n"
            "**Status:** Source candidate\n"
        ),
        stderr_contains="missing visible sections",
    ),
    dict(
        id="codex-nested-normalizer-placeholder",
        expected=1,
        validation="TODO;",
        nest_existing_record=True,
        stderr_contains=(
            "empty/template/structural/markup-only mandatory section ## Validation"
        ),
    ),
    # Parsed Markdown note links resolve from the containing record.
    dict(
        id="codex-wrong-relative-source-note",
        expected=1,
        source="[note](sources/AUDIT-NOTE.md)",
        note="https://example.com/source",
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="control-correct-relative-source-note",
        expected=0,
        source="[note](../sources/AUDIT-NOTE.md)",
        note="https://example.com/source",
    ),
    # Current Codex review round.
    dict(
        id="codex-percent-encoded-source-note",
        expected=0,
        source="[note](../sources/AUDIT%2dNOTE.md)",
        note="https://example.com/source",
    ),
    dict(
        id="control-reject-encoded-source-separator",
        expected=1,
        source="[note](../sources/AUDIT%2fNOTE.md)",
        note="https://example.com/source",
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="codex-generic-contract-placeholder-punctuation",
        expected=1,
        contract_field=("X", "TODO;"),
        stderr_contains="has empty field X",
    ),
    dict(
        id="codex-classification-template-punctuation",
        expected=1,
        contract_field=(
            "Variables",
            "continuous / integer / categorical / conditional / mixed;",
        ),
        stderr_contains="unselected template placeholder for Variables",
    ),
    dict(
        id="codex-reference-dot-segment-record",
        expected=1,
        readme=(
            "[details][record-dot]\n\n"
            "[record-dot]: ./optimizations/does-not-exist.md"
        ),
        stderr_contains=(
            "broken visible record link in README.md: "
            "optimizations/does-not-exist.md"
        ),
    ),
    dict(
        id="codex-reference-percent-record",
        expected=1,
        readme=(
            "[details][record-percent]\n\n"
            "[record-percent]: optimiz%61tions/does-not-exist.md"
        ),
        stderr_contains=(
            "broken visible record link in README.md: "
            "optimizations/does-not-exist.md"
        ),
    ),
    dict(
        id="codex-template-record-title",
        expected=1,
        title="Optimization Name",
        stderr_contains="empty/template/markup-only Optimization Name",
    ),
    dict(
        id="codex-indented-source-evidence",
        expected=0,
        source="    https://example.com/source",
    ),
    # Latest Codex follow-up.
    dict(
        id="codex-percent-encoded-note-suffix",
        expected=0,
        source="[note](../sources/AUDIT-NOTE%2emd)",
        note="https://example.com/source",
    ),
    dict(
        id="codex-punctuated-todo-title",
        expected=1,
        title="TODO;",
        stderr_contains="empty/template/markup-only Optimization Name",
    ),
    dict(
        id="codex-punctuated-tbd-title",
        expected=1,
        title="TBD,",
        stderr_contains="empty/template/markup-only Optimization Name",
    ),
    dict(
        id="codex-punctuated-template-title",
        expected=1,
        title="Optimization Name;",
        stderr_contains="empty/template/markup-only Optimization Name",
    ),
    dict(
        id="codex-angle-reference-destination-with-space",
        expected=1,
        readme=(
            "[details][angle-record]\n\n"
            "[angle-record]: <optimizations/does not exist.md>"
        ),
        stderr_contains=(
            "broken visible record link in README.md: "
            "optimizations/does not exist.md"
        ),
    ),
    dict(
        id="control-angle-reference-valid-record",
        expected=0,
        readme=(
            "[OPT-INC-001][angle-valid]\n\n"
            "[angle-valid]: <" + VALID_RECORD + ">"
        ),
    ),
    dict(
        id="codex-reference-entity-newline",
        expected=1,
        readme=(
            "[details][record-newline]\n\n"
            "[record-newline]: <optimizations/does-not&#10;exist.md>"
        ),
        stderr_contains="broken visible record link in README.md:",
    ),
    dict(
        id="codex-reference-invalid-txt-suffix",
        expected=1,
        readme=(
            "[details][bad-txt]\n\n"
            "[bad-txt]: optimizations/does-not-exist.txt"
        ),
        stderr_contains=(
            "visible record link in README.md has invalid destination: "
            "optimizations/does-not-exist.txt"
        ),
    ),
    dict(
        id="codex-reference-query-suffix",
        expected=1,
        readme=(
            "[details][bad-query]\n\n"
            "[bad-query]: optimizations/does-not-exist.md?x=1"
        ),
        stderr_contains=(
            "visible record link in README.md has invalid destination: "
            "optimizations/does-not-exist.md?x=1"
        ),
    ),
    # Latest Codex image/HTML scan round.
    dict(
        id="codex-reference-image-not-source-identity",
        expected=1,
        source=(
            "![diagram][ref]\n\n"
            "[ref]: https://example.com/source"
        ),
        stderr_contains="## Source evidence lacks a concrete source identity",
    ),
    dict(
        id="codex-reference-image-not-record-link",
        expected=0,
        readme=(
            "![diagram][record-image]\n\n"
            "[record-image]: optimizations/does-not-exist.md"
        ),
    ),
    dict(
        id="codex-recovered-hidden-end-tag",
        expected=1,
        readme=(
            '<div hidden>x</div class="ignored">'
            '<a href="optimizations/does-not-exist.md">details</a>'
        ),
        stderr_contains=(
            "broken visible record link in README.md: "
            "optimizations/does-not-exist.md"
        ),
    ),
    dict(
        id="codex-html-href-leading-whitespace",
        expected=1,
        readme=(
            '<a href=" optimizations/does-not-exist.md">details</a>'
        ),
        stderr_contains=(
            "broken visible record link in README.md: "
            "optimizations/does-not-exist.md"
        ),
    ),
    dict(
        id="control-html-href-whitespace-valid-record",
        expected=0,
        readme=(
            '<a href="  ' + VALID_RECORD + '  ">OPT-INC-001</a>'
        ),
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

            title = case.get("title")
            if isinstance(title, str):
                record_path = root / RECORD
                record_text = record_path.read_text(encoding="utf-8")
                _first, separator, rest = record_text.partition("\n")
                self.assertTrue(separator)
                record_path.write_text(
                    "# OPT-INC-001 — " + title + "\n" + rest,
                    encoding="utf-8",
                )

            contract_field = case.get("contract_field")
            if (
                isinstance(contract_field, tuple)
                and len(contract_field) == 2
                and all(isinstance(item, str) for item in contract_field)
            ):
                field, value = contract_field
                record_path = root / RECORD
                lines = record_path.read_text(encoding="utf-8").splitlines(keepends=True)
                prefix = f"- {field}:"
                matches = [
                    index
                    for index, line in enumerate(lines)
                    if line.startswith(prefix)
                ]
                self.assertEqual(len(matches), 1)
                index = matches[0]
                ending = "\n" if lines[index].endswith("\n") else ""
                lines[index] = f"{prefix} {value}{ending}"
                record_path.write_text("".join(lines), encoding="utf-8")

            validation = case.get("validation")
            if isinstance(validation, str):
                record_path = root / RECORD
                before, rest = record_path.read_text(encoding="utf-8").split(
                    "## Validation", 1
                )
                _old_validation, after = rest.split("## Target-repo adaptation", 1)
                record_path.write_text(
                    before
                    + "## Validation\n\n"
                    + validation
                    + "\n\n## Target-repo adaptation"
                    + after,
                    encoding="utf-8",
                )

            nested_record = case.get("nested_record")
            if isinstance(nested_record, str):
                nested_dir = root / "optimizations" / "incubator"
                nested_dir.mkdir(parents=True, exist_ok=True)
                (nested_dir / "OPT-NEW-999-unvalidated.md").write_text(
                    nested_record,
                    encoding="utf-8",
                )

            if case.get("nest_existing_record") is True:
                source_path = root / RECORD
                nested_path = (
                    root
                    / "optimizations"
                    / "incubator"
                    / Path(RECORD).name
                )
                nested_path.parent.mkdir(parents=True, exist_ok=True)
                source_path.replace(nested_path)
                old_destination = RECORD
                new_destination = (
                    "optimizations/incubator/" + Path(RECORD).name
                )
                for document_name in ("README.md", "CATALOG.md"):
                    document_path = root / document_name
                    document_path.write_text(
                        document_path.read_text(encoding="utf-8").replace(
                            old_destination,
                            new_destination,
                        ),
                        encoding="utf-8",
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

    def test_symlinked_markdown_input_cannot_modify_external_target(self) -> None:
        with tempfile.TemporaryDirectory(prefix="opt-catalog-symlink-") as temporary:
            temp = Path(temporary)
            root = temp / "repo"
            root.mkdir()

            for name in ("README.md", "CATALOG.md", "OPTIMIZATION-PROBLEM.md"):
                shutil.copy2(ROOT / name, root / name)
            for name in ("scripts", "optimizations", "sources"):
                shutil.copytree(
                    ROOT / name,
                    root / name,
                    ignore=shutil.ignore_patterns("__pycache__"),
                )

            record_path = root / RECORD
            original = record_path.read_text(encoding="utf-8")
            before, rest = original.split("## Validation", 1)
            _old_validation, after = rest.split("## Target-repo adaptation", 1)
            external_text = (
                before
                + "## Validation\n\nTODO;\n\n## Target-repo adaptation"
                + after
            )

            external = temp / "external-record.md"
            external.write_text(external_text, encoding="utf-8")
            expected_external = external.read_bytes()

            record_path.unlink()
            record_path.symlink_to(external.resolve())

            completed = subprocess.run(
                [sys.executable, "scripts/check_catalog.py"],
                cwd=root,
                check=False,
                capture_output=True,
                text=True,
                timeout=30,
            )

            self.assertNotEqual(
                completed.returncode,
                0,
                completed.stdout + completed.stderr,
            )
            self.assertIn("symlinked Markdown input is not allowed", completed.stderr)
            self.assertEqual(external.read_bytes(), expected_external)


if __name__ == "__main__":
    unittest.main()
