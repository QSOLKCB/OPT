"""Deterministic conformance, not timing assertions."""
from dataclasses import replace
from pathlib import Path
import sys
import unittest
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "examples"))
import hybrid_execution as h


class HybridTests(unittest.TestCase):
    def setUp(self):
        self.w = h.Workload((h.Unit("b", 3, ("a",)), h.Unit("a", 4),
                             h.Unit("c", 2)), 3)
        self.ctx = h.Context("a"*40, *("b"*64 for _ in range(6)))
        self.p = h.Plan("PARALLEL", 2)
        self.h = h.Plan("HYBRID", 2, ("a",))
        self.policy = h.Policy()
        # Independently calculated: prep=3, a=17, b=5+3+17=25, c=4.
        self.expected = (("b", 25), ("a", 17), ("c", 4))

    def evidence(self, plan, wall, *, cpu=10, memory=20, result=True):
        return h.Evidence(plan, h.identity(self.w, self.ctx, plan),
                          h.digest(self.expected) if result else None,
                          (h.Sample(wall, cpu, memory),)*2)

    def choose(self, *ledger, policy=None, override=None):
        return h.select(self.w, self.ctx, ledger, policy or self.policy,
                        override=override)

    def test_small_serial_and_setup_overhead(self):
        s, p = self.evidence(h.SERIAL, 100), self.evidence(self.p, 180)
        self.assertEqual(self.choose(s,p)[0], h.SERIAL)
        self.assertEqual(self.choose()[0], h.SERIAL)

    def test_larger_parallel(self):
        s, p = self.evidence(h.SERIAL, 2000), self.evidence(self.p, 1000)
        self.assertEqual(self.choose(s,p)[0], self.p)

    def test_mixed_hybrid(self):
        s, p, hy = (self.evidence(h.SERIAL, 2000), self.evidence(self.p, 1300),
                    self.evidence(self.h, 900))
        self.assertEqual(self.choose(s,p,hy)[0], self.h)

    def test_near_tie_and_common_cost(self):
        s, p = self.evidence(h.SERIAL, 100), self.evidence(self.p, 95)
        self.assertEqual(self.choose(s,p)[0], h.SERIAL)
        p = self.evidence(self.p, 70)
        self.assertEqual(self.choose(s,p)[0], self.p)
        self.assertEqual(self.choose(s,p,policy=replace(self.policy, common_wall_ns=1000))[0], h.SERIAL)

    def test_kernel_only_boundary_rejected(self):
        s = self.evidence(h.SERIAL, 100)
        p = self.evidence(self.p, 30)  # kernel-only score not eligible
        with self.assertRaises(ValueError):
            self.choose(s, replace(p, boundary="kernel-only"))
        self.assertEqual(self.choose(s, self.evidence(self.p, 130))[0], h.SERIAL)

    def test_resource_budgets(self):
        s = self.evidence(h.SERIAL, 100)
        p = self.evidence(self.p, 50, memory=30)
        self.assertEqual(self.choose(s,p,policy=replace(self.policy,max_workers=1))[0], h.SERIAL)
        self.assertEqual(self.choose(s,p,policy=replace(self.policy,max_memory_bytes=25))[0], h.SERIAL)
        p = self.evidence(self.p, 50, memory=None)
        self.assertEqual(self.choose(s,p,policy=replace(self.policy,max_memory_bytes=25))[0], h.SERIAL)
        with self.assertRaises(h.BudgetError):
            self.choose(policy=replace(self.policy,max_memory_bytes=25))

    def test_missing_correctness_and_repetitions(self):
        s = self.evidence(h.SERIAL, 100)
        p = self.evidence(self.p, 20, result=False)
        self.assertEqual(self.choose(s,p)[0], h.SERIAL)
        p = self.evidence(self.p, 20)
        self.assertEqual(self.choose(s,replace(p,samples=p.samples[:1]))[0], h.SERIAL)
        self.assertEqual(self.choose(p)[0], h.SERIAL)
        with self.assertRaises(h.BudgetError):
            self.choose(s,override=self.p)

    def test_stale_all_material_fields(self):
        s,p = self.evidence(h.SERIAL,100),self.evidence(self.p,20)
        for field in ("materialized_source","configuration","runtime","dependencies",
                      "host_limits","generation"):
            with self.subTest(field=field):
                changed = replace(self.ctx, **{field:"c"*64})
                chosen, receipt = h.select(self.w,changed,(s,p))
                self.assertEqual(chosen,h.SERIAL)
                self.assertTrue(all(r["reason"] == "stale identity" for r in receipt["candidates"]))
        changed = replace(self.w, preparation=4)
        self.assertEqual(h.select(changed,self.ctx,(s,p))[0],h.SERIAL)

    def test_invalid_ledger(self):
        p = self.evidence(self.p, 20)
        for ledger in ((p,p), (replace(p,identity="bad"),),
                       (replace(p,samples=(h.Sample(True,0),)),)):
            with self.subTest(ledger=ledger), self.assertRaises(ValueError):
                self.choose(*ledger)

    def test_current_mismatch_never_falls_back(self):
        s = self.evidence(h.SERIAL,100)
        p = replace(self.evidence(self.p,20),result_digest="d"*64)
        with self.assertRaises(h.CorrectnessError):
            self.choose(s,p,policy=replace(self.policy,max_workers=1))

    def test_pareto_mixed_directions_and_ties(self):
        s = self.evidence(h.SERIAL,1000)
        p = self.evidence(self.p,100,cpu=20)
        hy = self.evidence(self.h,100,cpu=20)
        q = self.evidence(h.Plan("PARALLEL",4),90,cpu=40)
        chosen, receipt = self.choose(s,p,hy,q)
        self.assertEqual(chosen,q.plan)
        self.assertEqual({r["id"] for r in receipt["frontier"]},{p.plan.id,hy.plan.id,q.plan.id})
        self.assertEqual(receipt["directions"],("minimize","maximize"))
        self.assertEqual((chosen,receipt),self.choose(q,hy,p,s))
        self.assertEqual(self.choose(s,p,hy)[0],self.h)  # H sorts before P

    def test_manual_override_requires_evidence(self):
        s,p = self.evidence(h.SERIAL,100),self.evidence(self.p,200)
        self.assertEqual(self.choose(s,p,override=self.p)[0],self.p)
        with self.assertRaises(h.BudgetError):
            self.choose(s,p,override=self.p,policy=replace(self.policy,max_workers=1))

    def test_invalid_units_and_dependencies(self):
        for units in ((h.Unit("a",1),h.Unit("a",1)),
                      (h.Unit("a",1,("missing",)),),
                      (h.Unit("a",1,("b",)),h.Unit("b",1,("a",))),
                      (h.Unit("a",1,("a","a")),)):
            with self.subTest(units=units), self.assertRaises(ValueError):
                h.levels(h.Workload(units))

    def test_invalid_worker_counts_and_partitions(self):
        for plan in (h.Plan("PARALLEL",0),h.Plan("PARALLEL",1),
                     h.Plan("PARALLEL",True),h.Plan("PARALLEL",33),
                     h.Plan("HYBRID",2,("missing",)),h.Plan("HYBRID",2,("a","a"))):
            with self.subTest(plan=plan), self.assertRaises(ValueError):
                h.identity(self.w,self.ctx,plan)

    def test_full_work_real_processes_order_and_dependencies(self):
        for plan in (h.SERIAL,self.p,self.h):
            with self.subTest(plan=plan):
                result,sample,receipt = h.run_verified(self.w,self.ctx,plan)
                self.assertEqual(result,self.expected)
                self.assertTrue(receipt["verified"])
                self.assertEqual(receipt["result_digest"],h.digest(self.expected))
                if plan != h.SERIAL:
                    self.assertGreaterEqual(len(receipt["observed_worker_pids"]),1)
                if plan == self.h:
                    self.assertEqual(receipt["parent_units"],2)

    def test_empty_workload(self):
        for plan in (h.SERIAL,self.p):
            result,_,run = h.run_verified(h.Workload(()),self.ctx,plan)
            self.assertEqual(result,())
            self.assertEqual(run["observed_worker_pids"],[])

    def test_worker_failure_propagates(self):
        s,p = self.evidence(h.SERIAL,100),self.evidence(self.p,20)
        with patch.object(h,"ProcessPoolExecutor") as pool:
            pool.return_value.__enter__.return_value.submit.return_value.result.side_effect = RuntimeError("worker failed")
            with self.assertRaisesRegex(RuntimeError,"worker failed"):
                h.execute_selected(self.w,self.ctx,(s,p))
            pool.assert_called_once()

    def test_oracle_mismatch_prevents_promotion_no_retry(self):
        s,p = self.evidence(h.SERIAL,100),self.evidence(self.p,20)
        with patch.object(h,"_stage",return_value=((("a",0),),{})) as stage:
            with self.assertRaises(h.CorrectnessError):
                h.execute_selected(self.w,self.ctx,(s,p))
            stage.assert_called_once_with(self.w,self.p)

    def test_missing_duplicate_worker_result(self):
        with patch.object(h,"_kernel",return_value=("missing",0,1,0,1)):
            with self.assertRaises(h.CorrectnessError):
                h.run_verified(self.w,self.ctx,h.SERIAL)

    def test_actual_invocation_receipt(self):
        result,selection,execution = h.execute_selected(self.w,self.ctx,())
        self.assertEqual(result,self.expected)
        self.assertEqual(selection["selected_identity"],execution["run"]["identity"])
        self.assertTrue(execution["run"]["verified"])


if __name__ == "__main__":
    unittest.main()
