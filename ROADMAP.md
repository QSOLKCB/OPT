# OPT Roadmap

This roadmap tracks candidate optimization families that are worth promoting into the catalog after their source identity, reusable contract, evidence boundary and target-specific validation are written down. A roadmap entry is **not** a verified optimization record and must not be cited as if it were already part of the catalog.

## Near-term donor mining: VORTEX-N v5.0.0

The VORTEX-N v5.0.0 Zenodo bundle contains three high-signal mechanisms that appear distinct from the existing GALAXY-derived records. The goal is to preserve the reusable mechanism while refusing to promote donor-specific dimensions, buffer layouts, workgroup sizes, matching counts, receipt sizes or benchmark numbers as universal settings.

Before any of these become catalog records, add a pinned VORTEX-N source note with the relevant release/DOI/commit identity, licensing boundary, exact donor files/sections, and a clear statement of which observations are implementation evidence versus target-independent claims.

### Candidate: `OPT-CONFLICT-001` — Conflict-free dependency partitioning

**Problem:** logically independent work is forced through atomics, locks, collision arbitration or serialized mutation because some operations can touch the same state.

**Reusable mechanism:** build or derive a conflict/dependency graph over each operation's complete read set, write set and externally observable effects; partition operations into independent sets such as matchings/color classes; and execute one phase in parallel only when it contains no write/write, write/read, read/write or observable-effect hazards.

**Why it looks promising:** this can replace runtime contention with an explicit scheduling transform. The pattern is applicable to graph processing, mesh/constraint updates, particle or interaction systems, sparse mutation, schedulers and other workloads where write conflicts are structurally knowable.

**Evidence gate before promotion:**

- prove the partition removes all declared write/write, write/read, read/write and observable-effect hazards for the operation model;
- compare scalar/serial and partitioned-parallel execution against the same canonical/reference semantics, including ordering where observable;
- measure scheduling/partition overhead as well as lock/atomic reduction;
- test skewed or adversarial graphs where the number of phases grows;
- do not assume the donor's number of matchings or graph topology transfers to another target.

### Candidate: `OPT-RESIDENT-001` — Accelerator-resident double-buffered execution

**Problem:** iterative accelerator workloads repeatedly pay host/device transfer, allocation, synchronization or read/write hazard costs even though most state is reused from one iteration to the next.

**Reusable mechanism:** keep the hot iterative working set resident on the accelerator and separate current/next state with explicit ping-pong or equivalent double buffering. Reuse resident allocations across rounds and cross the host/device boundary only when the public contract requires it.

**Why it looks promising:** this attacks transfer and lifecycle overhead while also making read-state/write-next-state ownership explicit. It composes naturally with local/shared-memory staging inside a workgroup and with compact readback after the resident computation finishes.

**Evidence gate before promotion:**

- compare lifecycle-adjusted runtime with a transfer-heavy or reallocation baseline;
- account for retained accelerator memory as a real resource cost;
- verify exact or declared-tolerance parity across many iterations;
- validate buffer-generation ownership so stale or partially written state cannot leak across rounds;
- test small workloads where residency overhead or retained memory is not justified;
- treat workgroup size, buffer shape and donor memory layout as target-specific.

### Candidate: `OPT-READBACK-001` — Device-side aggregation and compact readback

**Problem:** a caller transfers a large accelerator-resident state back to the host merely to compute a much smaller verification, summary or decision payload.

**Reusable mechanism:** aggregate evidence where the data already lives, then transfer only the smallest result needed by the external contract—for example counts, histograms, extrema, mismatch summaries, digests/receipts or other bounded evidence rather than the full state.

**Why it looks promising:** this turns readback volume into an explicit optimization target and can remove a bandwidth/synchronization boundary without changing the underlying computation.

**Evidence gate before promotion:**

- define exactly which host-visible questions the compact evidence must answer;
- prove the aggregate is sufficient for that contract rather than merely convenient;
- compare full-state readback with device-side reduction plus compact transfer;
- include reduction-kernel cost, synchronization and transfer latency in the objective;
- retain full-output comparison paths where exact element-level validation is required;
- do not treat a donor-specific receipt size or reduction schema as portable.

## Supporting mechanisms to keep as composition/validation notes for now

### Topology-aligned cooperative workgroups

Map one self-contained logical unit to one cooperative workgroup and stage its hot local state in workgroup/shared memory when that reduces global-memory traffic and synchronization. This is likely to compose with `OPT-RESIDENT-001`, but it should not become a separate record until there is evidence that the mapping itself—not merely residency or data layout—delivers a distinct reusable win.

### Deterministic procedural control regeneration

Regenerate deterministic control/schedule state from compact seeds or round/cell identities instead of storing and transferring a large precomputed schedule when arithmetic is cheaper than memory traffic. Keep this as a candidate composition technique until a controlled comparison isolates its memory/bandwidth benefit and proves replay equivalence.

### Exact inverse/replay verification

Where an optimized transformation is reversible, use forward-then-inverse replay as supplementary correctness evidence and require restoration of the original state under the declared exactness contract. Also require a forward-result oracle—direct parity with a trusted reference output or independent semantic invariants—so mutually consistent forward/inverse defects cannot pass merely because they round-trip. This is valuable validation guidance, but it is not automatically a performance optimization and should not be promoted as one without an independent objective win.

## Promotion rule

A roadmap candidate becomes a catalog record only when it has:

1. a concrete source identity and provenance note;
2. a complete `P = (X, F, f, d, C, B, S)` contract;
3. all required problem-classification fields;
4. a preserved-contract statement and explicit failure/rollback boundaries;
5. before/after evidence or an explicit no-benchmark statement;
6. validation that tests the mechanism's own failure modes rather than only the happy path; and
7. no donor constant promoted as a universal default without target evidence.

The intended progression for the VORTEX-N-derived work is:

**reduce conflicts → localize/cooperate → keep state resident → reduce before transfer**

This complements the GALAXY-derived progression already in the catalog:

**data layout → ISA exploitation → persistent execution → empirical runtime selection**
