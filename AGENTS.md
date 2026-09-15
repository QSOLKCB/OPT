# AGENTS.md

Machine-facing rules for agents using this repository.

1. Read `README4AI.md`, `OPTIMIZATION-PROBLEM.md`, and `CATALOG.md` before applying an optimization elsewhere.
2. Define the target optimization contract before selecting a mechanism: search space, feasible set, objective/direction, correctness constraints, evaluation budget and stopping rule.
3. Treat optimization records as patterns, not universal parameter sets.
4. Preserve reference semantics and add/retain conformance tests for optimized paths.
5. Prefer deterministic, bounded reuse over opaque caches.
6. If equivalence enables reuse, encode the equivalence as a named invariant and test it directly.
7. For incremental reuse, bind the complete effective input identity and persist a new reusable state only after successful completion.
8. For coalescing, merge only semantically equivalent in-flight work; define cancellation/error semantics explicitly.
9. For Lean caches, distinguish verified reuse from cold reconstruction in implementation and claims.
10. For parallel work, retain deterministic output ordering where required and verify scalar/parallel equivalence. Measure effective concurrency rather than assuming requested workers ran concurrently.
11. For adaptive search, preserve the trial ledger and evaluation budget. Remember that excessive parallel batch width can reduce information efficiency.
12. For approximation, state an explicit error/degradation contract and keep an exact/reference path where practical. Never silently weaken exact semantics.
13. For pruning, test bound soundness independently; never prune on a heuristic presented as proof.
14. For critical-path/speculative work, ensure speculation cannot expose side effects before commitment and does not starve the actual critical path.
15. For performance budgets, characterize benchmark noise/environment before enforcing a threshold.
16. For real-time/DSP work, separate slow control work from hot sample/block work when semantics allow it; avoid allocations and synchronization on the hot path.
17. For SIMD/native specialization, require reference parity plus actual code-generation evidence and repeated target-host measurement. Never infer end-to-end speedup merely from wider instructions or an isolated probe.
18. For SoA/tiling, bound temporary storage per worker, prove packed-field and reduction equivalence, and re-profile tile sizes on the target cache/memory hierarchy rather than copying donor values.
19. For persistent worker pools, test repeated-dispatch state isolation and account for startup/teardown amortization. Physical/logical worker selection is not evidence of CPU affinity or NUMA placement.
20. For automatic execution-path promotion, calibrate only already-correct candidates on workload-shaped samples, include lifecycle/tuning costs, require a material promotion margin, preserve canonical/manual control, and fail closed against an independent oracle on parity mismatch.
21. `power_module.md` contains both implemented ideas and aspirational performance language. Check corresponding code/evidence before promoting a claim.
22. `suxen.zip` is a source candidate, not validated evidence. Inventory and read relevant source before extracting optimization claims.
23. The three pinned v1 Lean model files are immutable historical formalization. New records do not become formally proved by association; version future formal modules separately.
24. New post-v1 records must state status, source identity, optimization problem contract, preserved contract, validation, limitations and rollback conditions.
25. Run `python3 scripts/check_catalog.py` after catalog changes.
