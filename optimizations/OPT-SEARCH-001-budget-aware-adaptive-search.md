# OPT-SEARCH-001 — Budget-aware adaptive parameter search

**Status:** Implemented external mechanisms; OPT synthesis proposed for target tuning  
**Domains:** expensive black-box tuning, CI/runtime parameters, simulation, numerical kernels

## Source evidence

- `bayesian-optimization/BayesianOptimization` inspected at `af8b928212f0eacd1ce20c20be72c1a7b1d8d421`
- `hyperopt/hyperopt` inspected at `9834314879c09c13e0b8e93eb678408ba46441a8`
- `stevengj/nlopt` inspected at `6e6593f131ba3a38bc9edbed0a357bc01526e54b`
- `sources/OPTIMIZATION-LIBRARIES.md`

## Problem

Optimization knobs are selected by folklore, exhaustive sweeps, or a few arbitrary values even when each benchmark evaluation is expensive.

## Optimization problem contract

Define `P = (X,F,f,d,C,B,S)` from `OPTIMIZATION-PROBLEM.md`. Explicitly classify continuous/discrete/conditional variables, noise, constraints, gradient availability, local/global scope and evaluation cost.

## Preserved contract

Search may choose *where to evaluate* but may not weaken correctness constraints to improve the objective.

## Optimization

Use observations to adapt future evaluations: surrogate/acquisition search for expensive black-box objectives, conditional spaces where parameters only exist under certain choices, progressive domain contraction where justified, and explicit stopping/evaluation budgets. For asynchronous workers, reserve pending regions or otherwise diversify proposals so workers do not redundantly evaluate the same neighborhood.

Parallelism has an information cost: very wide batches receive less feedback between suggestions and can degenerate toward non-adaptive/random search.

## Validation

Keep a deterministic search seed where practical, preserve the full trial ledger, re-evaluate finalists, and validate the selected candidate against the reference contract on held-out/repeated workloads.

## Target-repo adaptation

Do not copy acquisition constants, trial counts, domain contraction rates or parallel widths. Treat them as optimizer parameters with their own evidence boundary.

## Failure modes

Noisy objectives, nonstationary machines, weak surrogates, excessive dimensionality and too much concurrency can waste evaluations or overfit benchmark noise.

## Rollback trigger

Stop adaptive search when its overhead exceeds evaluation savings, the budget is exhausted, or repeated validation does not confirm the selected improvement.
