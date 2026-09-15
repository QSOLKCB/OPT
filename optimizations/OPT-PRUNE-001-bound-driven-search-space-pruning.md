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

- Search space `X`, feasible set `F`, objective `f`
- Incumbent: best validated feasible solution
- Bound: optimistic objective bound for each unexplored region
- Exactness: declare whether full branch-and-bound proof or anytime/budgeted search is required

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
