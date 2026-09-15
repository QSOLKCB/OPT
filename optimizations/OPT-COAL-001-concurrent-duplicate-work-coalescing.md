# OPT-COAL-001 — Concurrent duplicate-work coalescing

**Status:** Implemented external reference; target validation required  
**Domains:** services, CI, artifact generation, metadata, parsing, model/data loading

## Source evidence

- Jazco, "Request Coalescing": https://jazco.dev/2023/09/28/request-coalescing/
- `sources/JAZCO.md`

## Problem

Many callers request the same expensive computation concurrently before any caller has populated a reusable result, producing a thundering herd.

## Optimization problem contract

- X: target-supported request-key canonicalizations, authorization/equivalence scopes, shared-operation lifetime policies, waiter limits, overflow/backpressure policies, per-waiter cancellation/deadline/terminal-claim policies, retry/error-sharing policies, and result-ownership policies
- F: policies that coalesce only requests equivalent in both computation semantics and authorization/visibility scope, preserve authorization, timeout, cancellation, result, ownership, and error semantics for every joined caller, linearize cancellation/deadline against terminal delivery for each waiter, bound waiter memory, and never admit new waiters to a closing or terminal generation
- f: measured duplicate upstream evaluations and end-to-end/tail latency, including coalescer synchronization, waiter-memory, atomic terminal-claim, overflow/backpressure, and result-copy overhead
- d: minimize under the target's predeclared scalar or lexicographic ordering
- C: every joined caller receives exactly one terminal outcome valid for its original request semantics, authorization scope, ownership contract, cancellation state, and deadline; non-equivalent or authorization-distinct requests are never merged; one caller leaving cannot incorrectly cancel work still required by another caller; closing/terminal generations are not joinable; waiter overflow has an explicit bounded behavior
- B: target-specific concurrent-load test budget declared before tuning; no portable request count or duration is supplied here
- S: stop when the declared load-test budget is exhausted or further policy changes fail to produce a validated material improvement without violating C
- Variables: categorical / integer / mixed
- Search scope: local policy tuning within one coalescing boundary
- Objective behavior: noisy under concurrent load; semantic equivalence remains deterministic
- Information: derivative-free / black-box performance measurements
- Evaluation cost: moderate to expensive concurrent-load testing
- Constraints: semantic equivalence, authorization, ownership, waiter-memory, cancellation, deadline, terminal-claim, timeout, and resource constraints
- Parallelism: asynchronous / concurrent
- Exactness: exact request/result semantics; no approximation is introduced

## Preserved contract

Coalescing may merge only requests that are equivalent for the same **joinable generation** of the shared operation, including any tenant/principal/visibility context that affects whether the computation or its result may be shared. Each caller retains independent authorization, cancellation, timeout/deadline, result-ownership, and error semantics. A caller abandoning its wait must not by itself terminate a shared operation that still has live waiters. Once a generation enters cancellation, closure, success, or failure handling, it becomes non-joinable before later callers can attach. A configured waiter bound must never be exceeded silently. Each waiter reaches exactly one linearized terminal state; a waiter that has already cancelled or timed out cannot later receive the shared value/error.

## Optimization

Create an in-flight registry entry for a canonical equivalence key. The key must include every request attribute required to establish safe sharing, including authorization-relevant tenant/principal/visibility scope unless the target instead proves that the upstream result is globally shareable and independently authorizes each delivered result.

Atomically create the joinable generation **with the initiating caller already registered as its first waiter before invoking, scheduling, or otherwise allowing the upstream operation to run**. This prevents an immediately/synchronously completing operation from reaching terminal state with an empty waiter set. Only after the first waiter is durably part of the generation may the upstream work begin.

Equivalent later callers may register as independent waiters only while the generation is joinable and the configured waiter capacity remains. Waiter admission is atomic with capacity accounting. When the final waiter slot is already occupied, apply one explicit target policy rather than silently exceeding the bound: reject/return a documented overload or retryable-backpressure result, block/queue the caller behind a separately bounded admission mechanism, or use another bounded policy with explicit timeout/cancellation semantics. Starting an unconstrained parallel generation for the same equivalence key is not the default overflow behavior because it recreates the duplicate upstream load this pattern is intended to prevent. If a target deliberately permits overflow generations, that concurrency bound and duplicate-work tradeoff must be part of C/B and validated separately.

Represent each admitted waiter with an atomic terminal state, initially `pending`. Cancellation attempts atomically claim `pending -> cancelled`; timeout/deadline handling atomically claims `pending -> timed-out`. A terminal result/error notifier may claim `pending -> delivered-success` or `pending -> delivered-error` only if the waiter's declared deadline has not expired at the claim point. If the deadline is already expired, the notifier must instead leave/transition that waiter to the target's timed-out state and must not deliver the shared terminal value/error. For explicit cancellation racing completion, whichever atomic transition claims `pending` first wins; the losing transition is a no-op for that waiter. These claim semantics are part of the public request contract and must not depend on scheduler timing after the claim.

Cancellation and timeout are otherwise per waiter: when one waiter leaves through a winning cancellation/timeout claim, remove only that waiter from the live-waiter accounting. If live waiters remain, keep the shared generation joinable. If the last live waiter leaves and the policy calls for upstream cancellation, atomically mark the registry entry **closing/non-joinable** (or remove it from the joinable map) before sending the asynchronous cancellation request upstream. A new caller arriving after that transition must create a fresh generation rather than attach to work already being canceled. The closing generation may remain internally tracked until its terminal completion for cleanup/accounting, but it is not eligible for coalescing.

On upstream success or failure, atomically transition the generation to **terminal/non-joinable** (or remove it from the joinable map) **before** snapshotting the candidate waiter set or notifying any waiter. New callers arriving after that terminal transition must create a fresh generation and cannot attach to the completed one. Snapshot the waiter records, but do not treat membership in that snapshot as entitlement to delivery: for each waiter, perform the atomic per-waiter terminal claim described above immediately before delivery. A waiter whose cancellation/timeout claim already won is skipped.

Define result ownership explicitly. If a terminal-success claim wins and the terminal value is immutable/share-safe under the target API, the same immutable value may be delivered to all authorized success-claimed waiters. If callers normally receive mutable or caller-owned results, create an independent defensive clone/copy/copy-on-write handle for each waiter after its successful terminal claim and before delivery so one caller cannot observably mutate another caller's result. Deliver a terminal failure only to waiters whose `delivered-error` claim wins (or a per-caller wrapped equivalent where the API requires ownership/context), then retire/clean up the generation deterministically.

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

Add **terminal-delivery races** for both upstream success and upstream failure. Pause after the terminal waiter snapshot, then race explicit cancellation and deadline expiry against each waiter's delivery claim. Prove exactly one `pending -> terminal` transition wins, cancelled/timed-out waiters never receive a later value/error, completion that legitimately claims before cancellation preserves the declared completion result, and an already-expired deadline cannot be bypassed merely because the timeout worker has not run yet. Repeat under high concurrency and verify no waiter observes two terminal outcomes.

Add an **immediate synchronous-completion** fixture where the upstream operation can finish inline at launch. Prove the initiating caller was already registered before launch and always receives the terminal result/error unless its own cancellation/deadline claim wins under the same rules.

Add authorization-boundary fixtures: issue syntactically identical requests under different tenants, principals, roles, ACL/visibility scopes, or other authorization context. Prove they either map to different equivalence keys **or** that the shared upstream result is explicitly safe to reuse and each caller is independently authorized before delivery. Verify that a result produced under one authorization scope can never leak to another merely because the resource parameters match.

Add ownership-isolation fixtures for mutable results: deliver one coalesced computation to multiple callers, mutate one caller's returned object, and prove every other caller's result remains unchanged. If the API declares the shared value immutable, attempt prohibited mutation through all exposed aliases and verify the immutability/share-safety contract.

Add waiter-overflow races: fill the waiter list to one slot below the maximum, launch multiple equivalent callers concurrently for the final slot, and prove admission is linearizable, capacity is never exceeded, non-admitted callers receive exactly the documented backpressure/overflow behavior, and cancellation/timeouts of queued or rejected callers remain correct.

## Target-repo adaptation

Define key canonicalization, the authorization/visibility context that participates in equivalence, maximum waiter count, bounded overflow/backpressure semantics, result ownership/share-safety policy, per-waiter atomic terminal-state representation, cancellation/deadline winning semantics, the exact condition for canceling upstream work, the atomic create-with-first-waiter rule, the atomic closing/terminal non-joinable transitions, cleanup of retired generations, and whether failures are shared as terminal or retried under one explicit shared retry policy.

## Failure modes

Over-broad keys merge non-equivalent or authorization-distinct work; launching upstream work before registering the initiating waiter can strand that caller on synchronous completion; non-linearized cancellation/deadline versus delivery can produce late values/errors or double terminal outcomes; treating terminal snapshot membership as delivery entitlement can notify a waiter after it has timed out; coupling shared lifetime to the first caller can terminate valid waiters; leaving a canceled or terminal generation joinable can attach new callers to doomed/completed work; omitting authorization scope can leak results across principals/tenants; sharing a mutable result object can create cross-caller aliasing; undefined overflow semantics can exceed memory bounds, drop callers, or recreate duplicate upstream load; never canceling after all waiters leave can leak work; a hung upstream operation can stall many callers; ambiguous retry/error policy can cause correlated or duplicated work.

## Rollback trigger

Disable if coalescing changes any caller's authorization/cancellation/deadline/result/ownership/error semantics; if a cancelled/timed-out waiter can receive a later terminal value/error; if one waiter can observe two terminal outcomes; if an expired deadline can lose merely because timeout processing was delayed; if authorization-distinct requests are merged without independent delivery authorization; if one caller can cancel work required by another; if the initiating caller is stranded on immediate completion; if a new caller joins a closing/terminal generation; if the waiter bound or documented overflow behavior is violated; if mutable-result aliasing is possible; if shared operations leak; or if tail latency/failure amplification becomes unacceptable.
