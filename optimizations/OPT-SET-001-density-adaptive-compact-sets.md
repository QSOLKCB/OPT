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

- Variables: partition width, sparse/dense representation threshold, serialization layout
- Objectives: memory footprint and set-operation latency
- Hard constraint: exact set semantics unless approximation is explicitly introduced elsewhere

## Preserved contract

Membership and set operations must match the reference set exactly.

## Optimization

Partition the identifier space and choose a representation per partition according to local density. Keep sparse regions compact while using bitmap-like containers where dense boolean algebra is advantageous. Prefer representations that can be serialized without expanding to a larger intermediate form.

## Evidence boundary

Jazco reports strong production-scale graph results, but OPT treats the numbers as source observations only. The portable claim is density-adaptive representation.

## Validation

Differential-test membership, union, intersection, difference and persistence against a simple canonical set implementation over sparse, dense and transition-boundary fixtures.

## Target-repo adaptation

Benchmark partition sizes and switching thresholds on the real identifier distribution and CPU/cache hierarchy.

## Failure modes

Conversion churn near thresholds, pathological distributions, serialization incompatibility and hidden temporary allocations can erase the benefit.

## Rollback trigger

Revert when target data does not show a memory/latency win or exact set differential tests fail.
