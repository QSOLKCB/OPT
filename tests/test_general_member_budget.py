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


class GeneralMemberBudgetTests(unittest.TestCase):
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

    def test_binary_member_does_not_inherit_nested_zip_limit(self) -> None:
        # Scale the review case down: 65 bytes is above the 64-byte nested ZIP
        # cap but below the independent 128-byte general-member cap.
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "binary-asset.zip"
            archive.write_bytes(
                zip_bytes({"image.bin": b"\x00" * 65})
            )
            result = self.run_inventory(
                archive,
                "--max-nested-zip-bytes=64",
                "--max-general-member-bytes=128",
                "--max-total-uncompressed-bytes=256",
                "--max-compressed-member-bytes=128",
            )

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )
        self.assertNotIn(
            "inventory_incomplete=declared_member_output_limit",
            result.stdout,
        )
        self.assertIn("actual_decompressed_bytes=65", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)

    def test_detected_nested_zip_still_obeys_nested_limit(self) -> None:
        inner = zip_bytes({"payload.bin": b"x" * 80})
        self.assertGreater(len(inner), 64)
        self.assertLess(len(inner), 512)

        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "nested-disguised.zip"
            archive.write_bytes(zip_bytes({"payload.bin": inner}))
            result = self.run_inventory(
                archive,
                "--max-nested-zip-bytes=64",
                "--max-general-member-bytes=512",
                "--max-total-uncompressed-bytes=1024",
                "--max-compressed-member-bytes=512",
            )

        self.assertEqual(
            result.returncode,
            4,
            result.stdout + result.stderr,
        )
        self.assertIn("inventory_incomplete=nested_zip_size", result.stdout)
        self.assertIn("inventory_complete=false", result.stdout)


if __name__ == "__main__":
    unittest.main()
