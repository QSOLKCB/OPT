# OPT-FAN-001 — Shared materialization for fan-out and replay

**Status:** Implemented external reference; target validation required  
**Domains:** streaming, serialization, compression, artifact pipelines, multi-consumer services

## Source evidence

- Jazco, Jetstream: https://jazco.dev/2024/09/24/jetstream/
- `sources/JAZCO.md`

## Problem

The same deterministic transformation is repeated independently for each consumer and again during replay.

## Optimization problem contract

- X: target-supported materialization boundaries, representation formats/versions, persistence policies, and raw-versus-materialized retention policies
- F: configurations whose materialized representation satisfies every declared consumer semantic, versioning, integrity, and trust requirement
- f: measured transformation CPU, replay CPU, fan-out latency, and storage/I/O overhead under the target's declared objective ordering
- d: minimize under the target's predeclared scalar or lexicographic ordering
- C: consumers receive the declared representation semantics exactly; verification/security metadata may be removed only under an explicit contract change
- B: target-specific fan-out/replay benchmark budget declared before tuning; no portable subscriber count, replay size, or retention duration is supplied here
- S: stop when the declared budget is exhausted or a validated materialization policy materially improves the target objective without violating C

## Preserved contract

Consumers must receive the same declared representation semantics. Removing verification/security metadata is **not** a correctness-preserving optimization unless the interface contract explicitly changes.

## Optimization

Perform an expensive deterministic transform once near production, persist or retain the reusable representation, and fan out/replay those bytes/objects rather than reconstructing them per consumer.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; Jetstream observations remain external source evidence.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Compare shared materialization against per-consumer reference output, including version changes, corruption, restart/replay and mixed consumer capabilities.

## Target-repo adaptation

Choose representation versioning, invalidation, storage-vs-CPU trade-offs and whether both raw and materialized forms are retained.

## Failure modes

Materializing unused forms wastes storage; format changes create invalidation/migration costs; mutable consumer-specific transformations cannot safely share one artifact.

## Rollback trigger

Disable when storage/invalidations outweigh avoided transform work or representation equivalence fails.
