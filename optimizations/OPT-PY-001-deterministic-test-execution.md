# OPT-PY-001 — Deterministic Test Execution

**Status:** Verified  
**Domains:** Python, pytest, deterministic numerical simulation, CI  
**Primary sources:** QEC v68.2.0, v68.4.0, v68.4.1

## Source evidence

- https://github.com/QSOLKCB/QEC/releases/tag/v68.2.0
- https://github.com/QSOLKCB/QEC/releases/tag/v68.4.0
- https://github.com/QSOLKCB/QEC/releases/tag/v68.4.1
- https://github.com/QSOLKCB/QEC/commit/36d4fe13f32d9d55fd3b1db4ffc8e4c26b67b1d0
- https://github.com/QSOLKCB/QEC/commit/48e13fc737df0c4f6aed313c8a12983e209a45ac
- https://github.com/QSOLKCB/QEC/commit/83f0479546e9d1d2bf8effdbbd2e18967c7ae711

## Problem

Deterministic scientific tests often spend most of their wall time repeating work that is useful for research sweeps but unnecessary for regression confidence: oversized fixtures, redundant parameter points, excessive iteration ceilings, repeated lookup construction, and loops that keep running after the state has converged or entered a cycle.

## Reusable pattern

### 1. Use the smallest fixture that still exercises the invariant

QEC introduced canonical minimal parity matrices for structural tests rather than constructing larger research-scale inputs. The fixture must still hit the same code path and assertion semantics.

### 2. Vectorize simple correctness classifications

QEC added ternary `+1 / 0 / -1` assertions backed by `np.int8`. This replaces Python-level element loops with array operations while making success/uncertain/failure states explicit.

### 3. Cache deterministic immutable intermediates

QEC used a bounded cache for arrays, stable keying, read-only cached arrays and test isolation/reset behavior. The generic rule is:

- cache only pure/deterministic results;
- make cached values immutable or defensively copied;
- bind the key to every input that can affect the result;
- bound memory;
- clear or namespace state between tests when cross-test reuse could hide contamination.

### 4. Stop deterministic loops when further work cannot change the result

QEC added windowed convergence detection based on recent state deltas and cycle/repeated-state detection. Early exit is valid only when the terminating condition is part of the tested algorithm or is proven not to alter the expected output.

### 5. Reduce sweep cardinality without deleting semantic coverage

The v68.4.0 optimization reduced expensive sweeps while preserving boundary coverage, monotonicity checks and trend correctness. Examples from the implementation include reducing trials, maximum iterations, frame counts, instance counts and intermediate parameter-grid points.

Do **not** transplant those exact numbers blindly. Re-derive the minimal set for the target test's assertions.

### 6. Precompute repeated lookups and eliminate redundant calls

The v68.4.1 implementation precomputed per-parameter dictionaries once and reused them across summary/analysis passes. See also `OPT-INV-001` for eliminating an entire benchmark call when a parameter point is provably baseline-equivalent.

## Evidence

Two source measurements exist for v68.4.0:

- implementation commit: ~127 s → ~52 s (~2.4×);
- published release notes: ~126 s → ~46 s (~2.7×).

The difference is normal benchmark/run variance and is preserved rather than averaged away. The v68.4.1 release reports ~40 s with **3779 passed / 8 skipped** and deterministic behavior preserved.

## Target-repo checklist

- Profile with `pytest --durations=20` (or another explicit count; `--durations=0` reports all) or equivalent before editing.
- Identify the top few expensive tests, not the median test.
- Write down the assertion semantics each expensive sweep is intended to establish.
- Minimize fixtures and grid cardinality against those semantics.
- Add deterministic early-exit only where result equivalence is defensible.
- Cache only pure state and test cache isolation.
- Re-run the full suite, not only the optimized tests.
- Record before/after wall time on the same machine/runner class.

## Do not use when

- sample count itself is the statistical claim;
- reducing trials invalidates a confidence interval or power requirement;
- convergence/cycle detection changes the algorithm under test;
- cached state depends on hidden process/global state;
- the proposed speedup comes from weakening tolerances or skipping assertions.

## Rollback trigger

Rollback if any deterministic output, assertion surface, public API, statistical guarantee, or isolation property changes unexpectedly, even if wall time improves.
