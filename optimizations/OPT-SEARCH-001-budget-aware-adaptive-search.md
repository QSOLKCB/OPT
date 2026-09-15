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
- C: search may choose where to evaluate but may not weaken correctness, determinism, evidence, API, trust, or other target semantics to improve f; asynchronous dispatch must not exceed B after accounting for consumed and conservatively reserved in-flight resources, every per-trial reservation must be an enforceable upper bound rather than an estimate, dispatch/completion accounting must be linearizable under concurrency, and targets that require deterministic search outcomes must use deterministic observation assimilation rather than completion-order updates
- B: an explicit target-specific hard maximum evaluation, wall-time, compute, monetary, or equivalent resource budget declared before the search starts; the accounting unit, enforceable per-trial cap mechanism, conservative reservation rule, atomic accounting boundary, and failure/cancellation charging policy are fixed before dispatch begins
- S: stop proposing/dispatching when no additional trial can be safely reserved within B, when a predeclared objective/quality target is met, or when a predeclared stagnation/convergence rule fires; preserve the reason for stopping in the trial ledger and apply stopping decisions only to the declared deterministic assimilation frontier when determinism is required

## Preserved contract

Search may choose *where to evaluate* but may not weaken correctness constraints to improve the objective. Under asynchronous execution, the declared maximum budget remains a hard bound: actual consumed resources plus all still-reserved in-flight capacity must remain within B, no individual trial may consume beyond its reserved cap, and concurrent dispatch/completion transitions must not transiently expose phantom free capacity.

If the target requires reproducible search traces or identical selected configurations across runs, asynchronous completion order is not allowed to change the optimizer's logical observation sequence. In that mode, results may finish in any wall-clock order, but they are assimilated into the optimizer only in a deterministic order such as monotonically increasing trial ID or explicit deterministic batches. If completion-order assimilation is intentionally used, the resulting nondeterminism must be declared as a contract change rather than hidden behind a fixed seed.

## Optimization

Use observations to adapt future evaluations: surrogate/acquisition search for expensive black-box objectives, conditional spaces where parameters only exist under certain choices, progressive domain contraction where justified, and explicit stopping/evaluation budgets. For asynchronous workers, reserve pending regions or otherwise diversify proposals so workers do not redundantly evaluate the same neighborhood.

Before dispatching an asynchronous trial, enter one atomic/serializable accounting boundary, reserve a conservative amount of the applicable budget, and record the pending trial in the ledger. If `consumed + reserved + proposed_reservation > B`, do not dispatch. The reservation must be an **enforceable upper limit** for that trial, not merely an estimate: use a per-trial quota, wall-time deadline with forced cancellation/termination, provider spending cap, cgroup/job resource limit, evaluation-slot ownership, or another mechanism that prevents actual trial consumption from exceeding the reservation. If the target cannot enforce such a cap for a resource dimension, that dimension cannot be advertised as a hard maximum B; instead define a different enforceable budget or explicitly classify the quantity as observational rather than bounded.

Completion, failure, cancellation, and forced termination use the **same atomic accounting boundary** as dispatch reservation. For one terminal transition, atomically: (1) read the trial's reservation, (2) meter/record the amount actually consumed, (3) move that consumed amount into permanent `consumed`, (4) release only the demonstrably unconsumed remainder from `reserved`, and (5) mark the trial terminal. No dispatcher may observe released reservation capacity before the corresponding consumed charge is committed, and concurrent terminal updates must not lose increments. Completion must not double-charge the same usage. A failed or cancelled trial never erases resources already consumed. For an evaluation-count budget, dispatch consumes the evaluation slot and it is not refunded merely because the trial later fails or is cancelled. For money/compute/time budgets, release only the measured or otherwise provable unused portion of the enforceable reservation. If unconsumed capacity cannot be established safely, retain the conservative charge. Every reservation, cap enforcement action, consumption adjustment, release, failure, cancellation, forced termination, and terminal accounting transaction is recorded in the ledger.

When deterministic search behavior is required, assign each proposal a stable trial ID at reservation/dispatch time and separate **physical completion** from **logical assimilation**. Buffer terminal results until the next deterministic trial-ID/batch frontier is complete, then update the surrogate/acquisition/stopping state in that fixed order. Failed/cancelled trials contribute their predeclared deterministic terminal observation/status at the same logical position. Later proposals may depend only on observations already admitted through that deterministic frontier. Alternative deterministic batching schemes are admissible if their ordering rule is fixed before execution and replayable from the ledger.

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

For targets that require deterministic optimization, run the same fixed-seed search repeatedly while deliberately perturbing worker latency/completion order. Verify that the persisted logical observation sequence, surrogate updates, proposals, stopping decision, and selected result are identical. Compare sequential execution with deterministic asynchronous/batched execution where the chosen scheme claims equivalence. Replay the ledger from scratch and prove it reconstructs the same optimizer state and final selection. If the target permits nondeterministic completion-order assimilation, record that explicitly and do not claim deterministic replay equivalence.

## Target-repo adaptation

Do not copy acquisition constants, trial counts, domain contraction rates or parallel widths. Treat them as optimizer parameters with their own evidence boundary. Define the budget accounting unit, conservative per-trial reservation amount, **enforcement mechanism for that reservation**, one atomic/serializable accounting mechanism shared by reservation and terminal conversion, metering source, failure/cancellation charging policy, and deterministic observation-assimilation rule when required before enabling asynchronous dispatch.

## Failure modes

Noisy objectives, nonstationary machines, weak surrogates, excessive dimensionality and too much concurrency can waste evaluations or overfit benchmark noise. Non-atomic reservation can oversubscribe an evaluation or monetary cap; non-atomic completion/release can transiently undercount consumed plus reserved or lose concurrent increments; an unenforced reservation can let a single trial exceed B before accounting observes it; refunding consumed resources can let repeated late failures exceed B; over-conservative reservations can reduce useful parallelism; completion-order assimilation can make fixed-seed asynchronous searches produce different traces, stopping points, and selected configurations.

## Rollback trigger

Stop adaptive search when its overhead exceeds evaluation savings, the budget is exhausted, repeated validation does not confirm the selected improvement, any trial can consume beyond its enforceable reservation, any accounting/concurrency test shows that dispatch, completion, failure, cancellation, forced termination, or reservation release can cause actual consumption plus outstanding reservations to exceed B or expose transient free capacity before consumption is committed, or a target that requires determinism cannot reproduce the same logical observation sequence and final selection under perturbed asynchronous completion order.
