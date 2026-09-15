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
- F: gate configurations based on a sufficiently characterized environment and workload, with statistically justified tolerance, selection-aware validation, a declared good-run/regression population or explicitly enumerated control scope, and no weakening of functional correctness or workload realism
- f: target-measured **loss vector** comprising missed-material-regression loss (for example false-negative rate and, where relevant, severity-weighted miss cost), flaky/false-failure loss (false-positive rate), and measurement/CI overhead
- d: minimize every component of the declared loss vector under the target's predeclared scalar, weighted, Pareto, or lexicographic ordering; if detection quality is reported separately, it is a diagnostic complement such as `1 - false-negative-rate`, not an oppositely oriented coordinate inside `f`
- C: the performance gate must not incentivize weakening tests, assertions, evidence, semantic coverage, or representative workload inputs; once a candidate gate is selected, its claimed false-positive/false-negative performance must be established on independent control executions or under a predeclared selection-aware procedure that accounts for every configuration tried, **and every reported detector error rate must name the population/generator and sampling scheme it estimates or be explicitly scoped to the enumerated controls only**
- B: target-specific calibration and certification budget specifying repetitions, environment samples, held-out/control executions, population/generator coverage where general error rates are claimed, and allowable CI/runtime measurement cost
- S: stop calibration when the declared sample budget is exhausted or the baseline/noise estimate is stable enough to freeze one candidate gate for independent certification; promote it only if the certification contract passes
- Variables: continuous / integer / categorical / mixed metric, statistic, fixture, and threshold choices
- Search scope: local gate/calibration tuning
- Objective behavior: noisy / stochastic measurement distributions
- Information: derivative-free statistical observations
- Evaluation cost: moderate to expensive depending on repetitions and fixture scale
- Constraints: functional correctness, representative workload, declared population/control scope, statistical tolerance, runner/environment characterization, false-positive/false-negative, selection bias, and CI-overhead constraints
- Parallelism: sequential or synchronous-batch calibration; parallel sampling only when runner interference is characterized
- Exactness: no semantic approximation; statistical tolerance/noise handling is explicit

## Preserved contract

A performance gate may not incentivize weakening functional tests, correctness, evidence or workload realism. The gate is valid only while its fixture, environment characterization, declared detection population/control scope, detection sensitivity and measurement overhead remain inside their declared contract. Calibration evidence used to choose among competing gates is not automatically valid certification evidence for the selected gate. A rate measured on a handpicked or finite control suite must not be generalized to unseen production regressions unless the target has declared and sampled from a population/generator that supports that inference.

## Optimization

Turn a stable, reproducible performance expectation into a regression gate. Compare distributions or robust summaries where noise matters; separate machine/environment drift from code regression; keep cold/warm claims distinct. Keep known-fast and known-regressed control fixtures (or equivalent calibration cases) so the gate can periodically prove it still distinguishes acceptable from materially regressed behavior.

Before claiming false-positive or false-negative rates beyond those exact controls, define the estimand. Declare the good-run population and the material-regression population or generator, including the target workloads, regression classes, severity range, environment distribution, and any exclusions. Predeclare how certification cases are sampled or generated from that population and how repeated executions are grouped. If the repository cannot justify a broader population model, use the controls strictly as an enumerated conformance suite and report control-suite detection/failure rates without implying a general production error rate.

When multiple metric/fixture/statistic/threshold configurations are explored, treat that search as model selection. Use calibration/tuning data to choose the candidate, then freeze its complete configuration before certification. The default certification path is an independent held-out sample of known-good and known-regressed executions drawn under the declared sampling scheme and playing no role in choosing the gate. If holding out controls is impractical, use a predeclared nested-resampling, simultaneous-confidence, multiple-testing, or other selection-aware procedure whose error guarantees cover the full configuration search—not nominal per-candidate estimates computed after selecting the best one.

## Before / after evidence

- Environment: No controlled target-repository budget calibration has been run for this OPT record.
- Baseline: No target baseline distribution is claimed here.
- Optimized: Not applicable until a target repository adopts and calibrates a performance budget.
- Speedup / memory reduction: This pattern protects performance; it does not itself claim a speedup.
- Variance / repetitions: Must be established in the target environment before a hard threshold is promoted.

## Validation

Calibrate variance before setting the threshold. During tuning, compare candidate metric/fixture/statistic/threshold configurations using explicitly designated calibration data and preserve raw samples where practical. Once one gate is selected, **freeze the entire gate configuration before measuring its claimed detection performance**.

Before certification, write down the exact error-rate scope: either (a) a declared good-run/regression population or generator plus sampling scheme, including regression classes/severities and environment/workload strata that the rate is intended to represent, or (b) a finite enumerated control suite to which the reported rates are explicitly limited. For population claims, draw the independent certification sample according to that scheme and record coverage/counts by the predeclared strata; do not substitute a convenient handpicked set after seeing gate behavior. For control-only claims, label the result as control-suite performance and prohibit extrapolation to unrepresented regression classes.

Certify the frozen gate on independent known-good and known-regressed executions that were not used to select it. Measure false positives, false negatives, and gate overhead against predeclared acceptance limits **within the declared scope**. If independent controls are unavailable, use a predeclared nested-resampling or selection-aware procedure that accounts for every candidate/configuration examined, and report the resulting adjusted uncertainty/error rates rather than reusing naive in-sample estimates. If the declared population/generator changes, previous rates do not automatically transfer.

Verify objective orientation explicitly: construct one candidate with fewer missed regressions but more false alarms and another with the opposite tradeoff, compute the declared loss coordinates, and prove the configured scalar/Pareto/lexicographic ordering ranks them exactly as documented. A separately reported positive detection-quality score must never be fed into a minimization coordinate without an explicit monotone conversion to loss.

Record which executions were used for calibration/selection versus certification, along with the population/control scope and sampling provenance for each certification case. Re-run independent controls after runner/toolchain changes and periodically enough to detect stale fixtures or sensitivity drift. Add an explicit overfitting fixture where several candidate gates are tuned on one noisy control sample set; prove the gate cannot be promoted merely because one candidate looked best on those same samples. Also include at least one deliberately omitted regression class in a test report to prove the tooling labels that class as outside the estimated scope rather than silently counting the observed controls as universal evidence.

## Target-repo adaptation

Never copy another project's milliseconds, bundle sizes or thresholds. Establish the target's own baseline and noise envelope, define control fixtures, and declare acceptable false-positive/false-negative rates plus a maximum measurement-overhead budget. **Define what population those rates refer to:** specify representative workloads, regression classes and severities, environment strata, exclusions, and the sampling/generation process; or explicitly limit the claim to a named finite control suite. Define `f` using consistently oriented loss coordinates and predeclare how those coordinates are ordered or scalarized; if the target also reports a positive detection-quality score, document its conversion to the minimized loss coordinate. Predeclare how calibration/selection is separated from certification: held-out controls by default, or a justified nested/selection-aware alternative. Preserve the candidate-search history and sampling provenance needed to audit the claimed certification error rates.

## Failure modes

Flaky gates from uncontrolled runners, benchmark gaming, stale fixtures, hardware drift, thresholds so loose they miss real regressions, thresholds so tight they block good changes, an objective vector mixing maximized quality with minimized costs without an explicit per-coordinate direction/conversion, selection bias from evaluating a chosen gate on the same controls used to tune it, **sampling bias or undefined detector populations that turn control-suite performance into an unjustified general false-positive/false-negative claim**, unrepresented regression classes/severities, unreported configuration search that invalidates nominal error rates, and measurement overhead large enough to damage CI usability or distort the workload under test.

## Rollback trigger

Disable or demote the gate to non-blocking and recalibrate whenever its measurement environment is invalid, its fixture is stale/nonrepresentative, its declared regression/good-run population or control scope no longer matches the deployment claim, its sampling process no longer represents the declared population, its objective orientation/scalarization is ambiguous or ranks a worse detector as better, independent/selection-aware certification no longer meets the declared false-positive/false-negative limits **within that stated scope**, known regressions are no longer detected, known-good controls fail above the declared false-positive limit, observed false negatives exceed the declared limit, or measurement overhead exceeds the predeclared budget. Do **not** disable merely because product code legitimately regressed; in that case keep the valid gate and fix or explicitly accept the regression through the target's normal review process.