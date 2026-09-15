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

- Variables: shard/domain count, namespace split, worker-to-domain mapping
- Objective: reduce coordination contention and tail latency
- Hard constraint: preserve the required global invariant (for example uniqueness or ordering scope)

## Preserved contract

Partitioning must not silently weaken uniqueness, ownership, visibility or ordering guarantees. If ordering becomes per-domain rather than global, that is a contract change and must be explicit.

## Optimization

Factor a global coordination space into independent domains. Encode domain identity into keys/IDs or route work so each domain can advance mostly independently. Prefer a small explicit merge/aggregation boundary to a permanently hot global lock/counter/poller.

## Validation

Check global invariants across all domains, collision/duplicate behavior, rebalance/restart behavior and target-scale contention profiles.

## Target-repo adaptation

Shard counts and bit splits are workload-specific. Measure skew, cache locality, failure domains and merge costs.

## Failure modes

Hot shards merely move the bottleneck; domain proliferation raises memory/management overhead; rebalancing may violate identity stability; global ordering requirements may make the pattern inadmissible.

## Rollback trigger

Revert if partitioning does not reduce measured contention or if any cross-domain invariant fails.
