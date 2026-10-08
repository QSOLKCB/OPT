#!/usr/bin/env python3
"""Characterize exact full joins; timing and traced allocations are separate.

JSON is emitted only after every sample matches the reference order and count.
Fixtures, preflight/oracle work and prebuilt inputs are excluded equally. Each
sample includes algorithm initialization, full enumeration and a hashing sink.
"""

from __future__ import annotations

import argparse
from collections import Counter
from datetime import datetime, timezone
import gc
import hashlib
import json
from pathlib import Path
import platform
import statistics
import sys
import time
import tracemalloc

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from examples.bounded_pair_streams import Pair, join_equal_sums  # noqa: E402


def materialized_join(first, second, third, fourth):
    """Sorted pair lists and an indexed merge; output is never accumulated."""
    left = sorted(Pair(a + b, i, j) for i, a in enumerate(first)
                  for j, b in enumerate(second))
    right = sorted(Pair(c + d, k, l) for k, c in enumerate(third)
                   for l, d in enumerate(fourth))
    i = j = 0
    while i < len(left) and j < len(right):
        if left[i].key < right[j].key:
            i += 1
        elif right[j].key < left[i].key:
            j += 1
        else:
            key = left[i].key
            end_i, end_j = i, j
            while end_i < len(left) and left[end_i].key == key:
                end_i += 1
            while end_j < len(right) and right[end_j].key == key:
                end_j += 1
            for p in range(i, end_i):
                for q in range(j, end_j):
                    yield left[p], right[q]
            i, j = end_i, end_j


def consume(items):
    digest = hashlib.sha256()
    count = 0
    for left, right in items:
        digest.update(f"{left.key},{left.left},{left.right}|"
                      f"{right.key},{right.left},{right.right}\n".encode("ascii"))
        count += 1
    return {"count": count, "ordered_sha256": digest.hexdigest()}


def positive(value):
    if type(value) is not int or value < 1:
        raise ValueError("sizes, repeats, capacities and work limits must be positive integers")
    return value


def fixtures(size):
    regular = tuple(range(size))
    spaced = tuple(i * (size + 1) for i in range(size))
    product = tuple(range(size * size))
    big = tuple((i - size // 2) * 10**80 for i in range(size))
    return [
        ("few_matches", (regular, regular,
                         tuple(range(2 * size - 2, 3 * size - 2)), regular)),
        ("unique_matches", (spaced, regular, spaced, regular)),
        ("duplicate_tie", ((0,) * size,) * 4),
        ("mixed_ties", (tuple(i % 2 for i in range(size)),
                        tuple(i % 3 for i in range(size))) * 2),
        ("asymmetric_thin_rows", ((0,), product, (0,), product)),
        ("asymmetric_wide_rows", (product, (0,), product, (0,))),
        ("signed_big_integers", (big, regular, big, tuple(reversed(regular)))),
    ]


def plan_fixtures(size, max_pairs, max_matches):
    positive(size)
    positive(max_pairs)
    positive(max_matches)
    # Check known construction sizes before allocating any fixture arrays.
    if size * size > max_pairs or size ** 4 > max_matches:
        raise ValueError("fixture exceeds the predeclared pair or match work limit")
    plan = []
    for name, arrays in fixtures(size):
        a, b, c, d = arrays
        left = Counter(x + y for x in a for y in b)
        right = Counter(x + y for x in c for y in d)
        count = sum(amount * right.get(key, 0) for key, amount in left.items())
        plan.append({"name": name, "inputs": arrays,
                     "input_sha256": hashlib.sha256(json.dumps(
                         arrays, separators=(",", ":")).encode("ascii")).hexdigest(),
                     "left_pairs": len(a) * len(b), "right_pairs": len(c) * len(d),
                     "max_right_tie": max(right.values(), default=0),
                     "expected_matches": count})
    return plan


def measure(factory, mode):
    if mode not in ("timing", "allocation"):
        raise ValueError("unknown measurement mode")
    if tracemalloc.is_tracing():
        raise RuntimeError("measurement requires an inactive allocation tracer")
    gc.collect()
    if mode == "timing":
        started = time.perf_counter_ns()
        result = consume(factory())
        result["elapsed_ns"] = time.perf_counter_ns() - started
    else:
        tracemalloc.start()
        try:
            result = consume(factory())
            _current, result["peak_traced_bytes"] = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    return result


def verify_result(result, expected):
    if any(result[key] != expected[key] for key in ("count", "ordered_sha256")):
        raise RuntimeError("reference parity failed; no benchmark evidence emitted")


def source_fingerprints():
    root = Path(__file__).resolve().parents[1]
    return {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
            for path in ("examples/bounded_pair_streams.py", "scripts/benchmark_pair_joins.py")}


def run_benchmark(size=16, repeats=5, capacities=(1, 8, 64, 256),
                  max_pairs=4096, max_matches=1_000_000, progress=False):
    sources = source_fingerprints()
    positive(repeats)
    capacities = tuple(capacities)
    if not capacities or len(set(capacities)) != len(capacities):
        raise ValueError("capacities must be nonempty and unique")
    for capacity in capacities:
        positive(capacity)
    plan = plan_fixtures(size, max_pairs, max_matches)
    cases = []
    for case_index, fixture in enumerate(plan):
        arrays = fixture["inputs"]
        reference = consume(materialized_join(*arrays))
        if reference["count"] != fixture["expected_matches"]:
            raise RuntimeError("materialized reference disagrees with independent match count")
        factories = [("materialized", None, lambda: materialized_join(*arrays))]
        factories.extend((f"streamed_k{capacity}", capacity,
                          lambda capacity=capacity: join_equal_sums(
                              *arrays, buffer_capacity=capacity)) for capacity in capacities)
        variants = {name: {"buffer_capacity": capacity, "timing_samples": [],
                           "allocation_samples": []} for name, capacity, _factory in factories}
        for mode in ("timing", "allocation"):
            for repeat in range(repeats):
                offset = (case_index + repeat) % len(factories)
                order = factories[offset:] + factories[:offset]
                for position, (name, _capacity, factory) in enumerate(order):
                    result = measure(factory, mode)
                    verify_result(result, reference)
                    result.update({"repeat": repeat, "order_position": position})
                    variants[name][mode + "_samples"].append(result)
        for variant in variants.values():
            variant["summary"] = {
                "median_elapsed_ns": statistics.median(
                    row["elapsed_ns"] for row in variant["timing_samples"]),
                "median_peak_traced_bytes": statistics.median(
                    row["peak_traced_bytes"] for row in variant["allocation_samples"])}
        cases.append({**fixture, "reference": reference, "variants": variants})
        if progress:
            print(f"completed {fixture['name']}: matches={reference['count']}", file=sys.stderr)
    if source_fingerprints() != sources:
        raise RuntimeError("source files changed during measurement; no benchmark evidence emitted")
    return {
        "schema": "opt.pair-join-reference-benchmark.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": sources,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "machine": platform.machine(), "processor": platform.processor()},
        "procedure": {"size": size, "repeats_per_mode": repeats,
                      "capacities": capacities, "max_pairs_per_stream": max_pairs,
                      "max_matches_per_fixture": max_matches,
                      "total_samples": len(plan) * (len(capacities) + 1) * repeats * 2,
                      "order": "rotate variants by (fixture index + repeat) modulo variant count",
                      "timing": "perf_counter_ns; tracemalloc disabled",
                      "allocation": "separate isolated tracemalloc peak; no elapsed time recorded; not RSS",
                      "included": "algorithm initialization, sorting, heap copies, replay, full join, ordered hashing sink",
                      "excluded": "fixture/preflight/oracle construction, prebuilt inputs, GC before each sample",
                      "sink": "no output retention; same ASCII ordered hash and count for all paths",
                      "budget_scope": "per-fixture pair/match work admission limits; no hard byte/deadline cap"},
        "cases": cases,
        "claim_boundary": "local synthetic joins; observational ratios, no portable buffer default or application speedup",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=16)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--capacities", default="1,8,64,256")
    parser.add_argument("--max-pairs", type=int, default=4096)
    parser.add_argument("--max-matches", type=int, default=1_000_000)
    args = parser.parse_args()
    try:
        capacities = tuple(int(part) for part in args.capacities.split(","))
        result = run_benchmark(args.size, args.repeats, capacities,
                               args.max_pairs, args.max_matches, progress=True)
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
