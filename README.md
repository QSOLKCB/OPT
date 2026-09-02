# OPT — QSOL Optimization Catalog

Reusable, provenance-linked optimization patterns extracted from QSOL projects.

The point of this repository is simple: when a future project needs to go faster, use less memory, avoid redundant work, or shorten CI without weakening correctness, point the implementing agent here first.

## Rules of the vault

1. **Correctness outranks speed.** An optimization must preserve the contract it claims to preserve.
2. **Measured and proposed work are different things.** Records say which is which.
3. **Keep the reference path.** Optimized/native/parallel paths should have a deterministic reference or conformance gate whenever practical.
4. **Do not cargo-cult constants.** Trial counts, worker caps, cache keys, tolerances, hashes, and block sizes belong to their source environment until re-measured.
5. **Provenance matters.** Every promoted optimization links back to the code, release, PR, or evidence that established it.

## Catalog

| ID | Optimization | Status | Source | Evidence snapshot |
| --- | --- | --- | --- | --- |
| [OPT-PY-001](optimizations/OPT-PY-001-deterministic-test-execution.md) | Deterministic test execution | **Verified** | QEC v68.2.0–v68.4.1 | ~126 s → ~46 s in v68.4.0 release; ~40 s after v68.4.1 hardening; 3779 passed / 8 skipped |
| [OPT-INV-001](optimizations/OPT-INV-001-invariant-driven-reuse.md) | Invariant-driven computation reuse | **Verified** | QEC v68.4.1 cycle | Eliminated a redundant benchmark at the proven-equivalent baseline point; commit reports ~43% speedup for that hot test |
| [OPT-LEAN-001](optimizations/OPT-LEAN-001-trust-preserving-lean-ci.md) | Trust-preserving Lean dependency reuse | **Verified on source PR** | QSOL-GEO-REASON PR #3 | Cold dependency reconstruction recorded at 2501.52 s; verified-cache project rebuild recorded at 8.47 s, while preserving separate cold-trust semantics |
| [OPT-PAR-001](optimizations/OPT-PAR-001-bounded-parallel-execution.md) | Bounded deterministic parallel execution | **Verified, environment-specific** | QEC v170.2.1 / NEXUS evidence | 69.694063 ns/eval scalar median → 18.310215 ns/eval at 7 workers; 3.806294× measured speedup |
| [OPT-DSP-001](optimizations/OPT-DSP-001-control-rate-sparse-vector-dsp.md) | Control-rate + sparse + vectorized DSP | **Implemented reference / native ideas partly proposed** | SPECTRAL + `power_module.md` | Control-rate decimation, sparse E8 coupling, shared phase computation and NumPy vectorization are implemented; native SIMD/zero-copy/lock-free claims are not locally benchmarked here |

See [CATALOG.md](CATALOG.md) for the decision map and [README4AI.md](README4AI.md) for machine-oriented usage.

## Provenance correction: the QEC links

The originally supplied QEC v170.2.0/v170.2.1 links are useful, but they are **not the origin of the large pytest/CI test-speed optimization**. The primary deterministic test optimization lineage is:

- [QEC v68.2.0 — Deterministic Execution Engine](https://github.com/QSOLKCB/QEC/releases/tag/v68.2.0)
- [QEC v68.4.0 — Deterministic Runtime Optimization](https://github.com/QSOLKCB/QEC/releases/tag/v68.4.0)
- [QEC v68.4.1 — Invariant Hardening & Repository Cleanup](https://github.com/QSOLKCB/QEC/releases/tag/v68.4.1)

The v170.2.x releases remain relevant here because v170.2.1 contains independently validated multicore benchmark evidence used by **OPT-PAR-001**.

## Existing source material

- [`power_module.md`](power_module.md) contains the E8/qutrit DSP architecture that motivated **OPT-DSP-001**.
- [`suxen.zip`](suxen.zip) is retained as an opaque source archive. It is **not yet promoted as optimization evidence** because GitHub's connector cannot unpack repository binary ZIPs. See [`sources/SUXEN.md`](sources/SUXEN.md) and run [`scripts/inventory_zip.py`](scripts/inventory_zip.py) in a normal checkout to audit it safely.

## Add the next optimization

Copy [`templates/OPTIMIZATION-RECORD.md`](templates/OPTIMIZATION-RECORD.md), assign the next ID, record before/after evidence, and state exactly what correctness property was preserved.
