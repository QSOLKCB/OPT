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

- X: target-supported shard/domain counts, namespace splits, worker-to-domain mappings, and merge/aggregation policies
- F: configurations that preserve the target's required uniqueness, ownership, visibility, failure-domain, and ordering guarantees
- f: measured coordination contention, tail latency, and coordination overhead under the declared workload
- d: minimize under the target's predeclared objective ordering
- C: partitioning must not silently weaken any global invariant; any intentional shift from global to per-domain ordering is a separately declared contract change
- B: target-specific contention/scale benchmark budget declared before tuning; no portable shard count or bit split is supplied here
- S: stop when the budget is exhausted or a validated partitioning materially reduces the target bottleneck without violating C

## Preserved contract

Partitioning must not silently weaken uniqueness, ownership, visibility or ordering guarantees. If ordering becomes per-domain rather than global, that is a contract change and must be explicit.

## Optimization

Factor a global coordination space into independent domains. Encode domain identity into keys/IDs or route work so each domain can advance mostly independently. Prefer a small explicit merge/aggregation boundary to a permanently hot global lock/counter/poller.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; donor observations motivate the pattern only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Check global invariants across all domains, collision/duplicate behavior, rebalance/restart behavior and target-scale contention profiles.

## Target-repo adaptation

Shard counts and bit splits are workload-specific. Measure skew, cache locality, failure domains and merge costs.

## Failure modes

Hot shards merely move the bottleneck; domain proliferation raises memory/management overhead; rebalancing may violate identity stability; global ordering requirements may make the pattern inadmissible.

## Rollback trigger

Revert if partitioning does not reduce measured contention or if any cross-domain invariant fails.
