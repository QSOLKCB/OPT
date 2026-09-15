# OPT-COAL-001 — Concurrent duplicate-work coalescing

**Status:** Implemented external reference; target validation required  
**Domains:** services, CI, artifact generation, metadata, parsing, model/data loading

## Source evidence

- Jazco, "Request Coalescing": https://jazco.dev/2023/09/28/request-coalescing/
- `sources/JAZCO.md`

## Problem

Many callers request the same expensive computation concurrently before any caller has populated a reusable result, producing a thundering herd.

## Optimization problem contract

- X: target-supported request-key canonicalizations, authorization/equivalence scopes, result-ownership policies, shared-operation lifetime policies, waiter limits, per-waiter cancellation policies, and retry/error-sharing policies
- F: policies that coalesce only requests equivalent in both computation semantics and authorization/visibility scope, preserve authorization, timeout, cancellation, result-ownership, and error semantics for every joined caller, and never admit new waiters to a closing or terminal generation
- f: measured duplicate upstream evaluations and end-to-end/tail latency, including coalescer synchronization, cloning/copy-on-delivery cost where required, and waiter-memory overhead
- d: minimize under the target's predeclared scalar or lexicographic ordering
- C: every joined caller receives a result or error valid for its original request semantics, authorization scope, and ownership contract; non-equivalent or authorization-distinct requests are never merged; one caller leaving cannot incorrectly cancel work still required by another caller; closing/terminal generations are not joinable; mutable caller-owned results are never observably aliased across callers unless the target contract explicitly declares shared mutation semantics
- B: target-specific concurrent-load test budget declared before tuning; no portable request count or duration is supplied by this record
- S: stop when the declared load-test budget is exhausted or further policy changes fail to produce a validated material improvement without violating C

## Preserved contract

Coalescing may merge only requests that are equivalent for the same **joinable generation** of the shared operation, including any tenant/principal/visibility context that affects whether the computation or its result may be shared. Each caller retains independent authorization, cancellation, timeout, and result-ownership semantics. A caller abandoning its wait must not by itself terminate a shared operation that still has live waiters. Once a generation enters cancellation, closure, success, or failure handling, it becomes non-joinable before later callers can attach.

If the upstream result is immutable or explicitly share-safe, all waiters may observe the same value. If callers normally receive mutable/caller-owned objects, the coalescer must preserve isolation by cloning/materializing an independent result per waiter, using copy-on-write with equivalent isolation, or another mechanism that makes one caller's mutation unobservable to other callers. Returning the same mutable object to independent callers is a contract change unless shared mutation is explicitly part of the target API.

## Optimization

Create an in-flight registry entry for a canonical equivalence key. The key must include every request attribute required to establish safe sharing, including authorization-relevant tenant/principal/visibility scope unless the target instead proves that the upstream result is globally shareable and independently authorizes each delivered result. The first caller starts the shared upstream operation, but **does not own its lifetime**. Every equivalent caller registers as an independent waiter on the currently joinable generation.

Cancellation and timeout are per waiter: when one waiter leaves, remove only that waiter. If live waiters remain, keep the shared generation joinable. If the last waiter leaves and the policy calls for upstream cancellation, atomically mark the registry entry **closing/non-joinable** (or remove it from the joinable map) before sending the asynchronous cancellation request upstream. A new caller arriving after that transition must create a fresh generation rather than attach to work already being canceled. The closing generation may remain internally tracked until its terminal completion for cleanup/accounting, but it is not eligible for coalescing.

On success or failure, atomically transition the generation to **terminal/non-joinable** (or remove it from the joinable map) **before** snapshotting the terminal waiter set or notifying any waiter. New callers arriving after that terminal transition must create a fresh generation and cannot attach to the completed one. Then snapshot the waiters still registered to that terminal generation. For each waiter, independently authorize delivery and apply the declared result-ownership policy: deliver the same object only when it is immutable/share-safe, otherwise clone/materialize an isolated caller-owned result (or equivalent copy-on-write view) before delivery. Deliver the shared terminal error under the declared error semantics, then retire/clean up the generation deterministically. Do not silently retry for only some joined callers; if shared retry is supported, its attempt limit, backoff, budget charging, authorization scope, ownership semantics, and terminal error semantics must be part of the declared policy. Otherwise, a retry starts a new generation after the failed generation is retired.

This differs from caching: the reusable result does not exist yet.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; the Jazco implementation is source evidence for the mechanism.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Stress simultaneous identical and non-identical keys; inject upstream failures/timeouts; cancel the first caller while other waiters remain; cancel all waiters and verify the declared upstream-cancellation policy; race a new caller against the last-waiter cancellation transition and prove it never joins the closing generation; race a new caller against success/failure completion and prove the terminal generation is made non-joinable before waiter snapshot/notification; test waiter-specific deadlines; verify shared failure delivery and retry accounting; prove only one upstream evaluation occurs per joinable generation while all surviving callers terminate correctly.

Add authorization-boundary fixtures: issue syntactically identical requests under different tenants, principals, roles, ACL/visibility scopes, or other authorization context. Prove they either map to different equivalence keys **or** that the shared upstream result is explicitly safe to reuse and each caller is independently authorized before delivery. Verify that a result produced under one authorization scope can never leak to another merely because the resource parameters match.

Add ownership-isolation fixtures for mutable results: coalesce multiple callers, mutate one caller's returned object after delivery, and prove every other caller's result remains unchanged and reference-equivalent to an independent call. Test nested/container mutation, retained references, and any copy-on-write transition. If the target declares immutable/share-safe results, attempt mutation or alias observation and verify the immutability/share-safety guarantee rather than assuming it.

## Target-repo adaptation

Define key canonicalization, the authorization/visibility context that participates in equivalence, result ownership/mutability rules, cloning or copy-on-write strategy where needed, maximum waiter count, per-waiter cancellation/deadline handling, the exact condition for canceling upstream work, the atomic closing/terminal non-joinable transitions, cleanup of retired generations, and whether failures are shared as terminal or retried under one explicit shared retry policy.

## Failure modes

Over-broad keys merge non-equivalent or authorization-distinct work; returning one mutable object to independent callers can create cross-caller corruption through aliasing; coupling shared lifetime to the first caller can terminate valid waiters; leaving a canceled or terminal generation joinable can attach new callers to doomed/completed work; snapshotting waiters before terminal closure can strand a late joiner; omitting authorization scope can leak results across principals/tenants; never canceling after all waiters leave can leak work; a hung upstream operation can stall many callers; unbounded waiter lists amplify memory; ambiguous retry/error policy can cause correlated or duplicated work.

## Rollback trigger

Disable if coalescing changes any caller's authorization/cancellation/result/error/ownership semantics, exposes mutable result aliasing between callers, merges authorization-distinct requests without independent delivery authorization, permits one caller to cancel work required by another, allows a new caller to join a closing or terminal generation, strands a late joiner during terminal notification, leaks orphaned shared operations, increases tail latency materially, or creates unacceptable failure amplification.
