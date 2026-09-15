# OPT-FAN-001 — Shared materialization for fan-out and replay

**Status:** Implemented external reference; target validation required  
**Domains:** streaming, serialization, compression, artifact pipelines, multi-consumer services

## Source evidence

- Jazco, Jetstream: https://jazco.dev/2024/09/24/jetstream/
- `sources/JAZCO.md`

## Problem

The same deterministic transformation is repeated independently for each consumer and again during replay.

## Optimization problem contract

- X: target-supported materialization boundaries, representation formats/versions, persistence policies, raw-versus-materialized retention policies, complete materialization-key definitions, immutable-source snapshot/mutation-control policies, monotonic source/config epochs, and crash-consistent publication schemes
- F: configurations whose materialized representation satisfies every declared consumer semantic, versioning, integrity, trust, materialization-equivalence, source-snapshot/mutation-consistency, and publication-atomicity requirement
- f: measured transformation CPU, replay CPU, fan-out latency, and storage/I/O overhead under the target's declared objective ordering
- d: minimize under the target's predeclared scalar or lexicographic ordering
- C: consumers receive the declared representation semantics exactly; reuse is allowed only when one committed state binds the artifact bytes to one coherent effective source/transform identity and no intervening mutable-input change can be erased by endpoint equality; verification/security metadata may be removed only under an explicit contract change
- B: target-specific fan-out/replay benchmark budget declared before tuning; no portable subscriber count, replay size, or retention duration is supplied here
- S: stop when the declared budget is exhausted or a validated materialization policy materially improves the target objective without violating C
- Variables: categorical / integer / mixed
- Search scope: local materialization-boundary / representation-policy tuning
- Objective behavior: noisy for performance; transformation identity/equivalence is deterministic
- Information: derivative-free / black-box performance measurements
- Evaluation cost: moderate to expensive depending on transform/replay size
- Constraints: semantic equivalence, source-snapshot/mutation consistency, integrity, versioning, trust/security, storage, and crash-consistency constraints
- Parallelism: concurrent fan-out/replay; publication must remain race-safe
- Exactness: exact representation semantics; no approximation is introduced

## Preserved contract

Consumers must receive the same declared representation semantics. A persisted representation is reusable only under a named **materialization-equivalence invariant** that binds the artifact to every effective input capable of changing its bytes or semantics, and that binding must survive source mutation, change-and-revert races, crashes, and interrupted publication. Removing verification/security metadata is **not** a correctness-preserving optimization unless the interface contract explicitly changes.

## Optimization

Perform an expensive deterministic transform once near production, persist or retain the reusable representation, and fan out/replay those bytes/objects rather than reconstructing them per consumer.

Define a materialization key that covers, as applicable, source object/content identity or immutable source version, transformation/encoder implementation identity, encoder configuration and dictionaries, schema/format version, feature flags, trust/security policy, and any other effective input that can affect the materialized result.

Bind the transform to one coherent source identity for the **entire transform-to-commit interval**. Prefer reading every mutable effective input from an immutable snapshot/version captured together with the materialization key. If immutable snapshots are unavailable, use a mechanism that records intervening mutation rather than comparing endpoint content alone: hold an appropriate mutation/read lock for the full interval, or capture a monotonically increasing, non-reusable version/epoch for each mutable source/config/transform input and require the same coherent epoch vector at commit. Every mutation must advance its witness durably/atomically with the mutation, including A→B→A changes that restore the original bytes. A final content/key recomputation may supplement this witness but must not be the sole protection. Any lock violation, epoch change, incoherent multi-input witness, or untrackable mutable input invalidates the candidate materialization; discard/retry it rather than publishing mixed-state bytes.

Publish the artifact and its identity as **one committed state**. Acceptable designs include content-addressed storage where the artifact digest is itself part of the committed key, an atomically replaced manifest that contains both the full materialization key and the artifact digest/location, or another crash-consistent transaction that makes old state or new state visible but never a mixed pair. Do not update artifact bytes and their key independently in a way that can expose a new artifact with stale metadata or stale bytes with a new key after a crash.

Before reuse, require: (1) exact agreement with the current effective-input materialization key and immutable snapshot/monotonic mutation identity, (2) a committed manifest/content-address relation that binds that identity to the artifact identity, and (3) artifact integrity/format validity. A key mismatch, mutation-epoch mismatch, missing/incomplete publication marker, digest mismatch, or unverifiable artifact is a cache miss and requires regeneration. Do not use format validation or endpoint key equality alone as evidence that an artifact corresponds to one stable input generation.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; Jetstream observations remain external source evidence.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Compare shared materialization against per-consumer reference output, including corruption, restart/replay and mixed consumer capabilities. Independently mutate each key component—source content/version, transform implementation, encoder options/dictionary, schema/format version, feature flags and trust policy—and prove that each output-affecting change invalidates reuse. Also test unchanged-key reuse, tampered artifacts with matching metadata, and migration/version-boundary cases.

Exercise **concurrent source mutation**, including explicit A→B→A races. Start a transform from source identity A, mutate one or more source/config/transform inputs to B while the transform is running, then restore the original bytes before commit. For snapshot-based targets, prove the transform reads only the immutable A snapshot. For lock-based targets, prove mutation cannot interleave with the protected transform/publication interval. For epoch/version-based targets, prove every mutation advances the monotonic witness and the final witness differs even when the final content/key returns to A. Reject/discard the candidate on any witness change and compare every accepted materialization with a fresh transform from the exact committed source identity.

Inject crashes/interruption at every publication boundary: after artifact write but before manifest commit, after provisional metadata write, during atomic replacement, and immediately after commit. After restart, prove that readers see either the previous valid committed materialization or the new valid committed materialization, never a mixed key/artifact state. Verify digest/key mismatch is rejected even when the artifact is otherwise parseable.

## Target-repo adaptation

Define the complete materialization-equivalence invariant for the target, choose the identity primitive for each effective input, specify whether mutable inputs are consumed from immutable snapshots, protected by full-duration locks, or guarded by monotonic mutation epochs, and define how a coherent multi-input witness is captured. Specify representation versioning, invalidation, integrity checking, **crash-consistent publication/commit mechanics**, storage-vs-CPU trade-offs and whether both raw and materialized forms are retained. Do not advertise commit-time endpoint rehashing alone as sufficient mutation detection.

## Failure modes

Incomplete keys can serve stale representations after source or transform changes; mutable sources can change during transformation and produce mixed-state output under a stale key; A→B→A races can defeat endpoint key comparisons; non-monotonic/reused mutation versions can erase intervening changes; incoherent epoch vectors can describe no real source state; non-atomic publication can pair new bytes with an old key or vice versa after a crash; metadata can match while artifact bytes are corrupted; materializing unused forms wastes storage; format changes create invalidation/migration costs; mutable consumer-specific transformations cannot safely share one artifact.

## Rollback trigger

Disable reuse immediately if any materialization-key hit, source-mutation race, publication-recovery path, or integrity check can return output that differs from a fresh transform for the same exact committed effective inputs; if an A→B→A race can evade the snapshot/lock/monotonic mutation witness; or if interrupted publication can expose a mixed key/artifact state. Also disable when storage/invalidations outweigh avoided transform work or representation equivalence fails.
