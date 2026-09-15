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
- C: search may choose where to evaluate but may not weaken correctness, evidence, API, trust, or other target semantics to improve f; asynchronous dispatch must not exceed B after accounting for consumed and conservatively reserved in-flight resources; every per-trial reservation must be an enforceable upper bound rather than an estimate; dispatch/completion accounting must be linearizable; and targets that require deterministic search outcomes must use deterministic observation assimilation independent of wall-clock completion order
- B: an explicit target-specific hard maximum evaluation, wall-time, compute, monetary, or equivalent resource budget declared before the search starts; the accounting unit, enforceable per-trial cap mechanism, conservative reservation rule, atomic accounting boundary, and failure/cancellation charging policy are fixed before dispatch begins
- S: stop proposing/dispatching when no additional trial can be safely reserved within B, when a predeclared objective/quality target is met, or when a predeclared stagnation/convergence rule fires; preserve the reason for stopping in the trial ledger and apply stopping decisions to the declared deterministic assimilation order when determinism is required
- Variables: mixed search spaces; may include continuous, integer, categorical, and conditional dimensions as explicitly declared by the target
- Search scope: local or global, explicitly declared for the target
- Objective behavior: deterministic, noisy, or stochastic as declared by the target; noise treatment must be explicit
- Information: derivative-free / black-box by default; gradient information may be used only when the selected target mechanism supports it
- Evaluation cost: typically expensive
- Constraints: bounds, semantic correctness, resource, platform, and target-specific equality/inequality constraints
- Parallelism: sequential / synchronous batch / asynchronous, explicitly declared
- Exactness: target evaluations must satisfy C exactly; the search itself need not prove a global optimum unless the target contract requires it

## Preserved contract

Search may choose *where to evaluate* but may not weaken correctness constraints to improve the objective. Under asynchronous execution, the declared maximum budget remains a hard bound: actual consumed resources plus all still-reserved in-flight capacity must remain within B, no individual trial may consume beyond its reserved cap, and concurrent dispatch/completion transitions must not transiently expose phantom free capacity. If the target requires deterministic selected configurations or trial traces, proposal updates and stopping decisions must not depend on nondeterministic completion order.

## Optimization

Use observations to adapt future evaluations: surrogate/acquisition search for expensive black-box objectives, conditional spaces where parameters only exist under certain choices, progressive domain contraction where justified, and explicit stopping/evaluation budgets. For asynchronous workers, reserve pending regions or otherwise diversify proposals so workers do not redundantly evaluate the same neighborhood.

Before dispatching an asynchronous trial, enter one atomic/serializable accounting boundary, reserve a conservative amount of the applicable budget, and record the pending trial in the ledger. If `consumed + reserved + proposed_reservation > B`, do not dispatch. The reservation must be an **enforceable upper limit** for that trial, not merely an estimate: use a per-trial quota, wall-time deadline with forced cancellation/termination, provider spending cap, cgroup/job resource limit, evaluation-slot ownership, or another mechanism that prevents actual trial consumption from exceeding the reservation. If the target cannot enforce such a cap for a resource dimension, that dimension cannot be advertised as a hard maximum B; instead define a different enforceable budget or explicitly classify the quantity as observational rather than bounded.

Completion, failure, cancellation, and forced termination use the **same atomic accounting boundary** as dispatch reservation. For one terminal transition, atomically: (1) read the trial's reservation, (2) meter/record the amount actually consumed, (3) move that consumed amount into permanent `consumed`, (4) release only the demonstrably unconsumed remainder from `reserved`, and (5) mark the trial terminal. No dispatcher may observe released reservation capacity before the corresponding consumed charge is committed, and concurrent terminal updates must not lose increments. Completion must not double-charge the same usage. A failed or cancelled trial never erases resources already consumed. For an evaluation-count budget, dispatch consumes the evaluation slot and it is not refunded merely because the trial later fails or is cancelled. For money/compute/time budgets, release only the measured or otherwise provable unused portion of the enforceable reservation. If unconsumed capacity cannot be established safely, retain the conservative charge. Every reservation, cap enforcement action, consumption adjustment, release, failure, cancellation, forced termination, and terminal accounting transaction is recorded in the ledger.

For targets that require deterministic search behavior, assign a deterministic trial ID/order at proposal time and **buffer asynchronous completions for assimilation in that declared order** (or use explicit deterministic batches/barriers). Surrogate/model updates, acquisition decisions, domain contraction, portfolio-selection state, and stopping criteria must consume observations according to this deterministic order rather than wall-clock completion order. A fixed random seed alone is not sufficient. If a target chooses completion-order assimilation for throughput, declare the resulting nondeterminism as an explicit contract change rather than claiming deterministic replay.

Parallelism has an information cost: very wide batches receive less feedback between suggestions and can degenerate toward non-adaptive/random search.

## Before / after evidence

- Environment: No controlled target-repository tuning study has been run for this OPT synthesis.
- Baseline: No target comparison against manual/exhaustive/random tuning has been established.
- Optimized: No target adaptive-search result has been established.
- Speedup / memory reduction: No transferable claim; upstream libraries establish mechanisms, not a QSOL target win.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Keep a deterministic search seed where practical, preserve the full trial ledger, re-evaluate finalists, and validate the selected candidate against the reference contract on held-out/repeated workloads. For asynchronous search, test the budget boundary with multiple workers contending for the last remaining reservation and prove no dispatch can make `consumed + reserved` exceed B. Deliberately run trials that attempt to exceed their per-trial money/compute/time reservation and prove the quota/deadline/termination mechanism prevents the overrun. Inject early failures, late failures, partial consumption, and cancellation after measurable work; verify that only demonstrably unconsumed reservation is released, evaluation-count slots are not resurrected after dispatch, and repeated failures cannot create extra budget capacity.

Race multiple trial completions/cancellations against one another and against workers attempting the final dispatch slot. Verify the accounting transaction is linearizable: no consumed increment is lost, no reservation is released before its corresponding consumption is charged, and a dispatcher never observes capacity that would make the post-transaction invariant `consumed + reserved <= B` false.

For deterministic targets, run the same seeded trial set with deliberately permuted worker speeds/completion orders. Verify observation assimilation follows the declared trial-ID/batch order, the surrogate/search state replays identically, and the selected candidate plus stopping reason match the deterministic reference. Where sequential/parallel equivalence is part of C, compare an asynchronous execution with its deterministic sequential or batch-assimilation replay. If deterministic equivalence is intentionally not required, verify the record/target explicitly labels that nondeterminism instead.

## Target-repo adaptation

Do not copy acquisition constants, trial counts, domain contraction rates or parallel widths. Treat them as optimizer parameters with their own evidence boundary. Define the budget accounting unit, conservative per-trial reservation amount, **enforcement mechanism for that reservation**, one atomic/serializable accounting mechanism shared by reservation and terminal conversion, metering source, failure/cancellation charging policy, and deterministic observation-assimilation policy (when required) before enabling asynchronous dispatch.

## Failure modes

Noisy objectives, nonstationary machines, weak surrogates, excessive dimensionality and too much concurrency can waste evaluations or overfit benchmark noise. Non-atomic reservation can oversubscribe an evaluation or monetary cap; non-atomic completion/release can transiently undercount consumed plus reserved or lose concurrent increments; an unenforced reservation can let a single trial exceed B before accounting observes it; refunding consumed resources can let repeated late failures exceed B; over-conservative reservations can reduce useful parallelism; wall-clock completion-order assimilation can make supposedly deterministic search traces, proposals, and stopping decisions irreproducible.

## Rollback trigger

Stop adaptive search when its overhead exceeds evaluation savings, the budget is exhausted, repeated validation does not confirm the selected improvement, any trial can consume beyond its enforceable reservation, any accounting/concurrency test shows that dispatch/terminal transitions can violate B, or any target that requires deterministic search fails replay under permuted asynchronous completion orders.
