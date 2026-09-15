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
- C: the returned incumbent satisfies the original feasibility/semantic contract, and every pruning decision is justified by a separately defined sound scalar region-bound function `b`
- B: a finite, predeclared target-specific cap on evaluations, wall time, compute, or equivalent resource consumption; exact-mode search may prove optimality before this cap but may not run without a finite cap
- S: stop immediately when optimality is proven or the frontier is exhausted; otherwise stop when B is exhausted and return the best validated incumbent plus the remaining valid bound/optimality gap without claiming exact completion

For each unexplored region `R`, define a bound `b(R)` separately from `f`:

- minimizing: `b(R) ≤ inf { f(x) | x ∈ F ∩ R }`; prune `R` only when `b(R) ≥ f(x_incumbent)`;
- maximizing: `b(R) ≥ sup { f(x) | x ∈ F ∩ R }`; prune `R` only when `b(R) ≤ f(x_incumbent)`.

An independently proven infeasible region may also be pruned. A heuristic estimate that does not satisfy the declared bound relation is search-ordering evidence at most, not a pruning proof. This record does not authorize scalar bounds to prune vector/Pareto or partially ordered objectives.

## Preserved contract

A region may be discarded only when its scalar bound proves it cannot improve the incumbent under the declared scalar objective and constraints. Heuristic guesses are not proof-based pruning, and exhausting B without an optimality proof does not permit an exactness claim.

## Optimization

Maintain an incumbent, partition the search space, compute a cheap sound `b(R)` for each region (often from a relaxation), prioritize promising regions, and prune only when the direction-specific scalar bound relation proves the region cannot improve the incumbent.

A relaxed solution is evidence for a bound, not automatically a feasible final answer.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No target exhaustive or unpruned search baseline has been established here.
- Optimized: No target branch-and-bound/pruned search result has been established here.
- Speedup / memory reduction: No transferable claim; this record captures a classical mechanism and adaptation rules.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

For small fixtures, compare with exhaustive enumeration. Test `b(R)` soundness independently by checking the direction-specific inequality against exhaustive feasible values inside each test region. Test pruning separately from search ordering. Verify that budget exhaustion returns an anytime result without an exactness claim, and record the remaining valid optimality gap/bound whenever exact completion was not proven.

## Target-repo adaptation

The quality/cost of bounds determines whether pruning helps. Develop target-specific scalar relaxations, branch ordering, and a finite resource cap before execution; do not assume one bound or budget is universally appropriate.

## Failure modes

Unsound bounds can remove the true optimum; weak bounds provide little pruning; expensive bounds can cost more than evaluation; numeric tolerance errors can create incorrect pruning; heuristic scores mislabeled as bounds invalidate the proof obligation; applying scalar pruning logic to vector/Pareto objectives can discard nondominated candidates; an unbounded exact-search policy can consume resources indefinitely.

## Rollback trigger

Disable any pruning rule that fails exhaustive small-case validation, violates the declared scalar bound relation, is applied to an unsupported objective ordering, or whose bound cost exceeds the work it eliminates. Abort exact-mode claims whenever B is exhausted before optimality is proven.
