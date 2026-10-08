# OPT — QSOL Optimization Catalog

[![Release](https://img.shields.io/github/v/release/QSOLKCB/OPT)](https://github.com/QSOLKCB/OPT/releases/latest)
[![Tests](https://github.com/QSOLKCB/OPT/actions/workflows/test.yml/badge.svg?branch=main)](https://github.com/QSOLKCB/OPT/actions/workflows/test.yml)
[![Catalog integrity](https://github.com/QSOLKCB/OPT/actions/workflows/catalog-integrity.yml/badge.svg?branch=main)](https://github.com/QSOLKCB/OPT/actions/workflows/catalog-integrity.yml)
[![Lean formalization](https://github.com/QSOLKCB/OPT/actions/workflows/lean-formal.yml/badge.svg?branch=main)](https://github.com/QSOLKCB/OPT/actions/workflows/lean-formal.yml)
[![DOI](https://img.shields.io/badge/DOI-10.5281%2Fzenodo.23237223-blue)](https://doi.org/10.5281/zenodo.23237223)
[![License: Apache 2.0](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](LICENSE)

OPT is a contract-driven catalog of reusable optimization patterns, with source provenance, explicit evidence boundaries and executable references. Use it to choose ways to reduce latency, memory, repeated work or CI cost while preserving the correctness contract of your application.

The current release, [**v1.4.0**](https://github.com/QSOLKCB/OPT/releases/tag/v1.4.0), contains **22 optimization records**, exact Python stream references and the preserved Lean model for the five original v1.0.0 records. Its [Zenodo archive and technical report](https://doi.org/10.5281/zenodo.23237223) provide a citable release record.

## Start here

1. Define the search space, feasible set, objective, correctness constraints, budget and stopping rule with [OPTIMIZATION-PROBLEM.md](OPTIMIZATION-PROBLEM.md).
2. Use [CATALOG.md](CATALOG.md) to find a mechanism that fits the workload. Read its record's contract, evidence, provenance and limitations before adapting it.
3. Keep a deterministic reference or conformance gate, then measure the complete lifecycle on the target system. Source timings, cache capacities, worker counts and thresholds need local validation.

[README4AI.md](README4AI.md) gives implementing agents the usage protocol; [AGENTS.md](AGENTS.md) gives repository contributors the maintenance rules. Record statuses distinguish verified mechanisms, implemented references and proposed OPT syntheses. **Correctness outranks speed.**

## What the recent releases add

- [v1.2.0](https://github.com/QSOLKCB/OPT/releases/tag/v1.2.0): the problem-contract framework and a 20-record catalog, including source-backed native vectorization, worker-local tiling, persistent worker pools and calibrated host-aware path promotion.
- [v1.3.0](https://github.com/QSOLKCB/OPT/releases/tag/v1.3.0): working-set-aware cache capacity, bringing the catalog to 21 records. This remains a proposed synthesis; donor cache-size constants are not portable settings.
- [v1.4.0](https://github.com/QSOLKCB/OPT/releases/tag/v1.4.0): the 22nd record, bounded replayable pair streams, plus exact equal-sum joins, residue-filtered pair streams, independent oracle tests and reproducible characterization.

The v1.4.0 references include:

| Reference | Behavior |
| --- | --- |
| [Pair streams and equal-sum joins](examples/bounded_pair_streams.py) | Enumerate indexed integer pair sums in deterministic order; snapshot and replay stream state; buffer bounded tie groups and replay overflow while preserving all matches. |
| [Modular pair streams](examples/modular_pair_streams.py) | Enumerate pairs satisfying a declared congruence, using residue buckets for any positive integer modulus, including composite moduli and modulus one. |

Duplicate values retain distinct indices. Modular filtering establishes congruence; it does not establish exact sum equality. A stopped stream prefix does not prove that no later match exists.

The [pair-allocation evidence](examples/evidence/pair-stream-reference.json), [full-join characterization](examples/evidence/pair-join-characterization.md) and [modular-filtering characterization](examples/evidence/modular-pair-stream-characterization.md) document synthetic workloads and their tradeoffs. Lower allocation can come with slower joins; sparse modular workloads can benefit while dense ones do not. These observations do not establish a target-application speedup or a universal default.

## Validate locally

From the repository root, run the Python checks with the standard library:

```sh
python3 scripts/check_catalog.py
python3 -m unittest discover -s tests -v
python3 scripts/check_lean_source.py Lean --self-test
```

With the Lean toolchain declared in [lean-toolchain](lean-toolchain) installed (currently Lean 4.33.1), build and audit the formal model:

```sh
lake build
lake env lean Lean/TrustAudit.lean
```

CI runs three workflows: **test** checks the Python regression suite and bounded inventory of the bundled source archive; **catalog-integrity** checks record structure, contracts, status vocabulary, README/CATALOG coverage and record links; **lean-formal** verifies the frozen release identity and model blobs, builds the model and audits declaration coverage and permitted axioms. The badges above track `main`.

## Formalization and evidence scope

The immutable v1.0.0 release and its five original records are the target of the pinned Lean model described in [FORMALIZATION.md](FORMALIZATION.md). Later releases preserve the three pinned model files. **Post-v1 records and the Python references do not acquire theorem coverage from that model.**

[EVIDENCE-SCOPE.md](EVIDENCE-SCOPE.md) separates input integrity, certificate replay, theorem coverage and target measurements. The [OpenAI math assessment](sources/OPENAI-MATH.md) records the pinned donor, classical pair-stream attribution and transfer limitations. External donor proofs have not been independently replayed by OPT.

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
| [OPT-CACHE-001](optimizations/OPT-CACHE-001-working-set-aware-cache-capacity.md) | Working-set-aware cache capacity | **Proposed / OPT synthesis** | Size/manage reuse caches against measured working-set cardinality and resource budget to avoid eviction/reconstruction thrash |
| [OPT-STREAM-001](optimizations/OPT-STREAM-001-bounded-replayable-pair-streams.md) | Bounded replayable pair streams | **Implemented reference** | Enumerate exact combinations from compact inputs; buffer and replay large ties instead of materializing every result |

See [CATALOG.md](CATALOG.md) for the decision map and [README4AI.md](README4AI.md) for machine-oriented usage.

## Source material

- [`sources/WONDERBUILD.md`](sources/WONDERBUILD.md) — incremental execution, scheduling and rebuild-benchmark donor; GPL implementation boundary recorded.
- [`sources/JAZCO.md`](sources/JAZCO.md) — production systems case studies for coalescing, compact sets, contention, fan-out, approximation and reduction.
- [`sources/OPTIMIZATION-LIBRARIES.md`](sources/OPTIMIZATION-LIBRARIES.md) — BayesianOptimization, Hyperopt and NLopt mechanism/taxonomy notes.
- [`sources/WPO.md`](sources/WPO.md) — critical-path and performance-budget discovery source.
- [`sources/MATHEMATICAL-OPTIMIZATION.md`](sources/MATHEMATICAL-OPTIMIZATION.md) — mathematical/combinatorial problem vocabulary and pruning foundations.
- [`sources/GALAXY-CPU.md`](sources/GALAXY-CPU.md) — merged GALAXY CPU optimization phases covering SIMD/autovectorization, worker-local SoA tiling, persistent topology-aware pools and calibrated host-aware path promotion.
- [`sources/UNSLOTH-CUDA-GRAPH-CACHE.md`](sources/UNSLOTH-CUDA-GRAPH-CACHE.md) — Unsloth issue #12468 regression evidence motivating working-set-aware cache capacity without promoting donor cache-size constants.
- [`sources/OPENAI-MATH.md`](sources/OPENAI-MATH.md) — pinned mathematical donor assessment, classical pair-stream attribution, and explicit proof/model limitations.
- [`power_module.md`](power_module.md) — E8/qutrit DSP architecture that motivated **OPT-DSP-001**.
- [`sources/SUXEN.md`](sources/SUXEN.md) — provenance and the required bounded recursive inventory procedure for the opaque `suxen.zip` source candidate.
- [`scripts/inventory_zip.py`](scripts/inventory_zip.py) — bounded recursive ZIP inventory entry point; use the explicit limits documented in `sources/SUXEN.md` rather than generic/unbounded extraction.
- [`suxen.zip`](suxen.zip) — opaque source archive, still **not promoted as optimization evidence** until the bounded inventory identifies reusable mechanisms.

## Contribute

Copy [templates/OPTIMIZATION-RECORD.md](templates/OPTIMIZATION-RECORD.md), define the problem contract, assign the next ID and state the correctness property preserved. Link the source and evidence, label proposals honestly, update the catalog indexes and run the integrity gate. Consult [ROADMAP.md](ROADMAP.md) for assessed candidates and deferred work.

## Cite v1.4.0

Slade, T. (2026). OPT v1.4.0: Contract-Driven Optimization and Exact Stream References - Archival Technical Report (Version v1.4.0) [Computer software]. Zenodo. https://doi.org/10.5281/zenodo.23237223

The DOI identifies the v1.4.0 archival record. For a different release, cite its corresponding version and source revision.

## License

Repository code is licensed under [Apache 2.0](LICENSE). The archival technical report is licensed under CC BY 4.0. Donor implementations retain their own licenses and reuse boundaries, recorded in the source notes.
