# OPT-REDUCE-001 — Early working-set reduction

**Status:** Implemented external pattern; broadly applicable mechanism  
**Domains:** databases, graphs, simulation, DSP, rendering, data pipelines

## Source evidence

- https://jazco.dev/2023/08/10/query-optimization/
- supporting sparse-evaluation pattern in `OPT-DSP-001`

## Problem

An expensive operation is applied to a large population even though only a small subset can affect the final result.

## Optimization problem contract

- X: semantically legal placements and implementations of filtering, culling, limiting, candidate selection, or other working-set reductions in the target pipeline
- F: placements that preserve every candidate and every contractually observable behavior required by the reference pipeline—including output, ordering/tie/join semantics, errors/exceptions, writes, mutations, auditing/telemetry, and other side effects—or that move only across stages proven pure with respect to those effects
- f: measured end-to-end pipeline cost and cardinality presented to the expensive stage
- d: minimize under the target's predeclared objective ordering
- C: the reordered/reduced pipeline is semantically equivalent to the reference for all declared outputs **and observable effects**; an effectful stage may be bypassed for discarded candidates only when those effects/errors are explicitly proven irrelevant by the target contract
- B: target-specific benchmark budget over representative and adversarial selectivity distributions; no portable selectivity threshold is supplied here
- S: stop when the declared budget is exhausted or a validated early-reduction placement materially lowers total cost without violating C

## Preserved contract

Moving a reduction earlier is valid only across a pure stage or when the earlier placement preserves the full observable contract of the reference pipeline. That contract includes final values plus ordering/top-k/tie/join semantics, exceptions/error checks, writes/mutations, audit events, metrics or other externally visible side effects where they are significant.

## Optimization

Push selective operations toward the input boundary only when doing so is semantics-preserving: filter before a pure expensive join/transform, cull before pure rendering work, select candidate roots before pure DSP calculation, or eliminate simulations proven unable to affect any required result/effect. If the expensive stage is effectful, either keep the effectful portion on every candidate that would have reached it in the reference path, split the stage into a pure expensive computation and a required effect layer, or prove those skipped effects/errors are outside the declared contract. Do not optimize away observable behavior merely because the final data rows match.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; external query observations and existing sparse-evaluation patterns are source evidence only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Differential-test reordered pipelines against the reference, with emphasis on ties, null/missing values, boundary ordering and rare candidates. Also compare observable side effects and error behavior: writes/mutations, audit/log/metric events, callbacks, exception/error surfaces and their relevant ordering/counts. Include a deliberately effectful fixture to prove the optimization is rejected or preserves the effects, and a pure-stage fixture where early reduction is admissible.

## Target-repo adaptation

Measure selectivity and reduction cost. Classify the expensive stage as pure or effectful before reordering; inventory contractually significant side effects/errors and define how each is preserved. A cheap filter with low selectivity may simply add another pass.

## Failure modes

Illegal predicate reordering, changed top-k semantics, underestimated filtering cost, loss of vectorization, duplicated scans, skipped writes/audit events/mutations, changed exceptions or validation failures, and reordered side effects can all make an apparently equivalent final result semantically wrong.

## Rollback trigger

Immediately revert if any output, ordering, error, or contractually significant side effect differs from the reference path. Also revert if total measured cost does not fall on representative workloads.
