# `suxen.zip` Source Candidate

**Status:** Not yet promoted as optimization evidence.

Repository metadata currently records:

- path: `suxen.zip`;
- size: **6,216,669 bytes**;
- Git blob ID: `9c9518ccb7a24792e6ff8f389785f08e7222fb4c`;
- added in OPT commit `67272fa60dcccb00ac3c93caea4711b9d1e57893` on 2026-08-31.

## Why this file is not yet cited by an OPT record

The connected GitHub file interface can read repository text but does not expose the bytes of a multi-megabyte binary ZIP for unpacking. No optimization claim is inferred from filenames or container structure alone.

Review of the initial scanner established that the current outer archive's non-directory payloads are themselves ZIP archives. That is exactly why the inventory tool now performs **bounded recursive ZIP inspection** rather than stopping at the outer suffix list.

The archive may be related to the architecture described in `power_module.md`, but that relationship is **not assumed** until the nested source inventory confirms it.

## Complete local inventory

Use the same expanded bounds as CI for this particular bundled archive and redirect the 1,000-plus matching lines to a file:

```bash
python3 scripts/inventory_zip.py suxen.zip \
  --max-depth=8 \
  --max-members=100000 \
  --max-nested-zip-bytes=134217728 \
  --max-total-uncompressed-bytes=1073741824 \
  --max-central-directory-bytes=134217728 \
  --max-compressed-member-bytes=134217728 \
  --max-text-bytes=16777216 \
  --max-hits=100000 \
  > suxen-inventory.txt
```

Then confirm the terminal summary:

```bash
grep -E '^(inventory_incomplete=|invalid_zip=|== summary ==|archives_scanned=|nested_archives=|members_seen=|text_members_scanned=|declared_uncompressed_bytes=|actual_decompressed_bytes=|hits=|inventory_complete=)' suxen-inventory.txt
```

The scanner never extracts members. It:

- computes the outer archive SHA-256;
- preflights outer and nested central directories before constructing `ZipFile` objects;
- limits central-directory bytes and rejects unsupported ZIP64/multi-disk structures;
- validates flagged UTF-8 filenames before the standard library decodes them;
- recognizes ordinary and self-extracting ZIP payloads even when their filename does not end in `.zip`;
- lists member paths and compressed/uncompressed sizes at each inspected ZIP depth;
- recursively inspects nested ZIP payloads up to explicit depth/member/size budgets;
- normalizes both `/` and `\` separators before rejecting absolute and parent-traversal paths;
- incrementally decompresses stored, DEFLATE, BZIP2 and LZMA members under actual-output limits;
- verifies actual output size and CRC instead of trusting declared `file_size` alone;
- reads known and content-detected text/source members directly from ZIP containers;
- escapes terminal control/format characters before printing untrusted text;
- prints bounded context around optimization-keyword hits such as SIMD, cache, parallel, sparse, vectorized, zero-copy and lock-free;
- exits nonzero with `inventory_complete=false` if any safety budget or validation gate prevents a complete scan.

Default safety budgets are intentionally conservative and can be overridden explicitly:

```text
max nested depth: 4
max members across inspected archives: 20,000
max one nested ZIP payload: 64 MiB
max declared and actual uncompressed bytes: 512 MiB
max central directory: 64 MiB
max compressed bytes for one member: 128 MiB
max one scanned text member: 2,000,000 bytes
max printed keyword hits: 500 (use 0 for no hit cap)
```

A successful `hits=0` is meaningful only when the summary also says `inventory_complete=true`.

Once the relevant nested source files are read, promote each reusable mechanism into its own `OPT-*` record with measured/proposed status and provenance.
