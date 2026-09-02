# OPT-LEAN-001 — Trust-Preserving Lean Dependency Reuse

**Status:** Verified on QSOL-GEO-REASON PR #3 source lane  
**Domains:** Lean 4, mathlib, Lake, GitHub Actions, formal-method CI

## Source evidence

- PR: https://github.com/QSOLKCB/QSOL-GEO-REASON/pull/3
- Cache policy: https://github.com/QSOLKCB/QSOL-GEO-REASON/blob/lean-phase1-v0.1.0/LEAN-CACHE-POLICY.md
- Current formalization line pins Lean v4.33.1 and a specific mathlib commit.

## Problem

A formal project can be tiny while its imported dependency closure is enormous. Rebuilding pinned mathlib dependencies from source on every pull request gives strong provenance but can dominate CI wall time.

Blindly restoring `.olean` files is faster but weakens the evidence claim if the restored proof objects are not bound to the exact toolchain and source graph.

## Reusable two-lane design

### Lane A — verified reuse for routine PRs

1. Pin and verify the Lean toolchain bytes/version.
2. Bind dependency source-cache identity to platform, toolchain identity, dependency declaration and frozen `lake-manifest.json` identity.
3. Restore dependency source state only under that exact identity.
4. Purge generated package `.lake` state before source verification.
5. Verify dependency source revisions and tracked bytes/modes against their commit trees; reject replacement/graft/index tricks and source-shadowing material.
6. Restore compiled dependency artifacts under a separately derived build-cache identity.
7. Verify the build tree against a **reviewed canonical per-file SHA-256 receipt** plus expected artifact count. A compact secondary fold may be used for regression detection but is not authority.
8. Delete the current project's own build output.
9. Rebuild the complete project from the current PR source.
10. Rerun source hygiene, sorry/axiom checks and compiled theorem audits.

### Lane B — cold trust for release-grade claims

A manual/release lane restores **no dependency cache**. It resolves the pinned source graph, purges generated state, verifies source identity, rebuilds dependencies from source, rebuilds the project and reruns the same proof audits.

Only this lane may claim that the dependency graph was reconstructed from pinned source **on that exact run**.

## Parallelism

The source project bounded Lean workers to available CPUs with an upper cap of four and required at least two CPUs for the multicore lane. Treat that cap as environment-specific: remeasure memory pressure and build throughput on a different runner class.

## Evidence snapshot

The QSOL-GEO-REASON cache policy records its first audited dependency build at:

- cold dependency source build wall time: **2501.52 s**;
- Lean threads: **4**;
- cached dependency artifact records: **37,312**.

A later verified-cache PR run records the **current GeoReason project rebuild** at **8.47 s** on four Lean threads after source/build cache verification.

These are different scopes. The record intentionally does **not** divide 2501.52 by 8.47 and call that a universal speedup.

## Generic cache-key ingredients

A target project should normally bind at least:

```text
schema-version
runner OS + architecture
Lean distribution identity
lean-toolchain identity
lakefile/dependency declaration identity
lake-manifest identity
```

Build-artifact reuse should additionally be anchored to a reviewed artifact receipt or equally strong reproducible identity appropriate to the project.

## Anti-patterns

- `actions/cache` hit ⇒ “trusted proof objects” without content verification.
- Using a receipt stored only inside the cache to authenticate that same cache.
- Reusing the target project's own stale `.lake/build` instead of rebuilding current source.
- Calling a verified-cache run a “cold build.”
- Letting dependency update hooks smuggle generated compiled state into a source cache.
- Treating a fast XOR/checksum fold as cryptographic authority.

## Rollback trigger

On any cache identity, source-tree, canonical receipt, artifact-count or proof-audit mismatch, fail closed and use the configured cold reconstruction path rather than silently accepting the cache.
