# OPT-APPROX-001 — Contract-bounded approximation

**Status:** External production pattern + existing OPT need; target-specific proof/measurement required  
**Domains:** visualization, search, streaming, telemetry, simulation, audition DSP

## Source evidence

- https://jazco.dev/2025/02/19/imperfection/
- existing `OPT-DSP-001` approximation boundary
- `sources/JAZCO.md`

## Problem

Exact processing has unbounded or unacceptable cost even though the product/scientific contract permits a bounded loss of precision, completeness or freshness.

## Optimization problem contract

- Objective: reduce bounded resource/latency cost
- Constraint: declared error/degradation metric remains within `ε` or another explicit envelope
- Reference: exact path or exact fixture remains available for conformance

## Preserved contract

Approximation is admissible only when the contract explicitly permits it. A previously exact API cannot be silently weakened and still be called correctness-preserving.

## Optimization

Introduce a resource ceiling and degrade only along a declared dimension: sample/cull, lower level of detail, approximate search, bounded stale data, or reduced update frequency. Make the error surface measurable and reversible.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No exact target baseline has been established here.
- Optimized: No target approximation implementation has been benchmarked here.
- Speedup / memory reduction: No transferable claim; external production observations remain source evidence only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Measure error/degradation and resource savings together across ordinary, boundary and adversarial workloads. Keep an exact reference for differential evaluation where practical.

## Target-repo adaptation

Define `ε`, quality metric, workload distribution, escape hatch and exact-mode availability locally.

## Failure modes

Unmeasured quality loss, biased sampling, hidden rare-case failures, cumulative error and callers incorrectly assuming exact semantics.

## Rollback trigger

Disable when error exceeds the declared envelope, reference comparisons drift, or resource savings are not material.
