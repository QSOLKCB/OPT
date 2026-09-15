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
- F: Candidates that pass an independent correctness oracle, preserve workload-relevant calibration dimensions, expose truthful lifecycle/tuning/verification costs, keep canonical/manual control available, withhold externally visible effects until parity is established, and fail closed on mismatch.
- f: Total user-paid automatic-selection cost: calibration/tuning, candidate lifecycle terms, selected full-work execution, mandatory independent full-work oracle/verification, and any staging/commit overhead. If verification is explicitly out-of-band rather than paid per invocation, state and score that different scope explicitly.
- d: Minimize expected total user-paid full-work cost under one symmetric accounting boundary, but keep the canonical path on near ties or insufficient evidence.
- C: Exact selected/oracle parity before selected-path effects become externally visible, no silent fallback after a correctness mismatch, explicit requested/effective topology policy, accurate evidence scope and no universal claim from one host calibration.
- B: A bounded end-to-end selection budget covering the calibration candidate matrix/repetitions, selected full-work execution, mandatory full-work oracle/verification, and required staging/commit overhead without exceeding the declared workload/resource envelope.
- S: Select an optimized candidate only when its expected total paid invocation cost, including mandatory verification/staging where applicable, beats canonical by a predeclared material margin and the staged full-work result passes oracle verification; otherwise select canonical.
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

A selected execution must either be side-effect-free until verification or stage all externally observable outputs and state changes transactionally. The staged result may become visible only after full-work oracle parity succeeds; on mismatch the staged result is discarded. A system that cannot defer irreversible effects must validate before those effects or is not feasible for this pattern.

Manual/canonical execution surfaces remain available for audit and recovery. A selector must not hide parity failures by silently switching paths after a mismatch; correctness failure is evidence that the candidate or calibration is invalid.

## Optimization

1. Define a bounded set of already-validated candidate implementations.
2. Build calibration work that preserves the workload dimensions that materially affect ranking, rather than using an arbitrary tiny microbenchmark.
3. Measure each candidate under the same calibration boundary and record requested versus effective topology/configuration.
4. Project or extrapolate only under an explicit documented model. Account for startup, teardown, allocation/first-touch, tuning, and the mandatory full-work oracle/verification and staging costs whenever the user pays them for the requested invocation horizon. Compare candidates and canonical under the same cost boundary; do not promote using an asymmetric score that omits work required only by the optimized path.
5. Keep the canonical path when candidates are within a predeclared margin so noise and model error do not trigger unstable path switching; apply that margin to the total expected paid invocation cost rather than only the selected kernel.
6. Execute the selected full workload into side-effect-free or transactional staging, run or validate the independent full-work oracle within the declared budget, and publish selected-path effects only after exact parity succeeds. Discard staged results and fail closed on any mismatch.
7. Emit a receipt explaining candidate scores, lifecycle/verification accounting, selection reason, oracle result, staging/publish result and evidence scope.

The reusable mechanism is calibrated promotion with a symmetric cost boundary, uncertainty margin and correctness oracle, not a static table mapping CPU names to implementations.

## Before / after evidence

- Environment: GALAXY PR #14 adds dedicated host-auto coverage on Linux x86-64, Linux ARM64, macOS ARM64 and Windows x86-64.
- Workload/fixture: canonical, spawned SoA and persistent SoA candidate families calibrated against requested resident/frame shape.
- Cold baseline: canonical BAM-LUT execution retained as an explicit candidate and fallback/manual path.
- Warm/no-op baseline where relevant: persistent candidate scores include amortized startup and teardown over requested repetitions rather than comparing only steady-state dispatch.
- Small invalidation / partial-work case where relevant: calibration is bounded and may use less resident work while preserving requested frame depth/effective tile shape.
- Large invalidation / full-work case where relevant: selected path is verified on the full requested workload against the streaming canonical oracle; the donor records full-oracle timing separately, and a target must include that verification cost in the user-paid objective/budget whenever it is mandatory per invocation.
- Optimized: host/workload-specific candidate chosen only after calibration and margin gating.
- Speedup / memory / I/O / quality change: donor uses a 5% projected promotion margin; that number is source-specific and is not promoted as a universal OPT default.
- Variance / repetitions / raw samples: donor uses three calibration repeats and versioned receipts; targets must choose their own statistically defensible budget and margin.

## Validation

- Verify every calibration candidate against an independent oracle before it can compete.
- Preserve workload dimensions known to affect ranking, including depth, effective tile shape and topology where relevant.
- Test projection/scoring identities and lifecycle accounting, including the selected full run, mandatory full-work oracle/verification, staging and publish costs whenever those are paid by the invocation.
- Compare the promoted path's total paid cost against canonical under the same scope; test a case where a fast selected kernel is correctly rejected because verification overhead erases the advantage.
- Include topology-detection and tuning time in the declared selection overhead when users pay that cost.
- Verify the selected full workload again against the oracle before making staged effects visible.
- Test side-effect-free and transactional staging, intentional parity failures, and prove that mismatching staged output/state is discarded rather than exposed.
- Test near ties, canonical wins and optimized wins.
- Scope RSS/memory evidence correctly; a process-wide high-water mark covering calibration plus selection cannot be presented as isolated selected-engine memory.
- Keep receipts versioned so future policy changes are distinguishable from earlier selection behavior.

## Target-repo adaptation

Re-profile candidate families, calibration size, repetitions, projection model, promotion margin, lifecycle amortization, full-work oracle cost, staging/publish strategy, workload-shape dimensions, topology policy and recalibration cadence. Do not copy GALAXY's 65,536-particle base, tile list, three repeats or 5% margin without target evidence. Prefer direct full-work measurement when calibration cost is affordable or projection error is material. If the target has irreversible externally visible effects, establish a pre-effect oracle/validation boundary before adopting automatic promotion.

## Failure modes

- Calibration shape does not preserve the feature that determines real-work ranking.
- Runtime scaling is nonlinear, making the projection misleading.
- Selection or mandatory verification overhead exceeds the saved runtime on short-lived workloads.
- The scoring boundary omits oracle/staging work paid only by promoted candidates and creates a false win.
- Selected-path output or state changes escape before oracle parity is known.
- Workload phases change after calibration and invalidate the choice.
- Near-tie noise causes path thrashing because the margin is too small.
- The oracle shares the same defect or optimized primitive as the candidate and is not genuinely independent.
- Process-wide memory evidence is mislabelled as per-candidate memory.
- Static host/model assumptions replace live evidence and age badly.

## Rollback trigger

Immediately reject the selected path on full-work oracle mismatch and discard all uncommitted staged results. Treat any already-exposed mismatching result as a contract failure. Revert automatic promotion to canonical/manual mode when the complete selection+execution+verification budget is exceeded, lifecycle-adjusted total paid benefit disappears, calibration becomes unstable or unrepresentative, workload drift changes rankings, or selector/verification overhead materially outweighs expected savings. Recalibrate rather than preserving a stale winner.

## Composition notes

This record selects among mechanisms such as `OPT-SOA-001`, `OPT-POOL-001`, `OPT-SIMD-001` and canonical paths after those mechanisms have their own correctness gates. It complements `OPT-BUDGET-001`: regression budgets can detect when a formerly promoted path stops meeting its measured advantage.