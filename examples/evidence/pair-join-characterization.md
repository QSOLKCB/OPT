# Full equal-sum join characterization

This is a local synthetic characterization of [OPT-STREAM-001](../../optimizations/OPT-STREAM-001-bounded-replayable-pair-streams.md), not a target-application speedup or a capacity recommendation. The [raw JSON](pair-join-reference.json) contains every input, source SHA-256, environment identity, ordered digest and sample. The original [pair-only evidence](pair-stream-reference.json) remains separate; its instrumented timings should not be compared with these uninstrumented join timings.

## Procedure

```sh
python3 scripts/benchmark_pair_joins.py --size 16 --repeats 5 --capacities 1,8,64,256 --max-pairs 4096 --max-matches 1000000
```

The runner compares an independent materialized sorted-merge baseline with the existing streamed join. Both emit full indexed Cartesian ties in the same order to the same non-retaining hashing/count sink. Every sample must match the baseline's count and ordered digest. An independent sum-frequency preflight verifies the baseline's count; small exhaustive four-loop oracle tests verify ordering and multiplicity. Source hashes are captured before measurement and checked again before evidence emission.

There are seven deterministic fixtures, five variants, five repetitions per mode, and two modes: 350 measured samples. Timing uses `perf_counter_ns` with allocation tracing disabled. Allocation uses a separate isolated `tracemalloc` peak with no elapsed time recorded. Variant order rotates by fixture index plus repetition. Algorithm initialization, sorting, snapshots, replay, full enumeration and sink work are included. Prebuilt input tuples, fixture construction, oracle/preflight work and garbage collection before each sample are excluded equally. Pair/match admission limits apply before fixture construction; they are not hard byte or deadline caps.

Run environment: Python 3.12.14, x86_64, Linux 6.18.44, glibc 2.39. The exact runtime string and UTC timestamp are in the raw JSON. These are five observational repetitions in a shared environment, without confidence intervals or a promotion threshold. The sink is part of end-to-end time and can dominate high-output cases; traced Python allocations are not process RSS or consumer-retained output.

## Observations

All fixtures have 256 indexed pairs per side. The table reports baseline medians; KiB means 1,024 bytes.

| Fixture | Full matches | Largest right tie | Baseline time (ms) | Baseline traced peak (KiB) |
|---|---:|---:|---:|---:|
| `few_matches` | 1 | 16 | 0.532 | 49.70 |
| `unique_matches` | 256 | 1 | 0.447 | 50.57 |
| `duplicate_tie` | 65,536 | 256 | 27.573 | 49.70 |
| `mixed_ties` | 18,048 | 88 | 8.050 | 49.70 |
| `asymmetric_thin_rows` | 256 | 1 | 0.423 | 49.70 |
| `asymmetric_wide_rows` | 256 | 1 | 0.469 | 49.70 |
| `signed_big_integers` | 256 | 1 | 0.629 | 78.74 |

### Elapsed-time ratio

Each cell is the streamed median divided by the materialized median. Below 1 is lower; above 1 is higher.

| Fixture | K=1 | K=8 | K=64 | K=256 |
|---|---:|---:|---:|---:|
| `few_matches` | 0.67 | 0.65 | 0.63 | 0.66 |
| `unique_matches` | 2.60 | 2.68 | 2.69 | 2.63 |
| `duplicate_tie` | 3.39 | 3.38 | 2.80 | 1.01 |
| `mixed_ties` | 3.22 | 3.05 | 1.42 | 1.02 |
| `asymmetric_thin_rows` | 2.56 | 2.71 | 2.71 | 2.77 |
| `asymmetric_wide_rows` | 2.44 | 2.62 | 2.64 | 2.68 |
| `signed_big_integers` | 2.01 | 2.09 | 2.09 | 2.19 |

### Traced-peak allocation ratio

Each cell is the streamed median divided by the materialized median. Below 1 is lower; above 1 is higher.

| Fixture | K=1 | K=8 | K=64 | K=256 |
|---|---:|---:|---:|---:|
| `few_matches` | 0.13 | 0.13 | 0.13 | 0.13 |
| `unique_matches` | 0.13 | 0.13 | 0.13 | 0.13 |
| `duplicate_tie` | 0.15 | 0.16 | 0.26 | 0.61 |
| `mixed_ties` | 0.19 | 0.20 | 0.28 | 0.30 |
| `asymmetric_thin_rows` | 0.71 | 0.71 | 0.71 | 0.71 |
| `asymmetric_wide_rows` | 0.85 | 0.85 | 0.85 | 0.85 |
| `signed_big_integers` | 0.11 | 0.11 | 0.11 | 0.11 |

For the all-equal fixture, K=1 retains about 0.15 of the baseline allocation peak but takes about 3.39 times as long. K=256 fits the whole right tie, raising the peak to about 0.61 of baseline while bringing elapsed time to about 1.01 of baseline. Mixed ties show the same general replay/storage tradeoff. These near-baseline timing ratios are observations, not proof of equal performance.

Sparse matches stop after exhausting the matching opportunity and are faster in this run; the baseline still constructs both full pair lists. Unique-match joins are slower through the streamed path despite lower allocation. Asymmetric fixtures expose input-storage and row-orientation costs: the wide-row orientation retains more traced allocation than the thin-row orientation, and both save much less than the balanced fixtures. The implementation preserves caller orientation; changing it requires restoring the original index/order contract.

Capacity affects tie replay, so a capacity sweep does not imply improvements on fixtures whose ties already fit K=1. Integer bit lengths, heap shape, output cardinality and consumer work all remain part of the tradeoff. No universal buffer default, asymptotic donor theorem or automatic path-promotion policy follows from these samples.

## Validation

```sh
python3 -m unittest discover -s tests -p test_pair_join_benchmark.py -v
```

Tests compare the independent merge baseline and streamed fixtures against a direct four-loop oracle, and reject count/digest corruption, changed source identities, active allocation tracing and oversized fixture plans. Allocation tracing is stopped even if consumption raises. The full existing test suite and catalog/formal-source checks run in repository CI; this characterization changes no Lean formalization or streaming algorithm.
