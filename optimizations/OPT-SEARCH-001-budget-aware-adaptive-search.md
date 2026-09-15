# OPT-SEARCH-001 — Budget-aware adaptive parameter search

**Status:** Proposed / OPT synthesis; upstream mechanisms are implemented externally  
**Domains:** expensive black-box tuning, CI/runtime parameters, simulation, numerical kernels

## Source evidence

- `bayesian-optimization/BayesianOptimization` inspected at `af8b928212f0eacd1ce20c20be72c1a7b1d8d421`
- `hyperopt/hyperopt` inspected at `9834314879c09c13e0b8e93eb678408ba46441a8`
- `stevengj/nlopt` inspected at `6e6593f131ba3a38bc9edbed0a357bc01526e54b`
- `sources/OPTIMIZATION-LIBRARIES.md`

## Problem

Optimization knobs are selected by folklore, exhaustive sweeps, or a few arbitrary values even when each benchmark evaluation is expensive.

## Optimization problem contract

- X: the target's explicitly bounded continuous, integer, categorical, conditional, or mixed parameter search space
- F: candidates in X that satisfy all hard resource, platform, semantic, and correctness constraints before objective ranking
- f: the target-measured objective or objective vector for each feasible candidate, including declared noise/statistical treatment
- d: the target's predeclared minimize, maximize, lexicographic, or Pareto ordering
- C: search may choose where to evaluate but may not weaken correctness, evidence, API, trust, or other target semantics to improve f; asynchronous dispatch must preserve the declared budget model under concurrency; additive resources such as evaluation count, compute, and spend use linearizable consumed/reserved accounting with enforceable per-trial caps, while elapsed wall-time budgets use one enforceable absolute search deadline shared by every worker; and targets that require deterministic search outcomes must use deterministic observation assimilation **and deterministic proposal/dispatch/refill scheduling** independent of wall-clock completion order
- B: an explicit target-specific hard maximum declared before the search starts together with its **budget semantics**: additive resources (for example evaluation count, compute units, or money) use conservative enforceable reservations from one shared ledger, whereas elapsed wall time uses one absolute monotonic search deadline that bounds the whole concurrent search rather than summing overlapping worker seconds; the accounting unit, enforcement mechanism, atomic boundary, and failure/cancellation charging policy are fixed before dispatch begins
- S: stop proposing/dispatching when no additional work is admissible under B, when the absolute wall-time deadline has arrived, when a predeclared objective/quality target is met, or when a predeclared stagnation/convergence rule fires; preserve the reason for stopping in the trial ledger and apply proposal, dispatch/refill, assimilation, and stopping decisions to the declared deterministic schedule when determinism is required
- Variables: mixed search spaces; may include continuous, integer, categorical, and conditional dimensions as explicitly declared by the target
- Search scope: local or global, explicitly declared for the target
- Objective behavior: deterministic, noisy, or stochastic as declared by the target; noise treatment must be explicit
- Information: derivative-free / black-box by default; gradient information may be used only when the selected target mechanism supports it
- Evaluation cost: typically expensive
- Constraints: bounds, semantic correctness, resource, platform, and target-specific equality/inequality constraints
- Parallelism: sequential / synchronous batch / asynchronous, explicitly declared
- Exactness: target evaluations must satisfy C exactly; the search itself need not prove a global optimum unless the target contract requires it

## Preserved contract

Search may choose *where to evaluate* but may not weaken correctness constraints to improve the objective. Under asynchronous execution, the declared maximum budget remains a hard bound according to its declared semantics. For **additive** resources, actual consumed resources plus all still-reserved in-flight capacity must remain within B, no individual trial may consume beyond its reserved cap, and concurrent dispatch/completion transitions must not transiently expose phantom free capacity. For **elapsed wall time**, all workers share one absolute search deadline; overlapping trials do not consume duplicate elapsed seconds, but no proposal, trial, retry, assimilation step, or cleanup that is part of the bounded search may continue past the enforceable deadline except target-declared bounded termination cleanup. If the target requires deterministic selected configurations or trial traces, **both the observation prefix used to create each proposal and the schedule that decides when a new proposal may be generated/dispatched must be deterministic**; worker completion timing may not change the proposal sequence.

## Optimization

Use observations to adapt future evaluations: surrogate/acquisition search for expensive black-box objectives, conditional spaces where parameters only exist under certain choices, progressive domain contraction where justified, and explicit stopping/evaluation budgets. For asynchronous workers, reserve pending regions or otherwise diversify proposals so workers do not redundantly evaluate the same neighborhood.

First classify each hard budget dimension. **Additive budgets**—for example evaluation slots, billable compute, accelerator-seconds, or monetary spend—use one atomic/serializable accounting ledger. Before dispatching a trial against an additive budget, reserve a conservative amount and record the pending trial. If `consumed + reserved + proposed_reservation > B`, do not dispatch. The reservation must be an **enforceable upper limit** for that trial, not merely an estimate: use an evaluation-slot token, provider spending cap, cgroup/job compute quota, or another mechanism that prevents actual additive consumption from exceeding the reservation. If the target cannot enforce such a cap for an additive resource dimension, that dimension cannot be advertised as a hard maximum B; define a different enforceable budget or classify the quantity as observational.

An **elapsed wall-time budget is different**. At search start, compute one absolute deadline from a monotonic clock and make every worker, trial, retry, proposal, model update, and stopping decision subordinate to that same deadline. Do not add overlapping worker durations into `consumed + reserved`; two trials that run concurrently until the same ten-minute deadline consume at most ten minutes of elapsed search time, not twenty. A trial-specific timeout may be shorter, but never later than the remaining global deadline. Dispatch must stop when insufficient time remains for the target's declared safe launch/termination policy, and the runtime must be able to cancel/terminate in-flight work at the global deadline if wall time is claimed as hard.

Completion, failure, cancellation, and forced termination for **additive** resources use the same atomic accounting boundary as dispatch reservation. For one terminal transition, atomically: (1) read the trial's reservation, (2) meter/record the amount actually consumed, (3) move that consumed amount into permanent `consumed`, (4) release only the demonstrably unconsumed remainder from `reserved`, and (5) mark the trial terminal. No dispatcher may observe released reservation capacity before the corresponding consumed charge is committed, and concurrent terminal updates must not lose increments. Completion must not double-charge the same usage. A failed or cancelled trial never erases additive resources already consumed. For an evaluation-count budget, dispatch consumes the evaluation slot and it is not refunded merely because the trial later fails or is cancelled. For money/compute budgets, release only the measured or otherwise provable unused portion of the enforceable reservation. If unconsumed capacity cannot be established safely, retain the conservative charge. For elapsed wall time, record start/finish/cancellation times for audit but enforce B via the shared absolute deadline rather than a refundable additive reservation. Every reservation, deadline/cap enforcement action, consumption adjustment, release, failure, cancellation, forced termination, and terminal accounting transaction is recorded in the ledger.

For targets that require deterministic search behavior, assign deterministic trial IDs and define a **deterministic proposal frontier**. A new proposal may be generated only from a declared ordered observation prefix that is the same in every replay. Buffer out-of-order completions until that prefix is available. Do **not** immediately refill whichever worker happens to become free if doing so would let wall-clock completion order choose the model state used for the next proposal. Acceptable deterministic designs include fixed deterministic batches/barriers, or an ordered-prefix scheduler where proposal `k+1` is generated only after the exact predeclared prefix needed for that proposal has been assimilated and its dispatch slot/order is determined independently of worker-speed races. Surrogate/model updates, acquisition decisions, domain contraction, portfolio-selection state, proposal generation, dispatch/refill decisions, and stopping criteria must consume the same deterministic state sequence. A fixed random seed plus buffered assimilation alone is not sufficient if worker availability can still change which proposal is generated next. If a target chooses immediate completion-driven refill for throughput, declare the resulting nondeterminism as an explicit contract change rather than claiming deterministic replay.

Parallelism has an information cost: very wide batches receive less feedback between suggestions and can degenerate toward non-adaptive/random search.

## Before / after evidence

- Environment: No controlled target-repository tuning study has been run for this OPT synthesis.
- Baseline: No target comparison against manual/exhaustive/random tuning has been established.
- Optimized: No target adaptive-search result has been established.
- Speedup / memory reduction: No transferable claim; upstream libraries establish mechanisms, not a QSOL target win.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Keep a deterministic search seed where practical, preserve the full trial ledger, re-evaluate finalists, and validate the selected candidate against the reference contract on held-out/repeated workloads. For asynchronous search with **additive** budgets, test the boundary with multiple workers contending for the last remaining reservation and prove no dispatch can make `consumed + reserved` exceed B. Deliberately run trials that attempt to exceed their per-trial money/compute reservation and prove the quota mechanism prevents the overrun. Inject early failures, late failures, partial consumption, and cancellation after measurable work; verify that only demonstrably unconsumed reservation is released, evaluation-count slots are not resurrected after dispatch, and repeated failures cannot create extra budget capacity.

For **elapsed wall-time** B, use a controlled monotonic clock and launch multiple workers concurrently under one shared deadline. Verify two trials each permitted to run until the same ten-minute deadline are admissible without requiring twenty minutes of additive reservation. Permute worker count, start order, and completion times; prove the search stops launching work as the deadline approaches, every in-flight worker observes the same deadline, forced termination completes within the declared enforcement bound, and total elapsed search lifetime never exceeds B plus only the explicitly declared bounded termination-cleanup allowance. Ensure no retry or model/proposal step can reset or extend the original deadline.

Race multiple additive-resource trial completions/cancellations against one another and against workers attempting the final dispatch slot. Verify the accounting transaction is linearizable: no consumed increment is lost, no reservation is released before its corresponding consumption is charged, and a dispatcher never observes capacity that would make the post-transaction invariant `consumed + reserved <= B` false.

For deterministic targets, run the same seeded search with deliberately permuted worker speeds and completion orders, including the case where trial 2 finishes before trial 1 and frees a worker first. Verify out-of-order completion **does not permit proposal 3 to be generated from a different observation prefix**. The complete proposal sequence, parameter values, deterministic trial IDs, logical dispatch/refill order, surrogate/search states, selected candidate, and stopping reason must match the deterministic reference. Test both fixed-batch/barrier scheduling and any ordered-prefix scheduler the target claims to support. Where sequential/parallel equivalence is part of C, compare the asynchronous execution with its deterministic sequential or batch replay. If completion-driven refill is intentionally retained, verify the target explicitly labels the search trace nondeterministic instead of claiming replay equivalence.

## Target-repo adaptation

Do not copy acquisition constants, trial counts, domain contraction rates or parallel widths. Treat them as optimizer parameters with their own evidence boundary. Define each budget dimension as either **additive** or **elapsed wall time**. For additive resources, define the accounting unit, conservative per-trial reservation amount, enforcement mechanism, one atomic/serializable reservation/completion ledger, metering source, and failure/cancellation charging policy. For elapsed wall time, define the monotonic absolute search deadline, maximum bounded termination-cleanup interval, worker cancellation/termination mechanism, and the minimum remaining-time rule for new dispatch. Also define the deterministic observation-assimilation policy, **deterministic proposal frontier and dispatch/refill schedule** (when required), and the exact condition under which a freed worker may receive new work before enabling asynchronous dispatch.

## Failure modes

Noisy objectives, nonstationary machines, weak surrogates, excessive dimensionality and too much concurrency can waste evaluations or overfit benchmark noise. Non-atomic reservation can oversubscribe an additive evaluation or monetary cap; non-atomic completion/release can transiently undercount consumed plus reserved or lose concurrent increments; an unenforced additive reservation can let a single trial exceed B before accounting observes it; refunding consumed resources can let repeated late failures exceed B; **treating elapsed wall time as an additive per-worker resource can falsely reject valid overlapping trials and serialize the search**; conversely, a nominal wall-time limit without one enforceable shared deadline can let work continue past B; wall-clock completion-order assimilation can make supposedly deterministic search traces irreproducible; **immediate worker refill can also make proposals nondeterministic even when assimilation itself is buffered**.

## Rollback trigger

Stop adaptive search when its overhead exceeds evaluation savings, the declared budget is exhausted, repeated validation does not confirm the selected improvement, any additive trial can consume beyond its enforceable reservation, additive accounting/concurrency tests can violate B, any hard elapsed-wall-time run can exceed its shared absolute deadline beyond the declared bounded cleanup allowance, a retry/worker can extend or reset that deadline, or any target that requires deterministic search produces different proposals, logical dispatch/refill order, model states, selected candidates, or stopping reasons under permuted asynchronous completion orders.
