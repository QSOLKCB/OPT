# OPT-PARETO-001 — Bounded deterministic Pareto-frontier selection

**Status:** Implemented reference; finite-ledger correctness only, no target speedup evidence  
**Domains:** multiobjective configuration selection, engine graphics profiles, CI tuning, simulation trials

## Source evidence

- Kochenderfer, Mykel J., and Tim A. Wheeler. *Algorithms for Optimization*, second edition, MIT Press, 2026, Chapter 15, especially §15.1 on Pareto dominance.
- The owner-supplied book PDF was inspected; see [source note](../sources/ALGORITHMS-FOR-OPTIMIZATION-2026.md).
- Executable original reference: [examples/pareto_frontier.py](../examples/pareto_frontier.py).
- Independent finite-oracle and adversarial regression cases: [tests/test_pareto_frontier.py](../tests/test_pareto_frontier.py).
- Licensing boundary: book CC BY-NC-ND 4.0; the PDF and book Julia source are not copied. The classical mathematical definition is implemented independently in Apache-2.0 OPT code.

### Evidence scope

- Computational model: exact Python order comparisons of finite real-valued metrics stored as finite Python floats or arbitrary-precision integers. Boolean, non-finite and nonnumeric metrics are rejected; no floating-point tolerance is silently introduced.
- Hypotheses / declared domain: explicitly feasible or infeasible candidates in an already evaluated finite ledger; 2–8 objectives; up to a configured cap of 4096 records; unique string identifiers.
- Guarantee and quantifiers: for every admitted finite ledger and declared direction vector, return exactly the feasible candidates for which no other **feasible observed** candidate is no worse in all objectives and strictly better in at least one. Preserve all equal-objective candidates and source ledger order.
- Formal coverage: no Lean theorem is claimed for the new Python implementation. The OPT frozen v1 Lean model is unchanged.
- Proof target and toolchain: independent exhaustive small finite-ledger oracle and seeded mutation/regression tests run with Python stdlib unittest; not a machine-checked general mathematical theorem.
- Axiom allowance: not applicable; no external proof checker or axioms are used.
- Certificate replay commands and scope: `python3 -m unittest discover -s tests -p 'test_pareto_frontier.py' -v`; checks finite fixtures, not any global search-space certificate.
- Independent replay status and retained evidence: CI must run on the proposed source head. Do not call the record CI-verified unless CI completes.
- Performance transfer boundary: no VANILLAJS or external workload speedup demonstrated. This is selection machinery, not a faster renderer.

## Problem

A system exposes multiple valid configurations with competing performance and quality criteria. Minimizing a single weighted score can conceal trade-offs; selecting only the fastest candidate can discard a feasible design with materially better visual fidelity, memory consumption or power consumption. The user needs a complete, stable, interpretable observed frontier without claiming global search optimality.

## Optimization problem contract

- X: the finite ordered ledger of observed configurations with unique IDs, declared objective vectors and explicit feasibility flags
- F: only the observed candidates whose separate target-specific correctness and hard resource checks have established `feasible = True`; this reference does not validate the evidence behind that flag
- f: an ordered vector of 2–8 finite integer/float metrics per candidate, with a common unit and interpretation for each objective across the ledger
- d: an ordered `minimize` or `maximize` direction for each metric; strict Pareto dominance, not an implicit weighted sum
- C: reject malformed/oversized ledgers before selection; preserve all equally-valued designs and input order; never rank infeasible candidates; preserve metric values exactly as represented; don't silently round tolerances or label an observed frontier a globally complete frontier
- B: at most 4096 input candidates and 8 objectives; explicit `max_candidates` can impose a smaller bound; O(n²k) comparisons and O(nk) stored input; no hard elapsed-time or CPU-unit guarantee
- S: terminate after each feasible candidate has been checked against every other feasible observed candidate or reject the input before comparison
- Variables: mixed; candidate generation is external, this selector handles recorded scalar objectives
- Search scope: local / observed finite set only; no global-search claim beyond the supplied ledger
- Objective behavior: deterministic **recorded** metrics; noisy measurement uncertainty is not resolved by this selector
- Information: derivative-free / black-box recorded observations
- Evaluation cost: cheap comparison relative to expensive external benchmarks, but quadratic cost can be significant at the cap
- Constraints: bounds, hard correctness and resource constraints are target-owned; this reference consumes their booleans only
- Parallelism: sequential, stable ledger order
- Exactness: exact dominance over supplied finite numeric representations, not exact knowledge of unmeasured true performance

## Preserved contract

Return a tuple of new `{"id": ..., "metrics": tuple(...)}` records in original ledger order. Two candidates with identical metric vectors remain represented. Hard-invalid configurations never enter the frontier. Input lists, values and candidate IDs remain unchanged. All input records are validated first; invalid data is never silently dropped.

## Optimization

Compare all feasible observed metric vectors using strict dominance. For minimization, A dominates B iff `A[i] <= B[i]` for all dimensions and `A[j] < B[j]` for at least one. Reverse comparisons for maximization dimensions. Retain B iff no other feasible candidate dominates B. This is a simple transparent offline selector intended as a correctness oracle for future faster implementations; it is not a runtime-game-frame algorithm.

## Before / after evidence

- Environment: reference authored for Python stdlib; target-host CI observation pending.
- Workload/fixture: synthetic graphics-profile vectors in `tests/test_pareto_frontier.py`, not actual FPS Lab measurements.
- Cold baseline: no existing OPT Pareto reference with comparable API.
- Warm/no-op baseline where relevant: no cache/reuse path.
- Small invalidation / partial-work case where relevant: complete recomputation is required; no incremental optimization claimed.
- Large invalidation / full-work case where relevant: all feasible records pairwise compared.
- Optimized: nondominated feasible vectors only; no runtime-performance optimization claimed.
- Speedup / memory / I/O / quality change: **not measured**; the mechanism enables correct multiobjective selection, not a benchmark win.
- Variance / repetitions / raw samples: not applicable until target workload measurements exist.

## Validation

`tests/test_pareto_frontier.py` independently evaluates all pairs with a structurally separate comparison routine across exhaustive small observed ledgers and seeded larger ledgers. Additional cases cover mixed directions, exact very large integers, tied observations, stable ordering, all infeasible ledgers, copied outputs, malformed candidates, duplicate IDs, NaN/Infinity and bounded-input admission. This suite must be executed on the exact PR head and the CI result recorded separately; adding tests is not itself execution evidence.

## Target-repo adaptation

For VANILLAJS FPS Lab, measure actual (not estimated) frame times under multiple user-visible graphics choices with the **same viewport, scene, input path, simulation stepping, seed and host**, and retain the raw samples and WebGL renderer identity. Distinguish wall-clock requestAnimationFrame cadence, JavaScript callback costs and actual GPU timings; headless SwiftShader results do not establish physical GPU/60 FPS performance. Choose target objectives up front (e.g. p95 frame interval, allocated render-pixel count as a *proxy* rather than exact GPU memory, measured image quality with an explicit visual score if available). Do not call raw dimensions a scalar `quality` score without defining it. Gate correctness separately. Feed metrics to this reference only after validating complete per-case measurement records.

## Failure modes

- Comparing headless software rendering as though it were native GPU performance.
- Treating an empty observed frontier as infeasibility of the whole design space.
- Treating noisy frame samples as deterministic truth or tolerating incomparable units.
- Untrusted feasibility flags: incorrect data can enter the frontier.
- Treating weak dominance/equality as strict dominance and losing tied designs.
- Quadratic cost at large n; arrays larger than the cap must be explicitly rejected.
- Cross-platform floating-point nondeterminism; integer-exact comparisons do not imply portable FPS samples.

## Rollback trigger

Disable/revert this selector for a target if oracle parity, input bounds, tie ordering or feasibility isolation fails, or if measured selection overhead breaches the target budget. Fall back to explicitly approved fixed configurations, not an unvalidated faster frontier.

## Composition notes

`OPT-SEARCH-001` may supply bounded trial observations and `OPT-BUDGET-001` may govern evidence collection. `OPT-PRUNE-001` is **scalar-only** and cannot be applied to discard Pareto candidates without a separately sound vector-bound proof. `OPT-APPROX-001` may admit approximate metrics only if a new explicit uncertainty/error contract is separately validated. Never insert this O(n²) selector inside VANILLAJS's 60 Hz hot loop.
