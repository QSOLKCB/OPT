# OPT-BUDGET-001 — Performance regression budgets

**Status:** Proposed / OPT synthesis; target calibration required  
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
- C: the performance gate must not incentivize weakening tests, assertions, evidence, semantic coverage, or representative workload inputs; the gate itself must continue to detect known regressions and accept known-good controls within the declared false-positive/false-negative envelope
- B: target-specific calibration budget specifying repetitions, environment samples, and allowable CI/runtime measurement cost
- S: stop calibration when the declared sample budget is exhausted or the baseline/noise estimate is stable enough to justify the predeclared warning and hard thresholds
- Variables: continuous / integer / categorical / mixed metric, statistic, fixture, and threshold choices
- Search scope: local gate/calibration tuning
- Objective behavior: noisy / stochastic measurement distributions
- Information: derivative-free statistical observations
- Evaluation cost: moderate to expensive depending on repetitions and fixture scale
- Constraints: functional correctness, representative workload, statistical tolerance, runner/environment characterization, false-positive/false-negative, and CI-overhead constraints
- Parallelism: sequential or synchronous-batch calibration; parallel sampling only when runner interference is characterized
- Exactness: no semantic approximation; statistical tolerance/noise handling is explicit

## Preserved contract

A performance gate may not incentivize weakening functional tests, correctness, evidence or workload realism. The gate is valid only while its fixture, environment characterization, detection sensitivity and measurement overhead remain inside their declared contract.

## Optimization

Turn a stable, reproducible performance expectation into a regression gate. Compare distributions or robust summaries where noise matters; separate machine/environment drift from code regression; keep cold/warm claims distinct. Keep known-fast and known-regressed control fixtures (or equivalent calibration cases) so the gate can periodically prove it still distinguishes acceptable from materially regressed behavior.

## Before / after evidence

- Environment: No controlled target-repository budget calibration has been run for this OPT record.
- Baseline: No target baseline distribution is claimed here.
- Optimized: Not applicable until a target repository adopts and calibrates a performance budget.
- Speedup / memory reduction: This pattern protects performance; it does not itself claim a speedup.
- Variance / repetitions: Must be established in the target environment before a hard threshold is promoted.

## Validation

Calibrate variance before setting the threshold. Self-test the gate with known-good and known-regressed fixtures and preserve raw samples where practical. Re-run these controls after runner/toolchain changes and periodically enough to detect stale fixtures or sensitivity drift. Measure false positives, false negatives and gate overhead against predeclared acceptance limits.

## Target-repo adaptation

Never copy another project's milliseconds, bundle sizes or thresholds. Establish the target's own baseline and noise envelope, define control fixtures, and declare acceptable false-positive/false-negative rates plus a maximum measurement-overhead budget.

## Failure modes

Flaky gates from uncontrolled runners, benchmark gaming, stale fixtures, hardware drift, thresholds so loose they miss real regressions, thresholds so tight they block good changes, and measurement overhead large enough to damage CI usability or distort the workload under test.

## Rollback trigger

Disable or demote the gate to non-blocking and recalibrate whenever its measurement environment is invalid, its fixture is stale/nonrepresentative, known regressions are no longer detected, known-good controls fail above the declared false-positive limit, observed false negatives exceed the declared limit, or measurement overhead exceeds the predeclared budget. Do **not** disable merely because product code legitimately regressed; in that case keep the valid gate and fix or explicitly accept the regression through the target's normal review process.
