"""Argument parsing and outer archive boundary."""

from __future__ import annotations

import argparse
import zlib
from pathlib import Path
from zipfile import BadZipFile, LargeZipFile, ZipFile

from .common import (
    EXIT_INCOMPLETE,
    EXIT_INVALID_ZIP,
    InventoryState,
    escape_untrusted,
    mark_invalid,
    nonnegative_int,
    positive_int,
    print_summary,
    sha256_file,
    stream_size,
)
from .preflight import preflight_zip_stream
from .scanner import inventory_zip


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--max-text-bytes", type=positive_int, default=2_000_000)
    parser.add_argument(
        "--max-hits",
        type=nonnegative_int,
        default=500,
        help="maximum printed hits; 0 disables the hit cap",
    )
    parser.add_argument("--max-depth", type=nonnegative_int, default=4)
    parser.add_argument("--max-members", type=positive_int, default=20_000)
    parser.add_argument("--max-nested-zip-bytes", type=positive_int, default=64 * 1024 * 1024)
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
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    state = InventoryState()
    status = EXIT_INVALID_ZIP

    if not args.archive.is_file():
        mark_invalid(state, f"archive_not_found path={args.archive}")
        print_summary(state, status)
        return status

    print(f"archive={escape_untrusted(str(args.archive))}")
    try:
        print(f"sha256={sha256_file(args.archive)}")
        with args.archive.open("rb") as stream:
            preflight = preflight_zip_stream(
                stream,
                size=stream_size(stream),
                label=str(args.archive),
                args=args,
                state=state,
                required=True,
                outer=True,
            )
    except (OSError, EOFError, UnicodeDecodeError) as exc:
        mark_invalid(state, f"archive_read error={type(exc).__name__}")
        preflight = None

    if preflight is None:
        status = EXIT_INCOMPLETE if state.incomplete and not state.invalid else EXIT_INVALID_ZIP
        print_summary(state, status)
        return status

    try:
        with ZipFile(args.archive) as zf:
            status = inventory_zip(
                zf,
                label=str(args.archive),
                depth=0,
                args=args,
                state=state,
            )
    except (
        BadZipFile,
        LargeZipFile,
        OSError,
        RuntimeError,
        UnicodeDecodeError,
        zlib.error,
    ) as exc:
        mark_invalid(state, f"archive_open error={type(exc).__name__}")
        status = EXIT_INVALID_ZIP

    print_summary(state, status)
    return status
