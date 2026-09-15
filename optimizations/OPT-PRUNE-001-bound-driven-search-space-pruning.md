# OPT-PRUNE-001 — Bound-driven search-space pruning

**Status:** Classical optimization mechanism; OPT adaptation guidance  
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
- f: the target objective evaluated on feasible candidates, plus a sound optimistic bound for each unexplored subregion
- d: the target's predeclared minimize or maximize direction, or an explicit ordering that defines when one incumbent improves another
- C: every pruning bound is sound for the declared objective/constraints and the returned incumbent satisfies the original feasibility and semantic contract
- B: for exact search, resources required until the search frontier is exhausted or optimality is proven; for anytime search, an explicit target-specific evaluation/time/compute budget
- S: exact mode stops only when optimality is proven or the frontier is exhausted; anytime mode stops on B and reports the incumbent plus the remaining optimality gap/bound

## Preserved contract

A region may be discarded only when its bound proves it cannot improve the incumbent under the declared objective and constraints. Heuristic guesses are not proof-based pruning.

## Optimization

Maintain an incumbent, partition the search space, compute cheap optimistic bounds (often from relaxations), prioritize promising regions and prune any region whose best possible outcome cannot beat the incumbent.

A relaxed solution is evidence for a bound, not automatically a feasible final answer.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No target exhaustive or unpruned search baseline has been established here.
- Optimized: No target branch-and-bound/pruned search result has been established here.
- Speedup / memory reduction: No transferable claim; this record captures a classical mechanism and adaptation rules.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

For small fixtures, compare with exhaustive enumeration. Test bound soundness separately from search ordering. Record the optimality gap when stopping before exact completion.

## Target-repo adaptation

The quality/cost of bounds determines whether pruning helps. Develop target-specific relaxations and branch ordering; do not assume one bound is universally strong.

## Failure modes

Unsound bounds can remove the true optimum; weak bounds provide little pruning; expensive bounds can cost more than evaluation; numeric tolerance errors can create incorrect pruning.

## Rollback trigger

Disable any pruning rule that fails exhaustive small-case validation or whose bound cost exceeds the work it eliminates.
