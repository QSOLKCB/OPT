# OPT-COAL-001 — Concurrent duplicate-work coalescing

**Status:** Implemented external reference; target validation required  
**Domains:** services, CI, artifact generation, metadata, parsing, model/data loading

## Source evidence

- Jazco, "Request Coalescing": https://jazco.dev/2023/09/28/request-coalescing/
- `sources/JAZCO.md`

## Problem

Many callers request the same expensive computation concurrently before any caller has populated a reusable result, producing a thundering herd.

## Optimization problem contract

- Key: canonical identity of equivalent in-flight requests
- Objective: minimize duplicate concurrent evaluations
- Hard constraint: all joined callers must receive a result/error valid for their request semantics

## Preserved contract

Coalescing may merge only requests that are semantically equivalent for the shared operation. Cancellation, timeout, authorization and error semantics must remain explicit.

## Optimization

Make the first caller the owner of an in-flight operation. Equivalent callers subscribe to that future/result instead of starting duplicate work. Remove the in-flight entry deterministically on completion/failure.

This differs from caching: the reusable result does not exist yet.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; the Jazco implementation is source evidence for the mechanism.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Stress simultaneous identical and non-identical keys; inject owner failures/timeouts; prove only one upstream evaluation occurs for a coalesced key while all callers terminate correctly.

## Target-repo adaptation

Define key canonicalization, maximum waiter count, cancellation semantics and whether errors are shared or retried.

## Failure modes

Over-broad keys merge non-equivalent work; a hung owner can stall many callers; unbounded waiter lists amplify memory; shared error policy may cause correlated failure.

## Rollback trigger

Disable if coalescing changes request semantics, increases tail latency materially, or creates unacceptable failure amplification.
