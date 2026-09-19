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

- X: target-supported partition widths, sparse/dense container choices, switching thresholds, serialization layouts/versions, and migration policies
- F: representations that preserve exact membership and set-operation semantics, preserve contractually significant iteration ordering when one exists, and satisfy target memory/serialization compatibility constraints
- f: measured memory footprint plus target-relevant set-operation and serialization latency
- d: minimize under the target's predeclared scalar, lexicographic, or Pareto ordering
- C: membership, union, intersection, difference, iteration behavior where observable, mutation semantics, and persistence/compatibility round trips match the canonical reference contract exactly
- B: target-specific benchmark budget over declared sparse, dense, mixed, transition-boundary, mutation, and compatibility datasets; no portable trial count is supplied here
- S: stop when the declared budget is exhausted or a validated representation meets the target objective without violating C
- Variables: integer / categorical / mixed
- Search scope: local representation/threshold/layout tuning
- Objective behavior: noisy for performance; set semantics are deterministic
- Information: derivative-free performance measurements
- Evaluation cost: cheap to moderate per fixture; may become expensive at production scale
- Constraints: exact set semantics, ordering where observable, memory, serialization, version compatibility, and migration constraints
- Parallelism: sequential for representation transitions unless the target separately defines safe concurrent mutation semantics
- Exactness: exact set semantics; no approximation is introduced

## Preserved contract

Membership and set operations must match the reference set exactly. If iteration order is part of the target API/serialization contract, representation changes must preserve that order exactly. Persisted or exchanged sets must remain readable/writable according to the target's explicit version-compatibility policy; otherwise the layout change requires an explicit migration/version boundary rather than being treated as transparent.

## Optimization

Partition the identifier space and choose a representation per partition according to local density. Keep sparse regions compact while using bitmap-like containers where dense boolean algebra is advantageous. Prefer representations that can be serialized without expanding to a larger intermediate form.

For mutable sets, representation switching is part of the state machine: insertion/deletion may cross thresholds in either direction. Conversions must be semantics-preserving and idempotent with respect to the canonical set state, including any observable iteration order and persistence metadata.

For persisted/mixed-version use, define a versioned serialization contract. Either retain backward/forward compatibility for the required reader/writer matrix or provide an explicit migration/version bump before emitting an incompatible layout. Do not infer external compatibility from a same-version self-round-trip.

## Evidence boundary

Jazco reports strong production-scale graph results, but OPT treats the numbers as source observations only. The portable claim is density-adaptive representation.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; reported graph results remain historical external observations.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Differential-test membership, union, intersection, difference, iteration (when observable), and persistence against a simple canonical set implementation over sparse, dense and transition-boundary fixtures.

Exercise **mutable transition sequences**: insert/delete elements so each switching threshold is crossed repeatedly sparse→dense and dense→sparse, including oscillation directly around thresholds. After every mutation and conversion, compare membership, cardinality, union/intersection/difference, and—when part of C—the exact iteration sequence with the canonical reference. Serialize and reload after every transition, then repeat the same comparisons.

Exercise **serialization compatibility** independently from same-version round trips. Keep golden fixtures from every required older format/version and prove the new reader accepts them without semantic loss. Where backward writing or forward reading is required, exercise those reader/writer combinations explicitly. If compatibility is intentionally broken, require a versioned migration that converts old persisted state before the new layout becomes authoritative, and verify old consumers cannot silently misinterpret new bytes.

## Target-repo adaptation

Benchmark partition sizes and switching thresholds on the real identifier distribution and CPU/cache hierarchy. Determine whether iteration order is observable. Define the serialization-version matrix, migration policy, and any hysteresis needed to avoid conversion churn around thresholds.

## Failure modes

Conversion defects can drop/duplicate members; repeated threshold crossing can cause churn; sparse↔dense transitions can reorder iteration; new layouts can make old persisted state unreadable or emit bytes older consumers reject; pathological distributions, serialization incompatibility and hidden temporary allocations can erase the benefit.

## Rollback trigger

Revert when target data does not show a memory/latency win, any mutable-transition differential test fails, observable iteration order changes, or any required persistence/version-compatibility fixture fails.
