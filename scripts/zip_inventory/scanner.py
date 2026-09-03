"""Recursive archive inventory and bounded keyword scanning."""

from __future__ import annotations

import io
import zlib
from zipfile import BadZipFile, LargeZipFile, ZipFile, ZipInfo

from .common import (
    EXIT_INCOMPLETE,
    EXIT_UNSAFE_MEMBER,
    KEYWORDS,
    TEXT_SUFFIXES,
    InventoryState,
    decode_text,
    escape_untrusted,
    looks_textual,
    mark_incomplete,
    match_context,
    member_suffix,
    unsafe_member,
)
from .preflight import preflight_zip_bytes
from .reader import read_member_bounded


def _validate_archive_limits(
    infos: list[ZipInfo],
    args: object,
    state: InventoryState,
    label: str,
) -> bool:
    state.members_seen += len(infos)
    if state.members_seen > args.max_members:
        mark_incomplete(
            state,
            f"member_limit label={label} "
            f"observed={state.members_seen} limit={args.max_members}",
        )
        return False

    declared = sum(info.file_size for info in infos)
    state.declared_uncompressed_bytes += declared
    if (
        state.declared_uncompressed_bytes
        > args.max_total_uncompressed_bytes
    ):
        mark_incomplete(
            state,
            f"declared_uncompressed_budget label={label} "
            f"observed={state.declared_uncompressed_bytes} "
            f"limit={args.max_total_uncompressed_bytes}",
        )
        return False
    return True


def scan_text(
    raw: bytes,
    label: str,
    args: object,
    state: InventoryState,
) -> None:
    """Scan one bounded text payload and enforce the printed-hit cap."""
    if len(raw) > args.max_text_bytes:
        mark_incomplete(
            state,
            f"text_member_size member={label} "
            f"size={len(raw)} limit={args.max_text_bytes}",
        )
        return

    try:
        text = decode_text(raw)
    except (LookupError, UnicodeDecodeError) as exc:
        mark_incomplete(
            state,
            f"text_decode_error member={label} error={type(exc).__name__}",
        )
        return

    state.text_members_scanned += 1
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = KEYWORDS.search(line)
        if match is None:
            continue

        state.hits += 1
        if args.max_hits and state.hits > args.max_hits:
            mark_incomplete(
                state,
                f"hit_limit observed={state.hits} "
                f"limit={args.max_hits}",
            )
            return

        print(
            f"{escape_untrusted(label)}:{lineno}: "
            f"{match_context(line, match)}"
        )


def _scan_sfx_prefix(
    raw: bytes,
    *,
    prefix_bytes: int,
    suffix: str,
    member_label: str,
    args: object,
    state: InventoryState,
) -> None:
    if prefix_bytes <= 0:
        return
    prefix = raw[:prefix_bytes]
    if suffix in TEXT_SUFFIXES or looks_textual(prefix):
        scan_text(
            prefix,
            f"{member_label}#sfx-prefix",
            args,
            state,
        )


def inventory_zip(
    zf: ZipFile,
    *,
    label: str,
    depth: int,
    args: object,
    state: InventoryState,
) -> int:
    state.archives_scanned += 1
    infos = zf.infolist()
    safe_label = escape_untrusted(label)
    print(f"\n== members: {safe_label} depth={depth} ==")

    if not _validate_archive_limits(infos, args, state, label):
        return EXIT_INCOMPLETE

    unsafe = [
        info.filename
        for info in infos
        if unsafe_member(info.filename)
    ]
    if unsafe:
        print(f"unsafe_members archive={safe_label}:")
        for name in unsafe:
            print(f"  {escape_untrusted(name)}")
        return EXIT_UNSAFE_MEMBER

    for info in infos:
        ratio = (
            0.0
            if info.file_size == 0
            else 1.0 - (info.compress_size / info.file_size)
        )
        member_label = f"{label}!/{info.filename}"
        print(
            f"{info.file_size:>10} {info.compress_size:>10} "
            f"saved={ratio:>7.1%} "
            f"{escape_untrusted(member_label)}"
        )

    probe_limit = max(
        args.max_text_bytes,
        args.max_nested_zip_bytes,
    )
    for info in infos:
        if state.incomplete:
            break

        member_label = f"{label}!/{info.filename}"
        is_directory = info.is_dir()
        if is_directory and info.file_size != 0:
            mark_incomplete(
                state,
                f"nonempty_directory_entry member={member_label} "
                f"size={info.file_size} "
                f"compressed_size={info.compress_size}",
            )
            break

        if info.flag_bits & 0x1:
            mark_incomplete(
                state,
                f"encrypted_member {member_label}",
            )
            break

        suffix = member_suffix(info.filename)
        required_zip = not is_directory and suffix == ".zip"
        if is_directory:
            member_limit = 0
        elif required_zip:
            member_limit = args.max_nested_zip_bytes
        else:
            member_limit = probe_limit

        raw = read_member_bounded(
            zf,
            info,
            member_label=member_label,
            member_limit=member_limit,
            args=args,
            state=state,
        )
        if raw is None:
            break

        # Directory-shaped entries still pass through the local-header
        # validator above. A valid empty directory has no payload to scan.
        if is_directory:
            continue

        preflight = preflight_zip_bytes(
            raw,
            label=member_label,
            args=args,
            state=state,
            required=required_zip,
        )
        if state.incomplete:
            break

        if preflight is not None:
            _scan_sfx_prefix(
                raw,
                prefix_bytes=preflight.prefix_bytes,
                suffix=suffix,
                member_label=member_label,
                args=args,
                state=state,
            )
            if state.incomplete:
                break

            if len(raw) > args.max_nested_zip_bytes:
                mark_incomplete(
                    state,
                    f"nested_zip_size member={member_label} "
                    f"size={len(raw)} "
                    f"limit={args.max_nested_zip_bytes}",
                )
                break

            if depth >= args.max_depth:
                mark_incomplete(
                    state,
                    f"depth_limit member={member_label} "
                    f"depth={depth} limit={args.max_depth}",
                )
                break

            try:
                with ZipFile(io.BytesIO(raw)) as nested:
                    state.nested_archives += 1
                    status = inventory_zip(
                        nested,
                        label=member_label,
                        depth=depth + 1,
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
                mark_incomplete(
                    state,
                    f"invalid_nested_zip member={member_label} "
                    f"error={type(exc).__name__}",
                )
                break

            if status == EXIT_UNSAFE_MEMBER:
                return status
            if status == EXIT_INCOMPLETE:
                break
            continue

        if suffix in TEXT_SUFFIXES or looks_textual(raw):
            scan_text(
                raw,
                member_label,
                args,
                state,
            )

    return EXIT_INCOMPLETE if state.incomplete else 0
