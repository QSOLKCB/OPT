# OPT-CRIT-001 — Critical-path prioritization

**Status:** Established performance-engineering pattern; target validation required  
**Domains:** UI, web, games, build systems, model/data loading, interactive pipelines

## Source evidence

- `davidsonfellipe/awesome-wpo` inspected at `84f32948a6298456d6a94cff64551f39f2666e6f`
- resource-hint, lazy-loading and prefetch references catalogued upstream
- `sources/WPO.md`

## Problem

Non-critical work competes with the dependency chain that determines user-visible or pipeline latency.

## Optimization problem contract

- X: target-supported task-priority, prefetch/precompute, lazy/deferred-work, and speculation policies
- F: policies that preserve all semantic deadlines, avoid externally visible speculative side effects before commitment, and satisfy starvation/resource constraints
- f: measured end-to-end latency of the declared critical dependency path, including resource pressure introduced by speculation/deferment
- d: minimize
- C: critical outputs and semantic deadlines are preserved; speculative work is safely discardable; deferred work completes before it becomes semantically required
- B: target-specific trace/benchmark budget covering cold/warm, hit/miss, and wrong-speculation cases; no portable prediction horizon is supplied here
- S: stop when the declared budget is exhausted or a validated policy materially reduces critical-path latency without violating C

## Preserved contract

Deferred work must still complete before its semantic deadline. Speculative work must be discardable and must not create externally visible side effects before commitment.

## Optimization

Execute critical dependencies first; prefetch/precompute likely-soon work only when probability and spare resources justify it; lazily defer non-critical work; avoid work with no demonstrated demand.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No target critical-path profile has been established here.
- Optimized: No target prioritization/prefetch policy has been benchmarked here.
- Speedup / memory reduction: No transferable claim; upstream WPO material supplies patterns and measurement guidance.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Trace the true dependency path and measure end-to-end latency, not only individual task duration. Test cold/warm, cache-hit/miss and wrong-speculation cases.

## Target-repo adaptation

Criticality and prediction horizons are workload-specific. Re-profile after topology or user-flow changes.

## Failure modes

Speculation steals resources from critical work, lazy work causes later latency cliffs, priorities become stale, or deferred tasks starve.

## Rollback trigger

Disable speculative/deferred policy if critical-path latency or resource pressure worsens materially.
