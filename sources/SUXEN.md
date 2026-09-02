# `suxen.zip` Source Candidate

**Status:** Not yet promoted as optimization evidence.

Repository metadata currently records:

- path: `suxen.zip`;
- size: **6,216,669 bytes**;
- Git blob ID: `9c9518ccb7a24792e6ff8f389785f08e7222fb4c`;
- added in OPT commit `67272fa60dcccb00ac3c93caea4711b9d1e57893` on 2026-08-31.

## Why this file is not yet cited by an OPT record

The connected GitHub file interface can read repository text but does not expose the bytes of a multi-megabyte binary ZIP for direct connector-side unpacking. No optimization claim is inferred from filenames or container structure alone.

Review of the initial scanner established that the current outer archive's non-directory payloads are themselves ZIP archives. That is exactly why the inventory tool performs **bounded recursive ZIP inspection** rather than stopping at the outer suffix list.

The archive may be related to the architecture described in `power_module.md`, but that relationship is **not assumed** until the nested source inventory confirms it.

## Safe local inventory

From a normal repository checkout:

```bash
python3 scripts/inventory_zip.py suxen.zip
```

The scanner never extracts members. It:

- computes the outer archive SHA-256;
- lists member paths and compressed/uncompressed sizes at each inspected ZIP depth;
- recursively inspects nested ZIP payloads up to explicit depth/member/size budgets;
- **preflights each nested central directory and enforces the member cap before constructing a nested `ZipFile` / materializing its `ZipInfo` list**;
- normalizes both `/` and `\` separators before rejecting absolute and parent-traversal paths;
- scans a broad source/evidence suffix set including `.inc`, `.mjs`, `.csv`, `.tex`, Lean, shell, web and common language/config formats;
- also detects bounded UTF-8 text content for extensionless or unfamiliar textual members;
- reports recognized/detected text members above the configured scan-size cap as **incomplete** rather than silently skipping them;
- converts CRC/decompression/read failures into fail-closed `inventory_incomplete=read_error` results;
- escapes terminal control/format characters before printing untrusted text;
- prints a bounded context window **around the matched optimization keyword**, so a hit after column 400 is still visible;
- exits nonzero with `inventory_complete=false` if a depth, member, byte, encryption, read, nested-ZIP, unsupported nested ZIP or hit limit prevents a complete scan.

Default safety budgets are intentionally bounded and can be overridden explicitly:

```text
max nested depth: 4
max members across inspected archives: 20,000
max one nested ZIP payload: 64 MiB
max declared uncompressed bytes across inspected archives: 512 MiB
max one scanned text member: 2,000,000 bytes
max printed keyword hits: 500
```

A successful `hits=0` is meaningful only when the summary also says `inventory_complete=true`.

The repository CI runs both synthetic regression cases and a bounded inventory pass over the bundled `suxen.zip`. Once the relevant nested source files are read and interpreted, promote each reusable mechanism into its own `OPT-*` record with measured/proposed status and provenance.
