# OPT-CRIT-001 — Critical-path prioritization

**Status:** Proposed / OPT synthesis; target validation required  
**Domains:** UI, web, games, build systems, model/data loading, interactive pipelines

## Source evidence

- `davidsonfellipe/awesome-wpo` inspected at `84f32948a6298456d6a94cff64551f39f2666e6f`
- resource-hint, lazy-loading and prefetch references catalogued upstream
- `sources/WPO.md`

## Problem

Non-critical work competes with the dependency chain that determines user-visible or pipeline latency.

## Optimization problem contract

- X: target-supported task-priority, prefetch/precompute, lazy/deferred-work, speculation, speculative-input identity, mutation-control, commitment, critical-capacity reservation, preemption/cancellation, and speculation-admission policies
- F: policies that preserve all semantic deadlines, avoid externally visible speculative side effects before commitment, commit speculative results only from one stable effective-input generation, satisfy starvation/resource constraints, and enforce enough protected or promptly reclaimable capacity that speculative work cannot occupy every resource a newly arriving critical task may need
- f: measured end-to-end latency of the declared critical dependency path, including resource pressure introduced by speculation/deferment
- d: minimize
- C: critical outputs and semantic deadlines are preserved; speculative work is safely discardable; any speculative result is bound to a complete immutable snapshot or full-duration mutation witness, and validation of that witness is linearized with commitment so intervening or final-window A→B→A/input changes cannot be erased before visibility; deferred work completes before it becomes semantically required; and speculative occupancy cannot delay newly arriving critical work beyond the declared critical-start/latency bound because critical capacity is reserved, speculative work is preemptible/cancellable within a bounded reclaim latency, or speculation admission is hard-limited to leave sufficient headroom
- B: target-specific trace/benchmark budget covering cold/warm, hit/miss, wrong-speculation, stale-speculation, change/revert, and critical-arrival-under-saturation cases; no portable prediction horizon is supplied here
- S: stop when the declared budget is exhausted or a validated policy materially reduces critical-path latency without violating C
- Variables: categorical / conditional / mixed priority, deferment, prefetch, speculation, capacity-reservation, preemption, and admission policies
- Search scope: local critical-path policy tuning
- Objective behavior: noisy under realistic workload timing; semantic identity/deadline/capacity checks are deterministic
- Information: derivative-free / black-box latency measurements
- Evaluation cost: moderate to expensive end-to-end tracing/benchmarking
- Constraints: semantic deadlines, starvation, side effects, input identity/mutation freshness, commitment linearizability, protected/reclaimable critical capacity, memory/CPU/I/O, and target resource constraints
- Parallelism: asynchronous / concurrent execution is common; speculative dispatch must preserve enforceable critical headroom or bounded preemption
- Exactness: exact target semantics; speculative work may be discarded but not committed stale or allowed to violate critical-capacity guarantees

## Preserved contract

Deferred work must still complete before its semantic deadline. Speculative work must be discardable and must not create externally visible side effects before commitment. A speculative result may be committed/delivered only if it was produced from one coherent effective-input generation equivalent to the non-speculative reference path; endpoint equality after an intervening mutation is not sufficient, and a successful freshness check is not sufficient unless the checked identity remains authoritative through the commit that makes the result visible. Priority must also remain operational rather than nominal: speculation may not consume all capacity needed by a critical request that arrives after speculative work has started. The target must preserve a declared critical-start/latency bound using reserved capacity, bounded-latency preemption/cancellation, or hard admission limits that leave sufficient headroom for non-preemptible speculation.

## Optimization

Execute critical dependencies first; prefetch/precompute likely-soon work only when probability and resource policy justify it; lazily defer non-critical work; avoid work with no demonstrated demand.

Treat "spare at dispatch" as insufficient evidence that speculation is safe. Before launching speculative work, perform an **enforceable critical-capacity admission check**. For non-preemptible speculation, reserve the worker, I/O, accelerator, memory, connection, queue, or other resource capacity required by the declared critical workload, or hard-limit speculative concurrency/occupancy so worst-case admitted speculation cannot consume that headroom. For preemptible/cancellable speculation, define and enforce a maximum reclaim latency and ensure cancellation/preemption returns enough capacity before the critical-start/deadline bound can be violated. Capacity accounting/admission must be atomic enough that concurrent speculative launches cannot each observe the same final spare slot and collectively consume protected headroom.

Bind every speculative/precomputed result to a complete effective-input identity for the **full speculation-to-commit interval**. Prefer speculation against an immutable snapshot/version. If snapshots are unavailable, use a full-duration mutation/read lock or capture a monotonically increasing, non-reusable version/epoch for every mutable effective input. Every relevant mutation must advance its witness, including A→B→A changes that restore original bytes. A commit-time hash/identity comparison may supplement the mutation witness but must not be the sole freshness proof.

Freshness validation and commitment must be **one linearizable operation**. For lock-based targets, hold the mutation/read lock through the exact commit/publication/delivery transition that makes the speculative result externally visible. For epoch/version-based targets, use an atomic compare-and-commit/conditional transaction that verifies the complete coherent epoch vector is still the witnessed vector and, only if that comparison succeeds in the same atomic boundary, publishes the result. A separate `check epochs; later publish` sequence is not sufficient. If the compare-and-commit loses a race, discard the speculative result and execute/recompute from the current reference identity. Any lock violation, epoch change, incoherent witness, or untrackable mutable input likewise forces discard/recompute.

Commitment is the semantic boundary: no stale speculative result may become externally visible merely because the speculation itself had no side effects.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No target critical-path profile has been established here.
- Optimized: No target prioritization/prefetch policy has been benchmarked here.
- Speedup / memory reduction: No transferable claim; upstream WPO material supplies patterns and measurement guidance.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Trace the true dependency path and measure end-to-end latency, not only individual task duration. Test cold/warm, cache-hit/miss and wrong-speculation cases. Explicitly test semantic deadlines, starvation, cancellation, and that speculative work cannot expose side effects before commitment.

Add a **critical-arrival-under-speculation-saturation** race. Fill speculative work to the maximum admitted occupancy, then introduce a critical request requiring each protected resource class (for example a worker plus I/O or accelerator capacity). For reserved-capacity designs, prove the critical request can acquire the reserved capacity without waiting for non-preemptible speculative completion. For preemptible/cancellable designs, prove enough speculation is reclaimed within the declared maximum reclaim latency to satisfy the critical-start/deadline bound. For admission-bound designs, prove concurrent speculative launches cannot race past the headroom limit. Repeat with non-preemptible long-running speculation, simultaneous critical arrivals, and mixed-resource bottlenecks; a policy that merely observed spare capacity before dispatch must fail this fixture if it can later block the critical path.

Add stale-speculation fixtures with explicit **A→B→A** races. Start speculation from identity A, mutate the effective inputs to B while speculation reads/runs, then restore original bytes before demand/commitment. For snapshot-based targets, prove speculation consumed only immutable A. For lock-based targets, prove the mutation cannot interleave. For epoch/version-based targets, prove every mutation increments the monotonic witness and that the final witness exposes the intervening change even though endpoint content equals A. Also test delayed speculative completion, version rollback, and concurrent config/schema changes. Compare every committed speculative result against the non-speculative reference path for the exact committed identity.

Add a **final validation-to-commit race**. Pause immediately after the last ordinary witness comparison but before the result would become visible, then mutate an effective input. For lock-based designs, prove the mutation is blocked until after commitment. For epoch/version designs, prove the atomic compare-and-commit rejects the stale speculative result rather than publishing it. Repeat with A→B→A and multi-input epoch-vector changes. No fixture may pass by doing an ordinary comparison followed by a separate publication step.

## Target-repo adaptation

Criticality and prediction horizons are workload-specific. Re-profile after topology or user-flow changes. Define the complete effective-input identity for each speculative result and choose immutable snapshots, full-duration mutation locks, or monotonic epochs that record every intervening change. Define the linearization boundary that couples freshness validation to external commitment: lock-through-commit or atomic compare-and-commit. Specify exactly when a stale speculative result is discarded. Also define the **critical-capacity invariant** for every contended resource: how much capacity is reserved, what speculative occupancy ceiling applies, or which work is preemptible/cancellable and the maximum reclaim latency. Make admission/concurrency accounting race-safe, and do not treat currently idle capacity as sufficient if non-preemptible speculation can consume it before future critical arrivals. Do not rely on commit-time endpoint revalidation alone, or on check-then-publish epoch validation, to establish freshness.

## Failure modes

Speculation steals resources from critical work; non-preemptible speculation can fill every worker, I/O slot, accelerator slot, connection, or other bottleneck before a new critical request arrives; concurrent speculative launches can oversubscribe supposedly reserved headroom; preemption/cancellation can be too slow to protect the critical-start/deadline bound; lazy work causes later latency cliffs; priorities become stale; deferred tasks starve; semantic deadlines are missed; speculative side effects escape before commitment; A→B→A mutations can fool endpoint-only freshness checks; non-monotonic/reused epochs can erase intervening changes; a check-then-publish window can expose stale speculation after a successful freshness check; or stale speculative output is committed after its effective inputs changed.

## Rollback trigger

Immediately disable/revert the policy on any violation of C, including a required task missing its semantic deadline; a critical request being delayed beyond the declared start/latency bound because speculative work consumed protected capacity; a reservation/admission race allowing speculation to exceed its occupancy ceiling; preemption/cancellation failing to reclaim capacity within its declared bound; speculative work exposing an externally visible side effect before commitment; a speculative result being committed/delivered without an immutable snapshot/lock/monotonic mutation witness proving one coherent effective-input generation; or any test showing freshness validation can be separated from commitment so a mutation can win in between. Also disable it if critical-path latency or resource pressure worsens materially.
