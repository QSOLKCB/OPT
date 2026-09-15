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

## Important distinctions

- **cache/reuse**: completed result already exists;
- **coalescing**: result does not exist yet, but equivalent callers share one in-flight evaluation;
- **async search diversification**: independent workers should intentionally avoid evaluating the same pending region;
- **parallelism**: improves throughput only when resource contention and information dependencies allow it;
- **approximation**: a contract choice, never a hidden optimization.

## Status vocabulary

- **Verified**: source project contains passing validation and measured/observed evidence.
- **Verified, environment-specific**: measured result is real but not a universal performance guarantee.
- **Implemented reference**: the mechanism exists in code, but no general speedup claim is made.
- **Implemented external reference/pattern**: mechanism exists in an external donor; target transfer still requires local validation.
- **Proposed / OPT synthesis**: architecture/design guidance only. Do not report it as achieved performance.
- **Source candidate**: material exists but has not been inspected sufficiently to promote claims.

## Non-negotiable rules

- Never remove tests merely to make CI faster.
- Never weaken an assertion, tolerance, theorem target, receipt, trust boundary or validation rule without an explicit contract change.
- Never treat a cache hit as proof of a cold rebuild.
- Never equate requested workers with observed effective execution.
- Never copy historical worker counts, thresholds, search budgets, bit partitions, cache sizes or approximation limits without target measurement.
- Never prune a search region unless the bound used for pruning is sound for the declared problem.
- Never call an approximate result exact.
- Never optimize from stale workload assumptions when fresh measurements are available.
- `suxen.zip` remains unpromoted until inventoried and inspected.

## What to copy vs what to adapt

Copy the **structure**: equivalence gates, complete signature identity, coalescing ownership, partitioned coordination, density-adaptive representation, shared materialization, adaptive trial ledgers, explicit approximation envelopes, early reduction, critical-path classification, performance budgets and sound bounds.

Adapt the **numbers and policies**: trial counts, worker caps, hashes, cache sizes, shard counts, bit splits, batch widths, domain-contraction rates, acquisition parameters, tolerances, error limits, benchmark thresholds and stopping budgets.

## Evidence expected in a new record

At minimum record:

- source identity and licensing/provenance boundary where relevant;
- the `OPTIMIZATION-PROBLEM.md` contract;
- baseline and optimized behavior;
- correctness/conformance gate;
- benchmark environment or an explicit statement that no benchmark exists;
- failure/rollback condition;
- whether the change affects latency, throughput, memory, I/O, CI time, quality or only architecture.

## Formalization boundary

`v1.0.0` contains five immutable Lean-formalized records. Post-v1 catalog records are not theorem-backed merely because they live in the same repository. See `FORMALIZATION.md`.
