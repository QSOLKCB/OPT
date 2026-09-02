# OPT-PAR-001 — Bounded Deterministic Parallel Execution

**Status:** Verified, environment-specific  
**Domains:** CPU parallelism, Rust/native workers, simulation batches, CI workloads

## Source evidence

- QEC v170.2.0: https://github.com/QSOLKCB/QEC/releases/tag/v170.2.0
- QEC v170.2.1: https://github.com/QSOLKCB/QEC/releases/tag/v170.2.1

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

### 6. Report speedup and efficiency with environment labels

Use:

```text
speedup = scalar_time / parallel_time
efficiency = speedup / workers
```

but keep runner/CPU/toolchain context attached.

## Evidence snapshot

The validated qBraid observation reports:

- scalar median: **69.694063 ns/eval**;
- 7-worker parallel median: **18.310215 ns/eval**;
- measured speedup: **3.8062940822923164×**;
- measured efficiency: **0.5437562974703309**;
- maximum threads observed: **8** (one main thread plus seven workers in the recorded evidence).

These are environment-specific implementation observations, not universal guarantees.

## Determinism checklist

- deterministic work partitioning or canonical result merge;
- stable output ordering;
- no shared mutable RNG without explicit stream partitioning;
- scalar/parallel equality or invariant comparison;
- bounded queue/buffer growth;
- worker failure propagated rather than dropped;
- repeated-run determinism test;
- benchmark excludes setup costs only when that exclusion is stated.

## Watch for nested parallelism

A worker pool calling NumPy/BLAS, Rayon, OpenMP or another threaded runtime can oversubscribe the machine. Measure total threads and consider constraining inner libraries when the outer layer owns parallelism.

## Rollback trigger

Disable or reduce parallelism if outputs diverge, deterministic ordering breaks, memory growth becomes unbounded, thread observation contradicts the worker model, or throughput regresses on the target environment.
