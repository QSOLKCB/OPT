# `suxen.zip` Source Candidate

**Status:** Not yet promoted as optimization evidence.

Repository metadata currently records:

- path: `suxen.zip`;
- size: **6,216,669 bytes**;
- Git blob ID: `9c9518ccb7a24792e6ff8f389785f08e7222fb4c`;
- added in OPT commit `67272fa60dcccb00ac3c93caea4711b9d1e57893` on 2026-08-31.

## Why this file is not yet cited by an OPT record

The connected GitHub file interface can read repository text but does not expose the bytes of a multi-megabyte binary ZIP for unpacking. A temporary branch workflow was attempted during catalog construction, but app-authored pushes did not trigger an Actions run, so no archive contents were fabricated or inferred.

The archive may be related to the architecture described in `power_module.md`, but that relationship is **not assumed** until the ZIP inventory confirms it.

## Safe local inventory

From a normal repository checkout:

```bash
python3 scripts/inventory_zip.py suxen.zip
```

The script:

- computes the archive SHA-256;
- lists member paths and compressed/uncompressed sizes;
- rejects suspicious absolute/parent-traversal paths;
- reads likely text/source members directly from the ZIP without extracting them;
- prints lines containing optimization keywords such as SIMD, cache, parallel, sparse, vectorized, zero-copy and lock-free.

Once the relevant source files are read, promote each reusable mechanism into its own `OPT-*` record with measured/proposed status and provenance.
