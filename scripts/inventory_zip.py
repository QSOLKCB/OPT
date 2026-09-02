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
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile, ZipInfo

TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".rs", ".toml", ".c", ".cc", ".cpp", ".h",
    ".hh", ".hpp", ".json", ".yml", ".yaml", ".xml", ".js", ".ts",
}
ZIP_MAGIC_PREFIXES = (b"PK\x03\x04", b"PK\x05\x06", b"PK\x07\x08")
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


def _read_prefix(zf: ZipFile, info: ZipInfo, count: int = 4) -> bytes:
    with zf.open(info, "r") as handle:
        return handle.read(count)


def _is_nested_zip(zf: ZipFile, info: ZipInfo) -> bool:
    if member_suffix(info.filename) == ".zip":
        return True
    try:
        return _read_prefix(zf, info) in ZIP_MAGIC_PREFIXES
    except (RuntimeError, OSError, BadZipFile):
        return False


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


def _read_member(
    zf: ZipFile,
    info: ZipInfo,
    *,
    member_label: str,
    state: InventoryState,
) -> bytes | None:
    try:
        return zf.read(info)
    except (BadZipFile, OSError, RuntimeError) as exc:
        _mark_incomplete(
            state,
            f"read_error member={member_label} error={type(exc).__name__}",
        )
        return None


def _scan_text_member(
    zf: ZipFile,
    info: ZipInfo,
    member_label: str,
    args: argparse.Namespace,
    state: InventoryState,
) -> None:
    if member_suffix(info.filename) not in TEXT_SUFFIXES:
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
        if not KEYWORDS.search(line):
            continue
        safe_line = escape_untrusted(line)
        print(f"{escape_untrusted(member_label)}:{lineno}: {safe_line[:400]}")
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
        if _is_nested_zip(zf, info):
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
            except BadZipFile:
                _mark_incomplete(state, f"invalid_nested_zip member={member_label}")
                break
            if status == EXIT_UNSAFE_MEMBER:
                return status
            if status == EXIT_INCOMPLETE:
                break
            continue

        _scan_text_member(zf, info, member_label, args, state)

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
