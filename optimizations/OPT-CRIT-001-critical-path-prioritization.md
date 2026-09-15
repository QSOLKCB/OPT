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

- Classify work: critical now / likely soon / deferrable / unnecessary
- Objective: reduce end-to-end critical-path latency
- Constraints: no starvation, stale-state or correctness violation from deferral/speculation

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
