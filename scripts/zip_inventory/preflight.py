"""Bounded EOCD and central-directory validation before ZipFile construction."""

from __future__ import annotations

import io
import struct
from typing import BinaryIO

from .common import (
    CENTRAL_FIXED_SIZE,
    CENTRAL_SIGNATURE,
    EOCD_SIGNATURE,
    MAX_EOCD_SEARCH,
    InventoryState,
    ZipPreflight,
    mark_incomplete,
    mark_invalid,
    read_exact,
)


def _find_eocd(stream: BinaryIO, size: int) -> tuple[int, bytes] | None:
    if size < 22:
        return None
    tail_size = min(size, MAX_EOCD_SEARCH)
    stream.seek(size - tail_size)
    tail = read_exact(stream, tail_size)
    cursor = len(tail)
    while True:
        relative = tail.rfind(EOCD_SIGNATURE, 0, cursor)
        if relative < 0:
            return None
        if relative + 22 <= len(tail):
            comment_length = struct.unpack_from("<H", tail, relative + 20)[0]
            absolute = size - tail_size + relative
            if absolute + 22 + comment_length == size:
                return absolute, tail[relative:relative + 22]
        cursor = relative


def preflight_zip_stream(
    stream: BinaryIO,
    *,
    size: int,
    label: str,
    args: object,
    state: InventoryState,
    required: bool,
    outer: bool,
) -> ZipPreflight | None:
    """Validate a central directory without materializing ZipInfo objects.

    A non-required probe with no EOCD is simply not a ZIP. Once an EOCD is
    found, malformed metadata fails closed. Positive prefix bytes are accepted
    so ordinary self-extracting ZIPs remain discoverable.
    """

    def reject(reason: str) -> None:
        message = f"label={label} reason={reason}"
        if outer:
            mark_invalid(state, message)
        else:
            mark_incomplete(state, f"invalid_nested_zip {message}")

    try:
        found = _find_eocd(stream, size)
    except (OSError, EOFError, struct.error) as exc:
        if required:
            reject(f"eocd_read error={type(exc).__name__}")
        return None
    if found is None:
        if required:
            reject("eocd_missing")
        return None

    eocd_offset, eocd = found
    try:
        (
            disk_number,
            central_disk,
            entries_on_disk,
            entries_total,
            central_size,
            central_offset,
            _comment_length,
        ) = struct.unpack_from("<4H2LH", eocd, 4)
    except struct.error:
        reject("eocd_fields")
        return None

    if disk_number != 0 or central_disk != 0 or entries_on_disk != entries_total:
        reject("multi_disk_unsupported")
        return None
    if entries_total == 0xFFFF or central_size == 0xFFFFFFFF or central_offset == 0xFFFFFFFF:
        reject("zip64_unsupported")
        return None
    if central_size > args.max_central_directory_bytes:
        reject(
            "central_directory_size "
            f"observed={central_size} limit={args.max_central_directory_bytes}"
        )
        return None

    prefix_bytes = eocd_offset - central_size - central_offset
    if prefix_bytes < 0:
        reject("central_offset_before_start")
        return None
    central_start = prefix_bytes + central_offset
    central_end = central_start + central_size
    if central_end != eocd_offset or central_start < 0 or central_end > size:
        reject("central_bounds")
        return None

    projected_base = state.members_seen
    cursor = central_start
    count = 0
    try:
        stream.seek(central_start)
        while cursor < central_end:
            if cursor + CENTRAL_FIXED_SIZE > central_end:
                reject("central_header_bounds")
                return None
            fixed = read_exact(stream, CENTRAL_FIXED_SIZE)
            if fixed[:4] != CENTRAL_SIGNATURE:
                reject("central_header_signature")
                return None

            flags = struct.unpack_from("<H", fixed, 8)[0]
            compressed_size = struct.unpack_from("<L", fixed, 20)[0]
            uncompressed_size = struct.unpack_from("<L", fixed, 24)[0]
            filename_len, extra_len, comment_len = struct.unpack_from("<HHH", fixed, 28)
            disk_start = struct.unpack_from("<H", fixed, 34)[0]
            local_offset = struct.unpack_from("<L", fixed, 42)[0]
            if (
                compressed_size == 0xFFFFFFFF
                or uncompressed_size == 0xFFFFFFFF
                or local_offset == 0xFFFFFFFF
                or disk_start == 0xFFFF
            ):
                reject("zip64_entry_unsupported")
                return None
            if disk_start != 0:
                reject("entry_on_other_disk")
                return None
            if filename_len == 0:
                reject("empty_filename")
                return None

            next_cursor = cursor + CENTRAL_FIXED_SIZE + filename_len + extra_len + comment_len
            if next_cursor > central_end:
                reject("central_entry_bounds")
                return None
            filename_raw = read_exact(stream, filename_len)
            if b"\x00" in filename_raw:
                reject("filename_contains_nul")
                return None
            if flags & 0x800:
                try:
                    filename_raw.decode("utf-8", errors="strict")
                except UnicodeDecodeError:
                    reject("filename_utf8")
                    return None
            stream.seek(extra_len + comment_len, io.SEEK_CUR)

            count += 1
            if projected_base + count > args.max_members:
                target = "member_limit_outer_preflight" if outer else "member_limit_preflight"
                detail = f"projected={projected_base + count} limit={args.max_members}"
                if outer:
                    mark_incomplete(state, f"{target} {detail}")
                else:
                    mark_incomplete(state, f"{target} member={label} {detail}")
                return None
            cursor = next_cursor
    except (OSError, EOFError, struct.error) as exc:
        reject(f"central_read error={type(exc).__name__}")
        return None

    if cursor != central_end or count != entries_total:
        reject(f"central_count observed={count} declared={entries_total}")
        return None
    return ZipPreflight(count, central_start, central_size, prefix_bytes)


def preflight_zip_bytes(
    raw: bytes,
    *,
    label: str,
    args: object,
    state: InventoryState,
    required: bool,
) -> ZipPreflight | None:
    with io.BytesIO(raw) as stream:
        return preflight_zip_stream(
            stream,
            size=len(raw),
            label=label,
            args=args,
            state=state,
            required=required,
            outer=False,
        )
