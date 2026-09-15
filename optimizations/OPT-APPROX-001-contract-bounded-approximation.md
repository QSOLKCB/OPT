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

- X: target-supported approximation policies, quality/resource ceilings, sampling/culling/LOD policies, update frequencies, state-reset rules, evaluation horizons, and exact-mode fallback choices
- F: policies whose declared error/degradation metric remains within the target's explicit envelope over the declared state/composition horizon and whose resource/semantic constraints are satisfied
- f: target-measured resource or latency cost, optionally paired with the declared quality/error metric
- d: minimize resource/latency cost subject to feasibility in F, or use the target's predeclared multi-objective ordering when quality is ranked rather than hard-bounded
- C: approximation is permitted only by an explicit contract; exact callers are not silently weakened; the error norm, aggregation rule, sequence/composition horizon, reset boundaries, and whether the envelope is hard worst-case or statistical/confidence/tail-based are declared before evaluation; an exact reference path or exact fixture remains available where practical
- B: target-specific benchmark/quality-evaluation budget over predeclared ordinary, boundary, adversarial, repeated-application, and long-horizon fixtures
- S: stop when the evaluation budget is exhausted or a validated policy meets the target resource objective while remaining inside the declared quality envelope over the entire declared horizon
- Variables: continuous / integer / categorical / conditional / mixed, depending on approximation policy
- Search scope: local or global, explicitly declared for the target
- Objective behavior: deterministic, noisy, or stochastic depending on the quality/resource metric
- Information: derivative-free / black-box by default
- Evaluation cost: moderate to expensive when exact references or long-horizon trajectories are required
- Constraints: explicit error envelope, semantic/API, resource, horizon/reset, and exact-fallback constraints
- Parallelism: sequential, synchronous batch, or asynchronous according to target evaluation; stateful validation must preserve trajectory semantics
- Exactness: approximation explicitly permitted only inside the declared measurable envelope

## Preserved contract

Approximation is admissible only when the contract explicitly permits it. A previously exact API cannot be silently weakened and still be called correctness-preserving. For stateful or repeatedly composed approximations, the contract applies over an explicitly declared horizon—not merely to each isolated step—so bounded per-step error is insufficient if drift can accumulate beyond the allowed envelope. The contract must also state whether compliance is pointwise/worst-case or statistical; a stochastic envelope is judged by its declared aggregation, confidence, exceedance-probability, quantile, or tail criterion rather than by silently substituting a hard per-sample limit.

## Optimization

Introduce a resource ceiling and degrade only along a declared dimension: sample/cull, lower level of detail, approximate search, bounded stale data, or reduced update frequency. Make the error surface measurable and reversible.

For stateful streaming, simulation, DSP, iterative numerical work, or any repeatedly applied approximation, define the error model before benchmarking: the norm/metric (for example absolute, relative, L2, perceptual, state-distance, or domain-specific), how error composes or is aggregated through time, the maximum sequence length or physical/time horizon over which the envelope must hold, and any reset/checkpoint/re-synchronization boundaries that legitimately restart the horizon. If the system can run longer than the validated horizon without reset, either extend validation to that operational horizon or define a separate long-run drift bound; do not infer long-run safety from one-step ε alone.

For stochastic/noisy approximations, also define the statistical compliance rule before evaluation: the sampling unit and workload distribution, aggregation statistic, confidence level or interval procedure, tolerated exceedance probability, quantile/tail bound, and the sample/evaluation budget used to decide compliance. Do not reinterpret a statistical guarantee as a pointwise worst-case guarantee, and do not weaken a declared hard worst-case envelope into an average-case claim after observing data.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No exact target baseline has been established here.
- Optimized: No target approximation implementation has been benchmarked here.
- Speedup / memory reduction: No transferable claim; external production observations remain source evidence only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Measure error/degradation and resource savings together across ordinary, boundary and adversarial workloads. Keep an exact reference for differential evaluation where practical. Declare and test the error norm/metric, aggregation rule, sequence/composition horizon, reset boundaries, and hard-versus-statistical envelope semantics explicitly.

For stateful/repeated use, run differential trajectories against the exact path across short, nominal, maximum-supported, and adversarially long sequences. Include biased-error fixtures where each individual step remains within the local ε but errors accumulate in the same direction; verify the cumulative/state error still respects the declared horizon envelope. Test reset/checkpoint boundaries before, at, and after the limit; verify resets actually restore the assumptions used by the next horizon.

Where stochastic approximation is used, evaluate the declared expected, quantile, exceedance-probability, confidence, tail, or worst-case criterion against the exact path as specified by C. Include fixtures where individual samples exceed a nominal pointwise value while the declared statistical envelope remains satisfied, and fixtures where the configured tail/confidence/exceedance criterion truly fails. Verify rollback decisions distinguish those cases rather than triggering on one sample unless the contract explicitly declares a hard single-sample/worst-case bound.

## Target-repo adaptation

Define `ε`, the exact quality/error norm, aggregation rule, workload distribution, maximum state/composition horizon, reset/checkpoint semantics, long-run drift policy, escape hatch and exact-mode availability locally. Explicitly classify the quality envelope as hard pointwise/worst-case or statistical, and for statistical contracts specify the confidence/tail/exceedance rule and decision sample budget. If the target has no finite operational horizon, establish a justified asymptotic/stability bound or periodic re-synchronization rule instead of copying a finite benchmark horizon from another system.

## Failure modes

Unmeasured quality loss, biased sampling, hidden rare-case failures, cumulative drift that is invisible to one-step checks, reset boundaries that fail to restore reference assumptions, state-dependent amplification, unstable feedback loops, misclassifying a statistical envelope as a hard pointwise bound (or vice versa), and callers incorrectly assuming exact semantics.

## Rollback trigger

Evaluate rollback against the **declared envelope semantics**. For a hard pointwise/worst-case contract, disable immediately when any supported-horizon observation exceeds the declared bound. For a stochastic/statistical contract, disable when the predeclared aggregation, confidence, exceedance-probability, quantile, or tail criterion fails under its stated evaluation procedure; an isolated sample beyond a nominal pointwise value is not by itself a contract violation unless the contract says it is. In all cases, disable when cumulative/state drift violates its declared bound, reset/checkpoint validation fails, reference comparisons violate C, a catastrophic semantic/safety constraint is breached, or resource savings are not material.
