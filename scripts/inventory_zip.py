#!/usr/bin/env python3
"""Safely inventory a ZIP archive and surface optimization-related text.

Reads text members directly from the archive; it does not extract files.
"""

from __future__ import annotations

import argparse
import hashlib
import re
from pathlib import Path, PurePosixPath
from zipfile import BadZipFile, ZipFile

TEXT_SUFFIXES = {
    ".md", ".txt", ".py", ".rs", ".toml", ".c", ".cc", ".cpp", ".h",
    ".hh", ".hpp", ".json", ".yml", ".yaml", ".xml", ".js", ".ts",
}
KEYWORDS = re.compile(
    r"simd|zero[- ]?copy|lock[- ]?free|cache|caching|parallel|thread|sparse|"
    r"precomput|control[-_ ]?rate|block[-_ ]?process|vectori[sz]|packed|rayon|"
    r"buffer|latency|benchmark|performance|optimi[sz]|allocation|audio[-_ ]?rate",
    re.IGNORECASE,
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def unsafe_member(name: str) -> bool:
    p = PurePosixPath(name)
    return p.is_absolute() or ".." in p.parts


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("archive", type=Path)
    parser.add_argument("--max-text-bytes", type=int, default=2_000_000)
    parser.add_argument("--max-hits", type=int, default=500)
    args = parser.parse_args()

    if not args.archive.is_file():
        parser.error(f"archive not found: {args.archive}")

    print(f"archive={args.archive}")
    print(f"sha256={sha256_file(args.archive)}")

    try:
        zf = ZipFile(args.archive)
    except BadZipFile as exc:
        print(f"invalid_zip={exc}")
        return 2

    with zf:
        infos = zf.infolist()
        print(f"members={len(infos)}")
        unsafe = [info.filename for info in infos if unsafe_member(info.filename)]
        if unsafe:
            print("unsafe_members:")
            for name in unsafe:
                print(f"  {name}")
            return 3

        print("\n== members ==")
        for info in infos:
            ratio = 0.0 if info.file_size == 0 else 1.0 - (info.compress_size / info.file_size)
            print(
                f"{info.file_size:>10} {info.compress_size:>10} "
                f"saved={ratio:>7.1%} {info.filename}"
            )

        print("\n== optimization keyword hits ==")
        hits = 0
        for info in infos:
            if info.is_dir() or info.file_size > args.max_text_bytes:
                continue
            if Path(info.filename).suffix.lower() not in TEXT_SUFFIXES:
                continue
            raw = zf.read(info)
            text = raw.decode("utf-8", errors="replace")
            for lineno, line in enumerate(text.splitlines(), start=1):
                if KEYWORDS.search(line):
                    print(f"{info.filename}:{lineno}: {line[:400]}")
                    hits += 1
                    if hits >= args.max_hits:
                        print(f"hit_limit={args.max_hits}")
                        return 0
        print(f"hits={hits}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
