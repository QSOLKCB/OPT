"""Argument parsing and outer archive boundary."""

from __future__ import annotations

import argparse
import zlib
from pathlib import Path
from typing import BinaryIO
from zipfile import BadZipFile, LargeZipFile, ZipFile

from .common import (
    EXIT_INCOMPLETE,
    EXIT_INVALID_ZIP,
    TEXT_SUFFIXES,
    InventoryState,
    escape_untrusted,
    looks_textual,
    mark_incomplete,
    mark_invalid,
    member_suffix,
    nonnegative_int,
    positive_int,
    print_summary,
    read_exact,
    sha256_stream,
    stream_size,
)
from .preflight import preflight_zip_stream
from .scanner import inventory_zip, scan_text


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument(
        "--max-text-bytes",
        type=positive_int,
        default=2_000_000,
    )
    parser.add_argument(
        "--max-hits",
        type=nonnegative_int,
        default=500,
        help="maximum printed hits; 0 disables the hit cap",
    )
    parser.add_argument(
        "--max-depth",
        type=nonnegative_int,
        default=4,
    )
    parser.add_argument(
        "--max-members",
        type=positive_int,
        default=20_000,
    )
    parser.add_argument(
        "--max-nested-zip-bytes",
        type=positive_int,
        default=64 * 1024 * 1024,
    )
    parser.add_argument(
        "--max-total-uncompressed-bytes",
        type=positive_int,
        default=512 * 1024 * 1024,
    )
    parser.add_argument(
        "--max-central-directory-bytes",
        type=positive_int,
        default=64 * 1024 * 1024,
    )
    parser.add_argument(
        "--max-compressed-member-bytes",
        type=positive_int,
        default=128 * 1024 * 1024,
    )
    parser.add_argument(
        "--max-lzma-dictionary-bytes",
        type=positive_int,
        default=64 * 1024 * 1024,
        help="maximum method-14 LZMA dictionary workspace",
    )
    return parser.parse_args()


def _scan_outer_sfx_prefix(
    stream: BinaryIO,
    *,
    prefix_bytes: int,
    label: str,
    args: argparse.Namespace,
    state: InventoryState,
) -> None:
    """Scan a textual outer SFX/polyglot prefix on the audited descriptor."""
    if prefix_bytes <= 0:
        return

    suffix = member_suffix(label)
    probe_size = min(prefix_bytes, 4096)
    stream.seek(0)
    probe = read_exact(stream, probe_size)
    if suffix not in TEXT_SUFFIXES and not looks_textual(probe):
        return

    if prefix_bytes > args.max_text_bytes:
        mark_incomplete(
            state,
            f"text_member_size member={label}#sfx-prefix "
            f"size={prefix_bytes} limit={args.max_text_bytes}",
        )
        return

    stream.seek(0)
    prefix = read_exact(stream, prefix_bytes)
    scan_text(
        prefix,
        f"{label}#sfx-prefix",
        args,
        state,
    )


def main() -> int:
    args = parse_args()
    state = InventoryState()
    status = EXIT_INVALID_ZIP
    label = str(args.archive)

    if not args.archive.is_file():
        mark_invalid(
            state,
            f"archive_not_found path={label}",
        )
        print_summary(state, status)
        return status

    print(f"archive={escape_untrusted(label)}")
    try:
        with args.archive.open("rb") as stream:
            print(f"sha256={sha256_stream(stream)}")
            preflight = preflight_zip_stream(
                stream,
                size=stream_size(stream),
                label=label,
                args=args,
                state=state,
                required=True,
                outer=True,
            )
            if preflight is None:
                status = (
                    EXIT_INCOMPLETE
                    if state.incomplete and not state.invalid
                    else EXIT_INVALID_ZIP
                )
            else:
                _scan_outer_sfx_prefix(
                    stream,
                    prefix_bytes=preflight.prefix_bytes,
                    label=label,
                    args=args,
                    state=state,
                )
                if state.incomplete:
                    status = EXIT_INCOMPLETE
                else:
                    stream.seek(0)
                    try:
                        with ZipFile(stream) as zf:
                            status = inventory_zip(
                                zf,
                                label=label,
                                depth=0,
                                args=args,
                                state=state,
                            )
                    except (
                        BadZipFile,
                        LargeZipFile,
                        MemoryError,
                        OSError,
                        RuntimeError,
                        UnicodeDecodeError,
                        zlib.error,
                    ) as exc:
                        mark_invalid(
                            state,
                            f"archive_open "
                            f"error={type(exc).__name__}",
                        )
                        status = EXIT_INVALID_ZIP
    except (
        MemoryError,
        OSError,
        EOFError,
        UnicodeDecodeError,
    ) as exc:
        mark_invalid(
            state,
            f"archive_read error={type(exc).__name__}",
        )
        status = EXIT_INVALID_ZIP

    print_summary(state, status)
    return status
