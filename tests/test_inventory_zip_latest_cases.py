from __future__ import annotations

import subprocess
import sys
import tempfile
import unittest
import zlib
from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
from unittest.mock import patch
from zipfile import BadZipFile, ZIP_DEFLATED, ZIP_LZMA, ZipFile

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "inventory_zip.py"
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

from zip_inventory import cli as inventory_cli
from zip_inventory import reader as inventory_reader


def zip_bytes(
    members: dict[str, bytes],
    *,
    compression: int = 0,
) -> bytes:
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
    name_len = int.from_bytes(
        patched[local + 26:local + 28],
        "little",
    )
    if len(replacement) != name_len:
        raise AssertionError((len(replacement), name_len))
    start = local + 30
    patched[start:start + name_len] = replacement
    return bytes(patched)


def patch_lzma_dictionary_size(
    raw: bytes,
    dictionary_size: int,
) -> bytes:
    patched = bytearray(raw)
    local = patched.find(b"PK\x03\x04")
    if local < 0:
        raise AssertionError("local header not found")
    name_len = int.from_bytes(
        patched[local + 26:local + 28],
        "little",
    )
    extra_len = int.from_bytes(
        patched[local + 28:local + 30],
        "little",
    )
    data_start = local + 30 + name_len + extra_len
    property_size = int.from_bytes(
        patched[data_start + 2:data_start + 4],
        "little",
    )
    if property_size != 5:
        raise AssertionError(
            f"unexpected LZMA property size: {property_size}"
        )
    patched[data_start + 5:data_start + 9] = (
        dictionary_size.to_bytes(4, "little")
    )
    return bytes(patched)


def patch_first_entry_to_overlap_next(raw: bytes) -> bytes:
    patched = bytearray(raw)
    first_local = patched.find(b"PK\x03\x04")
    second_local = patched.find(
        b"PK\x03\x04",
        first_local + 4,
    )
    first_central = patched.find(b"PK\x01\x02")
    if min(first_local, second_local, first_central) < 0:
        raise AssertionError("required ZIP headers not found")

    name_len = int.from_bytes(
        patched[first_local + 26:first_local + 28],
        "little",
    )
    extra_len = int.from_bytes(
        patched[first_local + 28:first_local + 30],
        "little",
    )
    data_start = first_local + 30 + name_len + extra_len
    new_size = second_local - data_start + 1
    if new_size <= 0:
        raise AssertionError("second header does not follow first data")

    covered = bytes(patched[data_start:data_start + new_size])
    crc = zlib.crc32(covered) & 0xFFFFFFFF

    patched[first_local + 14:first_local + 18] = (
        crc.to_bytes(4, "little")
    )
    patched[first_local + 18:first_local + 22] = (
        new_size.to_bytes(4, "little")
    )
    patched[first_local + 22:first_local + 26] = (
        new_size.to_bytes(4, "little")
    )
    patched[first_central + 16:first_central + 20] = (
        crc.to_bytes(4, "little")
    )
    patched[first_central + 20:first_central + 24] = (
        new_size.to_bytes(4, "little")
    )
    patched[first_central + 24:first_central + 28] = (
        new_size.to_bytes(4, "little")
    )
    return bytes(patched)


class InventoryZipLatestCases(unittest.TestCase):
    def run_inventory(
        self,
        archive: Path,
        *extra: str,
    ) -> subprocess.CompletedProcess[str]:
        return subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                str(archive),
                *extra,
            ],
            check=False,
            capture_output=True,
            text=True,
        )

    def test_empty_directory_local_name_is_validated(self) -> None:
        raw = patch_local_filename(
            zip_bytes({"safe/": b""}),
            b"../x/",
        )
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "directory-name.zip"
            archive.write_bytes(raw)
            result = self.run_inventory(archive)

        self.assertEqual(
            result.returncode,
            4,
            result.stdout + result.stderr,
        )
        self.assertIn(
            "inventory_incomplete=read_error",
            result.stdout,
        )
        self.assertIn("inventory_complete=false", result.stdout)

    def test_compressed_empty_directory_is_allowed(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "compressed-directory.zip"
            archive.write_bytes(
                zip_bytes(
                    {"safe/": b""},
                    compression=ZIP_DEFLATED,
                )
            )
            result = self.run_inventory(archive)

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )
        self.assertIn("inventory_complete=true", result.stdout)

    def test_scans_outer_textual_sfx_prefix(self) -> None:
        wrapper = (
            b"#!/usr/bin/env python3\n"
            b"# SIMD outer evidence\n"
        )
        raw = wrapper + zip_bytes(
            {"plain.txt": b"ordinary\n"}
        )
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "tool.py"
            archive.write_bytes(raw)
            result = self.run_inventory(archive)

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )
        self.assertIn("tool.py#sfx-prefix:2:", result.stdout)
        self.assertIn("SIMD outer evidence", result.stdout)
        self.assertIn("hits=1", result.stdout)
        self.assertIn("inventory_complete=true", result.stdout)

    def test_lzma_dictionary_size_is_capped(self) -> None:
        raw = patch_lzma_dictionary_size(
            zip_bytes(
                {"source.py": b"SIMD\n"},
                compression=ZIP_LZMA,
            ),
            0xFFFFFFFF,
        )
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "huge-dictionary.zip"
            archive.write_bytes(raw)
            result = self.run_inventory(
                archive,
                "--max-lzma-dictionary-bytes=1048576",
            )

        self.assertEqual(
            result.returncode,
            4,
            result.stdout + result.stderr,
        )
        self.assertIn(
            "inventory_incomplete=read_error",
            result.stdout,
        )
        self.assertIn("inventory_complete=false", result.stdout)
        self.assertNotIn("Traceback", result.stderr)

    def test_lzma_allocation_failure_is_reported(self) -> None:
        raw = zip_bytes(
            {"source.py": b"SIMD\n"},
            compression=ZIP_LZMA,
        )
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "allocation.zip"
            archive.write_bytes(raw)

            output = StringIO()
            with (
                patch.object(
                    inventory_reader.lzma,
                    "LZMADecompressor",
                    side_effect=MemoryError,
                ),
                patch.object(
                    sys,
                    "argv",
                    ["inventory_zip.py", str(archive)],
                ),
                redirect_stdout(output),
            ):
                status = inventory_cli.main()

        text = output.getvalue()
        self.assertEqual(status, 4, text)
        self.assertIn(
            "inventory_incomplete=read_error",
            text,
        )
        self.assertIn("error=MemoryError", text)
        self.assertIn("inventory_complete=false", text)

    def test_compressed_data_overlap_is_rejected(self) -> None:
        raw = patch_first_entry_to_overlap_next(
            zip_bytes(
                {
                    "first.bin": b"A",
                    "second.bin": b"B",
                }
            )
        )
        with ZipFile(BytesIO(raw)) as zf:
            with self.assertRaises(BadZipFile):
                zf.read("first.bin")

        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "overlap.zip"
            archive.write_bytes(raw)
            result = self.run_inventory(archive)

        self.assertEqual(
            result.returncode,
            4,
            result.stdout + result.stderr,
        )
        self.assertIn(
            "inventory_incomplete=read_error",
            result.stdout,
        )
        self.assertIn("inventory_complete=false", result.stdout)

    def test_exact_hit_cap_remains_complete(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "one-hit.zip"
            archive.write_bytes(
                zip_bytes({"README.md": b"SIMD only\n"})
            )
            result = self.run_inventory(
                archive,
                "--max-hits=1",
            )

        self.assertEqual(
            result.returncode,
            0,
            result.stdout + result.stderr,
        )
        self.assertIn("hits=1", result.stdout)
        self.assertNotIn(
            "inventory_incomplete=hit_limit",
            result.stdout,
        )
        self.assertIn("inventory_complete=true", result.stdout)

    def test_hit_cap_fails_only_on_additional_match(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "two-hits.zip"
            archive.write_bytes(
                zip_bytes(
                    {
                        "README.md":
                        b"SIMD first\nparallel second\n"
                    }
                )
            )
            result = self.run_inventory(
                archive,
                "--max-hits=1",
            )

        self.assertEqual(
            result.returncode,
            4,
            result.stdout + result.stderr,
        )
        self.assertIn(
            "inventory_incomplete=hit_limit "
            "observed=2 limit=1",
            result.stdout,
        )
        self.assertIn("hits=2", result.stdout)
        self.assertIn("inventory_complete=false", result.stdout)


if __name__ == "__main__":
    unittest.main()
