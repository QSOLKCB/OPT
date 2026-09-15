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
- f: the target objective evaluated on feasible candidates only
- d: the target's predeclared minimize or maximize direction, or an explicit total/partial ordering that defines when one incumbent improves another
- C: the returned incumbent satisfies the original feasibility/semantic contract, and every pruning decision is justified by a separately defined sound region-bound function b
- B: for exact search, resources required until the search frontier is exhausted or optimality is proven; for anytime search, an explicit target-specific evaluation/time/compute budget
- S: exact mode stops only when optimality is proven or the frontier is exhausted; anytime mode stops on B and reports the incumbent plus the remaining optimality gap/bound

For each unexplored region `R`, define a bound `b(R)` separately from `f`:

- minimizing: `b(R) ≤ inf { f(x) | x ∈ F ∩ R }`; prune `R` only when `b(R) ≥ f(x_incumbent)`;
- maximizing: `b(R) ≥ sup { f(x) | x ∈ F ∩ R }`; prune `R` only when `b(R) ≤ f(x_incumbent)`.

An independently proven infeasible region may also be pruned. A heuristic estimate that does not satisfy the declared bound relation is search-ordering evidence at most, not a pruning proof.

## Preserved contract

A region may be discarded only when its bound proves it cannot improve the incumbent under the declared objective and constraints. Heuristic guesses are not proof-based pruning.

## Optimization

Maintain an incumbent, partition the search space, compute a cheap sound `b(R)` for each region (often from a relaxation), prioritize promising regions, and prune only when the direction-specific bound relation proves the region cannot improve the incumbent.

A relaxed solution is evidence for a bound, not automatically a feasible final answer.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No target exhaustive or unpruned search baseline has been established here.
- Optimized: No target branch-and-bound/pruned search result has been established here.
- Speedup / memory reduction: No transferable claim; this record captures a classical mechanism and adaptation rules.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

For small fixtures, compare with exhaustive enumeration. Test `b(R)` soundness independently by checking the direction-specific inequality against exhaustive feasible values inside each test region. Test pruning separately from search ordering, and record the optimality gap when stopping before exact completion.

## Target-repo adaptation

The quality/cost of bounds determines whether pruning helps. Develop target-specific relaxations and branch ordering; do not assume one bound is universally strong.

## Failure modes

Unsound bounds can remove the true optimum; weak bounds provide little pruning; expensive bounds can cost more than evaluation; numeric tolerance errors can create incorrect pruning; heuristic scores mislabeled as bounds invalidate the proof obligation.

## Rollback trigger

Disable any pruning rule that fails exhaustive small-case validation, violates the declared bound relation, or whose bound cost exceeds the work it eliminates.
