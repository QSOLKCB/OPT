# OPT-BUDGET-001 — Performance regression budgets

**Status:** Established engineering pattern; enforcement must be environment-scoped  
**Domains:** CI, web, numerical kernels, builds, services, DSP

## Source evidence

- `davidsonfellipe/awesome-wpo` inspected at `84f32948a6298456d6a94cff64551f39f2666e6f`
- performance-budget tooling and measurement resources catalogued upstream
- `sources/WPO.md`

## Problem

Small performance regressions accumulate because performance is measured occasionally but not guarded as an engineering contract.

## Optimization problem contract

- Metric: explicitly named latency/throughput/memory/I/O quantity
- Fixture/environment: pinned or sufficiently characterized
- Baseline distribution: repeated observations
- Budget: warning/hard boundary with justified statistical tolerance

## Preserved contract

A performance gate may not incentivize weakening functional tests, correctness, evidence or workload realism.

## Optimization

Turn a stable, reproducible performance expectation into a regression gate. Compare distributions or robust summaries where noise matters; separate machine/environment drift from code regression; keep cold/warm claims distinct.

## Before / after evidence

- Environment: No controlled target-repository budget calibration has been run for this OPT record.
- Baseline: No target baseline distribution is claimed here.
- Optimized: Not applicable until a target repository adopts and calibrates a performance budget.
- Speedup / memory reduction: This pattern protects performance; it does not itself claim a speedup.
- Variance / repetitions: Must be established in the target environment before a hard threshold is promoted.

## Validation

Calibrate variance before setting the threshold. Self-test the gate with known fast/slow fixtures and preserve raw samples where practical.

## Target-repo adaptation

Never copy another project's milliseconds, bundle sizes or thresholds. Establish the target's own baseline and noise envelope.

## Failure modes

Flaky gates from uncontrolled runners, benchmark gaming, stale fixtures, hardware drift and thresholds so loose they provide no protection.

## Rollback trigger

Temporarily disable only when the measurement environment is proven invalid; fix/recalibrate the benchmark rather than deleting the budget because code regressed.
