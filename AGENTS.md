# AGENTS.md

Machine-facing rules for agents using this repository.

1. Read `README4AI.md` and `CATALOG.md` before applying an optimization elsewhere.
2. Treat optimization records as patterns, not universal parameter sets.
3. Preserve reference semantics and add/retain conformance tests for optimized paths.
4. Prefer deterministic, bounded reuse over opaque caches.
5. If equivalence enables reuse, encode the equivalence as a named invariant and test it directly.
6. For Lean caches, distinguish verified reuse from cold reconstruction in both implementation and claims.
7. For parallel work, retain deterministic output ordering and verify scalar/parallel equivalence.
8. For real-time/DSP work, separate slow control work from hot sample/block work when semantics allow it; avoid allocations and synchronization on the hot path.
9. `power_module.md` contains both implemented ideas and aspirational performance language. Check the corresponding code/evidence before promoting a claim.
10. `suxen.zip` is a source candidate, not validated evidence. Use `scripts/inventory_zip.py` in an environment with the archive bytes available before extracting optimization claims.
11. New records must state status, source identity, preserved contract, evidence, limitations, and rollback conditions.
