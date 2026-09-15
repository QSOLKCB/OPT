# Optimization Problem Contract

OPT separates **the problem being optimized** from **the mechanism used to search for an improvement**.

For a target repository, define the optimization problem before selecting an optimization record.

## Canonical contract

Represent a problem as

\[
P = (X, F, f, d, C, B, S)
\]

where:

- `X` — search space / decision-variable domain;
- `F ⊆ X` — feasible set after hard constraints;
- `f : F → R^k` — measured objective or objective vector;
- `d` — objective direction (`minimize`, `maximize`, or explicit multi-objective ordering);
- `C` — correctness and semantic contract that may not be weakened implicitly;
- `B` — evaluation/resource budget;
- `S` — stopping rule.

A candidate is admissible only if it lies in `F` **and** satisfies `C`. A faster candidate that violates `C` is not an optimization under the same problem definition.

## Required classification

Record the following before tuning:

| Dimension | Typical values |
| --- | --- |
| Variables | continuous / integer / categorical / conditional / mixed |
| Search scope | local / global |
| Objective | deterministic / noisy / stochastic |
| Information | gradient available / derivative-free / black-box |
| Evaluation cost | cheap / moderate / expensive |
| Constraints | bounds / equality / inequality / semantic / resource |
| Parallelism | sequential / synchronous batch / asynchronous |
| Exactness | exact / approximation permitted under an explicit error contract |

## Examples

### Worker-count tuning

- `X = {1, …, 32}`
- `F = X` subject to peak-memory and platform limits
- `f(x) = median wall time`
- `d = minimize`
- `C = scalar/parallel result equivalence + deterministic required ordering`
- `B = 40 benchmark trials`
- `S = budget exhausted or improvement below the predeclared threshold`

### Approximate visualization

- `X = {LOD policies}`
- `F = policies satisfying frame-memory limits`
- `f = (frame latency, perceptual/error metric)`
- `C = error ≤ ε and reference path remains available`
- `B = fixed benchmark fixture set`
- `S = Pareto candidate chosen under the documented priority rule`

## Search-mechanism selection

Use the problem classification to select a mechanism:

- expensive black-box continuous or mixed tuning → `OPT-SEARCH-001`;
- discrete search with provable optimistic bounds → `OPT-PRUNE-001`;
- independent work that can run concurrently → `OPT-PAR-001`;
- repeated equivalent work → `OPT-INV-001`;
- simultaneous identical in-flight work → `OPT-COAL-001`;
- approximation explicitly permitted → `OPT-APPROX-001`.

The mechanism is subordinate to the contract. Do not reshape the problem after seeing results merely to make an optimization look successful.

## Measurement rule

Source-project constants and historical observations are priors, not targets. Transfer requires fresh target-context measurement and validation.

See `FORMALIZATION.md` for the frozen v1.0.0 Lean boundary. This problem-contract layer is post-v1 catalog guidance and does not mutate the pinned v1 formal model.
