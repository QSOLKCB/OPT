# OPT-FAN-001 — Shared materialization for fan-out and replay

**Status:** Implemented external reference; target validation required  
**Domains:** streaming, serialization, compression, artifact pipelines, multi-consumer services

## Source evidence

- Jazco, Jetstream: https://jazco.dev/2024/09/24/jetstream/
- `sources/JAZCO.md`

## Problem

The same deterministic transformation is repeated independently for each consumer and again during replay.

## Optimization problem contract

- X: target-supported materialization boundaries, representation formats/versions, persistence policies, raw-versus-materialized retention policies, and complete materialization-key definitions
- F: configurations whose materialized representation satisfies every declared consumer semantic, versioning, integrity, trust, and materialization-equivalence requirement
- f: measured transformation CPU, replay CPU, fan-out latency, and storage/I/O overhead under the target's declared objective ordering
- d: minimize under the target's predeclared scalar or lexicographic ordering
- C: consumers receive the declared representation semantics exactly; reuse is allowed only when the materialization key proves the persisted artifact was produced from the same effective source and transformation identity; verification/security metadata may be removed only under an explicit contract change
- B: target-specific fan-out/replay benchmark budget declared before tuning; no portable subscriber count, replay size, or retention duration is supplied here
- S: stop when the declared budget is exhausted or a validated materialization policy materially improves the target objective without violating C

## Preserved contract

Consumers must receive the same declared representation semantics. A persisted representation is reusable only under a named **materialization-equivalence invariant** that binds the artifact to every effective input capable of changing its bytes or semantics. Removing verification/security metadata is **not** a correctness-preserving optimization unless the interface contract explicitly changes.

## Optimization

Perform an expensive deterministic transform once near production, persist or retain the reusable representation, and fan out/replay those bytes/objects rather than reconstructing them per consumer.

Persist a materialization key beside the artifact. The key must cover, as applicable, source object/content identity or immutable source version, transformation/encoder implementation identity, encoder configuration and dictionaries, schema/format version, feature flags, trust/security policy, and any other effective input that can affect the materialized result. Before reuse, require both: (1) exact agreement with the current materialization key, and (2) artifact integrity/format validity. A key mismatch or unverifiable artifact is a cache miss and requires regeneration. Do not use format validation alone as evidence that an artifact corresponds to current inputs.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; Jetstream observations remain external source evidence.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Compare shared materialization against per-consumer reference output, including corruption, restart/replay and mixed consumer capabilities. Independently mutate each key component—source content/version, transform implementation, encoder options/dictionary, schema/format version, feature flags and trust policy—and prove that each output-affecting change invalidates reuse. Also test unchanged-key reuse, tampered artifacts with matching metadata, and migration/version-boundary cases.

## Target-repo adaptation

Define the complete materialization-equivalence invariant for the target, choose the identity primitive for each effective input, and specify representation versioning, invalidation, integrity checking, storage-vs-CPU trade-offs and whether both raw and materialized forms are retained.

## Failure modes

Incomplete keys can serve stale representations after source or transform changes; metadata can match while artifact bytes are corrupted; materializing unused forms wastes storage; format changes create invalidation/migration costs; mutable consumer-specific transformations cannot safely share one artifact.

## Rollback trigger

Disable reuse immediately if any materialization-key hit or integrity check can return output that differs from a fresh transform for the same current effective inputs. Also disable when storage/invalidations outweigh avoided transform work or representation equivalence fails.
