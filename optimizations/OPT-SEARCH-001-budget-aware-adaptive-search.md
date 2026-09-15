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
- C: search may choose where to evaluate but may not weaken correctness, determinism, evidence, API, trust, or other target semantics to improve f
- B: an explicit target-specific maximum evaluation, wall-time, compute, monetary, or equivalent resource budget declared before the search starts
- S: stop on the declared budget, a predeclared objective/quality target, or a predeclared stagnation/convergence rule; preserve the reason for stopping in the trial ledger

## Preserved contract

Search may choose *where to evaluate* but may not weaken correctness constraints to improve the objective.

## Optimization

Use observations to adapt future evaluations: surrogate/acquisition search for expensive black-box objectives, conditional spaces where parameters only exist under certain choices, progressive domain contraction where justified, and explicit stopping/evaluation budgets. For asynchronous workers, reserve pending regions or otherwise diversify proposals so workers do not redundantly evaluate the same neighborhood.

Parallelism has an information cost: very wide batches receive less feedback between suggestions and can degenerate toward non-adaptive/random search.

## Before / after evidence

- Environment: No controlled target-repository tuning study has been run for this OPT synthesis.
- Baseline: No target comparison against manual/exhaustive/random tuning has been established.
- Optimized: No target adaptive-search result has been established.
- Speedup / memory reduction: No transferable claim; upstream libraries establish mechanisms, not a QSOL target win.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Keep a deterministic search seed where practical, preserve the full trial ledger, re-evaluate finalists, and validate the selected candidate against the reference contract on held-out/repeated workloads.

## Target-repo adaptation

Do not copy acquisition constants, trial counts, domain contraction rates or parallel widths. Treat them as optimizer parameters with their own evidence boundary.

## Failure modes

Noisy objectives, nonstationary machines, weak surrogates, excessive dimensionality and too much concurrency can waste evaluations or overfit benchmark noise.

## Rollback trigger

Stop adaptive search when its overhead exceeds evaluation savings, the budget is exhausted, or repeated validation does not confirm the selected improvement.
