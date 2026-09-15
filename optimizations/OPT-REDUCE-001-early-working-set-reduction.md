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
- F: placements that preserve every candidate and ordering/tie/join semantic required by the final result and satisfy target resource constraints
- f: measured end-to-end pipeline cost and cardinality presented to the expensive stage
- d: minimize under the target's predeclared objective ordering
- C: the reordered/reduced pipeline must be semantically equivalent to the reference pipeline for all declared output, ordering, top-k, tie, null, and join semantics
- B: target-specific benchmark budget over representative and adversarial selectivity distributions; no portable selectivity threshold is supplied here
- S: stop when the declared budget is exhausted or a validated early-reduction placement materially lowers total cost without violating C

## Preserved contract

Moving a reduction earlier is valid only if it is semantically equivalent to the original later reduction, including ordering/top-k/tie and join semantics where relevant.

## Optimization

Push selective operations toward the input boundary: filter before join, cull before render, select candidate roots before expensive DSP, prune impossible simulations before full evaluation. Prefer indexed/cheap predicates to expensive composition over the full population.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; external query observations and existing sparse-evaluation patterns are source evidence only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Differential-test reordered pipelines against the reference, with emphasis on ties, null/missing values, boundary ordering and rare candidates.

## Target-repo adaptation

Measure selectivity and reduction cost. A cheap filter with low selectivity may simply add another pass.

## Failure modes

Illegal predicate reordering, changed top-k semantics, underestimated filtering cost, loss of vectorization and duplicated scans.

## Rollback trigger

Revert if outputs differ or total measured cost does not fall on representative workloads.
