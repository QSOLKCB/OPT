from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from zipfile import ZipFile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_zip.py"


def zip_bytes(members: dict[str, bytes]) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w") as zf:
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


if __name__ == "__main__":
    unittest.main()
