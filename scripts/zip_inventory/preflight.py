"""Bounded EOCD and central-directory validation before ZipFile construction."""

from __future__ import annotations

import io
import struct
from typing import BinaryIO

from .common import (
    CENTRAL_FIXED_SIZE,
    CENTRAL_SIGNATURE,
    EOCD_SIGNATURE,
    LOCAL_SIGNATURE,
    MAX_EOCD_SEARCH,
    InventoryState,
    ZipPreflight,
    mark_incomplete,
    mark_invalid,
    read_exact,
)

ZIP64_LOCATOR_SIGNATURE = b"PK\x06\x07"
ZIP64_LOCATOR_SIZE = 20


def _find_eocd(stream: BinaryIO, size: int) -> tuple[int, bytes] | None:
    """Select the same last EOCD signature that ``ZipFile`` will consume."""
    if size < 22:
        return None
    tail_size = min(size, MAX_EOCD_SEARCH)
    tail_start = size - tail_size
    stream.seek(tail_start)
    tail = read_exact(stream, tail_size)
    relative = tail.rfind(EOCD_SIGNATURE)
    if relative < 0 or relative + 22 > len(tail):
        return None
    absolute = tail_start + relative
    return absolute, tail[relative:relative + 22]


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
            comment_length,
        ) = struct.unpack_from("<4H2LH", eocd, 4)
    except struct.error:
        reject("eocd_fields")
        return None

    # Python's ZipFile selects the last EOCD signature even when it appears in
    # bytes an earlier candidate called a comment. Do the same, then fail closed
    # if that selected record cannot fit its own declared comment.
    available_comment = size - (eocd_offset + 22)
    if comment_length > available_comment:
        reject(
            "eocd_comment_bounds "
            f"declared={comment_length} available={available_comment}"
        )
        return None

    # ``ZipFile`` checks for the ZIP64 locator immediately before the classic
    # EOCD even when the classic count/size/offset fields are not sentinels, and
    # replaces them with ZIP64 values when the locator is present. Since this
    # scanner deliberately does not support ZIP64, reject that same locator
    # before trusting or applying any classic EOCD resource limits.
    if eocd_offset >= ZIP64_LOCATOR_SIZE:
        current = stream.tell()
        try:
            stream.seek(eocd_offset - ZIP64_LOCATOR_SIZE)
            locator = read_exact(stream, ZIP64_LOCATOR_SIZE)
        except (OSError, EOFError) as exc:
            reject(f"zip64_locator_read error={type(exc).__name__}")
            return None
        finally:
            try:
                stream.seek(current)
            except (OSError, ValueError):
                pass
        if locator[:4] == ZIP64_LOCATOR_SIGNATURE:
            reject("zip64_locator_unsupported")
            return None

    if disk_number != 0 or central_disk != 0 or entries_on_disk != entries_total:
        reject("multi_disk_unsupported")
        return None
    if entries_total == 0xFFFF or central_size == 0xFFFFFFFF or central_offset == 0xFFFFFFFF:
        reject("zip64_unsupported")
        return None
    if central_size > args.max_central_directory_bytes:
        target = (
            "central_directory_size_outer_preflight"
            if outer
            else "central_directory_size_preflight"
        )
        detail = (
            f"observed={central_size} "
            f"limit={args.max_central_directory_bytes}"
        )
        if outer:
            mark_incomplete(state, f"{target} {detail}")
        else:
            mark_incomplete(state, f"{target} member={label} {detail}")
        return None

    # This is the concatenation adjustment used by ``ZipFile`` when offsets in
    # the central directory were *not* rebased after prepending an SFX wrapper.
    # It is not, by itself, a reliable prefix boundary: producers may instead
    # rebase both the EOCD central offset and each local-header offset, making
    # this adjustment zero even though wrapper bytes precede the first header.
    concatenation_adjustment = eocd_offset - central_size - central_offset
    if concatenation_adjustment < 0:
        reject("central_offset_before_start")
        return None
    central_start = concatenation_adjustment + central_offset
    central_end = central_start + central_size
    if central_end != eocd_offset or central_start < 0 or central_end > size:
        reject("central_bounds")
        return None

    projected_base = state.members_seen
    cursor = central_start
    count = 0
    earliest_local_header: int | None = None
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

            adjusted_local_offset = concatenation_adjustment + local_offset
            if adjusted_local_offset < 0 or adjusted_local_offset >= central_start:
                reject(
                    "local_header_offset "
                    f"observed={adjusted_local_offset} central_start={central_start}"
                )
                return None
            if (
                earliest_local_header is None
                or adjusted_local_offset < earliest_local_header
            ):
                earliest_local_header = adjusted_local_offset

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

    # The first adjusted local-header offset is the actual SFX prefix boundary
    # for both styles: offsets left archive-relative plus a concatenation
    # adjustment, and offsets explicitly rebased by the SFX producer. For an
    # empty archive there is no local header, so the central directory itself is
    # the first ZIP structure after any wrapper.
    prefix_bytes = (
        earliest_local_header
        if earliest_local_header is not None
        else central_start
    )
    if earliest_local_header is not None:
        current = stream.tell()
        try:
            stream.seek(earliest_local_header)
            if read_exact(stream, 4) != LOCAL_SIGNATURE:
                reject("first_local_header_signature")
                return None
        finally:
            stream.seek(current)

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
