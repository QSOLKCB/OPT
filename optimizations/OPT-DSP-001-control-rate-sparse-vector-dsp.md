# OPT-DSP-001 — Control-Rate, Sparse and Vectorized DSP

**Status:** Implemented reference for control-rate/sparse/vector patterns; whole-block audition approximation and native backend ideas are proposed only  
**Domains:** audio DSP, numerical real-time systems, vectorized simulation, control systems

## Source evidence

- Local design source: [`../power_module.md`](../power_module.md)
- Implemented NumPy reference pinned to SPECTRAL commit `5265b7f130287f80b5cf0d3de5bb2953152f90cd`:
  https://github.com/QSOLKCB/SPECTRAL/blob/5265b7f130287f80b5cf0d3de5bb2953152f90cd/e8_fractal_power_module.py

The immutable commit is the evidence source for the implementation details below. A mutable `main` branch is not used as the provenance anchor.

## Implemented optimization pattern

The pinned SPECTRAL E8 fractal power-module reference contains several reusable hot-loop ideas.

### 1. Separate control rate from sample rate

Slow E8/qutrit state is evolved at a default **~1 kHz control rate** while audio runs at **48 kHz** in the example configuration. This means control evolution is not recomputed for every audio sample.

At 48 kHz / 1 kHz there are nominally 48 samples per control update. That is a reduction in **control-update frequency**, not a claim of 48× total program speedup.

### 2. Precompute static structures

At initialization the reference builds:

- the 240×8 E8 root matrix;
- deterministic sparse root indices per node;
- base frequencies;
- sample/control scheduling constants.

Do not rebuild static topology inside the hot path.

### 3. Compute shared intermediates once

Each control step computes all root phases once with a vectorized matrix product (`roots @ theta`) and shares that result across nodes.

### 4. Use sparse per-node coupling

The reference selects **12 roots per node** from the 240-root system. Each node sums only its sparse subset rather than evaluating all roots independently.

This reduces per-node coupling terms from 240 to 12 in that reference design (20× fewer terms at that stage), while preserving a globally computed 240-root phase vector.

### 5. Vectorize block synthesis

The NumPy reference uses float32 arrays, broadcasting and batch operations for phase construction, waveform morphing and mixdown instead of a Python sample loop. It also precomputes constants such as `2π / sample_rate` per render call.

### 6. Do not promote the reference renderer's whole-block modulation shortcut

The pinned research `render()` implementation first advances scheduled control updates for the requested sample count and then synthesizes the whole requested block using the resulting modulation values as constants. Its own source calls this a cheap approximation and recommends sub-chunking for tighter coupling.

That shortcut is **implemented research/audition behavior, not a verified reusable optimization contract**. The source project does not define a maximum valid block size, numerical/audio error tolerance, or comparison receipt against a higher-rate reference. OPT therefore does not tell consumers to copy it as correctness-preserving behavior.

Before a target project may promote block-held control state as an optimization, it must define and test all of the following:

1. a reference execution with the intended control-update semantics;
2. a maximum chunk/block size;
3. comparison metrics appropriate to the domain, such as max absolute sample error, RMS error, state/phase error, or application-specific perceptual/numerical bounds;
4. explicit acceptance tolerances;
5. regression vectors that cover control-boundary crossings and worst-case modulation rates.

Until those exist, process bounded sub-chunks according to the target's control schedule or retain the reference path.

## Native/backend ideas in `power_module.md`

The design document additionally proposes:

- block SIMD for the audio-rate LFO path;
- sparse E8 coupling rather than full 248×248 algebra at audio rate;
- Rust/native zero-copy buffer handling;
- lock-free data structures on the real-time path.

Those are sensible optimization directions, but this catalog does **not** claim the document's native SIMD/latency/CPU numbers as QSOL-verified benchmarks.

## Important limitation in the NumPy reference

The research `render()` builds an `num_nodes × num_samples` phase matrix. That is convenient and vectorized, but it can allocate a large temporary and is explicitly **not a hard-real-time renderer**.

For production real-time use, preserve the same control-rate/sparse/shared-computation structure while processing bounded chunks into preallocated buffers.

## Generic application recipe

1. Profile state update rates and classify parameters as static, control-rate or sample-rate.
2. Precompute static topology/constants.
3. Move slow state evolution to the lowest valid rate.
4. Compute shared intermediates once per control/block tick.
5. Sparsify coupling only when the sparse contract is intentional and validated.
6. Batch/vectorize the hot path.
7. Preallocate bounded buffers for real-time code.
8. Keep synchronization, allocation, logging and filesystem/network work off the hot thread.
9. Treat any block/chunk approximation as proposed until it has a reference, maximum size, metrics, tolerances and regression tests.

## Rollback trigger

Rollback or reduce control/block decimation if the target's defined equivalence/error gate fails, state updates are missed, sparse coupling changes intended behavior, or memory/latency becomes worse despite higher arithmetic throughput. If no approximation contract exists, do not enable the approximation in a correctness-bearing path.
