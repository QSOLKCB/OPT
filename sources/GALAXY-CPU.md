# GALAXY CPU optimization phases

## Source identity

- Repository: `QSOLKCB/GALAXY`
- License: Apache-2.0 (`LICENSE` on the source repository)
- Optimization sequence: merged PRs #10 through #14 on 2026-09-15
- Scope: CPU SIMD/autovectorization evidence, worker-local SoA tiling, guarded production integration, persistent topology-aware worker pools, and calibrated host-aware execution-path promotion.

## Merged donor evidence

### PR #10 — deterministic CPU SIMD probe

- PR: https://github.com/QSOLKCB/GALAXY/pull/10
- Merge commit: `02f26f0f3630487b7db9522e9db3a5e5536f5765`
- Key files: `cpu-runtime/src/bin/simd_probe.rs`, `scripts/bench-cpu-simd.sh`, `docs/CPU-SIMD.md`
- Mechanism: reshape an exact hot contribution/hash loop into a batch/SoA form that LLVM can autovectorize, build the same source for generic and host-native CPU targets, inspect generated assembly, and require element/checksum parity before considering integration.
- Environment-scoped donor observation reported by the next phase: Ryzen 9 5950X generic median 34,942,130 ns versus native median 10,742,437 ns, a 3.252719099x isolated speedup and 69.256491% median reduction. The donor identified SSE2 packed operations in the generic build and AVX2/VEX packed operations in the native build; AVX-512 was absent on that Zen 3 host as expected.
- Boundary: PR #10 explicitly did not claim an end-to-end GALAXY speedup.

### PR #11 — worker-local SoA runtime probe

- PR: https://github.com/QSOLKCB/GALAXY/pull/11
- Merge commit: `8c69f87278d071db47d85a787905778eeec64ded`
- Key files: `cpu-runtime/src/bin/worker_soa_probe.rs`, `scripts/bench-cpu-worker-soa.sh`, `docs/CPU-WORKER-SOA.md`
- Mechanism: replace a full-resident AoS traversal in the experimental path with deterministic contiguous worker ranges, bounded compact SoA particle tiles, reusable worker-local scratch, and SIMD-friendly batch contribution hashing. Working memory scales with workers × tile instead of total resident population.
- Validation: reference/generic/native/SoA checksum parity across every benchmark matrix cell, deterministic worker-count behavior, tile-range sweeps, disassembly evidence where available, RSS evidence, and cross-platform native CI.
- Boundary: the donor requires a practical winning tile range, useful worker scaling, and acceptable RSS before promotion; one pathological fast point is insufficient.

### PR #12 — guarded production SoA integration

- PR: https://github.com/QSOLKCB/GALAXY/pull/12
- Merge commit: `0e389cb4179902fae93f4a77d6ab2a539e73bc72`
- Key files: `cpu-runtime/src/bin/galaxy_cpu_dispatch.rs`, `docs/CPU-SOA-INTEGRATION.md`
- Mechanism: integrate the proven worker-local SoA path behind explicit opt-in production commands while preserving the canonical AoS path as unchanged default, correctness oracle, and fallback.
- Validation: cross-platform integrated `verify-soa`, production-identity receipts, guarded execution metadata, and exact checksum equality with the canonical BAM-LUT path.
- Boundary: guarded integration is evidence for the SoA record's safe deployment shape, not a claim that opt-in command surfaces are themselves a performance optimization.

### PR #13 — persistent topology-aware SoA execution

- PR: https://github.com/QSOLKCB/GALAXY/pull/13
- Merge commit: `1966bc2595a402a2c653f2e392465224621e20fb`
- Key mechanism: create the SoA worker set once, allocate each worker's compact tile once, reuse threads/buffers across warm-up and measured repetitions, collect completion asynchronously, and reduce strictly in worker-index order.
- Topology policy: explicit `physical-first` versus `logical`; Linux uses process CPU allowance plus sysfs topology, macOS uses `sysctl`, and unsupported/unreliable physical topology falls back explicitly to logical availability.
- Timing boundary: steady-state timings exclude pool startup but record `pool_startup_ns` separately. The donor explicitly makes no CPU-affinity or NUMA-placement claim.
- Validation: canonical checksum = spawned SoA checksum = first persistent dispatch = second persistent dispatch, plus cross-platform CI and explicit topology/fallback receipts.

### PR #14 — calibrated host-aware CPU promotion

- PR: https://github.com/QSOLKCB/GALAXY/pull/14
- Merge commit: `b2e860309a04d7591c86f71d2b4ab1e5eec4c4d7`
- Policy identifier in donor: `calibrated-host-auto-v1`
- Candidate families: canonical execution, spawned worker-local SoA across a finite tile set, persistent physical-first SoA, and persistent logical/SMT SoA when distinct.
- Calibration shape: preserves requested frame depth, preserves effective per-worker tile shape by expanding only within the requested resident workload, and uses an explicit projection from calibration to requested particle-frame work.
- Lifecycle accounting: persistent candidates include full requested pool startup plus teardown amortized over requested repetitions; startup includes worker creation, tile allocation, and first-touch/commitment of worker-local buffers.
- Promotion: donor uses a 5% projected advantage over canonical; near-ties remain canonical.
- Correctness: every calibration candidate and the selected full workload must match an independent streaming canonical oracle exactly. Any mismatch fails closed rather than silently falling back.
- Evidence scope: process-wide Linux `VmHWM` is labelled whole-invocation evidence and is not misrepresented as selected-engine RSS.

## Reusable mechanisms promoted into OPT

1. **Evidence-gated native autovectorization** — expose a compiler-friendly batch shape, compare generic and native builds from identical source, inspect actual code generation, and require exact parity plus repeatable gain before integration.
2. **Worker-local SoA tiling** — transform a large AoS traversal into bounded worker-local SoA tiles with deterministic partition/reduction and an unchanged oracle path.
3. **Persistent topology-aware worker pools** — amortize thread/buffer setup across repeated executions, choose physical/logical worker policies explicitly, and keep completion-order independence through deterministic reduction.
4. **Calibrated host/workload-aware promotion** — benchmark a bounded candidate set on workload-shaped calibration, include lifecycle/tuning costs, require a material promotion margin, and verify the selected full execution against an independent fail-closed oracle.

## Non-transferable constants

Do not copy the donor's worker counts, tile sizes (including 1,024 / 4,096 / 16,384 / 65,536), 65,536-particle calibration base, three calibration repeats, 5% promotion margin, or Ryzen timing observations as universal settings. They are source-environment evidence only. Re-profile candidate sets, calibration budgets, promotion margins, topology policy, and lifecycle amortization in the target repository.

## Licensing / reuse boundary

Both GALAXY and OPT are Apache-2.0 repositories at the time of this source note. The OPT records describe reusable mechanisms and provenance; they do not require copying GALAXY implementation code. If code is copied later, retain the applicable Apache-2.0 notices and re-check the donor license at the pinned source revision.