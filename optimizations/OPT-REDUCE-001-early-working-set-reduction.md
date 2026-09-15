# OPT-REDUCE-001 — Early working-set reduction

**Status:** Implemented external pattern; broadly applicable mechanism  
**Domains:** databases, graphs, simulation, DSP, rendering, data pipelines

## Source evidence

- https://jazco.dev/2023/08/10/query-optimization/
- supporting sparse-evaluation pattern in `OPT-DSP-001`

## Problem

An expensive operation is applied to a large population even though only a small subset can affect the final result.

## Optimization problem contract

- Variable: where semantics-preserving filtering/culling/limiting occurs
- Objective: minimize cardinality presented to the expensive stage
- Hard constraint: early reduction must preserve every candidate required by the final result

## Preserved contract

Moving a reduction earlier is valid only if it is semantically equivalent to the original later reduction, including ordering/top-k/tie and join semantics where relevant.

## Optimization

Push selective operations toward the input boundary: filter before join, cull before render, select candidate roots before expensive DSP, prune impossible simulations before full evaluation. Prefer indexed/cheap predicates to expensive composition over the full population.

## Validation

Differential-test reordered pipelines against the reference, with emphasis on ties, null/missing values, boundary ordering and rare candidates.

## Target-repo adaptation

Measure selectivity and reduction cost. A cheap filter with low selectivity may simply add another pass.

## Failure modes

Illegal predicate reordering, changed top-k semantics, underestimated filtering cost, loss of vectorization and duplicated scans.

## Rollback trigger

Revert if outputs differ or total measured cost does not fall on representative workloads.
