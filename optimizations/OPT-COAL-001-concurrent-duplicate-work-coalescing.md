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
- C: every joined caller receives a result or error valid for its original request semantics; non-equivalent requests are never merged; one caller leaving cannot incorrectly cancel work still required by another caller; once a shared generation enters cancellation/closure it is no longer joinable by new callers
- B: target-specific concurrent-load test budget declared before tuning; no portable request count or duration is supplied by this record
- S: stop when the declared load-test budget is exhausted or further policy changes fail to produce a validated material improvement without violating C

## Preserved contract

Coalescing may merge only requests that are semantically equivalent for the same **joinable generation** of the shared operation. Each caller retains independent cancellation and timeout semantics. A caller abandoning its wait must not by itself terminate a shared operation that still has live waiters. Once the last waiter leaves and cancellation is initiated, that generation is closed to new joiners before upstream cancellation proceeds asynchronously.

## Optimization

Create an in-flight registry entry for the canonical request key. The first caller starts the shared upstream operation, but **does not own its lifetime**. Every equivalent caller registers as an independent waiter on the currently joinable generation.

Cancellation and timeout are per waiter: when one waiter leaves, remove only that waiter. If live waiters remain, keep the shared generation joinable. If the last waiter leaves and the policy calls for upstream cancellation, atomically mark the registry entry **closing/non-joinable** (or remove it from the joinable map) before sending the asynchronous cancellation request upstream. A new caller arriving after that transition must create a fresh generation rather than attach to work already being canceled. The closing generation may remain internally tracked until its terminal completion for cleanup/accounting, but it is not eligible for coalescing.

On success or failure, deliver the same shared terminal result/error to all waiters still registered to that generation, then remove/retire the entry deterministically. Do not silently retry for only some joined callers; if shared retry is supported, its attempt limit, backoff, budget charging, and terminal error semantics must be part of the declared policy. Otherwise, a retry starts a new generation after the failed generation is retired.

This differs from caching: the reusable result does not exist yet.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; the Jazco implementation is source evidence for the mechanism.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Stress simultaneous identical and non-identical keys; inject upstream failures/timeouts; cancel the first caller while other waiters remain; cancel all waiters and verify the declared upstream-cancellation policy; race a new caller against the last-waiter cancellation transition and prove it never joins the closing generation; test waiter-specific deadlines; verify shared failure delivery and retry accounting; prove only one upstream evaluation occurs per joinable generation while all surviving callers terminate correctly.

## Target-repo adaptation

Define key canonicalization, maximum waiter count, per-waiter cancellation/deadline handling, the exact condition for canceling upstream work, the atomic closing/non-joinable transition, cleanup of retired generations, and whether failures are shared as terminal or retried under one explicit shared retry policy.

## Failure modes

Over-broad keys merge non-equivalent work; coupling shared lifetime to the first caller can terminate valid waiters; leaving a canceled generation joinable can attach new callers to doomed work; never canceling after all waiters leave can leak work; a hung upstream operation can stall many callers; unbounded waiter lists amplify memory; ambiguous retry/error policy can cause correlated or duplicated work.

## Rollback trigger

Disable if coalescing changes any caller's cancellation/result/error semantics, permits one caller to cancel work required by another, allows a new caller to join a closing/canceled generation, leaks orphaned shared operations, increases tail latency materially, or creates unacceptable failure amplification.
