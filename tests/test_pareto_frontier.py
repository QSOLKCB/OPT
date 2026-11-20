"""Contract and independent finite-set oracle tests for OPT-PARETO-001."""

import itertools
import random
import unittest

from examples.pareto_frontier import MAX_CANDIDATES, pareto_frontier


def trial(key, values, feasible=True):
    return {"id": key, "metrics": values, "feasible": feasible}


def oracle(trials, directions):
    """Deliberately simple independent component-wise comparison oracle."""
    result = []
    for a in trials:
        if not a["feasible"]:
            continue
        beaten = False
        for b in trials:
            if not b["feasible"] or b is a:
                continue
            no_worse = True
            strictly = False
            for av, bv, d in zip(a["metrics"], b["metrics"], directions):
                is_better = bv < av if d == "minimize" else bv > av
                is_worse = bv > av if d == "minimize" else bv < av
                no_worse &= not is_worse
                strictly |= is_better
            if no_worse and strictly:
                beaten = True
                break
        if not beaten:
            result.append(a["id"])
    return tuple(result)


class ParetoFrontierTests(unittest.TestCase):
    def test_synthetic_game_tradeoffs(self):
        cases = [
            trial("fast", [10., 220, 4]),
            trial("balanced", [12., 180, 7]),
            trial("detailed", [16., 250, 10]),
            trial("inferior", [18., 300, 3]),
            trial("invalid", [8., 160, 9], False),
        ]
        original = [dict(x) for x in cases]
        got = pareto_frontier(cases, ("minimize", "minimize", "maximize"))
        self.assertEqual(tuple(x["id"] for x in got), ("fast", "balanced", "detailed"))
        self.assertEqual(cases, original)
        self.assertEqual(got, pareto_frontier(cases, ("minimize", "minimize", "maximize")))

    def test_equality_and_order(self):
        cases = [trial("z", [1, 2]), trial("a", [1., 2.]), trial("bad", [2, 2])]
        self.assertEqual(tuple(x["id"] for x in pareto_frontier(cases, ["minimize"]*2)), ("z", "a"))
        self.assertEqual(tuple(x["id"] for x in pareto_frontier(cases[::-1], ["minimize"]*2)), ("a", "z"))
        self.assertEqual(pareto_frontier([trial("x", [0, 0], False)], ["minimize"]*2), ())
        self.assertEqual(pareto_frontier([], ["minimize"]*2), ())

    def test_mixed_max_min_and_exact_integer(self):
        huge = 10**120
        cases = [trial("a", [huge, 1]), trial("b", [huge+1, 1]), trial("c", [huge+2, 2])]
        got = pareto_frontier(cases, ["maximize", "minimize"])
        self.assertEqual(tuple(x["id"] for x in got), ("b", "c"))

    def test_exhaustive_small_ledger_oracle(self):
        directions = ("minimize", "maximize")
        universe = list(itertools.product(range(3), repeat=2))
        for length in range(5):
            for chosen in itertools.combinations(universe, length):
                cases = [trial(str(i), list(p), i % 3 != 2) for i, p in enumerate(chosen)]
                expected = oracle(cases, directions)
                actual = tuple(c["id"] for c in pareto_frontier(cases, directions))
                self.assertEqual(actual, expected)

    def test_seeded_oracle_and_replay(self):
        rand = random.Random(126051)
        for _ in range(80):
            n = rand.randrange(2, 65)
            directions = tuple(rand.choice(("minimize", "maximize")) for _ in range(3))
            cases = [trial(f"case{i}", [rand.randrange(-10, 11) for _ in range(3)], bool(rand.getrandbits(1))) for i in range(n)]
            expected = oracle(cases, directions)
            self.assertEqual(tuple(c["id"] for c in pareto_frontier(cases, directions)), expected)

    def test_fail_closed_invalid_ledgers(self):
        valid = [trial("ok", [1, 2])]
        invalids = [
            {"id": "bad", "metrics": [1, 2]},
            trial("bad", [1, float("nan")]),
            trial("bad", [1, float("inf")]),
            trial("bad", [1, True]),
            trial("bad", [1, "2"]),
            trial("bad", [1]),
            trial("bad", [1, 2], 1),
            trial("ok", [3, 4]),
            trial("", [1, 2]),
            trial(1, [1, 2]),
        ]
        for bad in invalids:
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                pareto_frontier(valid + [bad], ("minimize", "maximize"))
        for directions in ([], ["minimize"], ["minimize"]*9, ["minimize", "MIN"], [1, "maximize"]):
            with self.assertRaises(ValueError):
                pareto_frontier(valid, directions)
        for budget in (0, -1, True, 4097, 3.0, "5"):
            with self.assertRaises(ValueError):
                pareto_frontier(valid, ("minimize", "minimize"), max_candidates=budget)
        with self.assertRaises(ValueError):
            pareto_frontier(valid + [trial("other", [3, 4])], ("minimize", "minimize"), max_candidates=1)
        with self.assertRaises(ValueError):
            pareto_frontier([trial(str(i), (i, i)) for i in range(MAX_CANDIDATES + 1)], ("minimize", "minimize"))
        with self.assertRaises(ValueError):
            pareto_frontier((trial("x", [1, 2]) for _ in range(2)), ("minimize", "minimize"))

    def test_returns_fresh_copies(self):
        point = trial("id", [3, 5])
        result = pareto_frontier([point], ["minimize", "maximize"])
        point["metrics"][0] = -100
        self.assertEqual(result[0]["metrics"], (3, 5))


if __name__ == "__main__":
    unittest.main()
