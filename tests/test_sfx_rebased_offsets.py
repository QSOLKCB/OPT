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


def rebased_sfx_zip(wrapper: bytes) -> bytes:
    """Prepend an SFX wrapper and rebase all stored archive offsets."""
    raw = bytearray(zip_bytes({"plain.txt": b"ordinary\n"}))
    central = raw.find(b"PK\x01\x02")
    eocd = raw.rfind(b"PK\x05\x06")
    if central < 0 or eocd < 0:
        raise AssertionError("required ZIP structures not found")

    shift = len(wrapper)
    local_offset = int.from_bytes(raw[central + 42:central + 46], "little")
    central_offset = int.from_bytes(raw[eocd + 16:eocd + 20], "little")
    raw[central + 42:central + 46] = (local_offset + shift).to_bytes(4, "little")
    raw[eocd + 16:eocd + 20] = (central_offset + shift).to_bytes(4, "little")
    combined = wrapper + bytes(raw)

    # This is a valid SFX form: Python's ZipFile reads the rebased offsets.
    with ZipFile(BytesIO(combined)) as zf:
        if zf.read("plain.txt") != b"ordinary\n":
            raise AssertionError("rebased SFX fixture is not readable")
    return combined


class RebasedSfxOffsetTests(unittest.TestCase):
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

    def test_outer_rebased_sfx_prefix_is_scanned(self) -> None:
        wrapper = (
            b"#!/usr/bin/env python3\n"
            b"# SIMD rebased outer evidence\n"
        )
        raw = rebased_sfx_zip(wrapper)
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tool.py"
            archive.write_bytes(raw)
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("tool.py#sfx-prefix:2:", result.stdout)
        self.assertIn("SIMD rebased outer evidence", result.stdout)
        self.assertIn("hits=1", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)

    def test_nested_rebased_sfx_prefix_is_scanned(self) -> None:
        wrapper = (
            b"#!/usr/bin/env python3\n"
            b"# parallel rebased nested evidence\n"
        )
        nested = rebased_sfx_zip(wrapper)
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "outer.zip"
            archive.write_bytes(zip_bytes({"payload.py": nested}))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("payload.py#sfx-prefix:2:", result.stdout)
        self.assertIn("parallel rebased nested evidence", result.stdout)
        self.assertIn("nested_archives=1", result.stdout)
        self.assertIn("hits=1", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)


if __name__ == "__main__":
    unittest.main()
