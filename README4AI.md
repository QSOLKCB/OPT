# OPT — AI Usage Guide

This repository is a reusable optimization knowledge base for QSOL projects.

## Start here

1. Read `OPTIMIZATION-PROBLEM.md`.
2. Define `P = (X,F,f,d,C,B,S)` for the target: search space, feasible set, objective, direction, correctness/semantic contract, budget and stopping rule.
3. Identify the dominant bottleneck and choose the closest record from `CATALOG.md`.
4. Read that record and its source note completely before modifying another repository.
5. Preserve target semantics, invariants, determinism, evidence boundaries and public API unless the task explicitly changes them.
6. Benchmark before/after in the target environment and retain raw/repeated observations where practical.
7. Record adaptations rather than pretending source constants are universal.

## Problem classification

Before choosing an optimizer, classify:

- continuous / integer / categorical / conditional / mixed variables;
- local / global search;
- deterministic / noisy / stochastic objective;
- gradient available / derivative-free / black-box;
- cheap / expensive evaluations;
- bound/equality/inequality/semantic/resource constraints;
- sequential / synchronous batch / asynchronous execution;
- exact / approximation explicitly permitted.

## Decision map

- slow deterministic tests → `OPT-PY-001`
- proven-equivalent repeated computation → `OPT-INV-001`
- Lean dependency reconstruction → `OPT-LEAN-001`
- independent parallel work → `OPT-PAR-001`
- hot numerical/audio loop with slower control state → `OPT-DSP-001`
- unchanged-input pipeline reruns → `OPT-INC-001`
- identical simultaneous in-flight work → `OPT-COAL-001`
- sparse/dense integer-set mixture → `OPT-SET-001`
- hot global coordination point → `OPT-CONT-001`
- repeated per-consumer transformation → `OPT-FAN-001`
- expensive parameter tuning → `OPT-SEARCH-001`
- approximation explicitly allowed → `OPT-APPROX-001`
- large population filtered only after expensive work → `OPT-REDUCE-001`
- latency-critical path competes with optional work → `OPT-CRIT-001`
- gradual performance drift/regression → `OPT-BUDGET-001`
- combinatorial search with valid optimistic bounds → `OPT-PRUNE-001`
- hot deterministic batch underuses vector ISA → `OPT-SIMD-001`
- large AoS traversal needs cache-local bounded hot-field chunks → `OPT-SOA-001`
- repeated parallel runs pay thread/buffer startup or need explicit physical/logical worker policy → `OPT-POOL-001`
- several exact execution paths trade places across hosts/workloads → `OPT-AUTO-001`
- reuse cache repeatedly evicts expensive states before reuse → `OPT-CACHE-001`
- materialized pair products or equal-key groups exceed working memory → `OPT-STREAM-001`

## Important distinctions

- **cache/reuse**: completed result already exists;
- **coalescing**: result does not exist yet, but equivalent callers share one in-flight evaluation;
- **async search diversification**: independent workers should intentionally avoid evaluating the same pending region;
- **parallelism**: improves throughput only when resource contention and information dependencies allow it;
- **SIMD/autovectorization**: changes instruction-level execution of equivalent batch work; code-generation evidence is not itself an end-to-end speedup;
- **SoA tiling**: changes temporary data layout/working-set shape while preserving the logical source/output contract;
- **persistent pools**: change worker lifetime and lifecycle amortization, not the kernel's semantics;
- **host-auto promotion**: selects among already-correct paths using live calibration and a fail-closed oracle; it does not make one path universally best;
- **cache capacity**: controls how much correct reusable state survives until reuse; a larger cache is not automatically better and a fixed cap is not portable across working sets;
- **approximation**: a contract choice, never a hidden optimization.
- **streaming/replay**: retains less intermediate state while regenerating exact occurrences; it does not reduce required output count or authorize pruning.

## Status vocabulary

Post-v1 records must use one of these exact status categories. A semicolon may follow the category with a short evidence-boundary caveat; `scripts/check_catalog.py` validates the category before that semicolon.

- **Verified**: source project contains passing validation and measured/observed evidence.
- **Verified, environment-specific**: measured result is real but not a universal performance guarantee.
- **Implemented reference**: the mechanism exists in repository code, but no general speedup claim is made.
- **Implemented external reference**: the mechanism exists in an external donor; target transfer still requires local validation.
- **Implemented external pattern**: an external donor demonstrates the pattern, but this OPT record does not claim a target implementation.
- **Proposed / OPT synthesis**: architecture/design guidance only. Do not report it as achieved performance.
- **Source candidate**: material exists but has not been inspected sufficiently to promote claims.

The frozen v1 records retain their historical release wording and are exempt from post-v1 status normalization.

## Non-negotiable rules

- Never remove tests merely to make CI faster.
- Never weaken an assertion, tolerance, theorem target, receipt, trust boundary or validation rule without an explicit contract change.
- Never treat a cache hit as proof of a cold rebuild.
- Never equate requested workers with observed effective execution.
- Never copy historical worker counts, thresholds, search budgets, bit partitions, cache sizes, tile sizes, calibration repeats, promotion margins or approximation limits without target measurement.
- Never prune a search region unless the bound used for pruning is sound for the declared problem.
- Never call an approximate result exact.
- Never infer end-to-end speedup from vector instructions or an isolated kernel probe alone.
- Never publish a native/ISA-specialized path as universal if deployment compatibility is not guaranteed.
- Never treat process-wide RSS gathered across calibration as isolated selected-engine memory evidence.
- Never let an auto selector hide a parity failure by silently falling back; fail closed and preserve explicit canonical/manual control.
- Never optimize from stale workload assumptions when fresh measurements are available.
- Never copy a donor cache-capacity constant or "fix" eviction thrash with an unbounded cache; measure the active reuse working set and enforce the target resource envelope.
- `suxen.zip` remains unpromoted until inventoried and inspected.

## What to copy vs what to adapt

Copy the **structure**: equivalence gates, complete signature identity, coalescing ownership, partitioned coordination, density-adaptive representation, shared materialization, adaptive trial ledgers, explicit approximation envelopes, early reduction, critical-path classification, performance budgets, sound bounds, SIMD parity/codegen gates, bounded SoA working sets, persistent-worker lifecycle accounting, calibrated promotion with independent oracle verification, and cache policies tied to measured reuse working sets plus explicit resource budgets.

Adapt the **numbers and policies**: trial counts, worker caps, hashes, cache sizes, eviction/admission policy, reuse horizons, shard counts, bit splits, batch widths, tile sizes, domain-contraction rates, acquisition parameters, tolerances, error limits, benchmark thresholds, calibration sizes/repeats, promotion margins, topology policy and stopping budgets.

## Evidence expected in a new record

At minimum record:

- source identity and licensing/provenance boundary where relevant;
- the `OPTIMIZATION-PROBLEM.md` contract;
- baseline and optimized behavior;
- correctness/conformance gate;
- benchmark environment or an explicit statement that no benchmark exists;
- failure/rollback condition;
- whether the change affects latency, throughput, memory, I/O, CI time, quality or only architecture.

## Mathematical donor evidence

Read `EVIDENCE-SCOPE.md` and `sources/OPENAI-MATH.md` for mathematical donors. Record the cost model, assumptions, guarantee quantifiers, selected proof coverage, exact solution target, toolchain/dependencies, permitted axioms, certificate commands and independently executed replay status. File integrity, numerical replay, manuscript reasoning, Lean proof and target performance are separate evidence classes. The catalog structure checker does not establish their truth.

For `OPT-STREAM-001`, preserve indexed duplicates, complete tie products and lookahead-aware immutable replay state. Charge heap copies, replay, input snapshots and consumer storage; report a resource-stopped prefix as incomplete. The integer example is not the donor's randomized Subset Sum solver and imports no donor proof.

The separate `FilteredPairSums` API generates only pairs satisfying a declared residue condition, with the same actual-sum/index ordering. Use it only for that filtered contract or an independently sound necessary condition. Congruence is not exact equality; arbitrary bucket concatenation does not preserve global ordering. Include residue arithmetic and temporary bucket construction in time/peak-memory measurements, even when eligibility is sparse. The existing exact join remains unfiltered.

## Formalization boundary

`v1.0.0` contains five immutable Lean-formalized records. Post-v1 catalog records are not theorem-backed merely because they live in the same repository. See `FORMALIZATION.md`.
