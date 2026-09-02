# Optimization Catalog

## Quick decision table

| Bottleneck | First record to inspect | Core idea |
| --- | --- | --- |
| Test suite spends most time in deterministic sweeps/simulations | `OPT-PY-001` | Reduce redundant work while keeping coverage semantics and deterministic assertions |
| Same expensive result is recomputed at a provably equivalent parameter/state | `OPT-INV-001` | Prove equivalence, then reuse the already-computed result |
| Lean CI repeatedly rebuilds an unchanged dependency closure | `OPT-LEAN-001` | Reuse only cryptographically/structurally verified dependency state; always rebuild project source |
| Independent jobs/items can execute concurrently | `OPT-PAR-001` | Bound workers, preserve deterministic ordering, prove scalar/parallel equivalence |
| Expensive state changes far slower than the sample/hot-loop rate | `OPT-DSP-001` | Move state evolution to control rate; sparse-evaluate couplings; batch/vectorize the hot path |

## Records

### OPT-PY-001 — Deterministic test execution

**Status:** Verified mechanism; historical performance context incomplete.

QEC combined minimal fixtures, vectorized assertions, bounded deterministic caching, convergence/cycle early exit, smaller high-cost sweeps, lower safe iteration/trial counts, and repeated-work removal. QEC v68.4.0 reports about 126 s → 46 s (~2.7×) with 3779 passed / 8 skipped; v68.4.1 reports about 40 s after hardening. The cited v68.x records do not preserve runner/CPU/Python/pytest/repetition metadata, so these are historical observations, not transferable benchmark targets.

### OPT-INV-001 — Invariant-driven computation reuse

**Status:** Verified mechanism; historical performance context incomplete.

QEC formalized the baseline equivalence `URW(min_sum, rho=1.0) == baseline min-sum`, tested exact equality, centralized the predicate, and reused the baseline result rather than rerunning the benchmark. The implementation commit reports about 43% speedup for that hot test, but does not preserve its runner/toolchain, exact hot-test wall times, or repetitions. Re-measure before making a target-repo speed claim.

### OPT-LEAN-001 — Trust-preserving Lean CI

**Status:** Verified on QSOL-GEO-REASON PR #3 source lane; timing observations are environment-scoped.

Separates source-state cache identity from compiled dependency artifacts, verifies both before use, rebuilds the current project source, and keeps a no-cache `cold-trust` lane for release-grade reconstruction claims. The cache policy records a 2501.52 s cold dependency build using four Lean threads on a four-CPU `ubuntu-24.04` / x86_64 lane; a later verified-cache run records an 8.47 s GeoReason project build on a four-CPU Ubuntu 24.04.4 hosted runner. These are single observations of different scopes, with no exact CPU model/repetition distribution preserved, so they must not be divided into a portable speedup.

### OPT-PAR-001 — Bounded parallel execution

**Status:** Verified, environment-specific; performance must be re-measured before transfer.

The QEC-validated NEXUS v4.0.1 qBraid evidence compared scalar and worker-count variants, checked output invariants, and recorded observed thread behavior. Its archived seven-worker observation was made on qBraid / Ubuntu 24.04.4 / AMD EPYC 7763 with 16 logical CPUs and effective worker capacity 7. The canonical receipt does not bind the performance samples to an exact `rustc --version`, so OPT retains the numbers as historical evidence rather than a transferable performance target.

### OPT-DSP-001 — Control-rate sparse vector DSP

**Status:** Implemented reference for control-rate/sparse/vector patterns; approximation/native ideas partly proposed.

The SPECTRAL NumPy reference is pinned to commit `5265b7f130287f80b5cf0d3de5bb2953152f90cd`. It precomputes static state, evolves E8/qutrit control state at ~1 kHz, computes all root phases once per control step, uses a sparse root subset per node, and vectorizes block synthesis. The audition renderer's whole-block modulation shortcut has no defined equivalence/error contract and is therefore not promoted as a reusable correctness-preserving optimization. `power_module.md` additionally proposes block SIMD, zero-copy buffers and lock-free/native Rust structures; those native performance claims are not promoted as verified here.

## Composition guidance

Optimizations compose only when their resource models do. In particular:

- pytest process parallelism plus BLAS/NumPy threads can oversubscribe CPUs;
- Lean parallel workers plus large dependency cache restore can raise memory and I/O pressure;
- a DSP block that is vectorized but allocates an `nodes × samples` temporary may still be unsuitable for hard real-time use;
- caching an equivalent result is safe only while the equivalence invariant remains true.

Prefer one measured bottleneck removal at a time, then re-profile.
