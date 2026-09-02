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

**Status:** Verified.

QEC combined minimal fixtures, vectorized assertions, bounded deterministic caching, convergence/cycle early exit, smaller high-cost sweeps, lower safe iteration/trial counts, and repeated-work removal. QEC v68.4.0 reports about 126 s → 46 s (~2.7×) with 3779 passed / 8 skipped; v68.4.1 reports about 40 s after hardening.

### OPT-INV-001 — Invariant-driven computation reuse

**Status:** Verified.

QEC formalized the baseline equivalence `URW(min_sum, rho=1.0) == baseline min-sum`, tested exact equality, centralized the predicate, and reused the baseline result rather than rerunning the benchmark. The implementation commit reports about 43% speedup for that hot test.

### OPT-LEAN-001 — Trust-preserving Lean CI

**Status:** Verified on QSOL-GEO-REASON PR #3 source lane.

Separates source-state cache identity from compiled dependency artifacts, verifies both before use, rebuilds the current project source, and keeps a no-cache `cold-trust` lane for release-grade reconstruction claims. The cache policy records a 2501.52 s cold dependency build; a later verified-cache run records an 8.47 s GeoReason project build on four Lean threads. These timings cover different scopes and must not be divided into a fake universal speedup ratio.

### OPT-PAR-001 — Bounded parallel execution

**Status:** Verified, environment-specific.

The QEC-validated NEXUS v4.0.1 qBraid evidence compared scalar and worker-count variants, checked output invariants, and recorded observed thread behavior. At seven workers the evidence reports 3.806294× speedup and 0.543756 efficiency in that environment.

### OPT-DSP-001 — Control-rate sparse vector DSP

**Status:** Implemented reference; native backend ideas partly proposed.

The SPECTRAL NumPy reference precomputes static state, evolves E8/qutrit control state at ~1 kHz, computes all root phases once per control step, uses a sparse root subset per node, and vectorizes block synthesis. `power_module.md` additionally proposes block SIMD, zero-copy buffers and lock-free/native Rust structures. Those native performance claims are not promoted as verified here.

## Composition guidance

Optimizations compose only when their resource models do. In particular:

- pytest process parallelism plus BLAS/NumPy threads can oversubscribe CPUs;
- Lean parallel workers plus large dependency cache restore can raise memory and I/O pressure;
- a DSP block that is vectorized but allocates an `nodes × samples` temporary may still be unsuitable for hard real-time use;
- caching an equivalent result is safe only while the equivalence invariant remains true.

Prefer one measured bottleneck removal at a time, then re-profile.
