from __future__ import annotations

import codecs
import struct
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


def patch_flags(raw: bytes, mask: int) -> bytes:
    patched = bytearray(raw)
    local = patched.find(b"PK\x03\x04")
    central = patched.find(b"PK\x01\x02")
    if min(local, central) < 0:
        raise AssertionError("ZIP headers not found")
    local_flags = int.from_bytes(patched[local + 6:local + 8], "little") | mask
    central_flags = int.from_bytes(patched[central + 8:central + 10], "little") | mask
    patched[local + 6:local + 8] = local_flags.to_bytes(2, "little")
    patched[central + 8:central + 10] = central_flags.to_bytes(2, "little")
    return bytes(patched)


def append_fake_eocd_in_comment(raw: bytes) -> bytes:
    patched = bytearray(raw)
    real_eocd = patched.rfind(b"PK\x05\x06")
    if real_eocd < 0:
        raise AssertionError("EOCD not found")
    fake = struct.pack(
        "<4s4H2LH",
        b"PK\x05\x06",
        0,
        0,
        1,
        1,
        46,
        0,
        1,
    )
    patched[real_eocd + 20:real_eocd + 22] = len(fake).to_bytes(2, "little")
    patched.extend(fake)
    return bytes(patched)


class ReviewRoundTests(unittest.TestCase):
    def run_inventory(
        self,
        archive: Path,
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(archive), *extra],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_rejects_unsupported_general_purpose_flags(self) -> None:
        for mask in (1 << 5, 1 << 6):
            with self.subTest(mask=mask), tempfile.TemporaryDirectory() as tmp:
                archive = Path(tmp) / "flags.zip"
                archive.write_bytes(
                    patch_flags(zip_bytes({"source.py": b"SIMD\n"}), mask)
                )
                result = self.run_inventory(archive)

            self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
            self.assertIn("inventory_incomplete=read_error", result.stdout)
            self.assertIn("unsupported_flags", result.stdout)
            self.assertIn("inventory_complete=false", result.stdout)
            self.assertNotIn("Traceback", result.stderr)

    def test_last_eocd_candidate_is_not_skipped(self) -> None:
        raw = append_fake_eocd_in_comment(
            zip_bytes({"README.md": b"SIMD should not be silently scanned\n"})
        )
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "ambiguous-eocd.zip"
            archive.write_bytes(raw)
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("reason=eocd_comment_bounds", result.stdout)
        self.assertIn("inventory_complete=false", result.stdout)
        self.assertNotIn("README.md:1:", result.stdout)

    def test_scans_bom_marked_utf16_source(self) -> None:
        payload = codecs.BOM_UTF16_LE + (
            "parallel optimization\r\n".encode("utf-16-le")
        )
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "utf16.zip"
            archive.write_bytes(zip_bytes({"build.ps1": payload}))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("build.ps1:1: parallel optimization", result.stdout)
        self.assertIn("hits=1", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)

    def test_extensionless_utf8_probe_allows_split_codepoint(self) -> None:
        payload = b"a" * 4095 + "é parallel optimization\n".encode("utf-8")
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "split.zip"
            archive.write_bytes(zip_bytes({"Makefile": payload}))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("Makefile:1:", result.stdout)
        self.assertIn("parallel optimization", result.stdout)
        self.assertIn("hits=1", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)

    def test_central_directory_cap_is_incomplete_not_invalid(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "cap.zip"
            archive.write_bytes(zip_bytes({"README.md": b"plain\n"}))
            result = self.run_inventory(
                archive,
                "--max-central-directory-bytes=1",
            )

        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn(
            "inventory_incomplete=central_directory_size_outer_preflight",
            result.stdout,
        )
        self.assertNotIn("invalid_zip=", result.stdout)
        self.assertIn("inventory_complete=false", result.stdout)


if __name__ == "__main__":
    unittest.main()
