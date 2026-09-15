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

- X: target-supported metric/fixture/statistic/threshold configurations for a performance-regression gate
- F: gate configurations based on a sufficiently characterized environment and workload, with statistically justified tolerance and no weakening of functional correctness or workload realism
- f: target-measured regression-detection quality together with CI noise/false-alarm rate and measurement overhead
- d: minimize missed material regressions and flaky/false failures under the target's predeclared multi-objective ordering
- C: the performance gate must not incentivize weakening tests, assertions, evidence, semantic coverage, or representative workload inputs
- B: target-specific calibration budget specifying repetitions, environment samples, and allowable CI/runtime measurement cost
- S: stop calibration when the declared sample budget is exhausted or the baseline/noise estimate is stable enough to justify the predeclared warning and hard thresholds

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
