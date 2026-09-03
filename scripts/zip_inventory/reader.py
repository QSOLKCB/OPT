"""Bounded member reads with incremental decompression and integrity checks."""

from __future__ import annotations

import bz2
import lzma
import struct
import zlib
from zipfile import (
    BadZipFile,
    LargeZipFile,
    ZIP_BZIP2,
    ZIP_DEFLATED,
    ZIP_LZMA,
    ZIP_STORED,
    ZipFile,
    ZipInfo,
)

from .common import (
    LOCAL_FIXED_SIZE,
    LOCAL_SIGNATURE,
    READ_CHUNK,
    InventoryState,
    MemberFormatError,
    OutputLimitExceeded,
    mark_incomplete,
    read_exact,
    stream_size,
    unsafe_member,
)

# Bits 5 and 6 change the interpretation of member data. Python's ZipFile
# rejects compressed-patched-data and strong-encryption members; this custom
# bounded reader must not silently decode either encoding as an ordinary stream.
_UNSUPPORTED_GENERAL_PURPOSE_FLAGS = (1 << 5) | (1 << 6)


class _BoundedZipLzmaDecompressor:
    """ZIP method-14 LZMA decoder with output and workspace limits."""

    def __init__(self, max_dictionary_bytes: int) -> None:
        self._header = bytearray()
        self._decoder: lzma.LZMADecompressor | None = None
        self._max_dictionary_bytes = max_dictionary_bytes

    def _filters(self, properties: bytes) -> list[dict[str, int]]:
        if len(properties) != 5:
            raise MemberFormatError("unsupported LZMA property length")
        encoded = properties[0]
        if encoded >= 9 * 5 * 5:
            raise MemberFormatError("invalid LZMA properties")
        lc = encoded % 9
        remainder = encoded // 9
        lp = remainder % 5
        pb = remainder // 5
        dictionary_size = int.from_bytes(properties[1:5], "little") or 1
        if dictionary_size > self._max_dictionary_bytes:
            raise MemberFormatError(
                "LZMA dictionary size exceeds limit "
                f"observed={dictionary_size} limit={self._max_dictionary_bytes}"
            )
        return [{
            "id": lzma.FILTER_LZMA1,
            "dict_size": dictionary_size,
            "lc": lc,
            "lp": lp,
            "pb": pb,
        }]

    @property
    def eof(self) -> bool:
        return bool(self._decoder and self._decoder.eof)

    @property
    def needs_input(self) -> bool:
        return True if self._decoder is None else self._decoder.needs_input

    @property
    def unused_data(self) -> bytes:
        return b"" if self._decoder is None else self._decoder.unused_data

    def decompress(self, data: bytes, max_length: int) -> bytes:
        if self._decoder is None:
            self._header.extend(data)
            if len(self._header) < 4:
                return b""
            property_size = struct.unpack_from("<H", self._header, 2)[0]
            if property_size > 64:
                raise MemberFormatError("LZMA property header exceeds limit")
            header_size = 4 + property_size
            if len(self._header) < header_size:
                return b""
            properties = bytes(self._header[4:header_size])
            payload = bytes(self._header[header_size:])
            self._header.clear()
            self._decoder = lzma.LZMADecompressor(
                format=lzma.FORMAT_RAW,
                filters=self._filters(properties),
            )
            data = payload
        return self._decoder.decompress(data, max_length=max_length)


def _decode_local_filename(zf: ZipFile, info: ZipInfo, flags: int, raw: bytes) -> str:
    encoding = "utf-8" if flags & 0x800 else (
        getattr(zf, "metadata_encoding", None) or "cp437"
    )
    try:
        decoded = raw.decode(encoding, errors="strict")
    except (LookupError, UnicodeDecodeError) as exc:
        raise MemberFormatError("local filename encoding") from exc
    if unsafe_member(decoded):
        raise MemberFormatError("unsafe local filename")
    if decoded != info.orig_filename:
        raise MemberFormatError("local filename mismatch")
    return decoded


def read_member_bounded(
    zf: ZipFile,
    info: ZipInfo,
    *,
    member_label: str,
    member_limit: int,
    args: object,
    state: InventoryState,
) -> bytes | None:
    """Read one member without trusting declared uncompressed size."""
    global_remaining = (
        args.max_total_uncompressed_bytes - state.actual_decompressed_bytes
    )
    if global_remaining < 0:
        mark_incomplete(
            state,
            "actual_uncompressed_budget "
            f"member={member_label} observed={state.actual_decompressed_bytes} "
            f"limit={args.max_total_uncompressed_bytes}",
        )
        return None
    output_limit = min(member_limit, global_remaining)
    limit_reason = (
        "actual_uncompressed_budget"
        if global_remaining <= member_limit
        else "member_output_limit"
    )
    if info.file_size > member_limit:
        mark_incomplete(
            state,
            f"declared_member_output_limit member={member_label} "
            f"size={info.file_size} limit={member_limit}",
        )
        return None
    if info.compress_size > args.max_compressed_member_bytes:
        mark_incomplete(
            state,
            f"compressed_member_size member={member_label} "
            f"size={info.compress_size} "
            f"limit={args.max_compressed_member_bytes}",
        )
        return None

    # Reject central-directory semantic flags before any decoder is allocated.
    unsupported_central = info.flag_bits & _UNSUPPORTED_GENERAL_PURPOSE_FLAGS
    if unsupported_central:
        mark_incomplete(
            state,
            f"read_error member={member_label} "
            f"error=unsupported_flags mask=0x{unsupported_central:04x}",
        )
        return None

    fp = zf.fp
    if fp is None:
        mark_incomplete(
            state,
            f"read_error member={member_label} error=closed_archive",
        )
        return None

    produced = 0
    crc = 0
    parts: list[bytes] = []

    def emit(piece: bytes) -> None:
        nonlocal produced, crc
        if not piece:
            return
        produced += len(piece)
        crc = zlib.crc32(piece, crc)
        if produced > output_limit:
            raise OutputLimitExceeded
        parts.append(piece)

    def room() -> int:
        return output_limit - produced + 1

    original_position = fp.tell()
    try:
        fp.seek(info.header_offset)
        fixed = read_exact(fp, LOCAL_FIXED_SIZE)
        if fixed[:4] != LOCAL_SIGNATURE:
            raise MemberFormatError("local header signature")

        local_flags = struct.unpack_from("<H", fixed, 6)[0]
        local_method = struct.unpack_from("<H", fixed, 8)[0]
        filename_len, extra_len = struct.unpack_from("<HH", fixed, 26)

        unsupported_local = local_flags & _UNSUPPORTED_GENERAL_PURPOSE_FLAGS
        if unsupported_local:
            raise MemberFormatError(
                "unsupported general-purpose flags "
                f"mask=0x{unsupported_local:04x}"
            )
        if local_flags & 0x1:
            raise MemberFormatError("encrypted local member")
        if local_method != info.compress_type:
            raise MemberFormatError("compression method mismatch")

        relevant_flags = 0x1 | 0x8 | 0x800 | _UNSUPPORTED_GENERAL_PURPOSE_FLAGS
        if info.compress_type == ZIP_LZMA:
            relevant_flags |= 0x2
        if (local_flags ^ info.flag_bits) & relevant_flags:
            raise MemberFormatError("local and central flags differ")

        local_filename_raw = read_exact(fp, filename_len)
        _decode_local_filename(zf, info, local_flags, local_filename_raw)

        data_offset = (
            info.header_offset + LOCAL_FIXED_SIZE + filename_len + extra_len
        )
        data_end = data_offset + info.compress_size
        archive_size = stream_size(fp)
        start_dir = getattr(zf, "start_dir", archive_size)
        member_end = getattr(info, "_end_offset", None)
        if not isinstance(member_end, int):
            raise MemberFormatError("missing member end boundary")
        data_ceiling = min(archive_size, start_dir, member_end)
        if data_offset < 0 or data_offset > member_end:
            raise MemberFormatError("compressed data offset")
        if data_end > member_end:
            raise MemberFormatError("overlapped entry")
        if data_end > data_ceiling:
            raise MemberFormatError("compressed data bounds")

        fp.seek(data_offset)
        compressed_remaining = info.compress_size

        if info.compress_type == ZIP_STORED:
            while compressed_remaining:
                chunk = read_exact(
                    fp,
                    min(READ_CHUNK, compressed_remaining),
                )
                compressed_remaining -= len(chunk)
                emit(chunk[:room()])

        elif info.compress_type == ZIP_DEFLATED:
            decoder = zlib.decompressobj(-15)
            while compressed_remaining:
                pending = read_exact(
                    fp,
                    min(READ_CHUNK, compressed_remaining),
                )
                compressed_remaining -= len(pending)
                while pending:
                    before = len(pending)
                    emit(
                        decoder.decompress(
                            pending,
                            max_length=room(),
                        )
                    )
                    pending = decoder.unconsumed_tail
                    if pending and len(pending) == before:
                        raise MemberFormatError(
                            "deflate made no progress"
                        )
            if not decoder.eof:
                emit(decoder.decompress(b"", max_length=room()))
            if not decoder.eof or decoder.unused_data:
                raise MemberFormatError("deflate stream boundary")

        elif info.compress_type == ZIP_BZIP2:
            decoder = bz2.BZ2Decompressor()
            while compressed_remaining:
                pending = read_exact(
                    fp,
                    min(READ_CHUNK, compressed_remaining),
                )
                compressed_remaining -= len(pending)
                while True:
                    piece = decoder.decompress(
                        pending,
                        max_length=room(),
                    )
                    emit(piece)
                    pending = b""
                    if decoder.eof:
                        if decoder.unused_data or compressed_remaining:
                            raise MemberFormatError(
                                "bzip2 trailing compressed data"
                            )
                        break
                    if decoder.needs_input:
                        break
                    if not piece:
                        raise MemberFormatError(
                            "bzip2 made no progress"
                        )
                if decoder.eof:
                    break
            if not decoder.eof:
                raise MemberFormatError("bzip2 stream boundary")

        elif info.compress_type == ZIP_LZMA:
            decoder = _BoundedZipLzmaDecompressor(
                args.max_lzma_dictionary_bytes
            )
            while compressed_remaining:
                pending = read_exact(
                    fp,
                    min(READ_CHUNK, compressed_remaining),
                )
                compressed_remaining -= len(pending)
                while True:
                    piece = decoder.decompress(
                        pending,
                        max_length=room(),
                    )
                    emit(piece)
                    pending = b""
                    if decoder.eof:
                        if decoder.unused_data or compressed_remaining:
                            raise MemberFormatError(
                                "LZMA trailing compressed data"
                            )
                        break
                    if decoder.needs_input:
                        break
                    if not piece:
                        raise MemberFormatError(
                            "LZMA made no progress"
                        )
                if decoder.eof:
                    break
            eos_marker_required = bool(local_flags & 0x2)
            if not decoder.eof and eos_marker_required:
                raise MemberFormatError("LZMA stream boundary")
        else:
            raise MemberFormatError(
                f"unsupported compression method {info.compress_type}"
            )

    except OutputLimitExceeded:
        state.actual_decompressed_bytes += produced
        mark_incomplete(
            state,
            f"{limit_reason} member={member_label} "
            f"observed_at_least={produced} "
            f"member_limit={member_limit} "
            f"total_limit={args.max_total_uncompressed_bytes}",
        )
        return None
    except (
        BadZipFile,
        EOFError,
        LargeZipFile,
        MemoryError,
        OSError,
        RuntimeError,
        UnicodeDecodeError,
        MemberFormatError,
        lzma.LZMAError,
        struct.error,
        zlib.error,
    ) as exc:
        state.actual_decompressed_bytes += produced
        mark_incomplete(
            state,
            f"read_error member={member_label} "
            f"error={type(exc).__name__}",
        )
        return None
    finally:
        try:
            fp.seek(original_position)
        except (OSError, ValueError):
            pass

    state.actual_decompressed_bytes += produced
    if produced != info.file_size:
        mark_incomplete(
            state,
            f"read_error member={member_label} error=size_mismatch "
            f"declared={info.file_size} actual={produced}",
        )
        return None
    if (crc & 0xFFFFFFFF) != info.CRC:
        mark_incomplete(
            state,
            f"read_error member={member_label} error=crc_mismatch",
        )
        return None
    try:
        return b"".join(parts)
    except MemoryError:
        mark_incomplete(
            state,
            f"read_error member={member_label} error=MemoryError",
        )
        return None
