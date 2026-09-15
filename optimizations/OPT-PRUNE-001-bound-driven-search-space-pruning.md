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
- C: every returned incumbent satisfies the original feasibility/semantic contract, every pruning decision is justified by a separately defined sound scalar region-bound function `b`, the target's observable tie semantics are preserved, parallel dispatch cannot oversubscribe the declared hard budget, **every unit of resource consumption covered by a hard wall-time/compute B is accounted for or enclosed by an enforceable whole-search cap**, every hard peak-memory B is enforced over live allocated/reserved memory rather than cumulative historical allocation, and frontier exhaustion is declared only after all queued **and leased/in-flight** regions are accounted for
- B: a finite, predeclared target-specific **enforceable** cap with its accounting semantics declared explicitly. Evaluation count, money/provider spend, CPU/GPU-seconds, energy, bytes transferred, or other cumulative-flow resources use cumulative accounting. Elapsed wall time uses one shared whole-search deadline. **Peak memory is a stock constraint, not a cumulative flow:** enforce `live_allocated + live_reserved + proposed <= B`, release live capacity when memory is freed, and retain only a recorded `peak_observed` for evidence. If a target instead wants cumulative allocation traffic, it must declare that as a distinct cumulative metric rather than calling it peak memory. Any resource dimension that cannot be hard-capped under its declared semantics must be labeled observational/best-effort rather than advertised as hard B
- S: stop immediately when the required optimality/tie contract is proven, or when the **global frontier is exhausted**, meaning there are no queued regions, no leased/in-flight regions still capable of producing candidates/children, and no unpublished child/frontier updates owned by active work. Otherwise stop when B is exhausted. If a validated incumbent exists, return it plus any remaining valid global bound/optimality gap. If no feasible incumbent exists, return `no-incumbent / feasibility-unknown` and only a separately valid global bound if one is available; do not report an optimality gap that requires an incumbent, and do not claim infeasibility or optimality
- Variables: integer / categorical / discrete / mixed
- Search scope: global over the declared candidate space
- Objective behavior: deterministic unless uncertainty/noise is incorporated into a separately sound bound model
- Information: derivative-free; bound/relaxation information is target-specific
- Evaluation cost: moderate to expensive when exhaustive evaluation is infeasible
- Constraints: feasibility, semantic correctness, scalar-bound soundness, tie semantics, global-frontier accounting, and enforceable finite-resource constraints including correctly typed cumulative, deadline, and peak/live-capacity budgets
- Parallelism: sequential, or parallel only with synchronized incumbent/frontier/bound state, **leased/in-flight region accounting**, linearizable reservation/completion accounting for cumulative resources, a shared absolute deadline for elapsed wall time, and live-allocation reservation accounting for hard peak-memory caps
- Exactness: exact only when the declared optimality and observable-tie contract is proven within B, including proof that no queued or leased region can still affect the answer; otherwise anytime/incomplete result semantics apply

For each unexplored region `R`, define a bound `b(R)` separately from `f`:

- minimizing: `b(R) ≤ inf { f(x) | x ∈ F ∩ R }`;
- maximizing: `b(R) ≥ sup { f(x) | x ∈ F ∩ R }`.

If the target contract accepts **any one scalar optimum** and equal-objective candidates are not observably distinct, minimization may prune `R` when `b(R) >= f(x_incumbent)` and maximization may prune when `b(R) <= f(x_incumbent)`.

If equal-objective candidates remain observable—for example the target requires a deterministic tie winner, a secondary total ordering, or enumeration of all optimal candidates—equality is not enough to discard a region under the scalar bound alone. In that case either:

- use strict objective pruning while unresolved ties remain (`b(R) > f(x_incumbent)` for minimization; `b(R) < f(x_incumbent)` for maximization), and continue exploring equality-bound regions as required by C; or
- define a separately sound bound over the **complete declared tie ordering/frontier** and validate that stronger bound independently.

An independently proven infeasible region may also be pruned. A heuristic estimate that does not satisfy the declared bound relation is search-ordering evidence at most, not a pruning proof. This record does not authorize scalar bounds to prune vector/Pareto or partially ordered objectives.

## Preserved contract

A region may be discarded only when its sound bound proves it cannot contain any candidate that remains observably preferable or required under the target's scalar objective **and tie contract**. Heuristic guesses are not proof-based pruning. Exhausting B without an optimality proof does not permit an exactness claim, exhausting B without a feasible incumbent does not permit an infeasibility claim, and parallel execution must preserve the same hard resource ceiling as sequential execution rather than oversubscribing work in flight. A temporarily empty shared queue is **not** frontier exhaustion while any worker owns a leased region that may still produce a candidate, proof obligation, or child region. Likewise, a hard wall-time/compute B applies to the whole search, while a hard peak-memory B applies to current live/reserved memory and must not be converted into irreversible historical consumption after memory is freed.

## Optimization

Maintain an incumbent when one exists, partition the search space, compute a cheap sound `b(R)` for each region (often from a relaxation), prioritize promising regions, and prune only when the direction-specific bound plus the target's tie semantics prove the region cannot affect the required answer. Before the first incumbent exists, sound bounds may prioritize regions or prove individual regions infeasible, but incumbent-based objective pruning is unavailable.

For **parallel** search, define one global frontier lifecycle. A region remains part of the frontier from enqueue until it is either (a) soundly pruned/closed, or (b) replaced by its child regions through an atomic/linearizable completion transition. Dequeuing for worker ownership therefore changes a region from `queued` to `leased/in-flight`; it does **not** remove that region from the global frontier. A worker that branches a leased region must publish all resulting children and close/release the parent as one frontier-accounting transition, or use another protocol that cannot expose a moment where the queue is empty even though unpublished descendants still exist. Worker failure/cancellation must return or recover the lease so unexplored work is not silently lost.

Treat hard resources according to their physical/accounting semantics rather than forcing them through one ledger shape:

- **Cumulative-flow budgets** such as evaluation count, money/provider spend, CPU/GPU-seconds, energy, or declared cumulative bytes use linearizable reservations. Atomically reserve before covered work starts; if `consumed + reserved + proposed_reservation > B`, do not start it. Completion/failure/cancellation moves actual consumed usage into permanent `consumed` and releases only demonstrably unconsumed reservation.
- **Elapsed wall time** uses one enforceable monotonic whole-search deadline shared by workers and coordinator paths. Parallel overlap is not double-counted as if seconds were additive reservations, and retries/workers cannot reset or extend the deadline.
- **Peak/live-capacity resources** such as peak memory use live state rather than permanent consumption. Atomically reserve enough live capacity before an allocation-producing operation starts; require `live_allocated + live_reserved + proposed <= B`; on successful allocation move reserved capacity to `live_allocated`; on free/reclamation release the live allocation so later non-overlapping work may reuse the capacity. Maintain `peak_observed = max(peak_observed, live_allocated + live_reserved)` for audit/evidence. Freed memory must not remain in cumulative `consumed` unless the separately declared metric is cumulative allocation traffic rather than peak memory.

The relevant hard cap must cover all search work that can consume that resource, including candidate/bound evaluation, branching, child construction, queue/frontier operations, serialization, incumbent updates, synchronization and cleanup. Per-evaluation controls do not by themselves prove a whole-search wall-time, compute, spend, or peak-memory bound.

If the target meters only candidate/bound evaluations, then only **evaluation count** may be claimed as a hard B from that accounting. Nominal wall-time/compute/memory targets in that design are observational/best-effort and cannot justify finite-cap correctness claims. Similarly, if branching/frontier/serialization overhead can escape an otherwise claimed resource cap, that resource dimension is not hard-bounded.

A relaxed solution is evidence for a bound, not automatically a feasible final answer.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: No target exhaustive or unpruned search baseline has been established here.
- Optimized: No target branch-and-bound/pruned search result has been established here.
- Speedup / memory reduction: No transferable claim; this record captures a classical mechanism and adaptation rules.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

For small fixtures, compare with exhaustive enumeration. Test `b(R)` soundness independently by checking the direction-specific inequality against exhaustive feasible values inside each test region. Test pruning separately from search ordering. Include fixtures where the first feasible candidate is found late and where B expires before any feasible candidate exists; verify that the latter returns `no-incumbent / feasibility-unknown`, reports only independently valid global-bound information, and makes no infeasibility, optimality, or incumbent-based gap claim. Verify that budget exhaustion with an incumbent returns an anytime result without an exactness claim.

Add **parallel frontier-exhaustion races**. Use a fixture where the last queued region is leased by one worker, making the shared queue empty, then pause that worker before it publishes one or more child regions. Prove the coordinator does not declare exhaustion or exact optimality while that lease remains live. Resume the worker and verify the children become searchable and the final result matches exhaustive/scalar search. Also inject worker failure/cancellation while holding the last lease and verify the region is recovered/requeued or otherwise completed without losing unexplored work. Test simultaneous parent-close/child-publish transitions and prove there is no observation in which both queued and leased frontier counts reach zero before all descendants are durably accounted for.

Add **parallel budget-boundary fixtures**. Race multiple workers against one remaining evaluation slot and prove only one reservation succeeds for an evaluation-count B. Race bound evaluations and candidate evaluations against the same final cumulative capacity and prove both charge the declared ledger. For elapsed wall time, run overlapping workers to the same absolute deadline and prove overlap is not double-counted while no worker/coordinator survives past the enforced deadline. For cumulative compute/spend, deliberately make branching/frontier/serialization work expensive and prove it is charged before the cap is exceeded.

Add a **peak-memory reuse fixture**. Under a hard peak-memory B, run many sequential/non-overlapping branches that each allocate and then free a large work buffer. Prove each live allocation/reservation is admitted only while `live_allocated + live_reserved <= B`, freed capacity becomes reusable, `peak_observed <= B`, and the search does **not** exhaust merely because the sum of historical allocations exceeds B. Then overlap enough workers to exceed the peak if all allocations were admitted and prove the final reservation is rejected/blocked before live memory can cross B. Race allocation, free, cancellation and cleanup to verify live-memory accounting remains linearizable and no capacity is released before the corresponding memory is actually reclaimable.

Add **equal-objective tie fixtures**. For an any-one-optimum contract, prove equality pruning cannot alter any observable result. For deterministic tie-winner contracts, construct regions containing equal-objective candidates with better/worse tie ranks and prove equality-bound regions are retained until the declared tie winner is established. For all-optima contracts, prove every equal-objective optimum is enumerated. If using a stronger total-order bound, validate its soundness independently against exhaustive fixtures.

## Target-repo adaptation

The quality/cost of bounds determines whether pruning helps. Develop target-specific scalar relaxations, branch ordering, feasible-candidate discovery strategy, **tie/secondary-order semantics**, and a finite resource cap before execution; do not assume one bound or budget is universally appropriate. For parallel implementations, define the global frontier state machine, lease ownership/recovery rules, parent-close/child-publish atomicity, and the exact exhaustion predicate over queued plus leased/in-flight work. Also define each budget's accounting type and enforcement boundary: cumulative flow (`consumed + reserved`), elapsed deadline, or peak/live capacity (`live_allocated + live_reserved`, plus `peak_observed`). If a target says “memory budget,” state whether it means peak live memory or cumulative allocation traffic. Downgrade any dimension that can escape its correct enforcement boundary to best-effort/observational rather than calling it hard B.

## Failure modes

Unsound bounds can remove the true optimum; weak bounds provide little pruning; expensive bounds can cost more than evaluation; numeric tolerance errors can create incorrect pruning; heuristic scores mislabeled as bounds invalidate the proof obligation; equality pruning can discard a required deterministic tie winner or additional optimum; applying scalar pruning logic to vector/Pareto objectives can discard nondominated candidates; treating queue-empty as frontier-empty can declare exact completion while a leased region still owns unexplored descendants; losing a worker lease can silently drop search regions; non-atomic parent-close/child-publication can create false exhaustion; parallel workers without linearizable evaluation reservations can oversubscribe the last evaluation slot; branching/child/frontier/serialization/incumbent overhead can exceed a nominal wall-time/compute B if only evaluations are charged; an unenforced coordinator/cleanup path can outlive a claimed whole-search deadline; treating peak memory as cumulative consumed spend can falsely exhaust a valid search and prevent reuse of freed capacity; releasing live-memory capacity before actual reclamation can instead oversubscribe the peak; treating an unenforceable resource target as hard B makes the stopping contract false; treating budget exhaustion without an incumbent as evidence of infeasibility is unsound.

## Rollback trigger

Disable any pruning rule that fails exhaustive small-case validation, violates the declared scalar/tie-bound relation, is applied to an unsupported objective ordering, discards an equal-objective candidate required by C, or whose bound cost exceeds the work it eliminates. Abort parallel/exact mode if frontier exhaustion can be observed while any leased/in-flight region may still produce work, if parent-close/child-publication or lease recovery can lose unexplored regions, if workers can oversubscribe an evaluation-count/cumulative budget, if an elapsed deadline can be reset/escaped, if peak live memory can exceed B, if freed peak-memory capacity is incorrectly made permanently unavailable, or if any resource-consumption path can escape a dimension advertised as hard. Abort exact-mode claims whenever B is exhausted before the full objective/tie/frontier contract is proven, and reject any implementation that converts a no-incumbent budget timeout into an infeasibility or optimality claim without a separate proof.
