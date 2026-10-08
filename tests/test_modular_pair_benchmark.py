"""Oracle parity and fail-closed modular benchmark measurement contracts."""

import hashlib
from pathlib import Path
import statistics
import tracemalloc
import unittest
from unittest.mock import patch

from scripts import benchmark_modular_pair_streams as benchmark


class ModularPairBenchmarkTests(unittest.TestCase):
    def test_fixtures_paths_and_frequency_counts_match_direct_oracle(self):
        for fixture in benchmark.plan_fixtures(4, 16):
            a, b, q, r = (fixture[k] for k in ("first", "second", "modulus", "supplied_residue"))
            expected = benchmark.direct_oracle(a, b, q, r)
            self.assertEqual(len(expected), fixture["expected_eligible_pairs"])
            self.assertEqual(list(benchmark.exhaustive_then_filter(a, b, q, r)), expected)
            self.assertEqual(list(benchmark.FilteredPairSums(a, b, modulus=q, residue=r)), expected)

    def test_raw_modes_rotation_source_identity_and_summary(self):
        result = benchmark.run_benchmark(size=2, repeats=2)
        self.assertEqual(result["procedure"]["total_samples"], 72)
        root = Path(__file__).resolve().parents[1]
        for path, digest in result["source_sha256"].items():
            self.assertEqual(hashlib.sha256((root / path).read_bytes()).hexdigest(), digest)
        for case in result["cases"]:
            for variant in case["variants"].values():
                positions = [row["order_position"] for row in variant["timing_samples"]]
                self.assertNotEqual(*positions)
                for mode, metric, forbidden in (("timing", "elapsed_ns", "peak_traced_bytes"),
                                                ("allocation", "peak_traced_bytes", "elapsed_ns")):
                    rows = variant[mode + "_samples"]
                    self.assertEqual(len(rows), 2)
                    for row in rows:
                        self.assertIn(metric, row)
                        self.assertNotIn(forbidden, row)
                        benchmark.verify_result(row, case["reference"])
                    self.assertEqual(variant["summary"]["median_" + metric],
                                     statistics.median(row[metric] for row in rows))

    def test_tracer_is_separate_and_cleaned_on_failure(self):
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

    def test_corruption_and_source_change_prevent_evidence(self):
        with patch.object(benchmark, "FilteredPairSums", return_value=iter(())):
            with self.assertRaisesRegex(RuntimeError, "parity failed"):
                benchmark.run_benchmark(size=2, repeats=1)
        good = benchmark.consume(benchmark.direct_oracle((0,), (0,), 1, 0))
        for changed in ({**good, "count": 0}, {**good, "ordered_sha256": "0" * 64}):
            with self.assertRaisesRegex(RuntimeError, "parity failed"):
                benchmark.verify_result(changed, good)
        with patch.object(benchmark, "source_fingerprints", side_effect=[{"source": "before"},
                                                                     {"source": "after"}]):
            with self.assertRaisesRegex(RuntimeError, "source files changed"):
                benchmark.run_benchmark(size=1, repeats=1)

    def test_limits_reject_before_fixture_construction(self):
        with patch.object(benchmark, "fixtures") as build, patch.object(benchmark, "measure") as measure:
            with self.assertRaisesRegex(ValueError, "work limit"):
                benchmark.run_benchmark(size=1000000, max_pairs=16384)
            build.assert_not_called()
            measure.assert_not_called()
        for value in (0, -1, True):
            for keyword in ("size", "repeats", "max_pairs"):
                with self.assertRaises(ValueError):
                    benchmark.run_benchmark(**{keyword: value})


if __name__ == "__main__":
    unittest.main()
