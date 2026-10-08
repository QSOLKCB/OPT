# OPT-STREAM-001 — Bounded replayable pair streams

**Status:** Implemented reference; local exact example and fixture measurements only, target benefit unverified
**Domains:** combinatorial enumeration, exact joins, memory-bounded search

## Source evidence

- Donor repository: https://github.com/openai/math at commit `fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb`, inspected 2026-10-08.
- Source note: [OpenAI mathematical manuscripts](../sources/OPENAI-MATH.md), especially the low-space Subset Sum manuscript's `build/streams.tex` filtered-stream and tie-join lemma.
- The donor credits Schroeppel and Shamir's sorted pair-sum method and later dissection work; this record does not attribute that classical mechanism to OpenAI.
- OPT code: [integer reference example](../examples/bounded_pair_streams.py), [independent tests](../tests/test_bounded_pair_streams.py), and [measurement procedure](../scripts/benchmark_pair_streams.py).
- Full-join characterization: [runner](../scripts/benchmark_pair_joins.py), [independent baseline and measurement tests](../tests/test_pair_join_benchmark.py), [raw samples](../examples/evidence/pair-join-reference.json), and [results and limitations](../examples/evidence/pair-join-characterization.md).
- Modular filtering: [separate exact pair-stream API](../examples/modular_pair_streams.py), [independent oracle tests](../tests/test_modular_pair_streams.py), [runner](../scripts/benchmark_modular_pair_streams.py), [measurement tests](../tests/test_modular_pair_benchmark.py), [raw samples](../examples/evidence/modular-pair-stream-reference.json), and [characterization](../examples/evidence/modular-pair-stream-characterization.md).
- Licensing boundary: the donor root is Apache-2.0; this is an independently written, narrower integer adaptation. No donor source code or Lean modules are imported.

### Evidence scope

- Computational model: exact arbitrary-precision Python integers, comparisons, heap operations, immutable input snapshots and a non-retaining output consumer. Arithmetic cost depends on integer bit length; this is not constant-cost word arithmetic.
- Hypotheses: finite exact-integer sequences; indexed duplicates are observable; positive integer buffer capacity for joins; positive exact-integer modulus and exact-integer residue for the separate filtered API; complete input snapshots fit the target's resource envelope.
- Guarantee: enumerate every indexed pair and every equal-sum indexed pair-of-pairs exactly once, in the declared deterministic order. The separate `FilteredPairSums` API emits exactly the subsequence satisfying `(a+b) % modulus == residue % modulus`. The existing join is `a+b == c+d`; it has no modular filter and neither API is a Subset Sum decision algorithm.
- Formal coverage: this OPT implementation is not Lean-formalized. The donor stream lemma is a manuscript argument; family 138 has no Lean scope link in the inspected catalogue. No external proof is inherited by association.
- Proof target/toolchain and axiom allowance: no Lean proof is claimed or replayed for this record; OPT's pinned v1 model remains separate.
- Independent replay: exhaustive differential tests cover small finite fixtures and adversarial regressions, not every possible Python input or the donor's headline resource theorem.
- Certificate replay: no numerical certificate is needed by this example. Ordered digests in the local benchmark are parity evidence, not a proof of universal correctness or performance.

## Problem

Materializing all combinations of smaller input arrays can dominate peak memory before a search or join consumes any results. Equal-key groups can themselves be too large to retain, especially when input values repeat.

## Optimization problem contract

- X: exact unfiltered/residue-filtered pair-enumeration and equal-sum-join implementations, with target-selected row orientation and positive tie-buffer capacity. Modulus/residue are declared query parameters, not freely changeable tuning variables.
- F: implementations preserving indexed multiplicity and ordering while fitting the target's complete input, heap, snapshot, buffer and output-storage limits.
- f: target-measured peak live memory and end-to-end enumeration/join latency, including initialization, residue bucketing, copies, replay and consumption.
- d: minimize peak live memory subject to a predeclared latency ceiling; break equal-memory ties by lower latency.
- C: preserve every required indexed occurrence, exact sum equality for joins, exact residue eligibility for filtered pairs, immutable replay inputs and deterministic actual-sum/index order; interrupted enumeration cannot establish absence of further matches or infeasibility.
- B: predeclare a finite target benchmark/evaluation budget, allowed input sizes and bit lengths (including modulus), positive buffer capacity, and memory/latency ceilings. The references validate their domains and enforce the tie-buffer item count; total bytes and runtime are observational unless the adapting target supplies complete enforcement.
- S: complete enumeration, explicit consumer cancellation, or a target-enforced resource stop; only natural exhaustion establishes that the enumeration is complete.

- Variables: integer buffer capacity and categorical implementation choice
- Search scope: local policy selection over the declared fixture set
- Objective behavior: noisy runtime and allocation measurements; deterministic reference output
- Information: derivative-free, with exact enumeration oracle
- Evaluation cost: moderate to expensive as output cardinality grows
- Constraints: exact occurrence/order semantics, stable replay state and resource ceilings
- Parallelism: sequential reference; parallel adaptation requires separate ordering and resource accounting
- Exactness: exact enumeration when exhausted; an interrupted prefix is incomplete

## Preserved contract

Pair identity is the original `(left_index, right_index)`, not just the sum or value. Equal values at different indices remain distinct. Pair streams, including the separate residue-filtered stream, sort by `(actual sum, left_index, right_index)`; joins sort by the first pair followed by the second pair at the same key. Snapshots include the next occurrence and independent mutable heap state, while sharing only immutable arrays.

The filtered API normalizes any signed integer residue, accepts composite moduli and modulus one, and never allocates a dense modulus-sized table. It snapshots on construction. Congruent sums can differ as actual integers: `[0,4]` paired with `[0,4]` under modulus four/residue zero emits sums `0,4,4,8`. A caller checking exact equality must still check actual sums. Existing unfiltered APIs and their semantics are unchanged.

Closing a generator yields a prefix, not a negative decision. Randomized donor decision guarantees and donor space/time exponents are outside this contract. If a target requires witnesses, occurrence counts, different ordering or modular keys, define and validate those requirements separately.

## Optimization

1. Snapshot integer inputs and sort the second array with its original indices.
2. Heap-merge one sorted pair-sum row per first-array item. Retain one current occurrence per row instead of the full Cartesian product.
3. Merge two pair streams by sum key. Buffer up to `K` occurrences from a matching right group; `K` is the tie-buffer capacity, distinct from the problem's resource budget `B`.
4. When a right tie exceeds `K`, snapshot its suffix and replay that suffix for every matching left occurrence. Never truncate the group.
5. Advance the authoritative right stream beyond the suffix before continuing. Charge this extra scan and all heap-state copies to total work.

For stored inputs/stream state of size `S`, working storage is `O(S+K)` items, excluding consumer-retained output. Integer bit lengths determine bytes per item. A join with `Z` matching occurrence pairs must still emit `Z` outputs. Oversized-tie snapshot/copy work can be charged to `O(SZ/K)` because each such left occurrence has more than `K` partners; heap advances and an extra authoritative scan also cost time. This is a storage tradeoff, not reduced result cardinality or free regeneration.

The reference keeps the caller's first-array orientation. A target may orient rows toward the smaller input to reduce heap state only if it restores the required index/order semantics.

### Generate eligible residue pairs directly

`FilteredPairSums(first, second, *, modulus, residue)` groups second-array occurrences by observed residues and sorts each bucket by `(value, original index)`. Each first-array row selects the bucket with residue `(residue-first_value) % modulus`. For fixed first value, traversing that bucket in value/index order gives increasing actual sums; merging eligible rows with the usual heap gives the exact filtered subsequence in the original pair order. No rejected pair enters the heap. This adapts the donor's residue-slice mechanism but retains actual-sum order instead of its modular direct/complementary-key order.

Let input lengths be `n,m`, eligible output count `E`, and nonempty eligible row count `h <= n`. Construction charges residue calculations, snapshots, bucket sorting and heap initialization. The comparison-count bound is `O(n+m+sum_r m_r log(m_r+1))`; full enumeration takes `O(E log(h+1))` heap comparisons and must emit all `E` indexed results. Python arithmetic/hash costs depend on integer bit length. Storage and clone costs remain linear in the retained input/row state and current heap; clones copy `O(h)` heap entries and share immutable tuples. Temporary bucket construction can increase peak bytes even when far fewer pairs are generated.

Filtering is admissible only when the requested output really is this residue subset, or the residue condition is independently proved necessary for a downstream query. It cannot be applied to an unfiltered enumeration contract. Processing buckets separately also does not preserve global sum order automatically.

## Before / after evidence

### Pair enumeration

- Environment: the Python/runtime/platform identity is recorded in [raw local evidence](../examples/evidence/pair-stream-reference.json), alongside SHA-256 identities for the example and measurement script.
- Workload/fixture: two arrays of 128 integers, producing 16,384 indexed pair sums, consumed by the same ordered hashing sink without retaining output.
- Cold baseline: snapshot-free materialization and sorting of the full pair product, including initialization and sink work in each sample.
- Warm/no-op baseline where relevant: no cache or warm-result reuse; garbage collection precedes each isolated allocation sample.
- Small invalidation / partial-work case where relevant: interrupted joins are tested for prefix correctness, not benchmarked here.
- Large invalidation / full-work case where relevant: every measured pair stream is fully exhausted.
- Optimized: heap-based pair enumeration under the same ordered output digest and count.
- Speedup / memory / I/O / quality change: consult the raw samples and medians; this pair-only fixture demonstrates lower traced allocation peak. It establishes no join performance, RSS, practical donor algorithm or portable speedup claim.
- Variance / repetitions / raw samples: five samples per path, alternating which runs first; `tracemalloc` is enabled during timing, so these timings are instrumented observations without a promotion threshold.

### Full equal-sum joins

The [full-join characterization](../examples/evidence/pair-join-characterization.md) records 350 samples across seven synthetic fixtures, a materialized sorted-merge baseline, four buffer capacities, five repetitions and two separate measurement modes. Each default fixture has 256 indexed pairs per side; output cardinality ranges from one match to 65,536. Fixtures cover sparse matches, unique keys, oversized duplicate groups, mixed ties, both asymmetric row orientations, and signed large integers.

Both paths consume the entire join through the same non-retaining count and ordered hashing sink. Timing runs with `tracemalloc` disabled; allocation peaks come from separate traced runs without recorded elapsed time. Initialization, sorting, input snapshots, replay copies and consumption are included. Input construction, independent match-count preflight and garbage collection before each sample are excluded. Variant order rotates across repetitions. Exact counts and ordered digests must agree in every sample; changing source bytes during the run also prevents evidence emission.

The raw samples show workload-dependent allocation/latency tradeoffs, including slower streaming paths and weaker allocation savings for asymmetric inputs. Larger buffers can reduce replay latency while increasing retained storage. These observations do not select a portable capacity or establish a target-application benefit, RSS limit or donor resource theorem. Input tuples are built before measurement for both paths; algorithm-created storage is included. Consumers that accumulate results must include that storage in their own measurements.

### Residue-filtered pair enumeration

The [modular characterization](../examples/evidence/modular-pair-stream-characterization.md) compares exhaustive `PairSums` enumeration followed by the residue predicate with direct eligible-pair generation. Nine fixtures each have 4,096 unfiltered indexed pairs; eligible counts range from zero to 4,096. All 180 samples match a direct two-loop sorted oracle and an independent residue-frequency count. Timing and traced allocation are measured separately; initialization, bucketing/sorting and the common non-retaining sink are charged. Raw source/input identities, repetitions, execution order and environment are retained.

Sparse balanced fixtures in this local run have much lower elapsed time but roughly twice the traced allocation peak because of bucket construction. Modulus one and all-eligible ties show no established latency advantage. Asymmetric wide rows show a different memory/latency tradeoff. No portable modulus, crossover threshold, join/solver benefit, or target-application speedup is claimed.

## Validation

Run `python3 -m unittest discover -s tests -p test_bounded_pair_streams.py -v`. The independent oracle directly enumerates and sorts all indexed occurrences without using heap/replay code. Tests cover small exhaustive domains, capacities below/at/above tie size, all-equal values, signed and 80-digit integers, empty arrays, immutable input snapshots, independent lookahead-preserving clones, rejection of floats/bools and interrupted prefixes followed by fresh complete runs. `PairSums` snapshots on construction; the join generator snapshots on its first advance and remains isolated from later caller mutations.

Replay measurements with `python3 scripts/benchmark_pair_streams.py --size 128 --repeats 5`. Every sample must match the baseline's ordered digest and exact occurrence count before JSON is emitted. The test suite runs through the existing CI unittest discovery; `python3 scripts/check_catalog.py` checks catalog integration.

Run `python3 -m unittest discover -s tests -p test_pair_join_benchmark.py -v` for the full-join baseline and measurement contracts. Its independent four-loop oracle covers small exhaustive inputs and all fixture shapes; fault injection checks parity rejection, source-change rejection, tracer isolation/cleanup and work-limit admission before fixture allocation. Replay full-join measurements with `python3 scripts/benchmark_pair_joins.py --size 16 --repeats 5 --capacities 1,8,64,256 --max-pairs 4096 --max-matches 1000000`. Pair/match limits bound admitted fixture work; they are not hard byte or deadline enforcement.

Run `python3 -m unittest discover -s tests -p 'test_modular_pair*.py' -v` for filtered streams and their measurement procedure. Independent exhaustive/seeded oracles cover signed values, large integers, duplicate identities, empty/no-match rows, composite and huge moduli, normalized residues, lookahead-aware clone independence, immutable snapshots and interrupted prefixes. Heap instrumentation verifies that exactly the eligible occurrences are inserted; residue collisions retain differing actual sums. Invalid bool/float/string domains are rejected even when the other input is empty. Replay measurements with `python3 scripts/benchmark_modular_pair_streams.py --size 64 --repeats 5 --max-pairs 16384`. Fixture pair limits apply before array construction; they do not enforce bytes or deadlines.

## Target-repo adaptation

Choose capacity from measured input/heap size, tie-size distribution, replay cost and the target memory envelope. Include integer bit growth, input snapshots, concurrently live replay state, output retention and downstream consumer work. Profile smaller-row orientation only after preserving the original order/identity contract. Do not copy donor bit splits, prime moduli, Subset Sum exponents, random-success guarantees or this fixture's buffer/array dimensions as defaults.

## Failure modes

- Deduplicating equal values loses indexed multiplicity or witnesses.
- Truncating a tie loses valid Cartesian matches.
- Mutable shared inputs or incomplete lookahead snapshots corrupt replay.
- Small buffers make snapshot/replay costs dominate; large buffers erase memory savings.
- Consumers materialize all output and restore the original memory bottleneck.
- Fixed-width arithmetic overflows, or word-count bounds hide growing integer byte sizes.
- Output cardinality is enormous despite bounded working state.
- A cancelled prefix is misreported as an exhaustive negative result.
- Pair-only measurements are misrepresented as join or target speedups.
- Congruence is mistaken for exact equality, or modular buckets are concatenated while claiming original global ordering.
- Bucket construction and residue arithmetic cost more than the rejected enumeration they avoid.

## Rollback trigger

Disable/revert the adapted path on any oracle/order/multiplicity mismatch, unstable replay input, exceeded target resource ceiling, or repeated controlled measurements failing the predeclared memory/latency tradeoff. Cancellation must remain explicitly incomplete. Restore the exact materialized/reference path only when it fits the target budget; otherwise report inability to complete rather than fabricating a result.

## Composition notes

`OPT-REDUCE-001` can reduce inputs before enumeration if the filter is independently sound. `OPT-PRUNE-001` can discard regions only with its own valid bounds; streaming alone authorizes no pruning. `OPT-FAN-001` chooses storage for reuse, while this pattern chooses regeneration to save storage: measure their combined lifecycle costs. Parallelization multiplies input/heap/buffer state and must preserve exact order under `OPT-PAR-001`.
