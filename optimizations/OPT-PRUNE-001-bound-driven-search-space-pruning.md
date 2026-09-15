# OPT-PRUNE-001 — Bound-driven search-space pruning

**Status:** Proposed / OPT synthesis; classical mechanism, target adaptation required  
**Domains:** combinatorial optimization, scheduling, assignment, configuration search, resource allocation

## Source evidence

- `sources/MATHEMATICAL-OPTIMIZATION.md`
- combinatorial optimization / branch-and-bound literature referenced there
- NLopt taxonomy as supporting optimizer-selection context

## Problem

A discrete or mixed search space is too large for exhaustive evaluation, but whole subregions can sometimes be proven unable to beat the best feasible solution already found.

## Optimization problem contract

- X: the target's explicitly defined discrete or mixed candidate space together with a partition of unexplored candidates into searchable subregions
- F: candidates in X satisfying every original hard constraint; relaxed/bounding solutions are not feasible final answers unless they also lie in F
- f: a scalar real-valued target objective `f : F → R` evaluated on feasible candidates only
- d: exactly one of scalar `minimize` or scalar `maximize`; vector, Pareto, lexicographic, or other partial-order objectives are outside this record unless a separately specified and validated frontier-bound mechanism is introduced
- C: every returned incumbent satisfies the original feasibility/semantic contract, every pruning decision is justified by a separately defined sound scalar region-bound function `b`, the target's observable tie semantics are preserved, and budget exhaustion without a feasible incumbent produces an explicit unknown/no-incumbent outcome rather than a feasibility or optimality claim
- B: a finite, predeclared target-specific cap on evaluations, wall time, compute, or equivalent resource consumption; exact-mode search may prove optimality before this cap but may not run without a finite cap
- S: stop immediately when the required optimality/tie contract is proven or the frontier is exhausted; otherwise stop when B is exhausted. If a validated incumbent exists, return it plus any remaining valid global bound/optimality gap. If no feasible incumbent exists, return `no-incumbent / feasibility-unknown` and only a separately valid global bound if one is available; do not report an optimality gap that requires an incumbent, and do not claim infeasibility or optimality
- Variables: integer / categorical / discrete / mixed
- Search scope: global over the declared candidate space
- Objective behavior: deterministic unless uncertainty/noise is incorporated into a separately sound bound model
- Information: derivative-free; bound/relaxation information is target-specific
- Evaluation cost: moderate to expensive when exhaustive evaluation is infeasible
- Constraints: feasibility, semantic correctness, scalar-bound soundness, tie semantics, and finite-resource constraints
- Parallelism: sequential or parallel only with synchronized incumbent/frontier/bound semantics
- Exactness: exact only when the declared optimality and observable-tie contract is proven; otherwise anytime/incomplete result semantics apply

For each unexplored region `R`, define a bound `b(R)` separately from `f`:

- minimizing: `b(R) ≤ inf { f(x) | x ∈ F ∩ R }`;
- maximizing: `b(R) ≥ sup { f(x) | x ∈ F ∩ R }`.

If the target contract accepts **any one scalar optimum** and equal-objective candidates are not observably distinct, minimization may prune `R` when `b(R) >= f(x_incumbent)` and maximization may prune when `b(R) <= f(x_incumbent)`.

If equal-objective candidates remain observable—for example the target requires a deterministic tie winner, a secondary total ordering, or enumeration of all optimal candidates—equality is not enough to discard a region under the scalar bound alone. In that case either:

- use strict objective pruning while unresolved ties remain (`b(R) > f(x_incumbent)` for minimization; `b(R) < f(x_incumbent)` for maximization), and continue exploring equality-bound regions as required by C; or
- define a separately sound bound over the **complete declared tie ordering/frontier** and validate that stronger bound independently.

An independently proven infeasible region may also be pruned. A heuristic estimate that does not satisfy the declared bound relation is search-ordering evidence at most, not a pruning proof. This record does not authorize scalar bounds to prune vector/Pareto or partially ordered objectives.

## Preserved contract

A region may be discarded only when its sound bound proves it cannot contain any candidate that remains observably preferable or required under the target's scalar objective **and tie contract**. Heuristic guesses are not proof-based pruning. Exhausting B without an optimality proof does not permit an exactness claim, and exhausting B without a feasible incumbent does not permit an infeasibility claim.

## Optimization

Maintain an incumbent when one exists, partition the search space, compute a cheap sound `b(R)` for each region (often from a relaxation), prioritize promising regions, and prune only when the direction-specific bound plus the target's tie semantics prove the region cannot affect the required answer. Before the first incumbent exists, sound bounds may prioritize regions or prove individual regions infeasible, but incumbent-based objective pruning is unavailable.

A relaxed solution is evidence for a bound, not automatically a feasible final answer.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No target exhaustive or unpruned search baseline has been established here.
- Optimized: No target branch-and-bound/pruned search result has been established here.
- Speedup / memory reduction: No transferable claim; this record captures a classical mechanism and adaptation rules.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

For small fixtures, compare with exhaustive enumeration. Test `b(R)` soundness independently by checking the direction-specific inequality against exhaustive feasible values inside each test region. Test pruning separately from search ordering. Include fixtures where the first feasible candidate is found late and where B expires before any feasible candidate exists; verify that the latter returns `no-incumbent / feasibility-unknown`, reports only independently valid global-bound information, and makes no infeasibility, optimality, or incumbent-based gap claim. Verify that budget exhaustion with an incumbent returns an anytime result without an exactness claim.

Add **equal-objective tie fixtures**. For an any-one-optimum contract, prove equality pruning cannot alter any observable result. For deterministic tie-winner contracts, construct regions containing equal-objective candidates with better/worse tie ranks and prove equality-bound regions are retained until the declared tie winner is established. For all-optima contracts, prove every equal-objective optimum is enumerated. If using a stronger total-order bound, validate its soundness independently against exhaustive fixtures.

## Target-repo adaptation

The quality/cost of bounds determines whether pruning helps. Develop target-specific scalar relaxations, branch ordering, feasible-candidate discovery strategy, **tie/secondary-order semantics**, and a finite resource cap before execution; do not assume one bound or budget is universally appropriate.

## Failure modes

Unsound bounds can remove the true optimum; weak bounds provide little pruning; expensive bounds can cost more than evaluation; numeric tolerance errors can create incorrect pruning; heuristic scores mislabeled as bounds invalidate the proof obligation; equality pruning can discard a required deterministic tie winner or additional optimum; applying scalar pruning logic to vector/Pareto objectives can discard nondominated candidates; an unbounded exact-search policy can consume resources indefinitely; treating budget exhaustion without an incumbent as evidence of infeasibility is unsound.

## Rollback trigger

Disable any pruning rule that fails exhaustive small-case validation, violates the declared scalar/tie-bound relation, is applied to an unsupported objective ordering, discards an equal-objective candidate required by C, or whose bound cost exceeds the work it eliminates. Abort exact-mode claims whenever B is exhausted before the full objective/tie contract is proven, and reject any implementation that converts a no-incumbent budget timeout into an infeasibility or optimality claim without a separate proof.
