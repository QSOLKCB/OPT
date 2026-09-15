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

- X: target-supported partition widths, sparse/dense container choices, switching thresholds/hysteresis policies, mutation/conversion policies, and serialization layouts
- F: representations that preserve exact membership and set-operation semantics across all supported mutations and representation transitions and satisfy target memory/serialization compatibility constraints
- f: measured memory footprint plus target-relevant set-operation, mutation/conversion, and serialization latency
- d: minimize under the target's predeclared scalar, lexicographic, or Pareto ordering
- C: membership, insertion, deletion, union, intersection, difference, representation transitions, and persistence round trips match the canonical reference set exactly after every mutation
- B: target-specific benchmark budget over declared sparse, dense, mixed, transition-boundary, and mutation-sequence datasets; no portable trial count is supplied here
- S: stop when the declared budget is exhausted or a validated representation meets the target objective without violating C

## Preserved contract

Membership and set operations must match the reference set exactly before, during, and after conversion between sparse and dense representations. A threshold crossing is an internal representation change only; it must not drop, duplicate, reorder semantically significant iteration, or corrupt members.

## Optimization

Partition the identifier space and choose a representation per partition according to local density. Keep sparse regions compact while using bitmap-like containers where dense boolean algebra is advantageous. For mutable sets, conversions triggered by insertions/deletions must be deterministic and exact. Consider hysteresis or other anti-thrashing policy when repeated near-threshold mutation would otherwise cause conversion churn, but do not change set semantics to avoid conversions. Prefer representations that can be serialized without expanding to a larger intermediate form.

## Evidence boundary

Jazco reports strong production-scale graph results, but OPT treats the numbers as source observations only. The portable claim is density-adaptive representation.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; reported graph results remain historical external observations.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Differential-test membership, insertion, deletion, union, intersection, difference and persistence against a simple canonical set implementation over sparse, dense and transition-boundary fixtures.

Add mutation-sequence tests that repeatedly cross every sparse↔dense switching threshold in **both directions**. Construct sequences that insert just past the promotion boundary, delete back below the demotion boundary, and repeat for many cycles; include randomized/adversarial churn near the boundary. After every mutation and every representation transition, verify exact membership/cardinality against the reference set, then re-run union/intersection/difference checks and a serialization round trip. Test duplicate insertions, deletion of absent elements, empty/full-ish containers, threshold off-by-one cases, and restart/deserialization followed by further transitions. If hysteresis is used, verify its exact promotion/demotion rules while preserving the same set contents.

## Target-repo adaptation

Benchmark partition sizes, switching thresholds, hysteresis/conversion policy, and serialization format on the real identifier distribution, mutation pattern, and CPU/cache hierarchy. Immutable/read-mostly and mutation-heavy workloads may justify different policies.

## Failure modes

Conversion bugs can drop or duplicate members; repeated near-threshold mutation can cause conversion thrash; asymmetric promotion/demotion logic can strand a container in the wrong representation; pathological distributions, serialization incompatibility and hidden temporary allocations can erase the benefit.

## Rollback trigger

Revert when target data does not show a memory/latency win, any static or mutation-sequence differential test fails, any transition loses/duplicates members, persistence round trips diverge, or conversion churn materially worsens the target workload.
