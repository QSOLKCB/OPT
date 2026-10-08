#!/usr/bin/env python3
"""Compare materialized and streamed pair sums with a non-retaining sink.

Writes JSON to stdout. Measurements cover Python traced allocations, not RSS.
The join mechanism has separate correctness tests and is not timed here.
"""

from __future__ import annotations

import argparse
import gc
import hashlib
import json
import platform
import statistics
import sys
import time
import tracemalloc
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from examples.bounded_pair_streams import Pair, PairSums  # noqa: E402


def positive_integer(value: str) -> int:
    result = int(value)
    if result < 1:
        raise argparse.ArgumentTypeError("must be positive")
    return result


def consume(items):
    digest = hashlib.sha256()
    count = 0
    for item in items:
        digest.update(f"{item.key},{item.left},{item.right}\n".encode("ascii"))
        count += 1
    return count, digest.hexdigest()


def measure(first, second, streaming):
    gc.collect()
    tracemalloc.start()
    try:
        started = time.perf_counter_ns()
        if streaming:
            items = PairSums(first, second)
        else:
            items = sorted(Pair(a + b, i, j) for i, a in enumerate(first)
                           for j, b in enumerate(second))
        count, digest = consume(items)
        elapsed = time.perf_counter_ns() - started
        _current, peak = tracemalloc.get_traced_memory()
    finally:
        tracemalloc.stop()
    return {"elapsed_ns": elapsed, "peak_traced_bytes": peak,
            "count": count, "ordered_sha256": digest}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--size", type=positive_integer, default=128)
    parser.add_argument("--repeats", type=positive_integer, default=5)
    args = parser.parse_args()
    # Prebuilt input tuples are excluded equally; each mechanism's own
    # initialization, enumeration and hashing sink are included in measurement.
    first = tuple(range(args.size))
    second = tuple(reversed(range(-args.size, 0)))
    samples = {"materialized": [], "streamed": []}
    for repeat in range(args.repeats):
        for streaming in ((False, True) if repeat % 2 == 0 else (True, False)):
            samples["streamed" if streaming else "materialized"].append(
                measure(first, second, streaming))
    results = [row for rows in samples.values() for row in rows]
    if {row["count"] for row in results} != {args.size ** 2} or len(
            {row["ordered_sha256"] for row in results}) != 1:
        raise SystemExit("reference parity failed; no benchmark promoted")
    summary = {name: {"median_elapsed_ns": statistics.median(
                         row["elapsed_ns"] for row in rows),
                      "median_peak_traced_bytes": statistics.median(
                         row["peak_traced_bytes"] for row in rows)}
               for name, rows in samples.items()}
    print(json.dumps({
        "schema": "opt.pair-stream-reference-benchmark.v1",
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "source_sha256": {path: hashlib.sha256(
            (Path(__file__).resolve().parents[1] / path).read_bytes()).hexdigest()
            for path in ("examples/bounded_pair_streams.py", "scripts/benchmark_pair_streams.py")},
        "environment": {"python": sys.version, "platform": platform.platform(),
                        "machine": platform.machine(), "processor": platform.processor()},
        "procedure": {"size_per_array": args.size, "repeats": args.repeats,
                      "order": "alternating materialized/streamed first",
                      "fixture": "range(size), reversed(range(-size, 0))",
                      "scope": "pair enumeration only; initialization and hashing sink included",
                      "memory": "isolated Python tracemalloc peak; prebuilt inputs excluded; not RSS",
                      "timing": "tracemalloc enabled; observational, no performance threshold"},
        "samples": samples, "summary": summary,
        "claim_boundary": "local reference fixture only; no join, donor theorem, or target speedup claim",
    }, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
