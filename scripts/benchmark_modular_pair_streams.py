#!/usr/bin/env python3
"""Compare eligible-pair generation with exhaustive pair streaming then filtering.

Timing and allocation runs are separate. JSON is emitted only after all
counts and ordered digests agree with a direct two-loop oracle.
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
from examples.bounded_pair_streams import Pair, PairSums  # noqa: E402
from examples.modular_pair_streams import FilteredPairSums  # noqa: E402


def exhaustive_then_filter(first, second, modulus, residue):
    target = residue % modulus
    return (item for item in PairSums(first, second) if item.key % modulus == target)


def direct_oracle(first, second, modulus, residue):
    return sorted(Pair(a + b, i, j) for i, a in enumerate(first)
                  for j, b in enumerate(second) if (a + b) % modulus == residue % modulus)


def consume(items):
    digest = hashlib.sha256()
    count = 0
    for item in items:
        digest.update(f"{item.key},{item.left},{item.right}\n".encode("ascii"))
        count += 1
    return {"count": count, "ordered_sha256": digest.hexdigest()}


def positive(value):
    if type(value) is not int or value < 1:
        raise ValueError("size, repeats and pair limit must be positive integers")
    return value


def fixtures(size):
    regular = tuple(range(size))
    reverse = tuple(reversed(regular))
    product = tuple(range(size * size))
    big = tuple((i - size // 2) * 10**80 for i in range(size))
    return [
        ("dense_modulus_one", regular, reverse, 1, 0),
        ("half_eligible", regular, reverse, 2, 1),
        ("sparse_prime", regular, reverse, 67, 3),
        ("sparse_composite", regular, reverse, 64, -1),
        ("all_eligible_tie", (0,) * size, (0,) * size, 64, 0),
        ("no_eligible_pairs", (0,) * size, (0,) * size, 64, 1),
        ("asymmetric_thin_rows", (0,), product, 64, -1),
        ("asymmetric_wide_rows", product, (0,), 64, -1),
        ("signed_big_integers", big, reverse, 67, -5),
    ]


def plan_fixtures(size, max_pairs):
    positive(size)
    positive(max_pairs)
    # Every constructed fixture has size**2 pairs; reject before building arrays.
    if size * size > max_pairs:
        raise ValueError("fixture exceeds the predeclared pair work limit")
    plan = []
    for name, first, second, modulus, residue in fixtures(size):
        target = residue % modulus
        left = Counter(a % modulus for a in first)
        right = Counter(b % modulus for b in second)
        eligible = sum(amount * right.get((target - key) % modulus, 0)
                       for key, amount in left.items())
        identity = [first, second, modulus, residue]
        plan.append({"name": name, "first": first, "second": second,
                     "modulus": modulus, "supplied_residue": residue,
                     "normalized_residue": target, "total_pairs": len(first) * len(second),
                     "expected_eligible_pairs": eligible,
                     "input_sha256": hashlib.sha256(json.dumps(
                         identity, separators=(",", ":")).encode("ascii")).hexdigest()})
    return plan


def measure(factory, mode):
    if mode not in ("timing", "allocation"):
        raise ValueError("unknown measurement mode")
    if tracemalloc.is_tracing():
        raise RuntimeError("measurement requires an inactive allocation tracer")
    gc.collect()
    if mode == "timing":
        start = time.perf_counter_ns()
        result = consume(factory())
        result["elapsed_ns"] = time.perf_counter_ns() - start
    else:
        tracemalloc.start()
        try:
            result = consume(factory())
            _current, result["peak_traced_bytes"] = tracemalloc.get_traced_memory()
        finally:
            tracemalloc.stop()
    return result


def verify_result(result, reference):
    if any(result[key] != reference[key] for key in ("count", "ordered_sha256")):
        raise RuntimeError("reference parity failed; no benchmark evidence emitted")


def source_fingerprints():
    root = Path(__file__).resolve().parents[1]
    return {path: hashlib.sha256((root / path).read_bytes()).hexdigest()
            for path in ("examples/bounded_pair_streams.py", "examples/modular_pair_streams.py",
                         "scripts/benchmark_modular_pair_streams.py")}


def run_benchmark(size=64, repeats=5, max_pairs=16384, progress=False):
    positive(repeats)
    sources = source_fingerprints()
    plan = plan_fixtures(size, max_pairs)
    cases = []
    for case_index, fixture in enumerate(plan):
        first, second = fixture["first"], fixture["second"]
        modulus, residue = fixture["modulus"], fixture["supplied_residue"]
        reference = consume(direct_oracle(first, second, modulus, residue))
        if reference["count"] != fixture["expected_eligible_pairs"]:
            raise RuntimeError("direct oracle disagrees with independent residue-frequency count")
        factories = [
            ("exhaustive_then_filter", lambda: exhaustive_then_filter(first, second, modulus, residue)),
            ("residue_filtered", lambda: FilteredPairSums(first, second,
                                                        modulus=modulus, residue=residue)),
        ]
        variants = {name: {"timing_samples": [], "allocation_samples": []}
                    for name, _factory in factories}
        for mode in ("timing", "allocation"):
            for repeat in range(repeats):
                offset = (case_index + repeat) % len(factories)
                order = factories[offset:] + factories[:offset]
                for position, (name, factory) in enumerate(order):
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
            print(f"completed {fixture['name']}: eligible={reference['count']}", file=sys.stderr)
    if source_fingerprints() != sources:
        raise RuntimeError("source files changed during measurement; no benchmark evidence emitted")
    return {
        "schema": "opt.modular-pair-stream-reference-benchmark.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": sources,
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "machine": platform.machine(), "processor": platform.processor()},
        "procedure": {"size": size, "repeats_per_mode": repeats,
                      "max_pairs_per_fixture": max_pairs, "total_samples": len(plan) * 2 * repeats * 2,
                      "order": "rotate variants by (fixture index + repeat) modulo variant count",
                      "timing": "perf_counter_ns; tracemalloc disabled",
                      "allocation": "separate isolated tracemalloc peak; no elapsed time; not RSS",
                      "included": "initialization, snapshots, sorting/bucketing, full eligible enumeration, hashing sink",
                      "excluded": "fixture/preflight/oracle construction, prebuilt inputs, GC before each sample",
                      "sink": "same non-retaining ASCII ordered hash and exact count",
                      "budget_scope": "pair-work admission before construction; no hard byte/deadline cap"},
        "cases": cases,
        "claim_boundary": "local synthetic filtered pair enumeration; no join, solver, portable modulus or target speedup",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=int, default=64)
    parser.add_argument("--repeats", type=int, default=5)
    parser.add_argument("--max-pairs", type=int, default=16384)
    args = parser.parse_args()
    try:
        result = run_benchmark(args.size, args.repeats, args.max_pairs, progress=True)
    except (ValueError, RuntimeError) as error:
        parser.error(str(error))
    print(json.dumps(result, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
