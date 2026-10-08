# Residue-filtered pair-stream characterization

This records a local comparison for [OPT-STREAM-001](../../optimizations/OPT-STREAM-001-bounded-replayable-pair-streams.md). The [raw JSON](modular-pair-stream-reference.json) retains inputs, normalized/supplied residues, source/input SHA-256 identities, environment, execution order and every sample. It measures filtered pair enumeration only; previous [pair-only](pair-stream-reference.json) and [full-join](pair-join-reference.json) evidence remain separate.

## Contract and mechanism

The requested output is every original indexed pair for which `(a+b) % modulus == residue % modulus`, sorted by `(actual sum, left index, right index)`. Duplicate values retain their distinct occurrences. A positive exact-integer modulus is required, including composite moduli and one. Residues may be signed and are normalized. Both inputs are snapshotted on construction.

The baseline fully enumerates the existing heap stream and applies the predicate afterwards. The new `FilteredPairSums` groups second-array occurrences by observed residues, sorts each bucket by value/index, and traverses only the complementary bucket for each first-array row. Rejected pairs never enter its heap. No table proportional to the modulus is allocated. Replay clones share immutable input/row tuples and copy their own next-occurrence heap.

Congruence is not exact equality: sums `0,4,4,8` all pass modulus four/residue zero. This API does not change the existing exact equal-sum join or implement a Subset Sum solver. A cancelled prefix remains incomplete.

## Procedure

```sh
python3 scripts/benchmark_modular_pair_streams.py --size 64 --repeats 5 --max-pairs 16384
```

Nine deterministic fixtures each have 4,096 unfiltered indexed pairs, with eligibility ranging from zero to all pairs. Two paths, five repetitions per mode and two modes produce 180 samples. Each sample must match a direct two-loop sorted oracle's ordered SHA-256 and count; an independent residue-frequency calculation checks the oracle count. Source fingerprints are recorded before measurement and checked again before emission.

Timing uses `perf_counter_ns` with allocation tracing disabled. Allocation uses a separate isolated `tracemalloc` peak with no elapsed time recorded. Variant order alternates by fixture index plus repetition; with five repetitions each path runs first either twice or three times. Initialization, input snapshots, sorting/bucketing, full enumeration/filtering and the identical non-retaining hash/count sink are included. Prebuilt input tuples, fixture/preflight/oracle construction and garbage collection before each sample are excluded equally. Pair limits reject oversized fixtures before array construction; they are not byte or deadline limits.

The environment is Python 3.12.14 on x86_64 Linux 6.18.44 with glibc 2.39; exact strings and UTC timestamp are retained in JSON. These are observational medians from five repetitions in a shared environment, with no confidence interval, performance threshold or automatic promotion policy. Traced Python allocation is not process RSS, retained consumer output or an application memory ceiling. Python integer arithmetic and hashing have bit-dependent costs.

## Observations

The ratios divide the filtered median by the exhaustive-then-filter median. Below one means lower elapsed time or lower traced peak. KiB means 1,024 bytes.

| Fixture | Modulus / normalized residue | Eligible pairs | Baseline time (ms) | Filtered time (ms) | Time ratio | Baseline peak (KiB) | Filtered peak (KiB) | Peak ratio |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| `dense_modulus_one` | 1 / 0 | 4,096 | 4.281 | 4.588 | 1.07 | 10.63 | 11.55 | 1.09 |
| `half_eligible` | 2 / 1 | 2,048 | 4.921 | 2.384 | 0.48 | 10.54 | 11.56 | 1.10 |
| `sparse_prime` | 67 / 3 | 61 | 2.688 | 0.114 | 0.04 | 10.44 | 22.59 | 2.16 |
| `sparse_composite` | 64 / 63 | 64 | 2.678 | 0.097 | 0.04 | 10.44 | 22.80 | 2.18 |
| `all_eligible_tie` | 64 / 0 | 4,096 | 4.543 | 4.567 | 1.01 | 10.47 | 11.41 | 1.09 |
| `no_eligible_pairs` | 64 / 1 | 0 | 2.689 | 0.036 | 0.01 | 10.35 | 6.75 | 0.65 |
| `asymmetric_thin_rows` | 64 / 63 | 64 | 2.765 | 0.742 | 0.27 | 393.77 | 404.68 | 1.03 |
| `asymmetric_wide_rows` | 64 / 63 | 64 | 5.477 | 0.591 | 0.11 | 546.67 | 42.02 | 0.08 |
| `signed_big_integers` | 67 / 62 | 61 | 3.231 | 0.138 | 0.04 | 14.58 | 26.33 | 1.81 |

Sparse balanced prime/composite fixtures complete in about 0.04 of baseline elapsed time, but their traced peaks rise to about 2.2 times baseline. The implementation temporarily retains bucket lists and sorted bucket tuples together during initialization; fewer heap occurrences do not imply lower peak bytes. The signed large-integer fixture also shows this tradeoff.

Modulus one and the all-eligible duplicate fixture have no established latency advantage; their traced peaks are higher. The no-eligible fixture skips heap enumeration entirely after construction. Asymmetric thin rows still pay second-array bucketing/sorting; asymmetric wide rows greatly shrink the active heap, but retain a row-reference tuple for the whole first input. Orientation remains unchanged because original index/order semantics are observable.

The baseline must advance through every unfiltered pair to decide eligibility, while the filtered path enumerates only the required subsequence. This is a gain for the filtered-output contract, not permission to drop outputs from an unfiltered contract. No portable modulus choice, crossover threshold, donor asymptotic bound, join/solver benefit or target-application speedup follows from these measurements. Re-profile density, row shape, integer bit length, setup/replay costs and output consumers together.

## Validation

```sh
python3 -m unittest discover -s tests -p 'test_modular_pair*.py' -v
```

Nine stream tests cover exhaustive small inputs, signed/large integers, negative normalized residues, composite/huge moduli, duplicate identities, no-match/empty rows, snapshots, lookahead-aware clone independence, interrupted prefixes and invalid domains. Heap instrumentation independently checks that exactly the oracle's eligible occurrences are inserted. Five measurement tests check fixture parity, independent counts, timing/tracing separation, raw medians/order, cleanup on failure, source-change/parity rejection and pair-limit admission before fixture construction. These checks and measurements are not universal formal proofs; no donor proof is imported or replayed.
