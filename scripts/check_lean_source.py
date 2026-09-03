#!/usr/bin/env python3
"""Fail closed on proof placeholders or primitive user declarations in Lean sources."""

from __future__ import annotations

import argparse
import re
from pathlib import Path

FORBIDDEN = re.compile(r"\b(sorry|admit|axiom|constant|unsafe)\b")
INTERPOLATOR = re.compile(r"[A-Za-z_][A-Za-z0-9_']*!\"")
RAW_STRING = re.compile(r'r(#*)"')


def strip_comments_and_strings(text: str) -> str:
    """Blank inert comments/literals while preserving interpolated Lean expressions."""
    out = [" "] * len(text)
    n = len(text)

    def keep_newline(i: int) -> None:
        if text[i] == "\n":
            out[i] = "\n"

    def ident_continuation(ch: str) -> bool:
        return ch.isalnum() or ch in "_'"

    def at_token_boundary(i: int) -> bool:
        return i == 0 or not ident_continuation(text[i - 1])

    def scan_line_comment(i: int) -> int:
        i += 2
        while i < n and text[i] != "\n":
            i += 1
        if i < n:
            out[i] = "\n"
            i += 1
        return i

    def scan_block_comment(i: int) -> int:
        depth = 1
        i += 2
        while i < n:
            if text.startswith("/-", i):
                depth += 1
                i += 2
                continue
            if text.startswith("-/", i):
                depth -= 1
                i += 2
                if depth == 0:
                    return i
                continue
            keep_newline(i)
            i += 1
        raise ValueError("unterminated block comment")

    def scan_plain_string(i: int) -> int:
        escaped = False
        while i < n:
            ch = text[i]
            keep_newline(i)
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                return i + 1
            i += 1
        raise ValueError("unterminated string literal")

    def scan_raw_string(i: int, hashes: int) -> int:
        """Skip one Lean raw string r#*"..."#* with no escape processing."""
        closer = '"' + "#" * hashes
        end = text.find(closer, i)
        if end < 0:
            raise ValueError("unterminated raw string literal")
        for j in range(i, end):
            keep_newline(j)
        return end + len(closer)

    def scan_char_literal(i: int) -> int:
        """Skip one Lean character literal without exposing brace payloads."""
        i += 1
        escaped = False
        while i < n:
            ch = text[i]
            if ch == "\n":
                raise ValueError("unterminated character literal")
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                return i + 1
            i += 1
        raise ValueError("unterminated character literal")

    def scan_code(i: int, interpolation_depth: int | None = None) -> int:
        depth = interpolation_depth
        while i < n:
            ch = text[i]

            if text.startswith("/-", i):
                i = scan_block_comment(i)
                continue
            if text.startswith("--", i):
                i = scan_line_comment(i)
                continue

            interpolator = INTERPOLATOR.match(text, i)
            if interpolator is not None:
                i = scan_interpolated_string(interpolator.end())
                continue

            # Raw strings must be recognized before the ordinary quote branch.
            # Otherwise embedded quotes/comment markers can hide later code.
            raw = RAW_STRING.match(text, i)
            if raw is not None and at_token_boundary(i):
                i = scan_raw_string(raw.end(), len(raw.group(1)))
                continue

            if ch == '"':
                i = scan_plain_string(i + 1)
                continue

            # Lean permits apostrophes in identifiers (for example `foo'`), so
            # only treat a quote at a token boundary as a character literal.
            if ch == "'" and at_token_boundary(i):
                i = scan_char_literal(i)
                continue

            if depth is not None:
                if ch == "{":
                    out[i] = ch
                    depth += 1
                    i += 1
                    continue
                if ch == "}":
                    out[i] = ch
                    depth -= 1
                    i += 1
                    if depth == 0:
                        return i
                    continue

            out[i] = ch
            i += 1

        if depth is not None:
            raise ValueError("unterminated interpolated-string expression")
        return i

    def scan_interpolated_string(i: int) -> int:
        escaped = False
        while i < n:
            ch = text[i]
            nxt = text[i + 1] if i + 1 < n else ""
            keep_newline(i)

            if escaped:
                escaped = False
                i += 1
                continue
            if ch == "\\":
                escaped = True
                i += 1
                continue
            if ch == '"':
                return i + 1
            if ch == "{" and nxt == "{":
                i += 2
                continue
            if ch == "{":
                out[i] = ch
                i = scan_code(i + 1, interpolation_depth=1)
                continue
            i += 1

        raise ValueError("unterminated interpolated string literal")

    scan_code(0)
    return "".join(out)


def findings_in_text(text: str, label: str) -> list[str]:
    stripped = strip_comments_and_strings(text)
    findings: list[str] = []
    for match in FORBIDDEN.finditer(stripped):
        line = stripped.count("\n", 0, match.start()) + 1
        findings.append(f"{label}:{line}: forbidden token {match.group(1)!r}")
    return findings


def check_file(path: Path) -> list[str]:
    return findings_in_text(path.read_text(encoding="utf-8"), str(path))


def run_self_test() -> None:
    safe_cases = {
        "ordinary string": 'def x := "sorry axiom constant unsafe"',
        "line comment": "-- sorry axiom constant unsafe\ntheorem t : True := by trivial",
        "block comment": "/- sorry /- constant -/ unsafe -/\ntheorem t : True := by trivial",
        "interpolation literal": 'def x := s!"sorry {{constant}} {1}"',
        "interpolation nested string": 'def x := s!"{let y := "sorry"; y}"',
        "character closing brace": "def x := s!\"{let c := '}'; c}\"",
        "identifier apostrophe": "def foo' : Nat := 1",
        "raw string": 'def x := r"sorry axiom constant unsafe"',
        "hashed raw string": 'def x := r#"sorry "quoted" admit"#',
        "raw string with comment marker": 'def x := r#"" -- sorry "#',
        "multiline raw string": 'def x := r##"line one\nsorry -- constant\nline three"##',
        "raw-like opener after identifier": 'def x := barr"sorry -- axiom"',
    }
    unsafe_cases = {
        "sorry interpolation": ('def x := s!"{(sorry : Nat)}"', "sorry"),
        "message interpolation": ('def x := m!"{(admit : MessageData)}"', "admit"),
        "constant declaration": ("constant untrusted : Prop", "constant"),
        "nested interpolation": ('def x := s!"{s!"{(admit : Nat)}"}"', "admit"),
        "char literal before sorry": (
            "def x := s!\"{let c := '}'; (sorry : Nat)}\"",
            "sorry",
        ),
        "escaped char before admit": (
            "def x := s!\"{let c := '\\\''; (admit : Nat)}\"",
            "admit",
        ),
        "raw string comment bypass": (
            'noncomputable def bad : Empty := (r#"" -- "#, (sorry : Empty)).2',
            "sorry",
        ),
        "raw string then admit": (
            'def x := (r"a", (admit : Nat)).2',
            "admit",
        ),
        "raw string brace inside interpolation": (
            'def x := s!"{let y := r#"} -- sorry"#; (admit : Nat)}"',
            "admit",
        ),
    }

    for name, source in safe_cases.items():
        findings = findings_in_text(source, f"<self-test:{name}>")
        if findings:
            raise RuntimeError(f"false positive for {name}: {findings}")

    for name, (source, token) in unsafe_cases.items():
        findings = findings_in_text(source, f"<self-test:{name}>")
        if not any(f"forbidden token '{token}'" in finding for finding in findings):
            raise RuntimeError(f"missed {token} in {name}: {findings}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("root", type=Path, nargs="?", default=Path("Lean"))
    parser.add_argument("--self-test", action="store_true")
    args = parser.parse_args()

    if args.self_test:
        try:
            run_self_test()
        except (RuntimeError, ValueError) as exc:
            print(f"LEAN_SOURCE_SELF_TEST_FAILED: {exc}")
            return 2
        print("LEAN_SOURCE_SELF_TEST_OK")

    files = sorted(args.root.rglob("*.lean"))
    if not files:
        print(f"no Lean sources found under {args.root}")
        return 2

    findings: list[str] = []
    for path in files:
        try:
            findings.extend(check_file(path))
        except (OSError, UnicodeDecodeError, ValueError) as exc:
            findings.append(f"{path}: source scan failed: {exc}")

    if findings:
        for finding in findings:
            print(finding)
        return 1

    print(f"LEAN_SOURCE_PURITY_OK files={len(files)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())