# OPT-FAN-001 — Shared materialization for fan-out and replay

**Status:** Implemented external reference; target validation required  
**Domains:** streaming, serialization, compression, artifact pipelines, multi-consumer services

## Source evidence

- Jazco, Jetstream: https://jazco.dev/2024/09/24/jetstream/
- `sources/JAZCO.md`

## Problem

The same deterministic transformation is repeated independently for each consumer and again during replay.

## Optimization problem contract

- Variables: materialization boundary, representation format, persistence policy
- Objectives: transformation CPU, replay CPU, fan-out latency
- Hard constraint: materialized form must satisfy the consumer contract and versioning/trust requirements

## Preserved contract

Consumers must receive the same declared representation semantics. Removing verification/security metadata is **not** a correctness-preserving optimization unless the interface contract explicitly changes.

## Optimization

Perform an expensive deterministic transform once near production, persist or retain the reusable representation, and fan out/replay those bytes/objects rather than reconstructing them per consumer.

## Validation

Compare shared materialization against per-consumer reference output, including version changes, corruption, restart/replay and mixed consumer capabilities.

## Target-repo adaptation

Choose representation versioning, invalidation, storage-vs-CPU trade-offs and whether both raw and materialized forms are retained.

## Failure modes

Materializing unused forms wastes storage; format changes create invalidation/migration costs; mutable consumer-specific transformations cannot safely share one artifact.

## Rollback trigger

Disable when storage/invalidations outweigh avoided transform work or representation equivalence fails.
