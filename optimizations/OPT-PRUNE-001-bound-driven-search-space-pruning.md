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
- C: every returned incumbent satisfies the original feasibility/semantic contract, every pruning decision is justified by a separately defined sound scalar region-bound function `b`, and budget exhaustion without a feasible incumbent produces an explicit unknown/no-incumbent outcome rather than a feasibility or optimality claim
- B: a finite, predeclared target-specific cap on evaluations, wall time, compute, or equivalent resource consumption; exact-mode search may prove optimality before this cap but may not run without a finite cap
- S: stop immediately when optimality is proven or the frontier is exhausted; otherwise stop when B is exhausted. If a validated incumbent exists, return it plus any remaining valid global bound/optimality gap. If no feasible incumbent exists, return `no-incumbent / feasibility-unknown` and only a separately valid global bound if one is available; do not report an optimality gap that requires an incumbent, and do not claim infeasibility or optimality

For each unexplored region `R`, define a bound `b(R)` separately from `f`:

- minimizing: `b(R) ≤ inf { f(x) | x ∈ F ∩ R }`; prune `R` only when `b(R) ≥ f(x_incumbent)`;
- maximizing: `b(R) ≥ sup { f(x) | x ∈ F ∩ R }`; prune `R` only when `b(R) ≤ f(x_incumbent)`.

An independently proven infeasible region may also be pruned. A heuristic estimate that does not satisfy the declared bound relation is search-ordering evidence at most, not a pruning proof. This record does not authorize scalar bounds to prune vector/Pareto or partially ordered objectives.

## Preserved contract

A region may be discarded only when its scalar bound proves it cannot improve the incumbent under the declared scalar objective and constraints. Heuristic guesses are not proof-based pruning. Exhausting B without an optimality proof does not permit an exactness claim, and exhausting B without a feasible incumbent does not permit an infeasibility claim.

## Optimization

Maintain an incumbent when one exists, partition the search space, compute a cheap sound `b(R)` for each region (often from a relaxation), prioritize promising regions, and prune only when the direction-specific scalar bound relation proves the region cannot improve the incumbent. Before the first incumbent exists, sound bounds may prioritize regions or prove individual regions infeasible, but incumbent-based objective pruning is unavailable.

A relaxed solution is evidence for a bound, not automatically a feasible final answer.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No target exhaustive or unpruned search baseline has been established here.
- Optimized: No target branch-and-bound/pruned search result has been established here.
- Speedup / memory reduction: No transferable claim; this record captures a classical mechanism and adaptation rules.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

For small fixtures, compare with exhaustive enumeration. Test `b(R)` soundness independently by checking the direction-specific inequality against exhaustive feasible values inside each test region. Test pruning separately from search ordering. Include fixtures where the first feasible candidate is found late and where B expires before any feasible candidate exists; verify that the latter returns `no-incumbent / feasibility-unknown`, reports only independently valid global-bound information, and makes no infeasibility, optimality, or incumbent-based gap claim. Verify that budget exhaustion with an incumbent returns an anytime result without an exactness claim.

## Target-repo adaptation

The quality/cost of bounds determines whether pruning helps. Develop target-specific scalar relaxations, branch ordering, feasible-candidate discovery strategy, and a finite resource cap before execution; do not assume one bound or budget is universally appropriate.

## Failure modes

Unsound bounds can remove the true optimum; weak bounds provide little pruning; expensive bounds can cost more than evaluation; numeric tolerance errors can create incorrect pruning; heuristic scores mislabeled as bounds invalidate the proof obligation; applying scalar pruning logic to vector/Pareto objectives can discard nondominated candidates; an unbounded exact-search policy can consume resources indefinitely; treating budget exhaustion without an incumbent as evidence of infeasibility is unsound.

## Rollback trigger

Disable any pruning rule that fails exhaustive small-case validation, violates the declared scalar bound relation, is applied to an unsupported objective ordering, or whose bound cost exceeds the work it eliminates. Abort exact-mode claims whenever B is exhausted before optimality is proven, and reject any implementation that converts a no-incumbent budget timeout into an infeasibility or optimality claim without a separate proof.
