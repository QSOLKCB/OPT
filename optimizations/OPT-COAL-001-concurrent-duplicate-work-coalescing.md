# OPT-COAL-001 — Concurrent duplicate-work coalescing

**Status:** Implemented external reference; target validation required  
**Domains:** services, CI, artifact generation, metadata, parsing, model/data loading

## Source evidence

- Jazco, "Request Coalescing": https://jazco.dev/2023/09/28/request-coalescing/
- `sources/JAZCO.md`

## Problem

Many callers request the same expensive computation concurrently before any caller has populated a reusable result, producing a thundering herd.

## Optimization problem contract

- X: target-supported request-key canonicalizations, authorization/equivalence scopes, shared-operation lifetime policies, waiter limits, overflow/backpressure policies, per-waiter cancellation policies, retry/error-sharing policies, and result-ownership policies
- F: policies that coalesce only requests equivalent in both computation semantics and authorization/visibility scope, preserve authorization, timeout, cancellation, result, ownership, and error semantics for every joined caller, bound waiter memory, and never admit new waiters to a closing or terminal generation
- f: measured duplicate upstream evaluations and end-to-end/tail latency, including coalescer synchronization, waiter-memory, overflow/backpressure, and result-copy overhead
- d: minimize under the target's predeclared scalar or lexicographic ordering
- C: every joined caller receives a result or error valid for its original request semantics, authorization scope, and ownership contract; non-equivalent or authorization-distinct requests are never merged; one caller leaving cannot incorrectly cancel work still required by another caller; closing/terminal generations are not joinable; waiter overflow has an explicit bounded behavior
- B: target-specific concurrent-load test budget declared before tuning; no portable request count or duration is supplied here
- S: stop when the declared load-test budget is exhausted or further policy changes fail to produce a validated material improvement without violating C
- Variables: categorical / integer / mixed
- Search scope: local policy tuning within one coalescing boundary
- Objective behavior: noisy under concurrent load; semantic equivalence remains deterministic
- Information: derivative-free / black-box performance measurements
- Evaluation cost: moderate to expensive concurrent-load testing
- Constraints: semantic equivalence, authorization, ownership, waiter-memory, cancellation, timeout, and resource constraints
- Parallelism: asynchronous / concurrent
- Exactness: exact request/result semantics; no approximation is introduced

## Preserved contract

Coalescing may merge only requests that are equivalent for the same **joinable generation** of the shared operation, including any tenant/principal/visibility context that affects whether the computation or its result may be shared. Each caller retains independent authorization, cancellation, timeout, result-ownership, and error semantics. A caller abandoning its wait must not by itself terminate a shared operation that still has live waiters. Once a generation enters cancellation, closure, success, or failure handling, it becomes non-joinable before later callers can attach. A configured waiter bound must never be exceeded silently.

## Optimization

Create an in-flight registry entry for a canonical equivalence key. The key must include every request attribute required to establish safe sharing, including authorization-relevant tenant/principal/visibility scope unless the target instead proves that the upstream result is globally shareable and independently authorizes each delivered result.

Atomically create the joinable generation **with the initiating caller already registered as its first waiter before invoking, scheduling, or otherwise allowing the upstream operation to run**. This prevents an immediately/synchronously completing operation from reaching terminal state with an empty waiter set. Only after the first waiter is durably part of the generation may the upstream work begin.

Equivalent later callers may register as independent waiters only while the generation is joinable and the configured waiter capacity remains. Waiter admission is atomic with capacity accounting. When the final waiter slot is already occupied, apply one explicit target policy rather than silently exceeding the bound: reject/return a documented overload or retryable-backpressure result, block/queue the caller behind a separately bounded admission mechanism, or use another bounded policy with explicit timeout/cancellation semantics. Starting an unconstrained parallel generation for the same equivalence key is not the default overflow behavior because it recreates the duplicate upstream load this pattern is intended to prevent. If a target deliberately permits overflow generations, that concurrency bound and duplicate-work tradeoff must be part of C/B and validated separately.

Cancellation and timeout are per waiter: when one waiter leaves, remove only that waiter. If live waiters remain, keep the shared generation joinable. If the last waiter leaves and the policy calls for upstream cancellation, atomically mark the registry entry **closing/non-joinable** (or remove it from the joinable map) before sending the asynchronous cancellation request upstream. A new caller arriving after that transition must create a fresh generation rather than attach to work already being canceled. The closing generation may remain internally tracked until its terminal completion for cleanup/accounting, but it is not eligible for coalescing.

On success or failure, atomically transition the generation to **terminal/non-joinable** (or remove it from the joinable map) **before** snapshotting the terminal waiter set or notifying any waiter. New callers arriving after that terminal transition must create a fresh generation and cannot attach to the completed one. Then snapshot the waiters still registered to that terminal generation.

Define result ownership explicitly. If the terminal value is immutable/share-safe under the target API, the same immutable value may be delivered to all authorized waiters. If callers normally receive mutable or caller-owned results, create an independent defensive clone/copy/copy-on-write handle for each waiter before delivery so one caller cannot observably mutate another caller's result. Deliver the shared terminal error (or per-caller wrapped equivalent where the API requires ownership/context) to the terminal waiter snapshot, then retire/clean up the generation deterministically.

Do not silently retry for only some joined callers; if shared retry is supported, its attempt limit, backoff, budget charging, authorization scope, and terminal error semantics must be part of the declared policy. Otherwise, a retry starts a new generation after the failed generation is retired.

This differs from caching: the reusable result does not exist yet.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; the Jazco implementation is source evidence for the mechanism.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Stress simultaneous identical and non-identical keys; inject upstream failures/timeouts; cancel the first caller while other waiters remain; cancel all waiters and verify the declared upstream-cancellation policy; race a new caller against the last-waiter cancellation transition and prove it never joins the closing generation; race a new caller against success/failure completion and prove the terminal generation is made non-joinable before waiter snapshot/notification; test waiter-specific deadlines; verify shared failure delivery and retry accounting; prove only one upstream evaluation occurs per joinable generation while all surviving callers terminate correctly.

Add an **immediate synchronous-completion** fixture where the upstream operation can finish inline at launch. Prove the initiating caller was already registered before launch and always receives the terminal result/error.

Add authorization-boundary fixtures: issue syntactically identical requests under different tenants, principals, roles, ACL/visibility scopes, or other authorization context. Prove they either map to different equivalence keys **or** that the shared upstream result is explicitly safe to reuse and each caller is independently authorized before delivery. Verify that a result produced under one authorization scope can never leak to another merely because the resource parameters match.

Add ownership-isolation fixtures for mutable results: deliver one coalesced computation to multiple callers, mutate one caller's returned object, and prove every other caller's result remains unchanged. If the API declares the shared value immutable, attempt prohibited mutation through all exposed aliases and verify the immutability/share-safety contract.

Add waiter-overflow races: fill the waiter list to one slot below the maximum, launch multiple equivalent callers concurrently for the final slot, and prove admission is linearizable, capacity is never exceeded, non-admitted callers receive exactly the documented backpressure/overflow behavior, and cancellation/timeouts of queued or rejected callers remain correct.

## Target-repo adaptation

Define key canonicalization, the authorization/visibility context that participates in equivalence, maximum waiter count, bounded overflow/backpressure semantics, result ownership/share-safety policy, per-waiter cancellation/deadline handling, the exact condition for canceling upstream work, the atomic create-with-first-waiter rule, the atomic closing/terminal non-joinable transitions, cleanup of retired generations, and whether failures are shared as terminal or retried under one explicit shared retry policy.

## Failure modes

Over-broad keys merge non-equivalent or authorization-distinct work; launching upstream work before registering the initiating waiter can strand that caller on synchronous completion; coupling shared lifetime to the first caller can terminate valid waiters; leaving a canceled or terminal generation joinable can attach new callers to doomed/completed work; snapshotting waiters before terminal closure can strand a late joiner; omitting authorization scope can leak results across principals/tenants; sharing a mutable result object can create cross-caller aliasing; undefined overflow semantics can exceed memory bounds, drop callers, or recreate duplicate upstream load; never canceling after all waiters leave can leak work; a hung upstream operation can stall many callers; ambiguous retry/error policy can cause correlated or duplicated work.

## Rollback trigger

Disable if coalescing changes any caller's authorization/cancellation/result/ownership/error semantics, merges authorization-distinct requests without independent delivery authorization, permits one caller to cancel work required by another, strands the initiating caller on immediate completion, allows a new caller to join a closing or terminal generation, exceeds the configured waiter bound, violates documented overflow/backpressure behavior, permits mutable-result aliasing across callers, leaks orphaned shared operations, increases tail latency materially, or creates unacceptable failure amplification.
