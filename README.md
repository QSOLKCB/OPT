# OPT — QSOL Optimization Catalog

Reusable, provenance-linked optimization patterns extracted from QSOL projects and carefully bounded external donors.

The point of this repository is simple: when a future project needs to go faster, use less memory, avoid redundant work, shorten CI, or tune an expensive system, point the implementing agent here first — **without weakening correctness to make a benchmark look good**.

## Rules of the vault

1. **Correctness outranks speed.** An optimization must preserve the contract it claims to preserve.
2. **Define the problem before choosing the trick.** Use [`OPTIMIZATION-PROBLEM.md`](OPTIMIZATION-PROBLEM.md) for the search space, feasible set, objective, constraints, budget and stopping rule.
3. **Measured and proposed work are different things.** Records say which is which.
4. **Keep the reference path.** Optimized/native/parallel/approximate paths should have a deterministic reference or conformance gate whenever practical.
5. **Do not cargo-cult constants.** Trial counts, worker caps, cache keys, tolerances, hashes, block sizes, thresholds and search parameters belong to their source environment until re-measured.
6. **Provenance matters.** Every promoted optimization links back to the code, release, PR, paper, or source that established it.

## Catalog

| ID | Optimization | Status | Core idea |
| --- | --- | --- | --- |
| [OPT-PY-001](optimizations/OPT-PY-001-deterministic-test-execution.md) | Deterministic test execution | **Verified mechanism; benchmark context incomplete** | Reduce repeated/high-cost test work without weakening coverage semantics |
| [OPT-INV-001](optimizations/OPT-INV-001-invariant-driven-reuse.md) | Invariant-driven computation reuse | **Verified mechanism; benchmark context incomplete** | Prove equivalence, then reuse the existing result |
| [OPT-LEAN-001](optimizations/OPT-LEAN-001-trust-preserving-lean-ci.md) | Trust-preserving Lean dependency reuse | **Verified on source PR; timings environment-scoped** | Reuse verified dependency state while rebuilding current project source |
| [OPT-PAR-001](optimizations/OPT-PAR-001-bounded-parallel-execution.md) | Bounded deterministic parallel execution | **Verified, environment-specific** | Bound concurrency and prove scalar/parallel equivalence |
| [OPT-DSP-001](optimizations/OPT-DSP-001-control-rate-sparse-vector-dsp.md) | Control-rate + sparse + vectorized DSP | **Implemented reference; approximation/native ideas proposed** | Move slow state out of the hot path; sparse/vectorize repeated numerical work |
| [OPT-INC-001](optimizations/OPT-INC-001-signature-bound-incremental-execution.md) | Signature-bound incremental execution | **Implemented external reference** | Rerun work only when complete effective-input identity changes |
| [OPT-COAL-001](optimizations/OPT-COAL-001-concurrent-duplicate-work-coalescing.md) | Concurrent duplicate-work coalescing | **Implemented external reference** | Share one in-flight computation among equivalent simultaneous callers |
| [OPT-SET-001](optimizations/OPT-SET-001-density-adaptive-compact-sets.md) | Density-adaptive compact sets | **Implemented external reference** | Choose sparse/dense representation locally while retaining exact set algebra |
| [OPT-CONT-001](optimizations/OPT-CONT-001-partitioned-coordination-domains.md) | Partitioned coordination domains | **Implemented external pattern** | Split one global contention hotspot into independent domains while preserving global invariants |
| [OPT-FAN-001](optimizations/OPT-FAN-001-shared-materialization-fanout.md) | Shared materialization for fan-out/replay | **Implemented external reference** | Transform/encode once and reuse the representation for many consumers |
| [OPT-SEARCH-001](optimizations/OPT-SEARCH-001-budget-aware-adaptive-search.md) | Budget-aware adaptive parameter search | **Proposed / OPT synthesis** | Spend expensive evaluations where they are most informative |
| [OPT-APPROX-001](optimizations/OPT-APPROX-001-contract-bounded-approximation.md) | Contract-bounded approximation | **Proposed / OPT synthesis** | Trade exactness only inside an explicit measurable error/degradation envelope |
| [OPT-REDUCE-001](optimizations/OPT-REDUCE-001-early-working-set-reduction.md) | Early working-set reduction | **Implemented external pattern** | Filter/cull/limit before expensive composition |
| [OPT-CRIT-001](optimizations/OPT-CRIT-001-critical-path-prioritization.md) | Critical-path prioritization | **Proposed / OPT synthesis** | Do critical work now, speculate carefully, defer non-critical work |
| [OPT-BUDGET-001](optimizations/OPT-BUDGET-001-performance-regression-budgets.md) | Performance regression budgets | **Proposed / OPT synthesis** | Turn performance expectations into environment-scoped regression contracts |
| [OPT-PRUNE-001](optimizations/OPT-PRUNE-001-bound-driven-search-space-pruning.md) | Bound-driven search-space pruning | **Proposed / OPT synthesis** | Prove whole search regions cannot improve the incumbent and skip them |
| [OPT-SIMD-001](optimizations/OPT-SIMD-001-evidence-gated-native-autovectorization.md) | Evidence-gated native autovectorization | **Verified, environment-specific** | Reshape a hot batch for vector codegen, prove parity, inspect instructions, then require measured native benefit |
| [OPT-SOA-001](optimizations/OPT-SOA-001-worker-local-soa-tiling.md) | Worker-local SoA tiling | **Implemented external reference** | Keep only hot fields in bounded per-worker SoA tiles and reuse cache-local scratch |
| [OPT-POOL-001](optimizations/OPT-POOL-001-persistent-topology-aware-worker-pools.md) | Persistent topology-aware worker pools | **Implemented external reference** | Reuse workers/buffers across dispatches and choose physical/logical topology explicitly |
| [OPT-AUTO-001](optimizations/OPT-AUTO-001-calibrated-host-aware-path-promotion.md) | Calibrated host-aware path promotion | **Implemented external reference** | Calibrate equivalent paths on the live host/workload, include lifecycle costs, and promote only with margin + oracle parity |

See [CATALOG.md](CATALOG.md) for the decision map and [README4AI.md](README4AI.md) for machine-oriented usage.

## Formalization boundary

The immutable `v1.0.0` release and its five original records are formalized by the pinned Lean v1 model described in [`FORMALIZATION.md`](FORMALIZATION.md). This catalog expansion is **post-v1**. It does not edit the three pinned v1 Lean model files or pretend the new records are already theorem-backed.

The new [`OPTIMIZATION-PROBLEM.md`](OPTIMIZATION-PROBLEM.md) supplies a canonical problem contract for future records:

`P = (X, F, f, d, C, B, S)`

where `d` is the objective direction/order; the remaining components are search space, feasible set, objective, correctness/semantic constraints, evaluation budget and stopping rule.

## Source material

- [`sources/WONDERBUILD.md`](sources/WONDERBUILD.md) — incremental execution, scheduling and rebuild-benchmark donor; GPL implementation boundary recorded.
- [`sources/JAZCO.md`](sources/JAZCO.md) — production systems case studies for coalescing, compact sets, contention, fan-out, approximation and reduction.
- [`sources/OPTIMIZATION-LIBRARIES.md`](sources/OPTIMIZATION-LIBRARIES.md) — BayesianOptimization, Hyperopt and NLopt mechanism/taxonomy notes.
- [`sources/WPO.md`](sources/WPO.md) — critical-path and performance-budget discovery source.
- [`sources/MATHEMATICAL-OPTIMIZATION.md`](sources/MATHEMATICAL-OPTIMIZATION.md) — mathematical/combinatorial problem vocabulary and pruning foundations.
- [`sources/GALAXY-CPU.md`](sources/GALAXY-CPU.md) — merged GALAXY CPU optimization phases covering SIMD/autovectorization, worker-local SoA tiling, persistent topology-aware pools and calibrated host-aware path promotion.
- [`power_module.md`](power_module.md) — E8/qutrit DSP architecture that motivated **OPT-DSP-001**.
- [`sources/SUXEN.md`](sources/SUXEN.md) — provenance and the required bounded recursive inventory procedure for the opaque `suxen.zip` source candidate.
- [`scripts/inventory_zip.py`](scripts/inventory_zip.py) — bounded recursive ZIP inventory entry point; use the explicit limits documented in `sources/SUXEN.md` rather than generic/unbounded extraction.
- [`suxen.zip`](suxen.zip) — opaque source archive, still **not promoted as optimization evidence** until the bounded inventory identifies reusable mechanisms.

## Integrity gate

`scripts/check_catalog.py` verifies heading/filename identity, post-v1 status vocabulary, complete contracts, complete README coverage, CATALOG coverage, and optimization-record link labels/targets. CI runs it via `.github/workflows/catalog-integrity.yml`.

## Add the next optimization

Copy [`templates/OPTIMIZATION-RECORD.md`](templates/OPTIMIZATION-RECORD.md), define the optimization problem contract, assign the next ID, record evidence honestly, and state exactly what correctness property is preserved.
