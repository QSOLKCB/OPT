# OPT-PAR-001 — Bounded Deterministic Parallel Execution

**Status:** Verified, environment-specific; benchmark numbers are archived observations and must be re-measured before transfer  
**Domains:** CPU parallelism, Rust/native workers, simulation batches, CI workloads

## Source evidence

- QEC v170.2.0: https://github.com/QSOLKCB/QEC/releases/tag/v170.2.0
- QEC v170.2.1: https://github.com/QSOLKCB/QEC/releases/tag/v170.2.1
- Immutable qBraid replication report:
  https://github.com/QSOLKCB/QEC/blob/v170.2.1/docs/replications/NEXUS_V4_0_1_QBRAID.md
- Immutable canonical receipt:
  https://github.com/QSOLKCB/QEC/blob/v170.2.1/docs/replications/nexus_v4_0_1_qbraid_receipt.json

QEC v170.2.1 independently validated NEXUS v4.0.1 qBraid replication evidence, including worker-count equivalence and observed thread behavior.

## Reusable pattern

### 1. Keep a scalar reference

Parallel output must be compared against a deterministic scalar/reference execution. Do not let the parallel implementation define correctness by itself.

### 2. Parallelize only independent work

Choose units whose result does not depend on completion order, or restore a canonical order before hashing/comparison/output.

### 3. Bound worker count

Expose a requested worker count, cap it against hardware/memory constraints, and include the effective/requested value in evidence.

### 4. Test multiple worker counts

The source evidence checked scalar/parallel invariants at **1, 2, 4 and 7 workers**, not just the fastest setting. This catches ordering, partitioning and boundary bugs.

### 5. Separate request evidence from execution evidence

QEC v170.2.0 explicitly refused to treat an echoed worker count as proof of effective multicore execution (`effective_workers_claim: false`). The later replication evidence additionally checked observed thread behavior.

This is a general rule: configuration is not observation.

### 6. Attach the preserved benchmark environment

Speedup numbers are interpretable only with their execution context. Attach runner/platform, OS/kernel, CPU, available logical CPUs, worker capacity, source identity and toolchain information when that information was actually captured.

If a field was **not** captured by the source evidence, say so rather than guessing it, and require a fresh benchmark before treating the source worker count or speedup as transferable.

Use:

```text
speedup = scalar_time / parallel_time
efficiency = speedup / workers
```

## Evidence snapshot

The canonical QEC receipt binds the observation to:

```text
platform: qBraid
os: Ubuntu 24.04.4 LTS
kernel: 6.8.0-1059-azure
cpu: AMD EPYC 7763 64-Core Processor
online logical CPUs: 16
effective worker capacity: 7
source package: nexus 4.0.0
source commit: 1e93a509a28144d70a17fa76b330ae042db7beab
QEC receipt/release: 170.2.1 / v170.2.1
observations per mode: 5
```

Measured medians in that environment:

- scalar median: **69.694063 ns/eval**;
- 7-worker parallel median: **18.310215 ns/eval**;
- measured speedup: **3.8062940822923164×**;
- measured efficiency: **0.5437562974703309**;
- maximum threads observed: **8** (one main thread plus seven workers in the recorded evidence).

### Toolchain capture boundary

The canonical receipt verifies successful primary format/Clippy/release-build/tests and a separate Rust **1.82.0 MSRV** install/build/test path. It does **not** bind the performance samples to an exact `rustc --version` string. OPT therefore does not claim toolchain-level benchmark reproducibility from this archive.

The numbers above are retained as a verified historical observation for the pinned source/environment. A consumer must re-run the benchmark on its own pinned compiler/toolchain and hardware before selecting seven workers or quoting an expected speedup.

## Determinism checklist

- deterministic work partitioning or canonical result merge;
- stable output ordering;
- no shared mutable RNG without explicit stream partitioning;
- scalar/parallel equality or invariant comparison;
- bounded queue/buffer growth;
- worker failure propagated rather than dropped;
- repeated-run determinism test;
- benchmark excludes setup costs only when that exclusion is stated;
- benchmark report records the exact toolchain in new evidence.

## Watch for nested parallelism

A worker pool calling NumPy/BLAS, Rayon, OpenMP or another threaded runtime can oversubscribe the machine. Measure total threads and consider constraining inner libraries when the outer layer owns parallelism.

## Rollback trigger

Disable or reduce parallelism if outputs diverge, deterministic ordering breaks, memory growth becomes unbounded, thread observation contradicts the worker model, or throughput regresses on the target environment.
