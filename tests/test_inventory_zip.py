from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_zip.py"


def zip_bytes(members: dict[str, bytes], *, compression: int = 0) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=compression) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buffer.getvalue()


class InventoryZipTests(unittest.TestCase):
    def run_inventory(self, archive: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(archive), *extra],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_recurses_into_nested_zip(self) -> None:
        inner = zip_bytes({"README.md": b"SIMD enabled\nordinary line\n"})
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "outer.zip"
            archive.write_bytes(zip_bytes({"bundle.zip": inner}))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("bundle.zip!/README.md:1: SIMD enabled", result.stdout)
        self.assertIn("nested_archives=1", result.stdout)
        self.assertIn("hits=1", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)

    def test_scans_additional_source_and_evidence_suffixes(self) -> None:
        payloads = {
            "kernel.inc": b"SIMD path\n",
            "suite.mjs": b"const mode = 'parallel';\n",
            "bench.csv": b"metric,performance\n",
            "spec.tex": b"optimization contract\n",
        }
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "formats.zip"
            archive.write_bytes(zip_bytes(payloads))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        for name in payloads:
            self.assertIn(name, result.stdout)
        self.assertIn("hits=4", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)

    def test_content_detects_extensionless_utf8_text(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "content.zip"
            archive.write_bytes(zip_bytes({"Makefile": b"benchmark: ; @echo performance\n"}))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Makefile:1:", result.stdout)
        self.assertIn("performance", result.stdout)

    def test_rejects_windows_parent_traversal(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "unsafe.zip"
            archive.write_bytes(zip_bytes({r"..\evil.py": b"SIMD\n"}))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
        self.assertIn("unsafe_members", result.stdout)
        self.assertIn(r"..\\evil.py", result.stdout)

    def test_escapes_terminal_control_and_bidi_characters(self) -> None:
        payload = "SIMD\x1b]52;c;clipboard\x07 \u202ereversed\n".encode("utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "controls.zip"
            archive.write_bytes(zip_bytes({"README.md": payload}))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertNotIn("\x1b", result.stdout)
        self.assertNotIn("\u202e", result.stdout)
        self.assertIn(r"\x1b", result.stdout)
        self.assertIn(r"\x07", result.stdout)
        self.assertIn(r"\u202e", result.stdout)

    def test_long_line_prints_context_around_keyword(self) -> None:
        payload = ("x" * 1200 + " SIMD optimized tail").encode()
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "long-line.zip"
            archive.write_bytes(zip_bytes({"sheet.xml": payload}))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        hit_line = next(line for line in result.stdout.splitlines() if "sheet.xml:1:" in line)
        self.assertIn("SIMD", hit_line)
        self.assertLessEqual(len(hit_line), 520)

    def test_text_size_limit_reports_incomplete_inventory(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "large-text.zip"
            archive.write_bytes(zip_bytes({"README.md": b"SIMD\n" * 20}))
            result = self.run_inventory(archive, "--max-text-bytes=16")

        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("inventory_incomplete=text_member_size", result.stdout)
        self.assertIn("inventory_complete=false", result.stdout)

    def test_depth_limit_reports_incomplete_inventory(self) -> None:
        deepest = zip_bytes({"README.md": b"SIMD\n"})
        middle = zip_bytes({"deep.zip": deepest})
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "outer.zip"
            archive.write_bytes(zip_bytes({"middle.zip": middle}))
            result = self.run_inventory(archive, "--max-depth=1")

        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("inventory_incomplete=depth_limit", result.stdout)
        self.assertIn("inventory_complete=false", result.stdout)
        self.assertNotIn("hits=1", result.stdout)

    def test_nested_member_limit_is_preflighted_before_open(self) -> None:
        inner = zip_bytes({f"f{i}.txt": b"plain\n" for i in range(4)})
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "outer.zip"
            archive.write_bytes(zip_bytes({"inner.zip": inner}))
            result = self.run_inventory(archive, "--max-members=3")

        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("inventory_incomplete=member_limit_preflight", result.stdout)
        self.assertIn("archives_scanned=1", result.stdout)
        self.assertIn("nested_archives=0", result.stdout)

    def test_corrupt_deflate_reports_read_error_without_traceback(self) -> None:
        raw = bytearray(zip_bytes({"broken.py": b"SIMD payload\n" * 20}, compression=ZIP_DEFLATED))
        marker = raw.find(b"PK\x03\x04")
        self.assertGreaterEqual(marker, 0)
        name_len = int.from_bytes(raw[marker + 26:marker + 28], "little")
        extra_len = int.from_bytes(raw[marker + 28:marker + 30], "little")
        data_start = marker + 30 + name_len + extra_len
        raw[data_start + 1] ^= 0xFF

        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "corrupt.zip"
            archive.write_bytes(raw)
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("inventory_incomplete=read_error", result.stdout)
        self.assertIn("inventory_complete=false", result.stdout)


if __name__ == "__main__":
    unittest.main()
