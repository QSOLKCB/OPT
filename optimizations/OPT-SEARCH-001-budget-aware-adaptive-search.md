# OPT-SEARCH-001 — Budget-aware adaptive parameter search

**Status:** Proposed / OPT synthesis; upstream mechanisms are implemented externally  
**Domains:** expensive black-box tuning, CI/runtime parameters, simulation, numerical kernels

## Source evidence

- `bayesian-optimization/BayesianOptimization` inspected at `af8b928212f0eacd1ce20c20be72c1a7b1d8d421`
- `hyperopt/hyperopt` inspected at `9834314879c09c13e0b8e93eb678408ba46441a8`
- `stevengj/nlopt` inspected at `6e6593f131ba3a38bc9edbed0a357bc01526e54b`
- `sources/OPTIMIZATION-LIBRARIES.md`

## Problem

Optimization knobs are selected by folklore, exhaustive sweeps, or a few arbitrary values even when each benchmark evaluation is expensive.

## Optimization problem contract

- X: the target's explicitly bounded continuous, integer, categorical, conditional, or mixed parameter search space
- F: candidates in X that satisfy all hard resource, platform, semantic, and correctness constraints before objective ranking
- f: the target-measured objective or objective vector for each feasible candidate, including declared noise/statistical treatment
- d: the target's predeclared minimize, maximize, lexicographic, or Pareto ordering
- C: search may choose where to evaluate but may not weaken correctness, determinism, evidence, API, trust, or other target semantics to improve f; asynchronous dispatch must not exceed B after accounting for consumed and conservatively reserved in-flight resources
- B: an explicit target-specific maximum evaluation, wall-time, compute, monetary, or equivalent resource budget declared before the search starts; the accounting unit, conservative per-trial reservation rule, and failure/cancellation charging policy are fixed before dispatch begins
- S: stop proposing/dispatching when no additional trial can be conservatively reserved within B, when a predeclared objective/quality target is met, or when a predeclared stagnation/convergence rule fires; preserve the reason for stopping in the trial ledger

## Preserved contract

Search may choose *where to evaluate* but may not weaken correctness constraints to improve the objective. Under asynchronous execution, the declared maximum budget remains a hard dispatch bound: actual consumed resources plus all still-reserved in-flight capacity must remain within B.

## Optimization

Use observations to adapt future evaluations: surrogate/acquisition search for expensive black-box objectives, conditional spaces where parameters only exist under certain choices, progressive domain contraction where justified, and explicit stopping/evaluation budgets. For asynchronous workers, reserve pending regions or otherwise diversify proposals so workers do not redundantly evaluate the same neighborhood.

Before dispatching an asynchronous trial, atomically reserve a conservative amount of the applicable budget and record the pending trial in the ledger. If `consumed + reserved + proposed_reservation > B`, do not dispatch. Completion converts the actually consumed amount into permanent budget consumption and releases only any **demonstrably unconsumed** remainder of the reservation; it must not double-charge the same usage. A failed or cancelled trial never erases resources already consumed. For an evaluation-count budget, dispatch consumes the evaluation slot and it is not refunded merely because the trial later fails or is cancelled. For money/compute/time budgets, release only the measured or otherwise provable unused portion of the reservation. If unconsumed capacity cannot be established safely, retain the conservative charge. Every reservation, consumption adjustment, release, failure, and cancellation is recorded in the ledger.

Parallelism has an information cost: very wide batches receive less feedback between suggestions and can degenerate toward non-adaptive/random search.

## Before / after evidence

- Environment: No controlled target-repository tuning study has been run for this OPT synthesis.
- Baseline: No target comparison against manual/exhaustive/random tuning has been established.
- Optimized: No target adaptive-search result has been established.
- Speedup / memory reduction: No transferable claim; upstream libraries establish mechanisms, not a QSOL target win.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Keep a deterministic search seed where practical, preserve the full trial ledger, re-evaluate finalists, and validate the selected candidate against the reference contract on held-out/repeated workloads. For asynchronous search, test the budget boundary with multiple workers contending for the last remaining reservation and prove no dispatch can make `consumed + reserved` exceed B. Inject early failures, late failures, partial consumption, and cancellation after measurable work; verify that only demonstrably unconsumed reservation is released, evaluation-count slots are not resurrected after dispatch, and repeated failures cannot create extra budget capacity.

## Target-repo adaptation

Do not copy acquisition constants, trial counts, domain contraction rates or parallel widths. Treat them as optimizer parameters with their own evidence boundary. Define the budget accounting unit, conservative per-trial reservation amount, atomic reservation mechanism, metering source, and failure/cancellation charging policy before enabling asynchronous dispatch.

## Failure modes

Noisy objectives, nonstationary machines, weak surrogates, excessive dimensionality and too much concurrency can waste evaluations or overfit benchmark noise. Non-atomic reservation can oversubscribe an evaluation or monetary cap; refunding consumed resources can let repeated late failures exceed B; over-conservative reservations can reduce useful parallelism.

## Rollback trigger

Stop adaptive search when its overhead exceeds evaluation savings, the budget is exhausted, repeated validation does not confirm the selected improvement, or any accounting/concurrency test shows that dispatch, failure, cancellation, or reservation release can cause actual consumption plus outstanding reservations to exceed B.
