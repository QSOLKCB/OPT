# OPT-POOL-001 — Persistent topology-aware worker pools

**Status:** Implemented external reference; persistent reuse and topology-aware selection are merged in GALAXY, while scaling remains host- and workload-specific.  
**Domains:** CPU batch runtimes, repeated simulation/render passes, parallel numerical pipelines, thread-pool execution

## Source evidence

- Repository: `QSOLKCB/GALAXY`
- PR: https://github.com/QSOLKCB/GALAXY/pull/13
- Merge commit: `1966bc2595a402a2c653f2e392465224621e20fb`
- Source note: `sources/GALAXY-CPU.md`
- Licensing boundary: Apache-2.0 donor; mechanism promoted without requiring copied source.

## Problem

A validated parallel kernel is fast enough that repeatedly creating worker threads, allocating worker-local buffers and choosing an unsuitable logical/physical worker count become material overheads. Per-run spawning also adds latency variance and can hide whether SMT helps or hurts.

## Optimization problem contract

- X: Persistent-pool lifetime, worker count, topology policy, reusable worker-local buffer capacity and dispatch strategy.
- F: Candidates preserving exact output/checksum parity, deterministic work ownership and reduction, bounded live resources, explicit topology fallback, correct shutdown/error handling, and truthful concurrency evidence: a candidate claiming parallel execution must demonstrate observed overlapping active work under workload-shaped dispatches rather than merely reporting participating worker identities.
- f: Total or amortized runtime across the expected repetition horizon, including pool lifecycle cost where relevant, plus resource/scaling evidence and observed concurrency/overlap metrics for candidates whose performance claim depends on parallel execution.
- d: Minimize lifecycle-adjusted runtime while preserving deterministic semantics; prefer simpler scheduling when gains are negligible.
- C: Completion order must not alter observable results, topology claims must match detected evidence, persistent workers must not retain stale per-dispatch state, and requested/configured/effective worker counts must not be presented as proof of simultaneous execution without a direct or equivalent overlap measurement.
- B: Bounded worker/schedule/tile sweeps and repeated dispatches on the target execution environment.
- S: Stop when the expected repetition horizon and topology policy have a repeatable useful winner, or retain spawned/canonical execution when startup amortization is insufficient; if a purportedly parallel candidate shows no meaningful overlap, classify it as serialized for evidence purposes and do not promote a concurrency claim from worker participation alone.
- Variables: integer, categorical and conditional
- Search scope: local
- Objective behavior: noisy
- Information: black-box
- Evaluation cost: moderate
- Constraints: semantic and resource
- Parallelism: asynchronous
- Exactness: exact

## Preserved contract

Persistent reuse changes worker lifetime, not computation semantics. Each dispatch must process the same logical work as the reference/spawned path, and reduction must remain deterministic where required. Buffer reuse must reset or overwrite all state that can affect a later dispatch.

A failed or cancelled dispatch may be followed by reuse only after every worker-local buffer, queue, completion flag and dispatch-generation marker is returned to a known clean state. If that reset cannot be proven complete, retire the pool.

Retirement must use one of two explicit strategies:

1. **Quiescent retirement:** do not start a successor pool until every worker from the retired pool has resumed or been cancelled, reached a terminal state and been joined/reaped.
2. **Generation-fenced retirement:** every externally visible publication is bound to a non-reused **pool-incarnation identity** plus the dispatch generation. Retirement and publication must linearize through the same lock, transaction, atomic compare-and-publish operation or equivalent primitive; a worker must not be able to validate its generation, pause across retirement, and then publish afterward. A replacement may begin before old workers terminate only when stale publications are rejected by that linearization rule.

Generation-fenced retirement does not waive resource bounds. Retired pools must still have an eventual termination/reaping path, and the implementation must bound the number or total resource cost of unreaped retired generations. When that bound is reached, apply backpressure or fall back to quiescent retirement/spawned execution instead of creating unbounded replacement pools.

Concurrency evidence is part of the claim boundary rather than the computation contract. A pool may involve multiple workers yet still execute effectively serially because of locks, queue policy, scheduler throttling, cgroup limits or runtime serialization. Such a path can still be semantically correct, but it must not be described as providing parallel execution unless overlapping active work is actually observed.

## Optimization

Create workers once, allocate their reusable local buffers once, and dispatch repeated jobs through the persistent pool. Give each worker a stable deterministic range or identity. Allow workers to finish independently, but collect/reduce results under a deterministic ordering rule when arithmetic or output order requires it.

Expose topology policy explicitly. A `physical-first` policy may cap workers at detected physical cores; a `logical` policy may include SMT threads. Detection must fail softly and record the fallback instead of pretending unavailable topology data is authoritative.

Treat dispatch completion as a state transition. Successful completion must leave all reusable state ready for the next generation. Failure or cancellation must either run the same complete reset protocol or retire the pool so partial state cannot leak into a later dispatch.

For generation-fenced retirement, identify publications by `(pool-incarnation, dispatch-generation)`, not by a generation counter alone. The pool-incarnation identity must not be reused by a replacement pool even if a local generation counter restarts or wraps. Retirement and every externally visible publication must participate in the same linearization mechanism so there is no check-then-write interval in which a retired worker can pass validation before retirement and publish after it. Apply the rule to shared output, completion state, queues, callbacks and any other externally visible mutation.

Track retired pools until all workers terminate and are reaped. Bound the number or retained-resource budget of generation-fenced retired pools; if the bound is exhausted, stop admitting replacements until retirement progresses or switch to a quiescent/spawned fallback.

Separate **worker participation** from **simultaneous overlap**. Instrument workload-shaped dispatches with an active-worker counter, timestamped task intervals, scheduler/runtime tracing, or another measurement that can establish how much work actually overlapped. Record at least the observed peak simultaneous active work and, where useful, overlap duration/fraction or a concurrency histogram. A queue that eventually touches every worker but runs only one task at a time is not evidence of parallel execution.

Separate steady-state dispatch timing from startup/teardown, then include lifecycle cost when deciding whether persistence is worthwhile for the real repetition horizon.

## Before / after evidence

- Environment: GALAXY PR #13 verifies Linux x86-64, Linux ARM64, macOS ARM64 and Windows x86-64 command/parity surfaces.
- Workload/fixture: repeated worker-local SoA executions over deterministic resident ranges.
- Cold baseline: spawned worker-local SoA creates worker threads for each complete execution.
- Warm/no-op baseline where relevant: persistent steady-state dispatch excludes startup but records pool startup separately.
- Small invalidation / partial-work case where relevant: repeated first/second dispatch parity verifies reused state does not leak.
- Quiescent-retirement cancellation fixture: pause an old worker after partial activity, cancel and retire its pool, then resume/cancel it to terminal state and join/reap it **before** starting the successor dispatch. Verify that successor admission is blocked until quiescence is complete and that no retired resources remain live afterward.
- Generation-fenced cancellation fixture: pause an old worker after it has validated its `(pool-incarnation, dispatch-generation)` but **before** the externally visible mutation. Retire the pool, start a successor pool with a distinct incarnation identity and deliberately collide/restart its local generation number, then resume the old worker. Verify that the publication linearization rejects the stale mutation despite the colliding generation number and that successor output, queues, completion state and callbacks remain unchanged.
- Retired-pool bound fixture: repeatedly cancel generation-fenced pools while holding old workers alive until the configured retired-generation/resource bound is reached. Verify that further replacement is backpressured or falls back rather than creating another pool, then release the held workers and verify eventual termination/reaping returns the retired count/resource budget to baseline.
- Large invalidation / full-work case where relevant: bounded production receipts exercise persistent dispatch across selected worker counts.
- Optimized: one persistent worker set and reusable tile buffers across warm-up and measured repetitions.
- Speedup / memory / I/O / quality change: donor establishes the mechanism and verification boundary but does not provide a universal scaling claim in the PR summary.
- Variance / repetitions / raw samples: target-specific receipts and repetitions are required before promotion.

## Validation

Require equality among canonical/reference output, spawned optimized output, first persistent dispatch and subsequent persistent dispatches. In addition to ordinary repeated-success cases, force success → failure → success and success → cancellation → success sequences after partial worker activity. Verify that every reusable buffer, queue, completion record and dispatch generation is reset before the final success.

Validate the chosen retirement strategy with the matching fixture rather than one ambiguous ordering. For quiescent retirement, hold an old worker, prove successor admission remains blocked, then release/cancel and join/reap the worker before the successor begins. For generation-fenced retirement, pause an old worker specifically **after validation but before mutation**, retire its pool, start a successor with a distinct pool-incarnation identity and a deliberately colliding local generation value, then resume the worker and prove the atomic/locked publication step rejects it. Also stress repeated fenced retirements to the configured outstanding-retired-pool/resource bound, prove backpressure/fallback at the bound, and prove eventual worker termination/reaping releases all retired resources. Test shutdown, worker-count changes, topology fallback and completion-order independence.

For every workload-shaped dispatch used to support a parallelism or scaling claim, instrument **observed simultaneous active work** or an equivalent overlap metric. Record requested workers, configured/effective workers, topology source, observed peak concurrent activity, and preferably overlap duration/fraction or a concurrency histogram. Verify the metric itself against a deliberately serialized control. If a queue, lock, runtime limit, scheduler policy or cgroup causes configured workers to take turns without overlapping, report the execution as serialized/limited rather than treating worker participation as concurrency evidence. Compare the overlap data with measured speedup so apparent scaling cannot be attributed to concurrency that never occurred.

Measure startup and teardown separately, then evaluate amortized cost for the actual repetition horizon.

## Target-repo adaptation

Re-profile pool lifetime, worker count, SMT policy, buffer size, task granularity, expected number of dispatches, CPU allowance/cgroup constraints, failure-reset protocol, shutdown behavior, pool-incarnation generation strategy, publication-linearization primitive, maximum outstanding retired-pool/resource budget, reaping timeout/backpressure policy, and the concurrency-observation method. Do not infer CPU affinity or NUMA placement from topology-aware worker counting; those require separate mechanisms and evidence. If locks, queues, external libraries or runtime quotas can serialize the hot region, instrument overlap around the actual work rather than only around task submission.

## Failure modes

- The workload is too infrequent to amortize pool startup and retained resources.
- Reused buffers leak stale state between dispatches.
- A failed/cancelled dispatch leaves partial buffers, queue entries or completion state that contaminates the next generation.
- A worker from a retired generation resumes after replacement and publishes stale output, completion, queue or callback state into the succeeding dispatch.
- A check-then-write race lets a worker validate before retirement and publish after retirement because validation and mutation do not linearize atomically.
- A replacement reuses a generation value from a retired pool because the fence omits a distinct pool-incarnation identity.
- Repeated generation-fenced cancellations leave too many unreaped pools, threads or worker-local buffers alive and exhaust the bounded live-resource budget.
- SMT/logical workers increase contention or memory pressure.
- Container CPU allowance or topology changes after pool creation.
- Multiple workers participate but a lock, queue, runtime limit, scheduler or cgroup serializes the hot work, creating false concurrency evidence.
- Long-lived workers hold scarce memory/resources during idle periods.
- Async completion accidentally changes reduction/output order.

## Rollback trigger

Use spawned/canonical execution on any parity failure, stale-state leak, failed-dispatch reset failure, late retired-generation publication, non-linearizable publication fence, pool-incarnation reuse, retired-pool bound violation, shutdown/resource leak, topology mismatch, or lifecycle-adjusted slowdown for the target repetition horizon. Retire a pool immediately when a failure/cancellation leaves its reusable state uncertain. Start a replacement only after quiescence/join, or under a generation-fenced strategy whose `(pool-incarnation, dispatch-generation)` publication operation linearizes with retirement and remains within the configured outstanding-retired-resource bound. If reaping stalls at that bound, apply backpressure or fall back to spawned/canonical execution. Disable physical-first selection when topology detection is unreliable and record the fallback. If the optimization depends on parallel execution but workload-shaped measurements show no meaningful simultaneous overlap, withdraw the parallelism claim and re-profile or fall back rather than promoting the configured worker count as effective concurrency.

## Composition notes

Composes with `OPT-SOA-001` when workers own reusable local tiles and with `OPT-SIMD-001` inside each worker kernel. Re-measure with `OPT-PAR-001` because persistent worker counts can still oversubscribe libraries or nested parallel regions.