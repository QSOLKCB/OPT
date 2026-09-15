# OPT-COAL-001 — Concurrent duplicate-work coalescing

**Status:** Implemented external reference; target validation required  
**Domains:** services, CI, artifact generation, metadata, parsing, model/data loading

## Source evidence

- Jazco, "Request Coalescing": https://jazco.dev/2023/09/28/request-coalescing/
- `sources/JAZCO.md`

## Problem

Many callers request the same expensive computation concurrently before any caller has populated a reusable result, producing a thundering herd.

## Optimization problem contract

- X: target-supported request-key canonicalizations, shared-operation lifetime policies, waiter limits, per-waiter cancellation policies, and retry/error-sharing policies
- F: policies that coalesce only semantically equivalent requests and preserve authorization, timeout, cancellation, result, and error semantics for every joined caller
- f: measured duplicate upstream evaluations and end-to-end/tail latency, including coalescer synchronization and waiter-memory overhead
- d: minimize under the target's predeclared scalar or lexicographic ordering
- C: every joined caller receives a result or error valid for its original request semantics; non-equivalent requests are never merged; one caller leaving cannot incorrectly cancel work still required by another caller
- B: target-specific concurrent-load test budget declared before tuning; no portable request count or duration is supplied by this record
- S: stop when the declared load-test budget is exhausted or further policy changes fail to produce a validated material improvement without violating C

## Preserved contract

Coalescing may merge only requests that are semantically equivalent for the shared operation. Each caller retains independent cancellation and timeout semantics. A caller abandoning its wait must not by itself terminate a shared operation that still has live waiters, and authorization/result/error semantics must remain explicit.

## Optimization

Create an in-flight registry entry for the canonical request key. The first caller starts the shared upstream operation, but **does not own its lifetime**. Every equivalent caller registers as an independent waiter on that shared operation.

Cancellation and timeout are per waiter: when one waiter leaves, remove only that waiter. Cancel the upstream operation only when no live waiters remain, or when a separately documented target policy proves that early cancellation is safe. On success or failure, deliver the same shared terminal result/error to all waiters that are still registered, then remove the in-flight entry deterministically. Do not silently retry for only some joined callers; if shared retry is supported, its attempt limit, backoff, budget charging, and terminal error semantics must be part of the declared policy. Otherwise, a retry starts a new operation after the failed entry is removed.

This differs from caching: the reusable result does not exist yet.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; the Jazco implementation is source evidence for the mechanism.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Stress simultaneous identical and non-identical keys; inject upstream failures/timeouts; cancel the first caller while other waiters remain; cancel all waiters and verify the declared upstream-cancellation policy; test waiter-specific deadlines; verify shared failure delivery and retry accounting; prove only one upstream evaluation occurs for a coalesced key while all surviving callers terminate correctly.

## Target-repo adaptation

Define key canonicalization, maximum waiter count, per-waiter cancellation/deadline handling, the exact condition for canceling upstream work, and whether failures are shared as terminal or retried under one explicit shared retry policy.

## Failure modes

Over-broad keys merge non-equivalent work; coupling shared lifetime to the first caller can terminate valid waiters; never canceling after all waiters leave can leak work; a hung upstream operation can stall many callers; unbounded waiter lists amplify memory; ambiguous retry/error policy can cause correlated or duplicated work.

## Rollback trigger

Disable if coalescing changes any caller's cancellation/result/error semantics, permits one caller to cancel work required by another, leaks orphaned shared operations, increases tail latency materially, or creates unacceptable failure amplification.
