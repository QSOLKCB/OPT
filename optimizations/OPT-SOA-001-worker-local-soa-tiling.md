# OPT-SOA-001 — Worker-local SoA tiling

**Status:** Implemented external reference; GALAXY demonstrates exact cross-platform parity and guarded production integration, while target tile/worker settings remain environment-specific.  
**Domains:** CPU simulation, rendering, numerical kernels, batch transforms, memory-bound pipelines

## Source evidence

- Repository: `QSOLKCB/GALAXY`
- Prototype PR: https://github.com/QSOLKCB/GALAXY/pull/11
- Guarded production integration PR: https://github.com/QSOLKCB/GALAXY/pull/12
- Merge commits: `8c69f87278d071db47d85a787905778eeec64ded` and `0e389cb4179902fae93f4a77d6ab2a539e73bc72`
- Source note: `sources/GALAXY-CPU.md`
- Licensing boundary: Apache-2.0 donor; this record describes the reusable data-layout/execution pattern rather than importing source code.

## Problem

A large array-of-structures working set is repeatedly traversed by multiple workers and frames/stages. The representation carries fields not needed by the hot path, causes poor cache/vector access, inflates resident memory, and forces worker execution to touch more data than necessary. A whole-population SoA conversion may itself be too large or expensive.

## Optimization problem contract

- X: Worker-local layout, packing, tile-capacity and deterministic partition choices that transform only the hot fields required for a bounded chunk of the source population.
- F: Candidates that preserve exact source-to-output semantics, deterministic partitioning and reduction, represent every required field without lossy reinterpretation, keep worker-local memory bounded, and retain an unchanged canonical/reference path.
- f: End-to-end runtime, peak working-memory/RSS evidence and useful worker scaling over the declared workload matrix.
- d: Pareto-minimize runtime and memory footprint subject to exact parity; reject candidates whose timing gain requires unacceptable RSS growth or unstable worker scaling.
- C: Exact checksum/output equality with the reference path, deterministic worker-count behavior where required, no dropped/duplicated elements, and bounded worker-local storage independent of total resident population.
- B: A bounded worker-count × tile-size benchmark matrix with repeated runs and representative workload sizes on the target machines.
- S: Stop after a practical winning tile/worker region is identified or all candidates fail; do not promote a single pathological fast point without surrounding evidence.
- Variables: integer and categorical
- Search scope: global
- Objective behavior: noisy
- Information: black-box
- Evaluation cost: expensive
- Constraints: semantic and resource
- Parallelism: synchronous batch
- Exactness: exact

## Preserved contract

The tiled SoA path must compute the same declared outputs/checksum as the reference AoS path for every processed element and supported worker count. Reordering storage is allowed only when observable output order, tie behavior, reduction semantics and deterministic identity remain unchanged.

Packing fields into narrower representations is permitted only when the representation is proven exact for the target domain or when the target contract explicitly allows approximation. This record is exact by default.

## Optimization

1. Keep the authoritative source representation or generation contract unchanged.
2. Partition the source population into deterministic contiguous or otherwise contract-safe worker ranges.
3. Give each worker a bounded tile containing only hot primitive fields in structure-of-arrays form.
4. Fill one tile, execute all profitable work for that tile while it is cache-resident, and reuse worker-local scratch rather than allocating a full transformed population.
5. Batch the resulting primitive lanes so compiler/native vectorization can operate on independent values.
6. Reduce worker results in a deterministic order when arithmetic/order semantics require it.
7. Sweep tile sizes and worker counts because the useful tile is a cache/memory/scheduling property of the target, not a universal constant.
8. Integrate behind an explicit guarded path until production evidence justifies any default change; preserve the canonical path as oracle/fallback.

The key scaling property is that optimized working storage grows roughly with workers × tile capacity, not with the complete resident population.

## Before / after evidence

- Environment: GALAXY PRs #11–#12 exercised Linux x86-64, Linux ARM64, macOS ARM64 and Windows x86-64 parity/CI surfaces; performance evidence remained host-scoped.
- Workload/fixture: resident particle generation, BAM-LUT projection, contribution hashing and deterministic worker reduction across multiple frames.
- Cold baseline: full-resident 40-byte AoS reference shape in the donor experiment.
- Warm/no-op baseline where relevant: not promoted as a portable metric.
- Small invalidation / partial-work case where relevant: small tile/worker matrix cells validate capacity and partition behavior.
- Large invalidation / full-work case where relevant: donor sweep supports resident populations up to the full experimental workload and multiple tile sizes/workers.
- Optimized: bounded worker-local compact SoA tiles with worker-local x/y/output scratch and SIMD-friendly batch hashing.
- Speedup / memory / I/O / quality change: donor PR #12 states that PR #11 established exact cross-platform parity and strong multi-host performance/memory evidence; this record intentionally does not turn those donor observations into universal target numbers.
- Variance / repetitions / raw samples: donor sweep emits raw matrix data, comparison tables and receipts; targets must repeat the sweep locally.

## Validation

- Check exact reference/generic/native/SoA checksum equality for every matrix cell.
- Verify deterministic partitioning covers every source element exactly once.
- Verify worker-count invariance when the target contract requires it.
- Test tile-capacity boundaries, partial final tiles and minimum/maximum supported sizes.
- Validate packed-field encode/decode or direct arithmetic equivalence independently.
- Measure end-to-end timing with the same setup/generation boundary for baseline and optimized paths.
- Record peak-memory/RSS scope honestly; process-wide high-water marks are not per-engine measurements unless isolated.
- Retain cross-platform CI for the guarded optimized path before changing defaults.

## Target-repo adaptation

Re-profile hot-field selection, field widths, tile capacity, cache hierarchy, worker count, scratch-array size, alignment, source-generation cost, frame/stage reuse depth and memory-bandwidth limits. Copy neither GALAXY's tile sizes nor its compact encodings without proving they fit the target domain exactly. Consider NUMA placement separately; ordinary worker-local tiling does not imply NUMA locality.

## Failure modes

- Tile fill/conversion overhead dominates the saved traversal cost.
- Tiles are too small to amortize setup or too large for useful cache residency.
- Narrow packing truncates or aliases values outside the donor's domain.
- Worker-local scratch multiplies memory enough to erase the AoS savings at high worker counts.
- Memory bandwidth becomes the bottleneck after vectorization/parallelism.
- Deterministic reduction is replaced by completion-order reduction and changes results.
- A guarded experimental win is promoted globally without evidence across the supported hardware/workload envelope.

## Rollback trigger

Fall back to the canonical representation/path on any parity failure, missing/duplicated work, representation-range violation, unstable worker-count behavior, unacceptable RSS growth, or reproducible end-to-end slowdown. Keep the optimized path opt-in when the winning region is narrow or host-specific.

## Composition notes

Composes strongly with `OPT-SIMD-001` because SoA/batched primitives often unlock vector code generation, and with `OPT-POOL-001` when worker-local tiles can persist across repeated runs. Re-measure with `OPT-PAR-001`: more workers can increase local scratch and memory-bandwidth pressure even when each worker is individually faster.