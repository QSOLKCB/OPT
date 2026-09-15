# OPT-REDUCE-001 — Early working-set reduction

**Status:** Implemented external pattern; broadly applicable mechanism  
**Domains:** databases, graphs, simulation, DSP, rendering, data pipelines

## Source evidence

- https://jazco.dev/2023/08/10/query-optimization/
- supporting sparse-evaluation pattern in `OPT-DSP-001`

## Problem

An expensive operation is applied to a large population even though only a small subset can affect the final result.

## Optimization problem contract

- X: semantically legal placements and implementations of filtering, culling, limiting, candidate selection, or other working-set reductions in the target pipeline, including any target-specific predicate rewrite required to move a reduction across a stage
- F: placements for which every reduction predicate is proven to commute with every crossed stage or is replaced by a semantics-preserving pre-stage predicate, while also preserving every candidate and every contractually observable behavior required by the reference pipeline—including output, ordering/tie/join semantics, errors/exceptions, writes, mutations, auditing/telemetry, and other side effects. Purity of a crossed stage proves only that displaced side effects are absent; it does not by itself prove that moving the predicate preserves values or membership
- f: measured end-to-end pipeline cost and cardinality presented to the expensive stage
- d: minimize under the target's predeclared objective ordering
- C: the reordered/reduced pipeline is semantically equivalent to the reference for all declared outputs **and observable effects**; for every crossed transformation `T` and post-stage predicate `p`, the early form must either use an equivalent predicate `p'` satisfying the target's declared commutation/rewrite law (for example `p(T(x)) = p'(x)` for every relevant `x`) or otherwise prove equivalent candidate membership and downstream semantics; an effectful stage may be bypassed for discarded candidates only when those effects/errors are explicitly proven irrelevant by the target contract
- B: target-specific benchmark budget over representative and adversarial selectivity distributions; no portable selectivity threshold is supplied here
- S: stop when the declared budget is exhausted or a validated early-reduction placement materially lowers total cost without violating C
- Variables: categorical / conditional / mixed placement and predicate choices
- Search scope: local pipeline-reordering / working-set-reduction decisions
- Objective behavior: noisy for performance; semantic equivalence is deterministic
- Information: derivative-free / black-box performance measurements
- Evaluation cost: moderate to expensive depending on downstream stage cost and workload size
- Constraints: predicate-commutation/rewrite equivalence, output, ordering/tie/join, side-effect/error, purity, and resource constraints
- Parallelism: sequential pipeline semantics with target-specific parallel execution only where equivalence remains valid
- Exactness: exact observable semantics; no approximation is introduced

## Preserved contract

Moving a reduction earlier is valid only when the reduction predicate remains semantically equivalent across **every crossed stage**. Purity is necessary only to establish that moving past the stage does not displace observable effects; purity alone is not sufficient to justify the reorder. For a transformation `T` followed by predicate `p`, the early placement must either prove that `p` commutes with `T` or use a correctly rewritten pre-stage predicate `p'` with an invariant such as `p(T(x)) = p'(x)` for every relevant input, together with preservation of any downstream values/order required after `T`. The full observable contract also includes final values, ordering/top-k/tie/join semantics, exceptions/error checks, writes/mutations, audit events, metrics, and other externally visible side effects where they are significant.

## Optimization

Push selective operations toward the input boundary only when doing so is semantics-preserving. Before crossing a stage, derive and validate the predicate relation for that stage: retain the same predicate only when it provably commutes, otherwise rewrite it to an equivalent pre-stage predicate, or do not push it across the stage. For example, a post-transform filter `value > 10` cannot be naively moved before a pure `value = input * 2` transform; over a compatible numeric domain it would require the proven rewrite `input > 5` (with boundary, overflow, NaN, rounding, and type semantics handled according to the target contract). Then filter before a pure expensive join/transform, cull before pure rendering work, select candidate roots before pure DSP calculation, or eliminate simulations proven unable to affect any required result/effect only when that relation is established.

If the expensive stage is effectful, either keep the effectful portion on every candidate that would have reached it in the reference path, split the stage into a pure expensive computation and a required effect layer, or prove those skipped effects/errors are outside the declared contract. Do not optimize away observable behavior merely because the final data rows match.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim; external query observations and existing sparse-evaluation patterns are source evidence only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Differential-test reordered pipelines against the reference, with emphasis on ties, null/missing values, boundary ordering and rare candidates. For **each crossed stage**, validate the declared commutation law or rewritten predicate over representative, boundary, randomized, and adversarial inputs; compare both candidate membership and final downstream values. Include a negative fixture where `T(x) = 2*x` and the reference applies `value > 10`: prove that naively applying `input > 10` before `T` is rejected because it drops values such as `x = 6`, and prove that any proposed `input > 5` rewrite is accepted only for a domain whose overflow, numeric, and boundary semantics make the equivalence valid.

Also compare observable side effects and error behavior: writes/mutations, audit/log/metric events, callbacks, exception/error surfaces and their relevant ordering/counts. Include a deliberately effectful fixture to prove the optimization is rejected or preserves the effects, and a pure-but-noncommuting fixture to prove purity alone never authorizes predicate motion.

## Target-repo adaptation

Measure selectivity and reduction cost. For every candidate reorder, enumerate the crossed stages, classify each stage as pure or effectful, and record the predicate-commutation proof or explicit predicate rewrite required for that stage. Inventory contractually significant side effects/errors and define how each is preserved. Do not infer predicate mobility from purity alone. A cheap filter with low selectivity may simply add another pass.

## Failure modes

Illegal predicate reordering, assuming purity implies predicate commutation, an incorrect or domain-incomplete predicate rewrite, changed top-k semantics, underestimated filtering cost, loss of vectorization, duplicated scans, skipped writes/audit events/mutations, changed exceptions or validation failures, and reordered side effects can all make an apparently equivalent final result semantically wrong.

## Rollback trigger

Immediately revert if any crossed stage lacks a valid commutation/rewrite proof, if differential testing finds different candidate membership or downstream values, or if any output, ordering, error, or contractually significant side effect differs from the reference path. Also revert if total measured cost does not fall on representative workloads.
