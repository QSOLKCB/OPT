"""Independent join baseline and fail-closed measurement contracts."""

import hashlib
import itertools
from pathlib import Path
import tracemalloc
import unittest
from unittest.mock import patch

from examples.bounded_pair_streams import Pair, join_equal_sums
from scripts import benchmark_pair_joins as benchmark


def oracle(arrays):
    a, b, c, d = arrays
    return sorted((Pair(x + y, i, j), Pair(z + w, k, l))
                  for i, x in enumerate(a) for j, y in enumerate(b)
                  for k, z in enumerate(c) for l, w in enumerate(d) if x + y == z + w)


class PairJoinBenchmarkTests(unittest.TestCase):
    def test_materialized_baseline_against_exhaustive_four_loop_oracle(self):
        arrays = [p for n in range(3) for p in itertools.product((-1, 1), repeat=n)]
        for inputs in itertools.product(arrays, repeat=4):
            self.assertEqual(list(benchmark.materialized_join(*inputs)), oracle(inputs))

    def test_fixtures_match_oracle_across_capacities(self):
        for fixture in benchmark.plan_fixtures(3, 20, 100):
            expected = oracle(fixture["inputs"])
            self.assertEqual(len(expected), fixture["expected_matches"])
            self.assertEqual(list(benchmark.materialized_join(*fixture["inputs"])), expected)
            for capacity in (1, 2, 9, 10):
                self.assertEqual(list(join_equal_sums(
                    *fixture["inputs"], buffer_capacity=capacity)), expected)

    def test_modes_rotation_source_identity_and_raw_sample_parity(self):
        result = benchmark.run_benchmark(size=2, repeats=2, capacities=(1, 4))
        root = Path(__file__).resolve().parents[1]
        for path, digest in result["source_sha256"].items():
            self.assertEqual(hashlib.sha256((root / path).read_bytes()).hexdigest(), digest)
        for case in result["cases"]:
            for variant in case["variants"].values():
                self.assertEqual(len(variant["timing_samples"]), 2)
                self.assertEqual(len(variant["allocation_samples"]), 2)
                positions = [row["order_position"] for row in variant["timing_samples"]]
                self.assertNotEqual(*positions)
                for row in variant["timing_samples"]:
                    self.assertIn("elapsed_ns", row)
                    self.assertNotIn("peak_traced_bytes", row)
                    benchmark.verify_result(row, case["reference"])
                for row in variant["allocation_samples"]:
                    self.assertIn("peak_traced_bytes", row)
                    self.assertNotIn("elapsed_ns", row)
                    benchmark.verify_result(row, case["reference"])

    def test_tracer_is_separate_and_cleanup_survives_failure(self):
        observed = []
        def factory():
            observed.append(tracemalloc.is_tracing())
            return iter(())
        benchmark.measure(factory, "timing")
        with patch.object(benchmark.time, "perf_counter_ns", side_effect=AssertionError("timed allocations")):
            benchmark.measure(factory, "allocation")
        self.assertEqual(observed, [False, True])
        def fail():
            raise RuntimeError("consumer failed")
        with self.assertRaisesRegex(RuntimeError, "consumer failed"):
            benchmark.measure(fail, "allocation")
        self.assertFalse(tracemalloc.is_tracing())
        tracemalloc.start()
        try:
            with self.assertRaisesRegex(RuntimeError, "inactive"):
                benchmark.measure(factory, "timing")
        finally:
            tracemalloc.stop()

    def test_corrupt_stream_cannot_emit_evidence(self):
        with patch.object(benchmark, "join_equal_sums", return_value=iter(())):
            with self.assertRaisesRegex(RuntimeError, "parity failed"):
                benchmark.run_benchmark(size=2, repeats=1, capacities=(1,))
        good = benchmark.consume(iter(oracle(((0,), (0,), (0,), (0,)))))
        for changed in ({**good, "count": 0}, {**good, "ordered_sha256": "0" * 64}):
            with self.assertRaisesRegex(RuntimeError, "parity failed"):
                benchmark.verify_result(changed, good)

    def test_changed_source_cannot_emit_evidence(self):
        with patch.object(benchmark, "source_fingerprints", side_effect=[{"source": "before"},
                                                                     {"source": "after"}]):
            with self.assertRaisesRegex(RuntimeError, "source files changed"):
                benchmark.run_benchmark(size=1, repeats=1, capacities=(1,))

    def test_limits_reject_before_fixture_allocation_or_measurement(self):
        with patch.object(benchmark, "fixtures") as build, patch.object(benchmark, "measure") as measure:
            for limits in ((1000000, 4096, 1000000), (8, 4096, 4095), (8, 63, 1000000)):
                with self.assertRaisesRegex(ValueError, "work limit"):
                    benchmark.plan_fixtures(*limits)
            build.assert_not_called()
            measure.assert_not_called()
        for capacities in ((), (1, 1), (0,), (True,)):
            with self.assertRaises(ValueError):
                benchmark.run_benchmark(capacities=capacities)


if __name__ == "__main__":
    unittest.main()
