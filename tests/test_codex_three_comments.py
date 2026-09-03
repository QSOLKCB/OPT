from __future__ import annotations

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


def add_zip64_locator_with_classic_eocd(raw: bytes) -> bytes:
    """Add a valid ZIP64 record/locator while leaving classic fields ordinary."""
    eocd = raw.rfind(b"PK\x05\x06")
    if eocd < 0:
        raise AssertionError("classic EOCD not found")
    (
        signature,
        disk_number,
        central_disk,
        entries_on_disk,
        entries_total,
        central_size,
        central_offset,
        comment_length,
    ) = struct.unpack_from("<4s4H2LH", raw, eocd)
    if signature != b"PK\x05\x06" or comment_length != 0:
        raise AssertionError("unexpected classic EOCD")
    if disk_number != 0 or central_disk != 0:
        raise AssertionError("unexpected multi-disk archive")

    zip64_eocd = struct.pack(
        "<4sQ2H2L4Q",
        b"PK\x06\x06",
        44,
        45,
        45,
        0,
        0,
        entries_on_disk,
        entries_total,
        central_size,
        central_offset,
    )
    locator = struct.pack(
        "<4sLQL",
        b"PK\x06\x07",
        0,
        eocd,
        1,
    )
    return raw[:eocd] + zip64_eocd + locator + raw[eocd:]


class LatestCodexCommentTests(unittest.TestCase):
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

    def test_known_text_sfx_is_detected_before_text_cap(self) -> None:
        nested = zip_bytes({"README.md": b"parallel nested\n"})
        payload = b"# SIMD wrapper\n" + nested
        self.assertGreater(len(payload), 32)

        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "outer.zip"
            archive.write_bytes(zip_bytes({"tool.py": payload}))
            result = self.run_inventory(
                archive,
                "--max-text-bytes=32",
                "--max-nested-zip-bytes=4096",
                "--max-general-member-bytes=4096",
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("tool.py#sfx-prefix:1:", result.stdout)
        self.assertIn("SIMD wrapper", result.stdout)
        self.assertIn("README.md:1: parallel nested", result.stdout)
        self.assertIn("nested_archives=1", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)
        self.assertNotIn("declared_member_output_limit", result.stdout)

    def test_zip64_locator_is_rejected_even_without_classic_sentinels(self) -> None:
        raw = add_zip64_locator_with_classic_eocd(
            zip_bytes({"README.md": b"plain\n"})
        )
        # Python consumes the ZIP64 locator even though the classic EOCD fields
        # are ordinary, which is why preflight must reject the same structure.
        with ZipFile(BytesIO(raw)) as zf:
            self.assertEqual(zf.read("README.md"), b"plain\n")

        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "zip64-locator.zip"
            archive.write_bytes(raw)
            result = self.run_inventory(
                archive,
                "--max-members=2",
                "--max-central-directory-bytes=200",
            )

        self.assertEqual(result.returncode, 2, result.stdout + result.stderr)
        self.assertIn("reason=zip64_locator_unsupported", result.stdout)
        self.assertIn("inventory_complete=false", result.stdout)

    def test_recursive_labels_are_bounded_before_repetition(self) -> None:
        inner = zip_bytes({f"f{i}.bin": b"" for i in range(30)})
        long_parent = "A" * 5000 + ".zip"

        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "long-label.zip"
            archive.write_bytes(zip_bytes({long_parent: inner}))
            result = self.run_inventory(archive, "--max-hits=0")

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        lines = result.stdout.splitlines()
        self.assertTrue(lines)
        self.assertLessEqual(max(map(len, lines)), 1200)
        self.assertLess(len(result.stdout), 100_000)
        self.assertIn("nested_archives=1", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)


if __name__ == "__main__":
    unittest.main()
