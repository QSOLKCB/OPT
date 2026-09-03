from __future__ import annotations

import hashlib
import subprocess
import sys
import tempfile
import unittest
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch
from zipfile import ZIP_LZMA, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_zip.py"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from zip_inventory import cli as inventory_cli


def zip_bytes(members: dict[str, bytes], *, compression: int = 0) -> bytes:
    buffer = BytesIO()
    with ZipFile(buffer, "w", compression=compression) as zf:
        for name, content in members.items():
            zf.writestr(name, content)
    return buffer.getvalue()


def patch_local_filename(raw: bytes, replacement: bytes) -> bytes:
    patched = bytearray(raw)
    local = patched.find(b"PK\x03\x04")
    if local < 0:
        raise AssertionError("local header not found")
    name_len = int.from_bytes(patched[local + 26:local + 28], "little")
    if len(replacement) != name_len:
        raise AssertionError((len(replacement), name_len))
    start = local + 30
    patched[start:start + name_len] = replacement
    return bytes(patched)


def zip_lzma_without_eos(name: str, payload: bytes) -> bytes:
    raw = bytearray(zip_bytes({name: payload}, compression=ZIP_LZMA))
    local = raw.find(b"PK\x03\x04")
    central = raw.find(b"PK\x01\x02")
    eocd = raw.rfind(b"PK\x05\x06")
    if min(local, central, eocd) < 0:
        raise AssertionError("ZIP headers not found")
    compressed_size = int.from_bytes(raw[central + 20:central + 24], "little")
    name_len = int.from_bytes(raw[local + 26:local + 28], "little")
    extra_len = int.from_bytes(raw[local + 28:local + 30], "little")
    data_start = local + 30 + name_len + extra_len
    central_offset = int.from_bytes(raw[eocd + 16:eocd + 20], "little")

    del raw[data_start + compressed_size - 1]
    central -= 1
    eocd -= 1

    local_flags = int.from_bytes(raw[local + 6:local + 8], "little") & ~0x2
    central_flags = int.from_bytes(raw[central + 8:central + 10], "little") & ~0x2
    raw[local + 6:local + 8] = local_flags.to_bytes(2, "little")
    raw[central + 8:central + 10] = central_flags.to_bytes(2, "little")
    raw[local + 18:local + 22] = (compressed_size - 1).to_bytes(4, "little")
    raw[central + 20:central + 24] = (compressed_size - 1).to_bytes(4, "little")
    raw[eocd + 16:eocd + 20] = (central_offset - 1).to_bytes(4, "little")
    return bytes(raw)


class InventoryZipEdgeCaseTests(unittest.TestCase):
    def run_inventory(self, archive: Path, *extra: str) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [sys.executable, str(SCRIPT), str(archive), *extra],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_nonempty_directory_entry_fails_closed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "odd.zip"
            archive.write_bytes(zip_bytes({"hidden.py/": b"SIMD hidden\n"}))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("inventory_incomplete=nonempty_directory_entry", result.stdout)
        self.assertIn("inventory_complete=false", result.stdout)

    def test_scans_textual_sfx_wrapper_prefix(self) -> None:
        wrapper = b"#!/usr/bin/env python3\n# SIMD wrapper optimization\n"
        nested = wrapper + zip_bytes({"plain.txt": b"ordinary\n"})
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "outer.zip"
            archive.write_bytes(zip_bytes({"tool.py": nested}))
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("tool.py#sfx-prefix:2:", result.stdout)
        self.assertIn("SIMD", result.stdout)
        self.assertIn("nested_archives=1", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)

    def test_lzma_without_eos_marker_is_accepted_when_flag_clear(self) -> None:
        payload = b"SIMD no EOS marker\n" * 20
        raw = zip_lzma_without_eos("source.py", payload)
        with ZipFile(BytesIO(raw)) as zf:
            self.assertEqual(zf.read("source.py"), payload)

        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "no-eos.zip"
            archive.write_bytes(raw)
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("SIMD no EOS marker", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)

    def test_hash_preflight_and_scan_share_open_descriptor(self) -> None:
        original = zip_bytes({"original.txt": b"SIMD original\n"})
        replacement = zip_bytes({"replacement.txt": b"parallel replacement\n"})
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "subject.zip"
            other = Path(tmp) / "replacement.zip"
            archive.write_bytes(original)
            other.write_bytes(replacement)

            real_hash = inventory_cli.sha256_stream

            def hash_then_replace(stream: object) -> str:
                digest = real_hash(stream)
                other.replace(archive)
                return digest

            output = StringIO()
            with (
                patch.object(inventory_cli, "sha256_stream", side_effect=hash_then_replace),
                patch.object(sys, "argv", ["inventory_zip.py", str(archive)]),
                redirect_stdout(output),
            ):
                status = inventory_cli.main()

        text = output.getvalue()
        self.assertEqual(status, 0, text)
        self.assertIn(hashlib.sha256(original).hexdigest(), text)
        self.assertIn("original.txt", text)
        self.assertNotIn("replacement.txt", text)

    def test_empty_member_allowed_at_total_budget_boundary(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "boundary.zip"
            archive.write_bytes(zip_bytes({"one.bin": b"x", "empty.txt": b""}))
            result = self.run_inventory(
                archive,
                "--max-total-uncompressed-bytes=1",
            )

        self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
        self.assertIn("actual_decompressed_bytes=1", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)

    def test_local_filename_mismatch_is_rejected(self) -> None:
        raw = patch_local_filename(zip_bytes({"good.py": b"SIMD\n"}), b"../x.py")
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "local-name.zip"
            archive.write_bytes(raw)
            result = self.run_inventory(archive)

        self.assertEqual(result.returncode, 4, result.stdout + result.stderr)
        self.assertIn("inventory_incomplete=read_error", result.stdout)
        self.assertIn("inventory_complete=false", result.stdout)


if __name__ == "__main__":
    unittest.main()
