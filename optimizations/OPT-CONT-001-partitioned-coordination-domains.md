# OPT-CONT-001 — Partitioned coordination domains

**Status:** Implemented external pattern; target validation required  
**Domains:** ID allocation, runtimes, queues, counters, ingestion, schedulers

## Source evidence

- https://jazco.dev/2025/09/26/interning/
- https://jazco.dev/2024/01/10/golang-and-epoll/
- `sources/JAZCO.md`

## Problem

Independent workers serialize on one globally coordinated resource even though the underlying work could proceed independently.

## Optimization problem contract

- X: target-supported shard/domain counts, namespace splits, worker-to-domain mappings, merge/aggregation policies, ownership-lease policies, fencing-epoch schemes, allocator-incarnation fencing, and restart-safe allocator-state policies
- F: configurations that preserve the target's required uniqueness, exclusive ownership, visibility, failure-domain, and ordering guarantees through assignment, rebalance, same-owner restart, crash recovery, process replacement, pause/resume, and split-brain recovery
- f: measured coordination contention, tail latency, and coordination overhead under the declared workload
- d: minimize under the target's predeclared objective ordering
- C: partitioning must not silently weaken any global invariant; any intentional shift from global to per-domain ordering is a separately declared contract change; every mutable ownership/allocator incarnation must be fenced at the authoritative mutation boundary so a superseded process cannot continue acting merely because its emitted IDs remain unique; allocator restart must not reuse IDs/ranges already issued before the crash
- B: target-specific contention/scale/failover benchmark budget declared before tuning; no portable shard count or bit split is supplied here
- S: stop when the budget is exhausted or a validated partitioning materially reduces the target bottleneck without violating C
- Variables: integer / categorical / mixed
- Search scope: local architecture/partition-policy tuning
- Objective behavior: noisy under concurrent load; ownership/uniqueness invariants are deterministic
- Information: derivative-free / black-box performance measurements
- Evaluation cost: moderate to expensive at target scale and during failover testing
- Constraints: uniqueness, ownership, ordering, visibility, failure-domain, lease/fencing, allocator-incarnation fencing, durable allocator-state, and resource constraints
- Parallelism: concurrent / asynchronous by construction
- Exactness: exact ownership/uniqueness semantics; no approximation is introduced

## Preserved contract

Partitioning must not silently weaken uniqueness, ownership, visibility or ordering guarantees. If ordering becomes per-domain rather than global, that is a contract change and must be explicit. When a domain can be reassigned or an owner process can be replaced, only the currently authoritative fenced owner/incarnation may mutate that domain; a delayed, partitioned, resumed, or split-brain previous process must be rejected even if it still believes its old lease is valid. A same-owner process restart is also part of the ownership contract: restarting an allocator must not reset process-local state in a way that can reissue an ID/range already made externally visible, and a replacement process must not coexist as an unfenced second owner with a paused predecessor.

## Optimization

Factor a global coordination space into independent domains. Encode domain identity into keys/IDs or route work so each domain can advance mostly independently. Prefer a small explicit merge/aggregation boundary to a permanently hot global lock/counter/poller.

For dynamic assignment/rebalance, use an **exclusive handoff with fencing**. A durable coordinator grants ownership together with a monotonically increasing epoch/token. Every state-changing operation that depends on domain ownership carries that fencing identity, and the authoritative storage/queue/allocation boundary rejects operations from older identities. A lease alone is insufficient if an old process can resume after expiry; the fencing token must make stale writes/actions impossible at the mutation boundary. Do not activate the replacement owner until its new fencing identity is durably authoritative.

Treat allocator process replacement as an ownership transition unless the target explicitly proves concurrent incarnations are harmless. A new allocator-incarnation token is safe only when it participates in the **authoritative fencing check**, not merely in the emitted ID namespace. Acceptable designs include: (1) advance the domain ownership/fencing epoch for every replacement allocator process, so the predecessor becomes stale automatically; or (2) maintain a separate monotonically increasing allocator-incarnation epoch that every mutation/allocation request carries and the authoritative boundary validates together with the domain ownership epoch. In both designs, replacing a paused/partitioned allocator invalidates the previous incarnation before the replacement may serve work. Merely embedding a fresh incarnation value in IDs prevents collisions but does **not** preserve exclusive ownership if the superseded process can still mutate queues/storage/state.

Where local IDs/counters are used, combine this fencing rule with a restart-safe allocation policy. Acceptable durable allocation designs include: (1) a high-water mark advanced atomically **before** an ID/range becomes externally usable, or (2) durable allocation of non-overlapping ranges/blocks so a restart resumes from a fresh unissued block and may safely burn any uncertain tail. A per-incarnation namespace may additionally participate in emitted IDs, but for exclusive-owner targets it cannot substitute for fencing the superseded incarnation at the mutation boundary.

If IDs must remain stable across allocator restarts and ownership epochs, use a durable monotonic counter/high-water mark or durable non-overlapping range allocator; do **not** reset an ephemeral counter. Persist/reserve advancement before returning the corresponding ID to the caller, or otherwise use a transaction whose crash semantics can prove that recovery never reissues an already-visible value. When commit status is uncertain after a crash, prefer skipping/burning an uncertain range over risking reuse.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; donor observations motivate the pattern only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Check global invariants across all domains, collision/duplicate behavior, restart behavior and target-scale contention profiles.

Exercise **same-owner allocator restarts** independently of reassignment. Issue IDs/ranges, crash the allocator before and after each persistence/reservation boundary, restart it, and prove it never reissues an externally visible ID/range. Test crashes after durable reservation but before delivery, after delivery but before acknowledgement bookkeeping, and with uncertain commit status. For high-water counters, verify monotonic durable recovery. For block/range allocation, verify recovered allocators never enter a previously issued block and that burning an uncertain tail preserves uniqueness.

Exercise **superseded-incarnation races** separately from ID-collision tests. Pause or partition allocator incarnation A without proving it dead, start replacement incarnation B, make B's fencing identity authoritative, then resume A. Prove the authoritative mutation/allocation boundary rejects every operation from A even if A's generated IDs would be collision-free because of a different incarnation namespace. Repeat with delayed A messages, queue acknowledgements, counter updates, and storage mutations. If the target uses a separate allocator-incarnation epoch, prove both ownership epoch and incarnation epoch are validated wherever exclusivity matters. If the target instead deliberately allows concurrent incarnations, state that as a contract change and verify all affected operations are designed for multi-writer semantics.

Exercise **rebalance/recovery races**: pause an owner, expire/revoke it, assign a higher fencing identity to a replacement, then resume the old owner and prove every stale mutation/allocation/queue claim is rejected. Inject network partition and split-brain conditions where both old and new processes run simultaneously. Verify only the highest authoritative fencing identity can mutate state, no duplicate IDs/work claims are produced, handoff is crash-recoverable, and ownership remains unique through coordinator/storage restarts. Include delayed messages from old epochs arriving after the new owner has already committed work.

## Target-repo adaptation

Shard counts and bit splits are workload-specific. Measure skew, cache locality, failure domains and merge costs. Define the durable ownership source, lease timeout if used, monotonically increasing fencing epoch/token, authoritative mutation boundary that validates fencing identity, handoff sequence, and restart/recovery semantics before enabling dynamic reassignment. For allocators, separately define the same-owner restart policy and the replacement-process fencing policy. Either advance the ownership epoch for every replacement or make allocator-incarnation epochs first-class fencing tokens at the mutation boundary. Do not rely on incarnation namespacing alone unless concurrent incarnations are explicitly admissible. Specify exactly which state is made durable before an ID/range can escape and how ambiguous crash outcomes are recovered without reuse.

## Failure modes

Hot shards merely move the bottleneck; domain proliferation raises memory/management overhead; rebalancing without fencing can allow stale and replacement owners to act concurrently; lease-only ownership can fail when an old process resumes; delayed old-epoch messages can duplicate allocations or queue work; a fresh allocator-incarnation namespace can hide ID collisions while still allowing two owners to mutate the same domain; a same-owner restart can reset an ephemeral local counter and reissue prior IDs even without any fencing race; persisting allocation state after delivery can create crash windows that reuse visible values; identity stability may be violated; global ordering requirements may make the pattern inadmissible.

## Rollback trigger

Revert if partitioning does not reduce measured contention, if any cross-domain invariant fails, if failover/rebalance/replacement testing shows a stale owner or superseded allocator incarnation can mutate state after a replacement becomes authoritative, if incarnation namespacing prevents duplicate IDs but does not fence the old process where exclusive ownership is required, or if same-owner crash/restart testing can reissue any externally visible ID/range or otherwise lose durable allocator progress.
