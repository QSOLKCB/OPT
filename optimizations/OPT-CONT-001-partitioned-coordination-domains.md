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

- X: target-supported shard/domain counts, namespace splits, worker-to-domain mappings, merge/aggregation policies, ownership-lease policies, and fencing-epoch schemes
- F: configurations that preserve the target's required uniqueness, exclusive ownership, visibility, failure-domain, and ordering guarantees through assignment, rebalance, restart, and split-brain recovery
- f: measured coordination contention, tail latency, and coordination overhead under the declared workload
- d: minimize under the target's predeclared objective ordering
- C: partitioning must not silently weaken any global invariant; any intentional shift from global to per-domain ordering is a separately declared contract change; mutable domain ownership transitions require one active fenced owner for each epoch
- B: target-specific contention/scale/failover benchmark budget declared before tuning; no portable shard count or bit split is supplied here
- S: stop when the budget is exhausted or a validated partitioning materially reduces the target bottleneck without violating C
- Variables: integer / categorical / mixed
- Search scope: local architecture/partition-policy tuning
- Objective behavior: noisy under concurrent load; ownership/uniqueness invariants are deterministic
- Information: derivative-free / black-box performance measurements
- Evaluation cost: moderate to expensive at target scale and during failover testing
- Constraints: uniqueness, ownership, ordering, visibility, failure-domain, lease/fencing, and resource constraints
- Parallelism: concurrent / asynchronous by construction
- Exactness: exact ownership/uniqueness semantics; no approximation is introduced

## Preserved contract

Partitioning must not silently weaken uniqueness, ownership, visibility or ordering guarantees. If ordering becomes per-domain rather than global, that is a contract change and must be explicit. When a domain can be reassigned, only the current fenced owner may mutate that domain; a delayed, partitioned, resumed, or split-brain previous owner must be rejected even if it still believes its old lease is valid.

## Optimization

Factor a global coordination space into independent domains. Encode domain identity into keys/IDs or route work so each domain can advance mostly independently. Prefer a small explicit merge/aggregation boundary to a permanently hot global lock/counter/poller.

For dynamic assignment/rebalance, use an **exclusive handoff with fencing**. A durable coordinator grants ownership together with a monotonically increasing epoch/token. Every state-changing operation that depends on domain ownership carries that epoch, and the authoritative storage/queue/allocation boundary rejects operations from epochs older than the current one. A lease alone is insufficient if an old process can resume after expiry; the fencing token must make stale writes/actions impossible at the mutation boundary. Do not activate the replacement owner until the new epoch is durably authoritative.

Where local IDs/counters are used, combine the stable domain identity with the fenced ownership epoch or another target-specific mechanism strong enough to prevent duplicate allocation across reassignment. If IDs must remain stable across ownership epochs, separate the stable domain namespace from the fencing metadata while still rejecting stale mutations.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; donor observations motivate the pattern only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Check global invariants across all domains, collision/duplicate behavior, restart behavior and target-scale contention profiles.

Exercise **rebalance/recovery races**: pause an owner, expire/revoke it, assign a higher fencing epoch to a replacement, then resume the old owner and prove every stale mutation/allocation/queue claim is rejected. Inject network partition and split-brain conditions where both old and new processes run simultaneously. Verify only the highest authoritative epoch can mutate state, no duplicate IDs/work claims are produced, handoff is crash-recoverable, and ownership remains unique through coordinator/storage restarts. Include delayed messages from old epochs arriving after the new owner has already committed work.

## Target-repo adaptation

Shard counts and bit splits are workload-specific. Measure skew, cache locality, failure domains and merge costs. Define the durable ownership source, lease timeout if used, monotonically increasing fencing epoch/token, authoritative mutation boundary that validates epochs, handoff sequence, and restart/recovery semantics before enabling dynamic reassignment.

## Failure modes

Hot shards merely move the bottleneck; domain proliferation raises memory/management overhead; rebalancing without fencing can allow stale and replacement owners to act concurrently; lease-only ownership can fail when an old process resumes; delayed old-epoch messages can duplicate allocations or queue work; identity stability may be violated; global ordering requirements may make the pattern inadmissible.

## Rollback trigger

Revert if partitioning does not reduce measured contention, if any cross-domain invariant fails, or if failover/rebalance testing shows a stale owner or old-epoch message can mutate state after a replacement owner becomes authoritative.
