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

A failed or cancelled dispatch may be followed by reuse only after every worker-local buffer, queue, completion flag and dispatch-generation marker is returned to a known clean state. If that reset cannot be proven complete, retire the pool. A retired pool must not be replaced while any worker from its dispatch generation can still publish externally visible state unless every such publication is guarded by a generation fence that rejects retired generations. Otherwise require full quiescence/join of the retired workers before the replacement pool may begin accepting work.

Concurrency evidence is part of the claim boundary rather than the computation contract. A pool may involve multiple workers yet still execute effectively serially because of locks, queue policy, scheduler throttling, cgroup limits or runtime serialization. Such a path can still be semantically correct, but it must not be described as providing parallel execution unless overlapping active work is actually observed.

## Optimization

Create workers once, allocate their reusable local buffers once, and dispatch repeated jobs through the persistent pool. Give each worker a stable deterministic range or identity. Allow workers to finish independently, but collect/reduce results under a deterministic ordering rule when arithmetic or output order requires it.

Expose topology policy explicitly. A `physical-first` policy may cap workers at detected physical cores; a `logical` policy may include SMT threads. Detection must fail softly and record the fallback instead of pretending unavailable topology data is authoritative.

Treat dispatch completion as a state transition. Successful completion must leave all reusable state ready for the next generation. Failure or cancellation must either run the same complete reset protocol or retire the pool so partial state cannot leak into a later dispatch. Retirement is not sufficient by itself: before a successor dispatch begins, either join/quiesce every worker from the retired generation or enforce a generation check on every write to shared output, completion state, queues, callbacks and other externally visible publication points so a late retired worker is unable to mutate successor state.

Separate **worker participation** from **simultaneous overlap**. Instrument workload-shaped dispatches with an active-worker counter, timestamped task intervals, scheduler/runtime tracing, or another measurement that can establish how much work actually overlapped. Record at least the observed peak simultaneous active work and, where useful, overlap duration/fraction or a concurrency histogram. A queue that eventually touches every worker but runs only one task at a time is not evidence of parallel execution.

Separate steady-state dispatch timing from startup/teardown, then include lifecycle cost when deciding whether persistence is worthwhile for the real repetition horizon.

## Before / after evidence

- Environment: GALAXY PR #13 verifies Linux x86-64, Linux ARM64, macOS ARM64 and Windows x86-64 command/parity surfaces.
- Workload/fixture: repeated worker-local SoA executions over deterministic resident ranges.
- Cold baseline: spawned worker-local SoA creates worker threads for each complete execution.
- Warm/no-op baseline where relevant: persistent steady-state dispatch excludes startup but records pool startup separately.
- Small invalidation / partial-work case where relevant: repeated first/second dispatch parity verifies reused state does not leak.
- Cancellation-generation fence fixture: pause an old-generation worker after partial activity, cancel and retire its pool, start the succeeding dispatch, then resume the paused worker. The fixture must prove either that replacement waited for old-worker quiescence/join or that every attempted late publication from the retired generation is rejected and cannot alter successor output, queues, completion state or external callbacks.
- Large invalidation / full-work case where relevant: bounded production receipts exercise persistent dispatch across selected worker counts.
- Optimized: one persistent worker set and reusable tile buffers across warm-up and measured repetitions.
- Speedup / memory / I/O / quality change: donor establishes the mechanism and verification boundary but does not provide a universal scaling claim in the PR summary.
- Variance / repetitions / raw samples: target-specific receipts and repetitions are required before promotion.

## Validation

Require equality among canonical/reference output, spawned optimized output, first persistent dispatch and subsequent persistent dispatches. In addition to ordinary repeated-success cases, force success → failure → success and success → cancellation → success sequences after partial worker activity. Verify that every reusable buffer, queue, completion record and dispatch generation is reset before the final success. When the affected pool is retired, run a late-worker fixture that deliberately holds one old-generation worker across cancellation until after the successor dispatch has started, then resumes it. Accept replacement only if the old generation was fully quiesced/joined before successor start or if generation fences reject every late externally visible publication from that worker. Test shutdown, worker-count changes, topology fallback and completion-order independence.

For every workload-shaped dispatch used to support a parallelism or scaling claim, instrument **observed simultaneous active work** or an equivalent overlap metric. Record requested workers, configured/effective workers, topology source, observed peak concurrent activity, and preferably overlap duration/fraction or a concurrency histogram. Verify the metric itself against a deliberately serialized control. If a queue, lock, runtime limit, scheduler policy or cgroup causes configured workers to take turns without overlapping, report the execution as serialized/limited rather than treating worker participation as concurrency evidence. Compare the overlap data with measured speedup so apparent scaling cannot be attributed to concurrency that never occurred.

Measure startup and teardown separately, then evaluate amortized cost for the actual repetition horizon.

## Target-repo adaptation

Re-profile pool lifetime, worker count, SMT policy, buffer size, task granularity, expected number of dispatches, CPU allowance/cgroup constraints, failure-reset protocol, shutdown behavior, and the concurrency-observation method. Do not infer CPU affinity or NUMA placement from topology-aware worker counting; those require separate mechanisms and evidence. If locks, queues, external libraries or runtime quotas can serialize the hot region, instrument overlap around the actual work rather than only around task submission.

## Failure modes

- The workload is too infrequent to amortize pool startup and retained resources.
- Reused buffers leak stale state between dispatches.
- A failed/cancelled dispatch leaves partial buffers, queue entries or completion state that contaminates the next generation.
- A worker from a retired generation resumes after replacement and publishes stale output, completion, queue or callback state into the succeeding dispatch.
- SMT/logical workers increase contention or memory pressure.
- Container CPU allowance or topology changes after pool creation.
- Multiple workers participate but a lock, queue, runtime limit, scheduler or cgroup serializes the hot work, creating false concurrency evidence.
- Long-lived workers hold scarce memory/resources during idle periods.
- Async completion accidentally changes reduction/output order.

## Rollback trigger

Use spawned/canonical execution on any parity failure, stale-state leak, failed-dispatch reset failure, late retired-generation publication, shutdown/resource leak, topology mismatch, or lifecycle-adjusted slowdown for the target repetition horizon. Retire a pool immediately when a failure/cancellation leaves its reusable state uncertain, and do not start a replacement until the retired generation is quiescent/joined or every externally visible publication is generation-fenced. Disable physical-first selection when topology detection is unreliable and record the fallback. If the optimization depends on parallel execution but workload-shaped measurements show no meaningful simultaneous overlap, withdraw the parallelism claim and re-profile or fall back rather than promoting the configured worker count as effective concurrency.

## Composition notes

Composes with `OPT-SOA-001` when workers own reusable local tiles and with `OPT-SIMD-001` inside each worker kernel. Re-measure with `OPT-PAR-001` because persistent worker counts can still oversubscribe libraries or nested parallel regions.