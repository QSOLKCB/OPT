# OPT-APPROX-001 — Contract-bounded approximation

**Status:** Proposed / OPT synthesis; external production pattern, target-specific proof/measurement required  
**Domains:** visualization, search, streaming, telemetry, simulation, audition DSP

## Source evidence

- https://jazco.dev/2025/02/19/imperfection/
- existing `OPT-DSP-001` approximation boundary
- `sources/JAZCO.md`

## Problem

Exact processing has unbounded or unacceptable cost even though the product/scientific contract permits a bounded loss of precision, completeness or freshness.

## Optimization problem contract

- X: target-supported approximation policies, quality/resource ceilings, sampling/culling/LOD policies, update frequencies, state-reset rules, evaluation horizons, exact-mode fallback choices, and stochastic tuning/certification procedures
- F: policies whose declared error/degradation metric remains within the target's explicit envelope over the declared state/composition horizon and whose resource/semantic constraints are satisfied; when a stochastic policy is selected from multiple candidates, feasibility certification is based on independent held-out conformance data or a predeclared selection-aware simultaneous-confidence/multiple-testing procedure rather than naive reuse of the tuning samples
- f: target-measured resource or latency cost, optionally paired with the declared quality/error metric
- d: minimize resource/latency cost subject to feasibility in F, or use the target's predeclared multi-objective ordering when quality is ranked rather than hard-bounded
- C: approximation is permitted only by an explicit contract; exact callers are not silently weakened; the error norm, aggregation rule, sequence/composition horizon, reset boundaries, whether the envelope is hard worst-case or statistical/confidence/tail-based, and the stochastic tuning-versus-certification procedure are declared before evaluation; an exact reference path or exact fixture remains available where practical
- B: target-specific benchmark/quality-evaluation budget over predeclared ordinary, boundary, adversarial, repeated-application, and long-horizon fixtures; for stochastic policy search, tuning/selection evaluations and independent certification evaluations (or the budget used by the predeclared simultaneous-confidence procedure) are accounted separately
- S: stop when the evaluation budget is exhausted or a selected policy meets the target resource objective and passes the declared conformance certification while remaining inside the quality envelope over the entire declared horizon
- Variables: continuous / integer / categorical / conditional / mixed, depending on approximation policy
- Search scope: local or global, explicitly declared for the target
- Objective behavior: deterministic, noisy, or stochastic depending on the quality/resource metric
- Information: derivative-free / black-box by default
- Evaluation cost: moderate to expensive when exact references, held-out certification, or long-horizon trajectories are required
- Constraints: explicit error envelope, semantic/API, resource, horizon/reset, selection-aware statistical certification, and exact-fallback constraints
- Parallelism: sequential, synchronous batch, or asynchronous according to target evaluation; stateful validation must preserve trajectory semantics
- Exactness: approximation explicitly permitted only inside the declared measurable envelope

## Preserved contract

Approximation is admissible only when the contract explicitly permits it. A previously exact API cannot be silently weakened and still be called correctness-preserving. For stateful or repeatedly composed approximations, the contract applies over an explicitly declared horizon—not merely to each isolated step—so bounded per-step error is insufficient if drift can accumulate beyond the allowed envelope. The contract must also state whether compliance is pointwise/worst-case or statistical; a stochastic envelope is judged by its declared aggregation, confidence, exceedance-probability, quantile, or tail criterion rather than by silently substituting a hard per-sample limit. When multiple stochastic policies are tuned or screened, choosing the apparent winner changes the sampling distribution: the data used to optimize/select a policy cannot be treated as independent nominal-confidence certification evidence unless the declared procedure explicitly accounts for that selection.

## Optimization

Introduce a resource ceiling and degrade only along a declared dimension: sample/cull, lower level of detail, approximate search, bounded stale data, or reduced update frequency. Make the error surface measurable and reversible.

For stateful streaming, simulation, DSP, iterative numerical work, or any repeatedly applied approximation, define the error model before benchmarking: the norm/metric (for example absolute, relative, L2, perceptual, state-distance, or domain-specific), how error composes or is aggregated through time, the maximum sequence length or physical/time horizon over which the envelope must hold, and any reset/checkpoint/re-synchronization boundaries that legitimately restart the horizon. If the system can run longer than the validated horizon without reset, either extend validation to that operational horizon or define a separate long-run drift bound; do not infer long-run safety from one-step ε alone.

For stochastic/noisy approximations, also define the statistical compliance rule before evaluation: the sampling unit and workload distribution, aggregation statistic, confidence level or interval procedure, tolerated exceedance probability, quantile/tail bound, and the sample/evaluation budget used to decide compliance. Do not reinterpret a statistical guarantee as a pointwise worst-case guarantee, and do not weaken a declared hard worst-case envelope into an average-case claim after observing data.

If more than one stochastic approximation policy is tuned, compared, adaptively searched, thresholded, or screened using sampled error data, **separate selection from certification**. The default pattern is to use one predeclared tuning/selection set (or stream) to choose the candidate and then evaluate that frozen candidate on an independent held-out conformance set drawn from the declared operational distribution. If independent holdout is impractical, use a predeclared selection-aware method that preserves the advertised guarantee across the entire candidate-selection procedure—for example simultaneous confidence bounds, family-wise/multiple-testing correction, valid selective-inference/e-process machinery, or another target-justified method. A nominal per-policy confidence interval computed on the same samples used to select the best-looking policy is not certification. Record exactly which evaluations influenced policy selection and which evaluations supported the final compliance claim.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No exact target baseline has been established here.
- Optimized: No target approximation implementation has been benchmarked here.
- Speedup / memory reduction: No transferable claim; external production observations remain source evidence only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Measure error/degradation and resource savings together across ordinary, boundary and adversarial workloads. Keep an exact reference for differential evaluation where practical. Declare and test the error norm/metric, aggregation rule, sequence/composition horizon, reset boundaries, hard-versus-statistical envelope semantics, and tuning-versus-certification procedure explicitly.

For stateful/repeated use, run differential trajectories against the exact path across short, nominal, maximum-supported, and adversarially long sequences. Include biased-error fixtures where each individual step remains within the local ε but errors accumulate in the same direction; verify the cumulative/state error still respects the declared horizon envelope. Test reset/checkpoint boundaries before, at, and after the limit; verify resets actually restore the assumptions used by the next horizon.

Where stochastic approximation is used, evaluate the declared expected, quantile, exceedance-probability, confidence, tail, or worst-case criterion against the exact path as specified by C. Include fixtures where individual samples exceed a nominal pointwise value while the declared statistical envelope remains satisfied, and fixtures where the configured tail/confidence/exceedance criterion truly fails. Verify rollback decisions distinguish those cases rather than triggering on one sample unless the contract explicitly declares a hard single-sample/worst-case bound.

Add **selection-bias fixtures** whenever multiple stochastic policies are considered. Generate several candidate policies whose apparent sampled errors vary by chance, select the best-looking candidate using the declared tuning procedure, and prove that the final compliance decision uses either fresh held-out samples unavailable to selection or the declared simultaneous/selection-aware inference procedure. Verify the tuning samples alone cannot certify the selected winner at nominal per-policy confidence. Include repeated/adaptive candidate selection, early stopping, and candidate-count changes; confirm the advertised confidence/tail/exceedance guarantee remains valid under the complete selection procedure. Persist an audit trail labeling each evaluation as tuning/selection, certification, or both only when the declared selection-aware method formally permits dual use.

## Target-repo adaptation

Define `ε`, the exact quality/error norm, aggregation rule, workload distribution, maximum state/composition horizon, reset/checkpoint semantics, long-run drift policy, escape hatch and exact-mode availability locally. Explicitly classify the quality envelope as hard pointwise/worst-case or statistical, and for statistical contracts specify the confidence/tail/exceedance rule and decision sample budget. If multiple policies are searched or compared, predeclare the tuning/selection dataset or stream, the independent certification dataset/budget, **or** the exact simultaneous-confidence/multiple-testing/selective-inference method that makes data reuse valid; record which observations affected selection versus certification. If the target has no finite operational horizon, establish a justified asymptotic/stability bound or periodic re-synchronization rule instead of copying a finite benchmark horizon from another system.

## Failure modes

Unmeasured quality loss, biased sampling, hidden rare-case failures, cumulative drift that is invisible to one-step checks, reset boundaries that fail to restore reference assumptions, state-dependent amplification, unstable feedback loops, selecting the best-looking stochastic policy and then certifying it on the same data with naive per-policy confidence, undisclosed adaptive candidate search/early stopping that invalidates nominal error guarantees, misclassifying a statistical envelope as a hard pointwise bound (or vice versa), and callers incorrectly assuming exact semantics.

## Rollback trigger

Evaluate rollback against the **declared envelope semantics and certification procedure**. For a hard pointwise/worst-case contract, disable immediately when any supported-horizon observation exceeds the declared bound. For a stochastic/statistical contract, disable when the predeclared aggregation, confidence, exceedance-probability, quantile, or tail criterion fails under its stated **selection-aware certification** procedure; an isolated sample beyond a nominal pointwise value is not by itself a contract violation unless the contract says it is. Treat a selected policy as uncertified—and disable or fall back—if held-out certification fails, if tuning and certification evidence are mixed contrary to the declared procedure, or if the simultaneous/multiple-testing/selective-inference assumptions required for data reuse are violated. In all cases, disable when cumulative/state drift violates its declared bound, reset/checkpoint validation fails, reference comparisons violate C, a catastrophic semantic/safety constraint is breached, or resource savings are not material.
