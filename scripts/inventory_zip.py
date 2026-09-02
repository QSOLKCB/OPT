#!/usr/bin/env python3
"""Safely inventory ZIP archives and surface optimization-related text.

The scanner reads members directly from ZIP containers and never extracts them.
Nested ZIPs are inspected recursively under explicit depth/member/size budgets.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import struct
import unicodedata
import zlib
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile, ZipInfo

TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".pyi", ".rs", ".toml", ".c", ".cc", ".cpp", ".h",
    ".hh", ".hpp", ".inc", ".json", ".jsonl", ".yml", ".yaml", ".xml", ".svg",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".csv", ".tsv", ".tex", ".rst",
    ".html", ".htm", ".css", ".scss", ".sh", ".bash", ".zsh", ".ps1", ".bat",
    ".cmd", ".java", ".kt", ".kts", ".go", ".rb", ".php", ".swift", ".scala",
    ".sql", ".ini", ".cfg", ".conf", ".properties", ".lock", ".lean", ".lake",
    ".cmake",
}
ZIP_MAGIC_PREFIXES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
EOCD_SIGNATURE = b"PK\x05\x06"
CENTRAL_SIGNATURE = b"PK\x01\x02"
KEYWORDS = re.compile(
    r"simd|zero[- ]?copy|lock[- ]?free|cache|caching|parallel|thread|sparse|"
    r"precomput|control[-_ ]?rate|block[-_ ]?process|vectori[sz]|packed|rayon|"
    r"buffer|latency|benchmark|performance|optimi[sz]|allocation|audio[-_ ]?rate",
    re.IGNORECASE,
)
WINDOWS_DRIVE = re.compile(r"^[A-Za-z]:")

EXIT_INVALID_ZIP = 2
EXIT_UNSAFE_MEMBER = 3
EXIT_INCOMPLETE = 4


@dataclass
class InventoryState:
    hits: int = 0
    archives_scanned: int = 0
    nested_archives: int = 0
    members_seen: int = 0
    text_members_scanned: int = 0
    declared_uncompressed_bytes: int = 0
    incomplete: list[str] = field(default_factory=list)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def escape_untrusted(text: str) -> str:
    """Return terminal-safe text with control/format characters escaped."""
    out: list[str] = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
            continue
        if unicodedata.category(ch) in {"Cc", "Cf", "Cs"}:
            out.append(ch.encode("unicode_escape").decode("ascii"))
            continue
        out.append(ch)
    return "".join(out)


def normalize_member_name(name: str) -> str:
    """Normalize ZIP path separators for validation only."""
    return name.replace("\\", "/")


def unsafe_member(name: str) -> bool:
    """Reject POSIX/Windows absolute paths and parent traversal spellings."""
    normalized = normalize_member_name(name)
    if "\x00" in normalized or WINDOWS_DRIVE.match(normalized):
        return True
    path = PurePosixPath(normalized)
    return path.is_absolute() or ".." in path.parts


def member_suffix(name: str) -> str:
    return PurePosixPath(normalize_member_name(name)).suffix.lower()


def _mark_incomplete(state: InventoryState, reason: str) -> None:
    state.incomplete.append(reason)
    print(f"inventory_incomplete={escape_untrusted(reason)}")


def _read_prefix(
    zf: ZipFile,
    info: ZipInfo,
    *,
    member_label: str,
    state: InventoryState,
    count: int = 4096,
) -> bytes | None:
    try:
        with zf.open(info, "r") as handle:
            return handle.read(count)
    except (BadZipFile, OSError, RuntimeError, EOFError, zlib.error) as exc:
        _mark_incomplete(
            state,
            f"read_error member={member_label} error={type(exc).__name__}",
        )
        return None


def _read_member(
    zf: ZipFile,
    info: ZipInfo,
    *,
    member_label: str,
    state: InventoryState,
) -> bytes | None:
    try:
        return zf.read(info)
    except (BadZipFile, OSError, RuntimeError, EOFError, zlib.error) as exc:
        _mark_incomplete(
            state,
            f"read_error member={member_label} error={type(exc).__name__}",
        )
        return None


def _looks_textual(prefix: bytes) -> bool:
    if not prefix:
        return False
    if b"\x00" in prefix:
        return False
    try:
        text = prefix.decode("utf-8")
    except UnicodeDecodeError:
        return False
    if not text:
        return False
    allowed_controls = {"\t", "\n", "\r", "\f"}
    suspicious = sum(
        1
        for ch in text
        if unicodedata.category(ch).startswith("C") and ch not in allowed_controls
    )
    return suspicious <= max(1, len(text) // 100)


def _match_context(line: str, match: re.Match[str], width: int = 400) -> str:
    """Return terminal-safe bounded context that always contains the match."""
    safe_match = escape_untrusted(line[match.start():match.end()])
    safe_before = escape_untrusted(line[:match.start()])
    safe_after = escape_untrusted(line[match.end():])
    left_marker = "…" if match.start() else ""
    right_marker = "…" if match.end() < len(line) else ""

    fixed = len(left_marker) + len(safe_match) + len(right_marker)
    if fixed >= width:
        return (left_marker + safe_match + right_marker)[:width]

    available = width - fixed
    before_budget = min(120, available // 3)
    before = safe_before[-before_budget:] if before_budget else ""
    after_budget = available - len(before)
    after = safe_after[:after_budget]
    return left_marker + before + safe_match + after + right_marker


def _validate_archive_limits(
    infos: list[ZipInfo],
    args: argparse.Namespace,
    state: InventoryState,
    label: str,
) -> bool:
    state.members_seen += len(infos)
    if state.members_seen > args.max_members:
        _mark_incomplete(
            state,
            f"member_limit label={label} observed={state.members_seen} limit={args.max_members}",
        )
        return False

    declared = sum(info.file_size for info in infos if not info.is_dir())
    state.declared_uncompressed_bytes += declared
    if state.declared_uncompressed_bytes > args.max_total_uncompressed_bytes:
        _mark_incomplete(
            state,
            "uncompressed_budget "
            f"label={label} observed={state.declared_uncompressed_bytes} "
            f"limit={args.max_total_uncompressed_bytes}",
        )
        return False
    return True


def _preflight_nested_zip(
    raw: bytes,
    *,
    member_label: str,
    args: argparse.Namespace,
    state: InventoryState,
) -> bool:
    """Count a nested ZIP central directory before ZipFile materializes ZipInfo objects."""
    search_start = max(0, len(raw) - (65535 + 22))
    eocd = raw.rfind(EOCD_SIGNATURE, search_start)
    if eocd < 0 or eocd + 22 > len(raw):
        _mark_incomplete(state, f"invalid_nested_zip member={member_label} reason=eocd")
        return False

    try:
        (
            disk_number,
            central_disk,
            entries_on_disk,
            entries_total,
            central_size,
            central_offset,
            comment_length,
        ) = struct.unpack_from("<4H2LH", raw, eocd + 4)
    except struct.error:
        _mark_incomplete(state, f"invalid_nested_zip member={member_label} reason=eocd_fields")
        return False

    if eocd + 22 + comment_length != len(raw):
        _mark_incomplete(state, f"invalid_nested_zip member={member_label} reason=trailing_or_comment")
        return False
    if disk_number != 0 or central_disk != 0 or entries_on_disk != entries_total:
        _mark_incomplete(state, f"unsupported_nested_zip member={member_label} reason=multi_disk")
        return False
    if (
        entries_total == 0xFFFF
        or central_size == 0xFFFFFFFF
        or central_offset == 0xFFFFFFFF
    ):
        _mark_incomplete(state, f"unsupported_nested_zip member={member_label} reason=zip64")
        return False

    central_end = central_offset + central_size
    if central_end != eocd or central_end > len(raw):
        _mark_incomplete(state, f"invalid_nested_zip member={member_label} reason=central_bounds")
        return False

    cursor = central_offset
    count = 0
    while cursor < central_end:
        if cursor + 46 > central_end or raw[cursor:cursor + 4] != CENTRAL_SIGNATURE:
            _mark_incomplete(
                state,
                f"invalid_nested_zip member={member_label} reason=central_header",
            )
            return False
        try:
            filename_len, extra_len, member_comment_len = struct.unpack_from(
                "<HHH", raw, cursor + 28
            )
        except struct.error:
            _mark_incomplete(
                state,
                f"invalid_nested_zip member={member_label} reason=central_lengths",
            )
            return False
        next_cursor = cursor + 46 + filename_len + extra_len + member_comment_len
        if next_cursor > central_end:
            _mark_incomplete(
                state,
                f"invalid_nested_zip member={member_label} reason=central_entry_bounds",
            )
            return False
        count += 1
        if state.members_seen + count > args.max_members:
            _mark_incomplete(
                state,
                "member_limit_preflight "
                f"member={member_label} projected={state.members_seen + count} "
                f"limit={args.max_members}",
            )
            return False
        cursor = next_cursor

    if cursor != central_end or count != entries_total:
        _mark_incomplete(
            state,
            f"invalid_nested_zip member={member_label} reason=central_count",
        )
        return False
    return True


def _scan_text_member(
    zf: ZipFile,
    info: ZipInfo,
    member_label: str,
    args: argparse.Namespace,
    state: InventoryState,
    *,
    detected_text: bool,
) -> None:
    known_text = member_suffix(info.filename) in TEXT_SUFFIXES
    if not known_text and not detected_text:
        return
    if info.file_size > args.max_text_bytes:
        _mark_incomplete(
            state,
            "text_member_size "
            f"member={member_label} size={info.file_size} limit={args.max_text_bytes}",
        )
        return

    raw = _read_member(zf, info, member_label=member_label, state=state)
    if raw is None:
        return
    text = raw.decode("utf-8", errors="replace")
    state.text_members_scanned += 1
    for lineno, line in enumerate(text.splitlines(), start=1):
        match = KEYWORDS.search(line)
        if match is None:
            continue
        print(
            f"{escape_untrusted(member_label)}:{lineno}: "
            f"{_match_context(line, match)}"
        )
        state.hits += 1
        if state.hits >= args.max_hits:
            _mark_incomplete(state, f"hit_limit observed={state.hits} limit={args.max_hits}")
            return


def inventory_zip(
    zf: ZipFile,
    *,
    label: str,
    depth: int,
    args: argparse.Namespace,
    state: InventoryState,
) -> int:
    state.archives_scanned += 1
    infos = zf.infolist()
    safe_label = escape_untrusted(label)

    print(f"\n== members: {safe_label} depth={depth} ==")
    if not _validate_archive_limits(infos, args, state, label):
        return EXIT_INCOMPLETE

    unsafe = [info.filename for info in infos if unsafe_member(info.filename)]
    if unsafe:
        print(f"unsafe_members archive={safe_label}:")
        for name in unsafe:
            print(f"  {escape_untrusted(name)}")
        return EXIT_UNSAFE_MEMBER

    for info in infos:
        ratio = 0.0 if info.file_size == 0 else 1.0 - (info.compress_size / info.file_size)
        member_label = f"{label}!/{info.filename}"
        print(
            f"{info.file_size:>10} {info.compress_size:>10} "
            f"saved={ratio:>7.1%} {escape_untrusted(member_label)}"
        )

    for info in infos:
        if info.is_dir():
            continue
        if state.incomplete:
            break
        if info.flag_bits & 0x1:
            _mark_incomplete(state, f"encrypted_member {label}!/{info.filename}")
            break

        member_label = f"{label}!/{info.filename}"
        suffix = member_suffix(info.filename)
        prefix: bytes | None = None

        if suffix == ".zip":
            nested_zip = True
        else:
            prefix = _read_prefix(
                zf,
                info,
                member_label=member_label,
                state=state,
            )
            if prefix is None:
                break
            nested_zip = prefix[:4] in ZIP_MAGIC_PREFIXES

        if nested_zip:
            if depth >= args.max_depth:
                _mark_incomplete(
                    state,
                    f"depth_limit member={member_label} depth={depth} limit={args.max_depth}",
                )
                break
            if info.file_size > args.max_nested_zip_bytes:
                _mark_incomplete(
                    state,
                    "nested_zip_size "
                    f"member={member_label} size={info.file_size} "
                    f"limit={args.max_nested_zip_bytes}",
                )
                break

            raw = _read_member(zf, info, member_label=member_label, state=state)
            if raw is None:
                break
            if not _preflight_nested_zip(
                raw,
                member_label=member_label,
                args=args,
                state=state,
            ):
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
            except (BadZipFile, zlib.error) as exc:
                _mark_incomplete(
                    state,
                    f"invalid_nested_zip member={member_label} error={type(exc).__name__}",
                )
                break
            if status == EXIT_UNSAFE_MEMBER:
                return status
            if status == EXIT_INCOMPLETE:
                break
            continue

        if prefix is None:
            prefix = _read_prefix(
                zf,
                info,
                member_label=member_label,
                state=state,
            )
            if prefix is None:
                break
        _scan_text_member(
            zf,
            info,
            member_label,
            args,
            state,
            detected_text=_looks_textual(prefix),
        )

    return EXIT_INCOMPLETE if state.incomplete else 0


def positive_int(value: str) -> int:
    parsed = int(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be > 0")
    return parsed


def nonnegative_int(value: str) -> int:
    parsed = int(value)
    if parsed < 0:
        raise argparse.ArgumentTypeError("must be >= 0")
    return parsed


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--max-text-bytes", type=positive_int, default=2_000_000)
    parser.add_argument("--max-hits", type=positive_int, default=500)
    parser.add_argument("--max-depth", type=nonnegative_int, default=4)
    parser.add_argument("--max-members", type=positive_int, default=20_000)
    parser.add_argument("--max-nested-zip-bytes", type=positive_int, default=64 * 1024 * 1024)
    parser.add_argument(
        "--max-total-uncompressed-bytes",
        type=positive_int,
        default=512 * 1024 * 1024,
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    if not args.archive.is_file():
        raise SystemExit(f"archive not found: {args.archive}")

    print(f"archive={escape_untrusted(str(args.archive))}")
    print(f"sha256={sha256_file(args.archive)}")

    try:
        zf = ZipFile(args.archive)
    except BadZipFile as exc:
        print(f"invalid_zip={escape_untrusted(str(exc))}")
        return EXIT_INVALID_ZIP

    state = InventoryState()
    with zf:
        status = inventory_zip(
            zf,
            label=str(args.archive),
            depth=0,
            args=args,
            state=state,
        )

    print("\n== summary ==")
    print(f"archives_scanned={state.archives_scanned}")
    print(f"nested_archives={state.nested_archives}")
    print(f"members_seen={state.members_seen}")
    print(f"text_members_scanned={state.text_members_scanned}")
    print(f"declared_uncompressed_bytes={state.declared_uncompressed_bytes}")
    print(f"hits={state.hits}")
    print(f"inventory_complete={str(status == 0 and not state.incomplete).lower()}")
    return status


if __name__ == "__main__":
    raise SystemExit(main())
