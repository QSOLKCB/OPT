# OPT — AI Usage Guide

This repository is a reusable optimization knowledge base for QSOL projects.

## Start here

1. Identify the dominant bottleneck.
2. Select the closest optimization record from `CATALOG.md`.
3. Read the source record completely before modifying another repository.
4. Preserve the target repository's semantics, invariants, determinism, evidence boundaries, and public API unless the task explicitly changes them.
5. Benchmark before and after in the target environment.
6. Record any adaptation rather than pretending source-project constants are universal.

## Decision map

- **Slow pytest / deterministic numerical tests** → `OPT-PY-001`
- **Repeated work known to be mathematically or bitwise equivalent** → `OPT-INV-001`
- **Lean/mathlib dependency rebuild dominates CI** → `OPT-LEAN-001`
- **Independent work can run concurrently** → `OPT-PAR-001`
- **High-rate numerical/audio loop with slower control state** → `OPT-DSP-001`

Patterns may be composed. Example: a numerical CI job can use `OPT-PY-001` inside the test process and `OPT-PAR-001` at a higher independent-work layer, but only after nested parallelism and memory pressure are measured.

## Status vocabulary

- **Verified**: source project contains passing validation and measured/observed evidence for the optimization.
- **Verified, environment-specific**: measured result is real but not a universal performance guarantee.
- **Implemented reference**: the optimization mechanism exists in code, but no general speedup claim is made.
- **Proposed**: architecture/design idea only. Do not report it as achieved performance.
- **Source candidate**: material exists but has not been inspected sufficiently to promote claims.

## Non-negotiable safety rules

- Never remove tests merely to make CI faster.
- Never weaken an assertion, tolerance, theorem target, receipt, claim boundary, or validation rule without an explicit contract change.
- Never treat a cache hit as proof of a cold rebuild.
- Never equate a requested worker count with observed effective parallel execution.
- Never claim SIMD/zero-copy/lock-free speedups from `power_module.md` without controlled measurements.
- Never claim anything from `suxen.zip` until it has been inventoried and the relevant source has been read.

## What to copy vs what to adapt

Copy the **structure** of the optimization: cache identity binding, deterministic reuse, equivalence gates, bounded workers, control-rate separation, sparse evaluation, vectorized batches.

Adapt the **numbers**: trial counts, iteration caps, cache sizes, worker caps, sample/control rates, sparse cardinalities, timing thresholds, tolerances and environment-specific hashes.

## Evidence expected in a new OPT record

At minimum record:

- source repository and immutable-enough source identity (release/commit/PR head);
- baseline and optimized behavior;
- correctness/conformance gate;
- benchmark environment or an explicit statement that no benchmark exists;
- failure/rollback condition;
- whether the optimization changes latency, throughput, memory, CI time, or only architecture.
