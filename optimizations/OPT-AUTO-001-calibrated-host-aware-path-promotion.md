# OPT-AUTO-001 — Calibrated host-aware path promotion

**Status:** Implemented external reference; GALAXY merges a fail-closed calibrated selector, while calibration constants and projection accuracy remain host/workload-specific.  
**Domains:** multi-path CPU runtimes, heterogeneous execution strategies, production tuning, adaptive dispatch

## Source evidence

- Repository: `QSOLKCB/GALAXY`
- PR: https://github.com/QSOLKCB/GALAXY/pull/14
- Merge commit: `b2e860309a04d7591c86f71d2b4ab1e5eec4c4d7`
- Source note: `sources/GALAXY-CPU.md`
- Licensing boundary: Apache-2.0 donor; record promotes policy structure, not target-specific constants.

## Problem

Several semantically equivalent execution paths exist, but the fastest path depends on CPU topology, workload shape, tile size, startup/teardown cost and repetition count. A universal hardware/model table becomes stale, while always choosing the apparently fastest microbenchmark can regress real workloads or violate correctness.

## Optimization problem contract

- X: A bounded candidate set of semantically equivalent execution paths plus target-specific calibration shape, scoring policy and promotion margin.
- F: Candidates that pass an independent correctness oracle, preserve workload-relevant calibration dimensions, expose truthful lifecycle/tuning costs, keep canonical/manual control available and fail closed on mismatch.
- f: Projected or directly measured full-work runtime including lifecycle amortization and tuning overhead, with supporting resource/evidence scope.
- d: Minimize expected full-work runtime, but keep the canonical path on near ties or insufficient evidence.
- C: Exact selected/oracle parity, no silent fallback after a correctness mismatch, explicit requested/effective topology policy, accurate evidence scope and no universal claim from one host calibration.
- B: A bounded calibration candidate matrix and repetition budget that never exceeds the requested workload/resource envelope.
- S: Select an optimized candidate only when it beats canonical by a predeclared material margin and then passes full-work oracle verification; otherwise select canonical.
- Variables: categorical, integer and conditional
- Search scope: global
- Objective behavior: noisy
- Information: black-box
- Evaluation cost: expensive
- Constraints: semantic and resource
- Parallelism: sequential
- Exactness: exact

## Preserved contract

Automatic selection may change which implementation executes, but not the externally declared result. Every candidate admitted to calibration and the final selected full workload must match an implementation-independent or sufficiently independent oracle under the target's exactness contract.

Manual/canonical execution surfaces remain available for audit and recovery. A selector must not hide parity failures by silently switching paths after a mismatch; correctness failure is evidence that the candidate or calibration is invalid.

## Optimization

1. Define a bounded set of already-validated candidate implementations.
2. Build calibration work that preserves the workload dimensions that materially affect ranking, rather than using an arbitrary tiny microbenchmark.
3. Measure each candidate under the same calibration boundary and record requested versus effective topology/configuration.
4. Project or extrapolate only under an explicit documented model; include startup, teardown, allocation/first-touch and other lifecycle terms when they affect the requested repetition horizon.
5. Keep the canonical path when candidates are within a predeclared margin so noise and model error do not trigger unstable path switching.
6. After selection, run or validate the full requested workload against an independent oracle and fail closed on any mismatch.
7. Emit a receipt explaining candidate scores, lifecycle accounting, selection reason, oracle result and evidence scope.

The reusable mechanism is calibrated promotion with an uncertainty margin and correctness oracle, not a static table mapping CPU names to implementations.

## Before / after evidence

- Environment: GALAXY PR #14 adds dedicated host-auto coverage on Linux x86-64, Linux ARM64, macOS ARM64 and Windows x86-64.
- Workload/fixture: canonical, spawned SoA and persistent SoA candidate families calibrated against requested resident/frame shape.
- Cold baseline: canonical BAM-LUT execution retained as an explicit candidate and fallback/manual path.
- Warm/no-op baseline where relevant: persistent candidate scores include amortized startup and teardown over requested repetitions rather than comparing only steady-state dispatch.
- Small invalidation / partial-work case where relevant: calibration is bounded and may use less resident work while preserving requested frame depth/effective tile shape.
- Large invalidation / full-work case where relevant: selected path is verified on the full requested workload against the streaming canonical oracle.
- Optimized: host/workload-specific candidate chosen only after calibration and margin gating.
- Speedup / memory / I/O / quality change: donor uses a 5% projected promotion margin; that number is source-specific and is not promoted as a universal OPT default.
- Variance / repetitions / raw samples: donor uses three calibration repeats and versioned receipts; targets must choose their own statistically defensible budget and margin.

## Validation

- Verify every calibration candidate against an independent oracle before it can compete.
- Preserve workload dimensions known to affect ranking, including depth, effective tile shape and topology where relevant.
- Test projection/scoring identities and lifecycle accounting.
- Include topology-detection and tuning time in the declared selection overhead when users pay that cost.
- Verify the selected full workload again against the oracle.
- Test near ties, canonical wins, optimized wins and intentional parity failures.
- Scope RSS/memory evidence correctly; a process-wide high-water mark covering calibration plus selection cannot be presented as isolated selected-engine memory.
- Keep receipts versioned so future policy changes are distinguishable from earlier selection behavior.

## Target-repo adaptation

Re-profile candidate families, calibration size, repetitions, projection model, promotion margin, lifecycle amortization, workload-shape dimensions, topology policy and recalibration cadence. Do not copy GALAXY's 65,536-particle base, tile list, three repeats or 5% margin without target evidence. Prefer direct full-work measurement when calibration cost is affordable or projection error is material.

## Failure modes

- Calibration shape does not preserve the feature that determines real-work ranking.
- Runtime scaling is nonlinear, making the projection misleading.
- Selection overhead exceeds the saved runtime on short-lived workloads.
- Workload phases change after calibration and invalidate the choice.
- Near-tie noise causes path thrashing because the margin is too small.
- The oracle shares the same defect or optimized primitive as the candidate and is not genuinely independent.
- Process-wide memory evidence is mislabelled as per-candidate memory.
- Static host/model assumptions replace live evidence and age badly.

## Rollback trigger

Immediately reject the selected path on full-work oracle mismatch. Revert automatic promotion to canonical/manual mode when lifecycle-adjusted benefit disappears, calibration becomes unstable or unrepresentative, workload drift changes rankings, or selector overhead materially outweighs expected savings. Recalibrate rather than preserving a stale winner.

## Composition notes

This record selects among mechanisms such as `OPT-SOA-001`, `OPT-POOL-001`, `OPT-SIMD-001` and canonical paths after those mechanisms have their own correctness gates. It complements `OPT-BUDGET-001`: regression budgets can detect when a formerly promoted path stops meeting its measured advantage.