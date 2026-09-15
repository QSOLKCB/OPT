# OPT-SET-001 — Density-adaptive compact set representation

**Status:** Implemented external reference; target validation required  
**Domains:** graphs, indexes, membership sets, telemetry, integer identifiers

## Source evidence

- https://jazco.dev/2024/04/20/roaring-bitmaps/
- https://jazco.dev/2024/04/15/in-memory-graphs/
- `sources/JAZCO.md`

## Problem

A single representation performs poorly across regions with very different density: sparse bitmaps waste memory, while list-like sparse structures make dense set algebra expensive.

## Optimization problem contract

- X: target-supported partition widths, sparse/dense container choices, switching thresholds, and serialization layouts
- F: representations that preserve exact membership and set-operation semantics and satisfy target memory/serialization compatibility constraints
- f: measured memory footprint plus target-relevant set-operation and serialization latency
- d: minimize under the target's predeclared scalar, lexicographic, or Pareto ordering
- C: membership, union, intersection, difference, and persistence round trips match the canonical reference set exactly
- B: target-specific benchmark budget over declared sparse, dense, mixed, and transition-boundary datasets; no portable trial count is supplied here
- S: stop when the declared budget is exhausted or a validated representation meets the target objective without violating C

## Preserved contract

Membership and set operations must match the reference set exactly.

## Optimization

Partition the identifier space and choose a representation per partition according to local density. Keep sparse regions compact while using bitmap-like containers where dense boolean algebra is advantageous. Prefer representations that can be serialized without expanding to a larger intermediate form.

## Evidence boundary

Jazco reports strong production-scale graph results, but OPT treats the numbers as source observations only. The portable claim is density-adaptive representation.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; reported graph results remain historical external observations.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Differential-test membership, union, intersection, difference and persistence against a simple canonical set implementation over sparse, dense and transition-boundary fixtures.

## Target-repo adaptation

Benchmark partition sizes and switching thresholds on the real identifier distribution and CPU/cache hierarchy.

## Failure modes

Conversion churn near thresholds, pathological distributions, serialization incompatibility and hidden temporary allocations can erase the benefit.

## Rollback trigger

Revert when target data does not show a memory/latency win or exact set differential tests fail.
