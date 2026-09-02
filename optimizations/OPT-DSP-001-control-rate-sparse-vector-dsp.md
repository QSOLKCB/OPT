# OPT-DSP-001 — Control-Rate, Sparse and Vectorized DSP

**Status:** Implemented reference; native backend ideas partly proposed  
**Domains:** audio DSP, numerical real-time systems, vectorized simulation, control systems

## Source evidence

- Local design source: [`../power_module.md`](../power_module.md)
- Implemented NumPy reference: https://github.com/QSOLKCB/SPECTRAL/blob/main/e8_fractal_power_module.py

## Implemented optimization pattern

The SPECTRAL E8 fractal power-module reference contains several reusable hot-loop ideas.

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

### 6. Hold slow modulation constant over a block when the contract allows it

The research renderer treats control modulation as constant across the rendered block. This is explicitly an approximation and must be sub-chunked when tighter control/audio coupling is required.

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
9. Validate block/chunk approximations against a higher-rate reference.

## Rollback trigger

Rollback or reduce block/control decimation if audible/numerical error exceeds the target contract, state updates are missed, sparse coupling changes intended behavior, or memory/latency becomes worse despite higher arithmetic throughput.
