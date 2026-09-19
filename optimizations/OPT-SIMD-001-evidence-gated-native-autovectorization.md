# OPT-SIMD-001 — Evidence-gated native autovectorization

**Status:** Verified, environment-specific; donor measurements are isolated-kernel evidence, not a transferable end-to-end speedup claim.  
**Domains:** CPU numerical kernels, hashing, simulation, DSP, batch transforms, compiler specialization

## Source evidence

- Repository: `QSOLKCB/GALAXY`
- PR: https://github.com/QSOLKCB/GALAXY/pull/10
- Merge commit: `02f26f0f3630487b7db9522e9db3a5e5536f5765`
- Source note: `sources/GALAXY-CPU.md`
- Key donor files: `cpu-runtime/src/bin/simd_probe.rs`, `scripts/bench-cpu-simd.sh`, `docs/CPU-SIMD.md`
- Licensing boundary: donor and this repository are Apache-2.0 at the pinned revisions; this record promotes the mechanism, not copied implementation code.

## Problem

A deterministic hot loop performs the same scalar or narrowly vectorized operation over a large batch, but the source layout or loop shape prevents the compiler from generating the widest useful instructions for the host. Hand-written ISA intrinsics may be premature, non-portable, or unsupported by the project's compiler baseline, while a generic build may leave substantial throughput unused.

## Optimization problem contract

- X: Semantically equivalent loop shapes, batch layouts, compiler target settings and optional native-specialized build variants for the identified hot kernel.
- F: Candidates that preserve exact element results and aggregate checksums, compile on the supported toolchain, never expose unsupported instructions through the portable/default path, and retain an auditable reference implementation.
- f: Measured kernel runtime together with code-generation evidence and portability/deployment cost for each validated candidate.
- d: Minimize repeatable runtime after correctness gates; prefer the simpler portable candidate when performance is a near tie or code-generation evidence is ambiguous.
- C: Exact output/checksum parity, deterministic repeat stability, truthful ISA evidence, and no promotion of an isolated-kernel result into an end-to-end claim without separate full-path measurement.
- B: A bounded set of generic/native builds, benchmark repetitions, representative batch sizes and assembly inspections on the target hardware envelope.
- S: Stop after all declared candidates have passed parity and repeated measurement; retain the generic/reference path unless a native/vectorized candidate shows a useful repeatable advantage without violating deployment constraints.
- Variables: categorical and conditional
- Search scope: local
- Objective behavior: noisy
- Information: black-box
- Evaluation cost: moderate
- Constraints: semantic and resource
- Parallelism: sequential
- Exactness: exact

## Preserved contract

The optimized build must produce exactly the same declared element outputs and aggregate checksum as the reference path. Build-target specialization may change generated instructions, but it must not silently weaken arithmetic, hashing, ordering, determinism, or supported-machine behavior. A native binary must not become the universal default unless deployment guarantees the required ISA.

Microbenchmark or probe wins remain probe evidence. They do not establish whole-application speedup until the transformed loop is measured inside the real memory, scheduling, setup and reduction path.

## Optimization

1. Isolate the suspected hot kernel behind a deterministic reference function.
2. Reshape data into a compiler-friendly batch form, commonly structure-of-arrays or separate primitive arrays, so independent iterations are visible to the optimizer.
3. Build the exact same source with a portable target and with target-specific/native code generation.
4. Compare every element and aggregate checksum against the scalar/reference path before timing.
5. Repeat timings under a controlled workload and inspect emitted assembly or equivalent compiler evidence to verify that the expected vector form actually exists.
6. Treat ISA width as evidence, not the objective: wider instructions are valuable only when the measured target workload improves.
7. Integrate only after the isolated gain survives the relevant production path, retaining a portable/reference fallback.

The reusable idea is not “turn on AVX2/AVX-512.” It is to make the loop vectorizable, verify what the compiler emitted, and require measured semantic-preserving benefit on the machine that will run it.

## Before / after evidence

- Environment: GALAXY donor run on AMD Ryzen 9 5950X / Zen 3, where AVX2/FMA are available and AVX-512 is not.
- Workload/fixture: deterministic contribution/hash batch from the GALAXY CPU runtime probe.
- Cold baseline: generic x86-64 build median reported as 34,942,130 ns in the subsequent merged phase's summary.
- Warm/no-op baseline where relevant: not applicable; the donor compared identical probe work under generic and host-native compilation.
- Small invalidation / partial-work case where relevant: not applicable.
- Large invalidation / full-work case where relevant: donor documentation includes an 8M-item confirmation procedure.
- Optimized: host-native build median reported as 10,742,437 ns.
- Speedup / memory / I/O / quality change: 3.252719099x isolated speedup and 69.256491% median reduction; exact checksum parity retained. Generic code used SSE2 packed operations while the native Zen 3 build showed AVX2/VEX packed operations.
- Variance / repetitions / raw samples: the donor retains machine-readable receipts and repeated runs; this OPT record does not promote the source timings as a target expectation.

## Validation

Require all of the following before promotion:

- element-by-element equality with the canonical/reference function;
- identical aggregate checksum across generic/native/vectorized candidates;
- repeat checksum stability;
- explicit host feature reporting or deployment capability guarantees;
- assembly/compiler evidence that the tested optimized build actually uses the intended vector form;
- repeated timing under the same workload and timing boundary;
- full-path validation after integration, including memory traffic, scheduling, reduction and RSS where those can erase the isolated gain.

## Target-repo adaptation

Re-profile the compiler version, minimum supported CPU, target-feature flags, batch size, data alignment, aliasing assumptions, integer/float semantics, hot-loop shape and deployment model. Do not copy `target-cpu=native` into distributed binaries unless the execution fleet guarantees compatibility. For floating-point kernels, separately decide whether reassociation, contraction/FMA or altered rounding is allowed; exact integer/hash evidence does not authorize floating-point semantic changes.

## Failure modes

- The loop is memory-bound, so wider arithmetic does not improve elapsed time.
- The compiler cannot vectorize because of aliasing, branches, gathers or unsupported operations.
- A native build improves the probe but regresses the integrated path due to cache pressure, downclocking or changed instruction mix.
- The optimized binary reaches hardware lacking the required ISA.
- Floating-point vectorization changes observable numerical behavior that the target contract requires to remain stable.
- Benchmark noise or frequency scaling makes a small apparent win non-repeatable.

## Rollback trigger

Disable or decline the specialized/vectorized path immediately on any parity/checksum failure, unsupported-instruction risk, reproducible full-path regression, or loss of deterministic behavior. Revert to the portable/reference implementation when the measured target workload does not retain a useful advantage after integration.

## Composition notes

Composes naturally with `OPT-SOA-001` when a data-layout change exposes independent batch lanes, and with `OPT-BUDGET-001` for environment-scoped regression protection after a configuration is promoted. Combine with `OPT-PAR-001` carefully: thread-level parallelism plus SIMD can shift the bottleneck to memory bandwidth or oversubscribe shared resources, so re-measure the complete path.