# OPT-HYBRID-001 — Evidence-gated hybrid execution

**Status:** Implemented reference; proposed OPT synthesis, no production speedup or theorem coverage established.
**Domains:** CI, batch computation, dependency DAGs, worker scheduling, lifecycle accounting.

## Source evidence

- Repository: QSOLKCB/yt-dlp-enhanced; [PR #1](https://github.com/QSOLKCB/yt-dlp-enhanced/pull/1).
- Audited candidate commit: 42e72529d839d2e862373386c611896fef602d3d.
- Original baseline commit: 29490a6c9b53e1b9d2c2471c48303afbc44c4796.
- Report: YTDLP-AUDIT-001; archive SHA-256 and audit-reported figures in [source note](../sources/YTDLP-AUDIT-001.md).
- No donor code copied; the report archive was not supplied for independent replay. The donor audit verdict was BLOCK — CORRECTNESS OR SECURITY DEFECT. Historical observations motivate this first-party synthetic reference, not production promotion.

## Problem

Unconditional parallel execution can multiply discovery, copying, interpreter startup, scheduling and aggregation work. Remove provably redundant preparation before tuning execution. Parallelism, hybrid partitioning and ordinary serial are competing configurations; none is intrinsically superior.

## Optimization problem contract

- X: finite candidate plans: SERIAL, PARALLEL-2, PARALLEL-4, PARALLEL-7 and other explicitly bounded worker counts, and HYBRID with an explicit ordered partition of work-unit identities.
- F: identity-current, full-work correctness-qualified plans under the worker, measurement and declared resource budgets. Serial is canonical; absent comparative evidence it may be freshly verified rather than promoted from stale data. With a hard metric ceiling, unknown evidence is not feasibility.
- f: complete paid elapsed lifecycle, total CPU, aggregate peak memory, temporary storage, filesystem operations, runner consumption and any declared service/queue/install/cache/oracle costs. The reference selects on worst recorded wall time and negative CPU time (or negative requested workers if CPU is unavailable); memory is an optional admission constraint.
- d: minimize wall and maximize negative CPU (or negative requested workers); retain observed Pareto ties, then apply the declared material margin and lexicographic ordering.
- C: exact full-work oracle parity, same canonical unit IDs/order/multiplicity, dependency semantics, immutable effective inputs, no externally visible results before verification, and no silent fallback on mismatch or worker exception.
- B: target-defined finite candidate/repetition and lifecycle resource budget. Reference caps 128 units, 20 million aggregate loop steps including preparation, 32 requested workers, 32 plans, 16 samples per plan and 256 total trials; default policy limits are configurable and are safety envelopes, not crossover constants. Hard aggregate memory enforcement requires an external resource controller; the reference refuses such live execution.
- S: stop at the declared trial bound; reject malformed evidence, exclude stale/incomplete evidence, retain serial unless the worst paid alternative strictly beats the best paid serial sample by the predeclared margin (or qualified serial is resource-infeasible); use only a correctness-qualified override. Verify selected full work before returning. Stop and discard on mismatch.
- Variables: mixed categorical, integer and conditional partitions.
- Search scope: finite observed ledger, not global optimization.
- Objective behavior: noisy measured lifecycle; deterministic selection given ledger and policy.
- Information: derivative-free, recorded observations.
- Evaluation cost: moderate to expensive full-work trials.
- Constraints: semantic, resource, bounds and dependency constraints.
- Parallelism: sequential selection, bounded process batches by topological level.
- Exactness: exact.

## Preserved contract

Apply OPT-AUTO-001 without weakening it: calibration candidates and the selected full workload require independent oracle parity. Stage side-effect-free results; failure is not permission to rerun serial and conceal the defect. A serial reference and explicit manual controls remain available. Preserve dependency precedence and canonical input ordering even if the input is not topologically ordered. The reference uses immutable dataclasses, a fixed arithmetic kernel and an independent closed-form oracle; it is not an arbitrary-code sandbox or a pytest adapter.

Bind evidence to source commit AND materialized source, runtime, dependencies/plugins, configuration, host/resource limits, workload (including all selected IDs, steps, dependencies and preparation), strategy/partition, and measurement generation. A SHA or clean Git tree alone is not proof of execution provenance. The caller must construct truthful complete manifests from a coherent immutable generation, and rotate the generation when measurements expire. Endpoint rehashes are diagnostics, not A→B→A protection. The reference consumes trusted manifest digests, not authenticated attestations.

## Optimization

1. Establish one immutable input generation, identify selected work, and prove redundant preparation can be removed without altering outcomes or observable effects (OPT-REDUCE-001 and OPT-INC-001).
2. Generate bounded serial, parallel and explicitly partitioned hybrid candidates. Preparation is performed once per invocation, not per worker; schedule topological levels, executing serial units on the parent then submitting parallel units to a bounded spawn pool. Hybrid may lose due to barriers, skew or startup.
3. Run complete correctness-verified calibration trials with identical boundaries; retain raw samples including losses. Do not admit a fast result without parity.
4. Reject malformed/duplicate ledgers and incompatible boundaries. Exclude stale, missing-correctness, undersampled or budget-infeasible records. A current mismatch is a correctness failure, even if the plan would otherwise be excluded.
5. Use the existing OPT-PARETO-001 finite-ledger implementation for the feasible observed frontier and the promotion-eligible subset. Compare worst alternative against best serial using an explicit basis-point margin, with ties staying serial. For eligible alternatives, lexicographic wall then secondary objective, fewer workers then stable ID; retain ties in receipts. Manual override bypasses margin only, never identity, resource or correctness gates.
6. Re-select and execute against the same immutable inputs; withhold results until independent full-work oracle succeeds. Record selection, identity, evidence digest and observed worker IDs/interval overlap. Overlapping worker task intervals are not proof of simultaneous physical CPU execution.

### Complete lifecycle accounting

T_total = T_discovery + T_preparation + T_calibration + T_worker_startup + T_scheduling + T_execution + T_aggregation + T_verification + T_cleanup for nonoverlapping phases. If phases overlap, measure elapsed critical-path wall time directly; separately sum CPU/resource consumption, never add overlapped wall intervals. Charge queue latency, dependency installation, cache misses, copies/storage/filesystem operations, total runner consumption, oracle and staging/commit costs where paid. Use identical boundaries for serial, parallel and hybrid. Never compare a kernel-only parallel measurement with a complete serial invocation.

The synthetic reference measures a single full-work interval (validation/identity derivation from established manifests, preparation, pool startup, scheduling, execution, aggregation, cleanup and independent oracle), not additive overlapping phase estimates. Common paid capture/calibration/selection overhead must be supplied symmetrically to the selector or measured separately with an explicitly out-of-band research scope. The optional harness reports capture and calibration separately, including the cost of losing candidates. It also runs the selected full workload. The reference has no external queue, dependency installation, file copies or caches in its execution kernel; real adapters must measure these rather than assume zero. CPU includes parent and reaped children where resource accounting is available. Aggregate peak memory is not measured by the stdlib reference; unknown is not zero. Live elapsed/CPU ceiling checks are post-execution, not preemptive timeouts.

## Before / after evidence

Audit-reported local workload: 250 selected tests, 246 passed and four skipped, two measured runs per configuration. Mean elapsed seconds: ordinary serial 4.6835, OPT one worker 7.8835, two 8.1710, four 8.4415, seven 8.9065. Full GitHub Actions workload: serial approximately 148 s and seven workers approximately 111 s. Different workload/environment; no universal threshold. Exact-module collection reportedly preserved the 250 selected IDs and reduced collection from 2.9–3.2 s to 0.951–0.965 s. These observations are not independently reproduced by OPT.

Reference benchmark: [optional harness](../scripts/benchmark_hybrid_execution.py), six deterministic synthetic fixture classes. Raw repetitions, identity manifests, requested/observed workers, full wall time, CPU, available RSS diagnostics and rationale are emitted as JSON. Aggregate memory, runner-level consumption and real pytest discovery/copy work are not measured by these fixtures. No speedup is claimed without retained executed measurements; synthetic selection tests are not benchmarks.

## Validation

Run `uv run python -m unittest discover -s tests -v` and `uv run python scripts/check_catalog.py` (or repository CI's python3 equivalent). [Regression tests](../tests/test_hybrid_execution.py) use independent expected results, real process workers and injected error cases; synthetic ledgers test lifecycle reversal, near ties, stale/duplicate evidence, resource rejection and deterministic Pareto selection. The separate optional benchmark runs the actual serial/parallel/hybrid implementations:

```sh
uv run --no-project python -I scripts/benchmark_hybrid_execution.py --workers 7 --repetitions 2 > hybrid-report.json
```

No timing threshold is a correctness gate. Existing formal-source integrity and frozen v1 Lean gates remain unchanged; this post-v1 reference has no inherited formal proof coverage.

## Target-repo adaptation

Define the target-specific unit/dependency model, independent oracle, complete effective-input manifests, mutation discipline, resource controller, candidate partitions, topology and real lifecycle measurement protocol. Re-profile worker caps, trial repetitions, margin and workload granularity; 7 workers is a preferred experimental candidate, not a default execution decision. Require independently verified equivalent test outcome identities, not counts. Do not transfer blocked donor code or calibration.

## Failure modes

Unrepresentative calibration, missing preparation charges, stale source/configuration, uncontrolled source mutation, oversubscribed workers, memory pressure, skewed durations, dependency barriers, high verification cost, forged evidence, or unavailable resource accounting. A valid digest binds claimed identity, not authenticity or universal correctness. The synthetic executor does not supervise arbitrary processes, provide hard preemption or enforce an aggregate memory limit. Measurements of max single-process RSS are not simultaneous aggregate peak memory.

## Rollback trigger

Discard staged outputs and fail on any current oracle mismatch, missing/duplicated outcomes or worker exception; never silently fall back after a correctness failure. Revoke promotion when identity, generation or lifecycle evidence is invalid, a budget is exceeded, or the material advantage disappears. Canonical fresh execution is allowed only under the same correctness and resource contract. Recalibrate on the new generation; keep all failed/unfavorable measurements.

## Composition notes

OPT-PY-001 preserves complete test semantics; OPT-PAR-001 bounds parallelism; OPT-AUTO-001 supplies symmetric full-work promotion; OPT-PARETO-001 ranks finite feasible ledgers; OPT-CRIT-001 protects dependency and commitment boundaries; OPT-INC-001 binds generation identity; OPT-REDUCE-001 removes redundant work only under equivalence; OPT-BUDGET-001 separates characterization from performance-gate certification. No record confers automatic theorem or production-performance coverage.
