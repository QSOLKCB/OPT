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

- X: target-supported shard/domain counts, namespace splits, worker-to-domain mappings, exclusive-ownership/handoff mechanisms, fencing-epoch policies, and merge/aggregation policies
- F: configurations that preserve the target's required uniqueness, ownership, visibility, failure-domain, and ordering guarantees under steady state, reassignment, restart, delayed-old-owner recovery, and split-brain conditions
- f: measured coordination contention, tail latency, and coordination overhead under the declared workload
- d: minimize under the target's predeclared objective ordering
- C: partitioning must not silently weaken any global invariant; only the currently fenced/authorized owner of a domain may mutate domain-scoped state, stale owners must be rejected after reassignment, and any intentional shift from global to per-domain ordering is a separately declared contract change
- B: target-specific contention/scale/failover benchmark budget declared before tuning; no portable shard count or bit split is supplied here
- S: stop when the budget is exhausted or a validated partitioning materially reduces the target bottleneck without violating C

## Preserved contract

Partitioning must not silently weaken uniqueness, ownership, visibility or ordering guarantees. Reassignment must preserve exclusive authority: once ownership moves, an old worker that remains alive, resumes after a pause, or recovers from a partition must be unable to allocate IDs, process queue ranges, commit writes, or otherwise act as the current owner. If ordering becomes per-domain rather than global, that is a contract change and must be explicit.

## Optimization

Factor a global coordination space into independent domains. Encode domain identity into keys/IDs or route work so each domain can advance mostly independently. Prefer a small explicit merge/aggregation boundary to a permanently hot global lock/counter/poller.

For any domain whose ownership can move, pair routing/assignment with an **exclusive handoff and fencing mechanism**. A typical design uses a durable lease/ownership record containing a monotonically increasing epoch (generation/fencing token). A worker may act for a domain only while holding the current valid lease/epoch, and every mutating downstream action must carry or be checked against that epoch so an older owner is rejected even if it is still running. Reassignment must advance the epoch before the replacement begins authoritative work; the old epoch can never become valid again merely because the old process resumes. Where a lease can expire, expiration alone is insufficient unless the storage/queue/allocator accepting writes also enforces the fencing token.

If two workers temporarily believe they own the same domain, the durable fencing boundary decides which epoch is authoritative. Recovery may retry idempotent work under the new epoch, but it must not accept stale-owner mutations that could duplicate IDs, process the same queue range twice, or overwrite newer state.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; donor observations motivate the pattern only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Check global invariants across all domains, collision/duplicate behavior, rebalance/restart behavior and target-scale contention profiles.

Add ownership-race fixtures. Start owner A for a domain, pause/delay it without terminating it, reassign the domain to owner B with a strictly newer fencing epoch, then resume A and prove every A mutation is rejected while B remains authoritative. Repeat with network partitions, lease expiry, process suspension, delayed messages, reordered retries, and split-brain recovery. For ID allocation, prove no duplicate local/global IDs can be emitted or committed across epochs. For queues, prove stale consumers cannot acknowledge/process the reassigned range authoritatively. For stores/counters, verify stale writes are rejected at the mutation boundary, not merely by the router. Exercise repeated reassignments A→B→C and recovery of both older owners.

## Target-repo adaptation

Shard counts and bit splits are workload-specific. Measure skew, cache locality, failure domains and merge costs. Define the durable ownership record, lease lifetime if any, monotonically increasing fencing epoch, which downstream operations must validate it, handoff ordering, retry/idempotency behavior, and recovery semantics before allowing dynamic reassignment.

## Failure modes

Hot shards merely move the bottleneck; domain proliferation raises memory/management overhead; stale owners without fencing can duplicate IDs/work or corrupt state during rebalance; lease expiry without downstream fencing can create split-brain authority; epoch reuse/wraparound or non-durable handoff can resurrect old ownership; rebalancing may violate identity stability; global ordering requirements may make the pattern inadmissible.

## Rollback trigger

Revert if partitioning does not reduce measured contention, if any cross-domain invariant fails, if a stale owner can mutate state after reassignment, if split-brain tests admit two authoritative epochs, or if fencing/handoff overhead outweighs the coordination benefit.
