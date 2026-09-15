# OPT-CRIT-001 — Critical-path prioritization

**Status:** Proposed / OPT synthesis; target validation required  
**Domains:** UI, web, games, build systems, model/data loading, interactive pipelines

## Source evidence

- `davidsonfellipe/awesome-wpo` inspected at `84f32948a6298456d6a94cff64551f39f2666e6f`
- resource-hint, lazy-loading and prefetch references catalogued upstream
- `sources/WPO.md`

## Problem

Non-critical work competes with the dependency chain that determines user-visible or pipeline latency.

## Optimization problem contract

- X: target-supported task-priority, prefetch/precompute, lazy/deferred-work, speculation, speculative-input identity, mutation-control, and commitment policies
- F: policies that preserve all semantic deadlines, avoid externally visible speculative side effects before commitment, commit speculative results only from one stable effective-input generation, and satisfy starvation/resource constraints
- f: measured end-to-end latency of the declared critical dependency path, including resource pressure introduced by speculation/deferment
- d: minimize
- C: critical outputs and semantic deadlines are preserved; speculative work is safely discardable; any speculative result is bound to a complete immutable snapshot or full-duration mutation witness, and validation of that witness is linearized with commitment so intervening or final-window A→B→A/input changes cannot be erased before visibility; deferred work completes before it becomes semantically required
- B: target-specific trace/benchmark budget covering cold/warm, hit/miss, wrong-speculation, stale-speculation, and change/revert cases; no portable prediction horizon is supplied here
- S: stop when the declared budget is exhausted or a validated policy materially reduces critical-path latency without violating C
- Variables: categorical / conditional / mixed priority, deferment, prefetch, and speculation policies
- Search scope: local critical-path policy tuning
- Objective behavior: noisy under realistic workload timing; semantic identity/deadline checks are deterministic
- Information: derivative-free / black-box latency measurements
- Evaluation cost: moderate to expensive end-to-end tracing/benchmarking
- Constraints: semantic deadlines, starvation, side effects, input identity/mutation freshness, commitment linearizability, memory/CPU/I/O, and target resource constraints
- Parallelism: asynchronous / concurrent execution is common
- Exactness: exact target semantics; speculative work may be discarded but not committed stale

## Preserved contract

Deferred work must still complete before its semantic deadline. Speculative work must be discardable and must not create externally visible side effects before commitment. A speculative result may be committed/delivered only if it was produced from one coherent effective-input generation equivalent to the non-speculative reference path; endpoint equality after an intervening mutation is not sufficient, and a successful freshness check is not sufficient unless the checked identity remains authoritative through the commit that makes the result visible.

## Optimization

Execute critical dependencies first; prefetch/precompute likely-soon work only when probability and spare resources justify it; lazily defer non-critical work; avoid work with no demonstrated demand.

Bind every speculative/precomputed result to a complete effective-input identity for the **full speculation-to-commit interval**. Prefer speculation against an immutable snapshot/version. If snapshots are unavailable, use a full-duration mutation/read lock or capture a monotonically increasing, non-reusable version/epoch for every mutable effective input. Every relevant mutation must advance its witness, including A→B→A changes that restore original bytes. A commit-time hash/identity comparison may supplement the mutation witness but must not be the sole freshness proof.

Freshness validation and commitment must be **one linearizable operation**. For lock-based targets, hold the mutation/read lock through the exact commit/publication/delivery transition that makes the speculative result externally visible. For epoch/version-based targets, use an atomic compare-and-commit/conditional transaction that verifies the complete coherent epoch vector is still the witnessed vector and, only if that comparison succeeds in the same atomic boundary, publishes the result. A separate `check epochs; later publish` sequence is not sufficient. If the compare-and-commit loses a race, discard the speculative result and execute/recompute from the current reference identity. Any lock violation, epoch change, incoherent witness, or untrackable mutable input likewise forces discard/recompute.

Commitment is the semantic boundary: no stale speculative result may become externally visible merely because the speculation itself had no side effects.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No target critical-path profile has been established here.
- Optimized: No target prioritization/prefetch policy has been benchmarked here.
- Speedup / memory reduction: No transferable claim; upstream WPO material supplies patterns and measurement guidance.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Trace the true dependency path and measure end-to-end latency, not only individual task duration. Test cold/warm, cache-hit/miss and wrong-speculation cases. Explicitly test semantic deadlines, starvation, cancellation, and that speculative work cannot expose side effects before commitment.

Add stale-speculation fixtures with explicit **A→B→A** races. Start speculation from identity A, mutate the effective inputs to B while speculation reads/runs, then restore original bytes before demand/commitment. For snapshot-based targets, prove speculation consumed only immutable A. For lock-based targets, prove the mutation cannot interleave. For epoch/version-based targets, prove every mutation increments the monotonic witness and that the final witness exposes the intervening change even though endpoint content equals A. Also test delayed speculative completion, version rollback, and concurrent config/schema changes. Compare every committed speculative result against the non-speculative reference path for the exact committed identity.

Add a **final validation-to-commit race**. Pause immediately after the last ordinary witness comparison but before the result would become visible, then mutate an effective input. For lock-based designs, prove the mutation is blocked until after commitment. For epoch/version designs, prove the atomic compare-and-commit rejects the stale speculative result rather than publishing it. Repeat with A→B→A and multi-input epoch-vector changes. No fixture may pass by doing an ordinary comparison followed by a separate publication step.

## Target-repo adaptation

Criticality and prediction horizons are workload-specific. Re-profile after topology or user-flow changes. Define the complete effective-input identity for each speculative result and choose immutable snapshots, full-duration mutation locks, or monotonic epochs that record every intervening change. Define the linearization boundary that couples freshness validation to external commitment: lock-through-commit or atomic compare-and-commit. Specify exactly when a stale speculative result is discarded. Do not rely on commit-time endpoint revalidation alone, or on check-then-publish epoch validation, to establish freshness.

## Failure modes

Speculation steals resources from critical work, lazy work causes later latency cliffs, priorities become stale, deferred tasks starve, semantic deadlines are missed, speculative side effects escape before commitment, A→B→A mutations can fool endpoint-only freshness checks, non-monotonic/reused epochs can erase intervening changes, a check-then-publish window can expose stale speculation after a successful freshness check, or stale speculative output is committed after its effective inputs changed.

## Rollback trigger

Immediately disable/revert the policy on any violation of C, including a required task missing its semantic deadline, speculative work exposing an externally visible side effect before commitment, a speculative result being committed/delivered without an immutable snapshot/lock/monotonic mutation witness proving one coherent effective-input generation, or any test showing freshness validation can be separated from commitment so a mutation can win in between. Also disable it if critical-path latency or resource pressure worsens materially.
