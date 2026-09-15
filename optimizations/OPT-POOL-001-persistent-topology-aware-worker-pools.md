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
- F: Candidates preserving exact output/checksum parity, deterministic work ownership and reduction, bounded live resources, explicit topology fallback, and correct shutdown/error handling.
- f: Total or amortized runtime across the expected repetition horizon, including pool lifecycle cost where relevant, plus resource/scaling evidence.
- d: Minimize lifecycle-adjusted runtime while preserving deterministic semantics; prefer simpler scheduling when gains are negligible.
- C: Completion order must not alter observable results, topology claims must match detected evidence, and persistent workers must not retain stale per-dispatch state.
- B: Bounded worker/schedule/tile sweeps and repeated dispatches on the target execution environment.
- S: Stop when the expected repetition horizon and topology policy have a repeatable useful winner, or retain spawned/canonical execution when startup amortization is insufficient.
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

## Optimization

Create workers once, allocate their reusable local buffers once, and dispatch repeated jobs through the persistent pool. Give each worker a stable deterministic range or identity. Allow workers to finish independently, but collect/reduce results under a deterministic ordering rule when arithmetic or output order requires it.

Expose topology policy explicitly. A `physical-first` policy may cap workers at detected physical cores; a `logical` policy may include SMT threads. Detection must fail softly and record the fallback instead of pretending unavailable topology data is authoritative.

Separate steady-state dispatch timing from startup/teardown, then include lifecycle cost when deciding whether persistence is worthwhile for the real repetition horizon.

## Before / after evidence

- Environment: GALAXY PR #13 verifies Linux x86-64, Linux ARM64, macOS ARM64 and Windows x86-64 command/parity surfaces.
- Workload/fixture: repeated worker-local SoA executions over deterministic resident ranges.
- Cold baseline: spawned worker-local SoA creates worker threads for each complete execution.
- Warm/no-op baseline where relevant: persistent steady-state dispatch excludes startup but records pool startup separately.
- Small invalidation / partial-work case where relevant: repeated first/second dispatch parity verifies reused state does not leak.
- Large invalidation / full-work case where relevant: bounded production receipts exercise persistent dispatch across selected worker counts.
- Optimized: one persistent worker set and reusable tile buffers across warm-up and measured repetitions.
- Speedup / memory / I/O / quality change: donor establishes the mechanism and verification boundary but does not provide a universal scaling claim in the PR summary.
- Variance / repetitions / raw samples: target-specific receipts and repetitions are required before promotion.

## Validation

Require equality among canonical/reference output, spawned optimized output, first persistent dispatch and subsequent persistent dispatches. Test repeated reuse, shutdown, worker-count changes, topology fallback and completion-order independence. Record requested/effective workers and topology source. Measure startup and teardown separately, then evaluate amortized cost for the actual repetition horizon.

## Target-repo adaptation

Re-profile pool lifetime, worker count, SMT policy, buffer size, task granularity, expected number of dispatches, CPU allowance/cgroup constraints and shutdown behavior. Do not infer CPU affinity or NUMA placement from topology-aware worker counting; those require separate mechanisms and evidence.

## Failure modes

- The workload is too infrequent to amortize pool startup and retained resources.
- Reused buffers leak stale state between dispatches.
- SMT/logical workers increase contention or memory pressure.
- Container CPU allowance or topology changes after pool creation.
- Long-lived workers hold scarce memory/resources during idle periods.
- Async completion accidentally changes reduction/output order.

## Rollback trigger

Use spawned/canonical execution on any parity failure, stale-state leak, shutdown/resource leak, topology mismatch, or lifecycle-adjusted slowdown for the target repetition horizon. Disable physical-first selection when topology detection is unreliable and record the fallback.

## Composition notes

Composes with `OPT-SOA-001` when workers own reusable local tiles and with `OPT-SIMD-001` inside each worker kernel. Re-measure with `OPT-PAR-001` because persistent worker counts can still oversubscribe libraries or nested parallel regions.