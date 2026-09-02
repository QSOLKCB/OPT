"""Shared constants, state, and terminal-safe helpers."""

from __future__ import annotations

import argparse
import hashlib
import io
import re
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path, PurePosixPath
from typing import BinaryIO

TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".pyi", ".rs", ".toml", ".c", ".cc", ".cpp", ".h",
    ".hh", ".hpp", ".inc", ".json", ".jsonl", ".yml", ".yaml", ".xml", ".svg",
    ".js", ".mjs", ".cjs", ".ts", ".tsx", ".jsx", ".csv", ".tsv", ".tex", ".rst",
    ".html", ".htm", ".css", ".scss", ".sh", ".bash", ".zsh", ".ps1", ".bat",
    ".cmd", ".java", ".kt", ".kts", ".go", ".rb", ".php", ".swift", ".scala",
    ".sql", ".ini", ".cfg", ".conf", ".properties", ".lock", ".lean", ".lake",
    ".cmake",
}

EOCD_SIGNATURE = b"PK\x05\x06"
CENTRAL_SIGNATURE = b"PK\x01\x02"
LOCAL_SIGNATURE = b"PK\x03\x04"
MAX_EOCD_SEARCH = 65535 + 22
CENTRAL_FIXED_SIZE = 46
LOCAL_FIXED_SIZE = 30
READ_CHUNK = 64 * 1024

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


@dataclass(frozen=True)
class ZipPreflight:
    entries: int
    central_start: int
    central_size: int
    prefix_bytes: int


@dataclass
class InventoryState:
    hits: int = 0
    archives_scanned: int = 0
    nested_archives: int = 0
    members_seen: int = 0
    text_members_scanned: int = 0
    declared_uncompressed_bytes: int = 0
    actual_decompressed_bytes: int = 0
    invalid: list[str] = field(default_factory=list)
    incomplete: list[str] = field(default_factory=list)


class OutputLimitExceeded(Exception):
    """Raised internally after one byte beyond a configured output limit."""


class MemberFormatError(Exception):
    """Raised internally for malformed or unsupported member encoding."""


def sha256_stream(stream: BinaryIO) -> str:
    """Hash one already-open seekable stream without changing its position."""
    current = stream.tell()
    digest = hashlib.sha256()
    try:
        stream.seek(0)
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
        return digest.hexdigest()
    finally:
        stream.seek(current)


def sha256_file(path: Path) -> str:
    with path.open("rb") as handle:
        return sha256_stream(handle)


def escape_untrusted(text: str) -> str:
    """Return terminal-safe text with control and format characters escaped."""
    out: list[str] = []
    for ch in text:
        if ch == "\\":
            out.append("\\\\")
        elif unicodedata.category(ch) in {"Cc", "Cf", "Cs"}:
            out.append(ch.encode("unicode_escape").decode("ascii"))
        else:
            out.append(ch)
    return "".join(out)


def normalize_member_name(name: str) -> str:
    return name.replace("\\", "/")


def unsafe_member(name: str) -> bool:
    normalized = normalize_member_name(name)
    if "\x00" in normalized or WINDOWS_DRIVE.match(normalized):
        return True
    path = PurePosixPath(normalized)
    return path.is_absolute() or ".." in path.parts


def member_suffix(name: str) -> str:
    return PurePosixPath(normalize_member_name(name)).suffix.lower()


def mark_invalid(state: InventoryState, reason: str) -> None:
    state.invalid.append(reason)
    print(f"invalid_zip={escape_untrusted(reason)}")


def mark_incomplete(state: InventoryState, reason: str) -> None:
    state.incomplete.append(reason)
    print(f"inventory_incomplete={escape_untrusted(reason)}")


def read_exact(stream: BinaryIO, size: int) -> bytes:
    data = stream.read(size)
    if len(data) != size:
        raise EOFError(f"expected {size} bytes, received {len(data)}")
    return data


def stream_size(stream: BinaryIO) -> int:
    current = stream.tell()
    stream.seek(0, io.SEEK_END)
    size = stream.tell()
    stream.seek(current)
    return size


def looks_textual(data: bytes) -> bool:
    prefix = data[:4096]
    if not prefix or b"\x00" in prefix:
        return False
    try:
        text = prefix.decode("utf-8")
    except UnicodeDecodeError:
        return False
    allowed_controls = {"\t", "\n", "\r", "\f"}
    suspicious = sum(
        1
        for ch in text
        if unicodedata.category(ch).startswith("C") and ch not in allowed_controls
    )
    return bool(text) and suspicious <= max(1, len(text) // 100)


def match_context(line: str, match: re.Match[str], width: int = 400) -> str:
    """Return bounded terminal-safe context that always includes the match."""
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
    after = safe_after[:available - len(before)]
    return left_marker + before + safe_match + after + right_marker


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


def print_summary(state: InventoryState, status: int) -> None:
    print("\n== summary ==")
    print(f"archives_scanned={state.archives_scanned}")
    print(f"nested_archives={state.nested_archives}")
    print(f"members_seen={state.members_seen}")
    print(f"text_members_scanned={state.text_members_scanned}")
    print(f"declared_uncompressed_bytes={state.declared_uncompressed_bytes}")
    print(f"actual_decompressed_bytes={state.actual_decompressed_bytes}")
    print(f"hits={state.hits}")
    complete = status == 0 and not state.invalid and not state.incomplete
    print(f"inventory_complete={str(complete).lower()}")
