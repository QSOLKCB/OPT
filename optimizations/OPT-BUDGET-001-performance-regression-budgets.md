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
- F: gate configurations based on a sufficiently characterized environment and workload, with statistically justified tolerance, selection-aware validation, and no weakening of functional correctness or workload realism
- f: target-measured regression-detection quality together with CI noise/false-alarm rate and measurement overhead
- d: minimize missed material regressions and flaky/false failures under the target's predeclared multi-objective ordering
- C: the performance gate must not incentivize weakening tests, assertions, evidence, semantic coverage, or representative workload inputs; once a candidate gate is selected, its claimed false-positive/false-negative performance must be established on independent control executions or under a predeclared selection-aware procedure that accounts for every configuration tried
- B: target-specific calibration and certification budget specifying repetitions, environment samples, held-out/control executions, and allowable CI/runtime measurement cost
- S: stop calibration when the declared sample budget is exhausted or the baseline/noise estimate is stable enough to freeze one candidate gate for independent certification; promote it only if the certification contract passes
- Variables: continuous / integer / categorical / mixed metric, statistic, fixture, and threshold choices
- Search scope: local gate/calibration tuning
- Objective behavior: noisy / stochastic measurement distributions
- Information: derivative-free statistical observations
- Evaluation cost: moderate to expensive depending on repetitions and fixture scale
- Constraints: functional correctness, representative workload, statistical tolerance, runner/environment characterization, false-positive/false-negative, selection bias, and CI-overhead constraints
- Parallelism: sequential or synchronous-batch calibration; parallel sampling only when runner interference is characterized
- Exactness: no semantic approximation; statistical tolerance/noise handling is explicit

## Preserved contract

A performance gate may not incentivize weakening functional tests, correctness, evidence or workload realism. The gate is valid only while its fixture, environment characterization, detection sensitivity and measurement overhead remain inside their declared contract. Calibration evidence used to choose among competing gates is not automatically valid certification evidence for the selected gate.

## Optimization

Turn a stable, reproducible performance expectation into a regression gate. Compare distributions or robust summaries where noise matters; separate machine/environment drift from code regression; keep cold/warm claims distinct. Keep known-fast and known-regressed control fixtures (or equivalent calibration cases) so the gate can periodically prove it still distinguishes acceptable from materially regressed behavior.

When multiple metric/fixture/statistic/threshold configurations are explored, treat that search as model selection. Use calibration/tuning data to choose the candidate, then freeze its complete configuration before certification. The default certification path is an independent held-out set of known-good and known-regressed executions that played no role in choosing the gate. If holding out controls is impractical, use a predeclared nested-resampling, simultaneous-confidence, multiple-testing, or other selection-aware procedure whose error guarantees cover the full configuration search—not nominal per-candidate estimates computed after selecting the best one.

## Before / after evidence

- Environment: No controlled target-repository budget calibration has been run for this OPT record.
- Baseline: No target baseline distribution is claimed here.
- Optimized: Not applicable until a target repository adopts and calibrates a performance budget.
- Speedup / memory reduction: This pattern protects performance; it does not itself claim a speedup.
- Variance / repetitions: Must be established in the target environment before a hard threshold is promoted.

## Validation

Calibrate variance before setting the threshold. During tuning, compare candidate metric/fixture/statistic/threshold configurations using explicitly designated calibration data and preserve raw samples where practical. Once one gate is selected, **freeze the entire gate configuration before measuring its claimed detection performance**.

Certify the frozen gate on independent known-good and known-regressed control executions that were not used to select it. Measure false positives, false negatives, and gate overhead against predeclared acceptance limits. If independent controls are unavailable, use a predeclared nested-resampling or selection-aware procedure that accounts for every candidate/configuration examined, and report the resulting adjusted uncertainty/error rates rather than reusing naive in-sample estimates.

Record which executions were used for calibration/selection versus certification. Re-run independent controls after runner/toolchain changes and periodically enough to detect stale fixtures or sensitivity drift. Add an explicit overfitting fixture where several candidate gates are tuned on one noisy control sample set; prove the gate cannot be promoted merely because one candidate looked best on those same samples.

## Target-repo adaptation

Never copy another project's milliseconds, bundle sizes or thresholds. Establish the target's own baseline and noise envelope, define control fixtures, and declare acceptable false-positive/false-negative rates plus a maximum measurement-overhead budget. Predeclare how calibration/selection is separated from certification: held-out controls by default, or a justified nested/selection-aware alternative. Preserve the candidate-search history needed to audit the claimed certification error rates.

## Failure modes

Flaky gates from uncontrolled runners, benchmark gaming, stale fixtures, hardware drift, thresholds so loose they miss real regressions, thresholds so tight they block good changes, selection bias from evaluating a chosen gate on the same controls used to tune it, unreported configuration search that invalidates nominal error rates, and measurement overhead large enough to damage CI usability or distort the workload under test.

## Rollback trigger

Disable or demote the gate to non-blocking and recalibrate whenever its measurement environment is invalid, its fixture is stale/nonrepresentative, independent/selection-aware certification no longer meets the declared false-positive/false-negative limits, known regressions are no longer detected, known-good controls fail above the declared false-positive limit, observed false negatives exceed the declared limit, or measurement overhead exceeds the predeclared budget. Do **not** disable merely because product code legitimately regressed; in that case keep the valid gate and fix or explicitly accept the regression through the target's normal review process.
