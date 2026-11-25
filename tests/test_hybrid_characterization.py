"""Regression reproductions for failed-trial retention and cgroup provenance."""
from contextlib import redirect_stdout
from io import StringIO
import json
from pathlib import Path
import sys
from tempfile import TemporaryDirectory
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "scripts"))
import benchmark_hybrid_execution as b

h = b.h


class CharacterizationTests(unittest.TestCase):
    def test_cli_retains_success_and_failed_attempt_and_does_not_retry(self):
        workload = h.Workload(tuple(h.Unit(f"u{i}", 2) for i in range(4)))
        ctx = h.Context("a"*40, *("b"*64 for _ in range(6)))
        real_run = h.run_verified
        for failure in (RuntimeError("injected worker failure"),
                        h.CorrectnessError("injected oracle mismatch")):
            calls = []
            def fail_second(*args):
                calls.append(args[2])
                if len(calls) == 2:
                    raise failure
                return real_run(*args)

            stdout = StringIO()
            with self.subTest(failure=type(failure).__name__), \
                 patch.object(sys, "argv", ["benchmark", "--workers", "2"]), \
                 patch.object(b, "context", return_value=(ctx, {"source": {}})), \
                 patch.object(b, "fixtures", return_value={"small": workload}), \
                 patch.object(h, "run_verified", side_effect=fail_second), \
                 patch.object(h, "execute_selected") as selected, \
                 redirect_stdout(stdout):
                with self.assertRaises(type(failure)) as caught:
                    b.main()
                self.assertIs(caught.exception, failure)
                selected.assert_not_called()
            self.assertEqual(calls, [h.SERIAL, h.Plan("PARALLEL", 2)])
            report = json.loads(stdout.getvalue())
            self.assertEqual(report["status"], "failed")
            entry = report["fixtures"]["small"]
            self.assertEqual(entry["calibration"]["status"], "failed")
            self.assertNotIn("selection", entry)
            raw = entry["raw"]
            good = raw["SERIAL"][0]
            self.assertEqual(good["attempt"]["status"], "passed")
            self.assertTrue(good["execution"]["verified"])
            self.assertGreater(good["sample"]["wall_ns"], 0)
            bad = raw["PARALLEL-2"][0]
            self.assertEqual(bad["attempt"]["status"], "failed")
            self.assertGreaterEqual(bad["attempt"]["wall_ns"], 0)
            self.assertIn("cpu_ns", bad["attempt"])
            self.assertEqual(bad["attempt"]["error"],
                             {"type": type(failure).__name__, "message": str(failure)})
            self.assertIsNone(bad["sample"])
            self.assertIsNone(bad["execution"])
            self.assertEqual(sum(map(len, raw.values())), 2)

    def test_selected_failure_retains_previous_fixture_and_full_calibration(self):
        workload = h.Workload(tuple(h.Unit(f"u{i}", 2) for i in range(4)))
        ctx = h.Context("a"*40, *("b"*64 for _ in range(6)))
        expected = h.oracle(workload)
        def calibration(w, c, plan):
            return expected, h.Sample(100, 100), {
                "identity": h.identity(w,c,plan), "result_digest": h.digest(expected),
                "verified": True}
        failure = h.CorrectnessError("selected oracle mismatch")
        report = {}
        with patch.object(b, "context", return_value=(ctx, {"source": {}})), \
             patch.object(b, "fixtures", return_value={"first": workload, "second": workload,
                                                       "never": workload}), \
             patch.object(h, "run_verified", side_effect=calibration), \
             patch.object(h, "execute_selected", side_effect=[(expected, {}, {"verified": True}),
                                                             failure]) as execute, \
             self.assertRaises(h.CorrectnessError) as caught:
            b.characterize(2, 2, report=report)
        self.assertIs(caught.exception, failure)
        self.assertEqual(execute.call_count, 2)
        self.assertEqual(report["status"], "failed")
        self.assertEqual(set(report["fixtures"]), {"first", "second"})
        first = report["fixtures"]["first"]
        second = report["fixtures"]["second"]
        self.assertEqual(first["selected_execution_attempt"]["status"], "passed")
        self.assertEqual(second["calibration"]["status"], "passed")
        self.assertEqual(sum(map(len, second["raw"].values())), 6)
        self.assertEqual(second["selected_execution_attempt"]["status"], "failed")
        self.assertNotIn("selected_full_execution", second)

    def test_failed_attempt_timing_is_retained_deterministically(self):
        record = {}
        error = RuntimeError("failed")
        with patch.object(b.time, "monotonic_ns", side_effect=[10, 75]), \
             patch.object(h, "_cpu_ns", side_effect=[20, 48]), \
             self.assertRaises(RuntimeError):
            with b.timed_phase(record):
                raise error
        self.assertEqual(record, {"status": "failed", "wall_ns": 65, "cpu_ns": 28,
                                  "error": {"type": "RuntimeError", "message": "failed"}})


class CgroupTests(unittest.TestCase):
    def setUp(self):
        self.tmp = TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        self.proc = self.root / "proc"
        self.proc.mkdir()
        self.mount = self.root / "cgroup mount"
        self.mount.mkdir()

    def configure(self, membership, root="/", kind="cgroup2", options="rw"):
        (self.proc / "cgroup").write_text(membership + "\n")
        escaped = str(self.mount).replace(" ", r"\040")
        (self.proc / "mountinfo").write_text(
            f"31 22 0:29 {root} {escaped} rw - {kind} cgroup {options}\n")

    def limits(self, relative, values):
        directory = self.mount / relative
        directory.mkdir(parents=True, exist_ok=True)
        for name, value in values.items():
            (directory / name).write_text(value + "\n")

    def test_v2_leaf_parent_root_and_changed_quota(self):
        self.configure("0::/bench/job")
        self.limits("", {"cpu.max": "max 100000"})
        self.limits("bench", {"cpu.max": "200000 100000", "memory.max": "4194304"})
        self.limits("bench/job", {"cpu.max": "100000 100000",
                                  "cpuset.cpus.effective": "0", "pids.max": "32"})
        first = b.cgroup_limits(self.proc)
        hierarchy = first["hierarchies"][0]
        self.assertEqual(hierarchy["membership"], "/bench/job")
        self.assertEqual(hierarchy["mount_point"], str(self.mount))
        self.assertTrue(hierarchy["visible_to_namespace_root"])
        self.assertEqual(hierarchy["leaf_to_mount_root"], [
            {"path": "/bench/job", "limits": {"cpu.max": "100000 100000",
                                              "cpuset.cpus.effective": "0", "pids.max": "32"}},
            {"path": "/bench", "limits": {"cpu.max": "200000 100000", "memory.max": "4194304"}},
            {"path": "/", "limits": {"cpu.max": "max 100000"}},
        ])
        self.limits("bench/job", {"cpu.max": "200000 100000"})
        second = b.cgroup_limits(self.proc)
        self.assertNotEqual(h.digest(first), h.digest(second))
        self.limits("bench", {"cpu.max": "300000 100000"})
        self.assertNotEqual(h.digest(second), h.digest(b.cgroup_limits(self.proc)))

    @unittest.skipUnless(sys.platform.startswith("linux"), "Linux cgroup identity")
    def test_actual_context_host_digest_binds_leaf_limits(self):
        self.configure("0::/bench")
        self.limits("", {"cpu.max": "max 100000"})
        self.limits("bench", {"cpu.max": "100000 100000"})
        snapshot = b.cgroup_limits
        with patch.object(b, "cgroup_limits", side_effect=lambda: snapshot(self.proc)):
            before, _ = b.context("same-generation")
            self.limits("bench", {"cpu.max": "200000 100000"})
            after, _ = b.context("same-generation")
        self.assertNotEqual(before.host_limits, after.host_limits)

    def test_nonroot_mount_maps_membership_without_duplicating_prefix(self):
        self.configure("0::/tenant/bench", root="/tenant")
        self.limits("", {"cpu.max": "300000 100000"})
        self.limits("bench", {"cpu.max": "100000 100000"})
        hierarchy = b.cgroup_limits(self.proc)["hierarchies"][0]
        self.assertFalse(hierarchy["visible_to_namespace_root"])
        self.assertEqual(hierarchy["mount_root"], "/tenant")
        self.assertEqual(hierarchy["leaf_to_mount_root"], [
            {"path": "/tenant/bench", "limits": {"cpu.max": "100000 100000"}},
            {"path": "/tenant", "limits": {"cpu.max": "300000 100000"}},
        ])

    def test_v1_cpu_hierarchy_binds_quota_and_ancestors(self):
        self.configure("3:cpu,cpuacct:/bench", kind="cgroup", options="rw,cpu,cpuacct")
        self.limits("", {"cpu.cfs_quota_us": "-1", "cpu.cfs_period_us": "100000"})
        self.limits("bench", {"cpu.cfs_quota_us": "100000", "cpu.cfs_period_us": "100000"})
        hierarchy = b.cgroup_limits(self.proc)["hierarchies"][0]
        self.assertEqual(hierarchy["version"], 1)
        self.assertEqual(hierarchy["controllers"], ("cpu",))
        self.assertEqual(hierarchy["leaf_to_mount_root"][0]["limits"]["cpu.cfs_quota_us"], "100000")
        self.assertEqual(hierarchy["leaf_to_mount_root"][1]["limits"]["cpu.cfs_quota_us"], "-1")

    def test_missing_or_unmapped_membership_is_not_root_evidence(self):
        self.configure("0::/bench", root="/other")
        with self.assertRaisesRegex(RuntimeError, "no visible mount"):
            b.cgroup_limits(self.proc)
        self.configure("0::/bench")
        with self.assertRaisesRegex(RuntimeError, "not accessible"):
            b.cgroup_limits(self.proc)


if __name__ == "__main__":
    unittest.main()
