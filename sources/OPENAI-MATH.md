# Source note — OpenAI mathematical manuscripts

- Repository: https://github.com/openai/math
- Inspected source commit: `fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb` (2026-10-08).
- Catalogue: [CONTENTS.md](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/CONTENTS.md); verification/revision history: [history.md](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/history.md).
- Licensing boundary: [root Apache-2.0 license](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/LICENSE). Third-party Lean dependencies and any future copied assets require their own license review. This OPT addition paraphrases mechanisms and independently implements a small integer example; it imports no donor code, certificates or Lean dependencies.
- Evidence boundary: screened catalogue descriptions and inspected selected manuscript sources, verification instructions/scripts, scope notes and challenge configuration. OPT has not independently rebuilt the donor Lean library or replayed its numerical certificates. The source includes revisions and withdrawals; pin each adopted source rather than citing moving `main` as immutable evidence.

## Adopted mechanism: streamed products and bounded tie replay

Family 138 contains [A Low-Space Algorithm for Worst-Case Subset Sum](https://github.com/openai/math/tree/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/A-Low-Space-Algorithm-for-Worst-Case-Subset-Sum-September-26-2026).

Relevant sections:

- [build/streams.tex](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/A-Low-Space-Algorithm-for-Worst-Case-Subset-Sum-September-26-2026/build/streams.tex): filtered pair-stream ordering, preservation of repeated occurrences, copied mutable generator state and bounded equal-key Cartesian joins. The lemma charges state restoration as well as stream advances and potential matches, including stopped executions.
- [build/compression.tex](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/A-Low-Space-Algorithm-for-Worst-Case-Subset-Sum-September-26-2026/build/compression.tex): regeneration, distinct-weight dictionaries and overflow handling in a specialized randomized decision procedure.
- [build/implementation.tex](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/A-Low-Space-Algorithm-for-Worst-Case-Subset-Sum-September-26-2026/build/implementation.tex): encoding, bounded sampling and operation counters in that procedure.

The manuscript explicitly credits Schroeppel and Shamir's classical sorted pair-sum method, Nederlof and Węgrzycki's later stream descriptions, and earlier dissection algorithms. The reusable OPT adaptation is the storage/replay tradeoff, not a claim that OpenAI invented lazy pair enumeration.

OPT's integer example has no modular filtering, random partitions, prime sampling, overflow-discard decision rule or Subset Sum solver. It preserves indexed duplicates, even though the donor can deduplicate weights in certain disjoint-domain decision-only subproblems. That donor permission cannot be copied into an enumeration/witness API. The inspected family 138 catalogue entry has no Lean coverage link; the stream lemma is treated as a manuscript argument. OPT's own tests and measurements are recorded separately in `OPT-STREAM-001`.

## Adopted evidence practice: distinguish integrity and proof replay

The [matrix multiplication verification README](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/Complex-Matrix-Multiplication-Below-2.258-and-Rectangular-Bounds-September-24-2026/README.md) describes:

1. hash/size and build-input inventory checks;
2. a separate square-certificate numerical replay and manuscript-bound check;
3. rectangular checks and optional numerical diagnostics.

The [integrity checker](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/Complex-Matrix-Multiplication-Below-2.258-and-Rectangular-Bounds-September-24-2026/verification/scripts/check_certificate.py) verifies manifest membership, hashes and sizes. Its success is not execution of the numerical proof. The instructions also distinguish numerical diagnostics from rigorous interval certificates and finite arithmetic checks from manuscript tensor/analytic arguments.

OPT adopts this separation in [EVIDENCE-SCOPE.md](../EVIDENCE-SCOPE.md) and the record template. No external replay is reported as completed. This is evidence hygiene, not a new speedup record.

## Research candidates and exclusions

| Family | Relevant donor scope | OPT disposition |
| --- | --- | --- |
| 124 — three-machine scheduling | [scope](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/124.md), [algorithm manuscript](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/preprints/A-polynomial-time-algorithm-for-three-machine-unit-job-scheduling-September-24-2026/build/paper.tex) | Candidate bounded-description dynamic programming; unit jobs, three identical machines, acyclic precedence. The explicit bound has degree 150020, so no practical scheduler promotion. |
| 110 — randomized k-server | [scope](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/110.md) | Candidate online placement policy; oblivious requests, movement objective, and potentially enormous additive constant. No generic cache-capacity or latency guarantee. |
| 107 — matrix multiplication | [scope](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/107.md) | Arithmetic-complexity donor; practical crossover and bit/numerical cost require independent work. No replacement of CPU numerical kernels. |
| 130 — exact Fourier circuits | [scope](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/130.md) | Exact-complex, unrestricted-coefficient model; separate subsequential and uniform statements. No floating-point DSP speed/stability claim. |
| 139 — log-concave sampling | [scope](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/139.md) | Exact value/gradient query count with unrestricted intervening computation, known minimizer and Hessian assumptions. Does not justify a general black-box tuner speedup. |
| 094 — Lp dimension reduction | [scope](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/094.md) | Existence/dimension/distortion result; no implemented embedding or end-to-end benefit established for OPT. |
| 118 — bin-packing gaps | [scope](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/docs/118.md) | Caution about relaxation/integrality gaps; no new implementation or performance mechanism promoted. |

The graph-matching, integer-multiplication and faster Subset Sum catalogue claims were also screened. Their headline complexity bounds are not target implementation evidence. Only the narrower streaming mechanism and explicit evidence practices above are adopted here.

## Lean boundary

The pinned [toolchain](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/lean-toolchain) uses Lean 4.34.1; the [Lake configuration](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/lakefile.lean) pulls numerous third-party dependencies. The [Comparator guide](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/ComparatorChallenges/README.md) distinguishes main statements from some supporting-result comparisons.

For example, [ThreeMachine.json](https://github.com/openai/math/blob/fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb/lean/ComparatorChallenges/ThreeMachine.json) compares a challenge with `OAI.Computability.Scheduling.Main` and permits `propext`, `Quot.sound` and `Classical.choice`. The challenge's placeholder proof is not the solution. These are external published configurations, not OPT-replayed results and not compatible-by-association with OPT's stricter pinned v1 trust surface.
