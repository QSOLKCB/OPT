"""Independent exhaustive oracles for exact streaming and tie replay."""

import itertools
import random
import unittest

from examples.bounded_pair_streams import Pair, PairSums, join_equal_sums


def reference_pairs(first, second):
    return sorted(Pair(a + b, i, j) for i, a in enumerate(first)
                  for j, b in enumerate(second))


def reference_join(a, b, c, d):
    # Direct four-loop oracle: it does not share the stream or tie-join logic.
    matches = [(Pair(x + y, i, j), Pair(z + w, k, l))
               for i, x in enumerate(a) for j, y in enumerate(b)
               for k, z in enumerate(c) for l, w in enumerate(d)
               if x + y == z + w]
    return sorted(matches)


class BoundedPairStreamTests(unittest.TestCase):
    def test_exhaustive_pair_occurrences_and_order(self):
        arrays = [p for n in range(4) for p in itertools.product((-1, 0, 1), repeat=n)]
        for first, second in itertools.product(arrays, repeat=2):
            self.assertEqual(list(PairSums(first, second)), reference_pairs(first, second))

    def test_exhaustive_joins_are_capacity_independent(self):
        arrays = [p for n in range(3) for p in itertools.product((-1, 1), repeat=n)]
        for arrays4 in itertools.product(arrays, repeat=4):
            expected = reference_join(*arrays4)
            for capacity in (1, 2, 5):
                self.assertEqual(list(join_equal_sums(*arrays4, buffer_capacity=capacity)), expected)

    def test_large_ties_preserve_full_cartesian_product(self):
        arrays = ([0] * 7, [0] * 5, [0] * 6, [0] * 4)
        expected = reference_join(*arrays)
        self.assertEqual(len(expected), 840)
        for capacity in (1, 23, 24, 25):
            self.assertEqual(list(join_equal_sums(*arrays, buffer_capacity=capacity)), expected)

    def test_seeded_signed_and_large_integer_fixtures(self):
        rng = random.Random(20261008)
        for _ in range(100):
            arrays = [[rng.choice((-10**80, -3, 0, 3, 10**80))
                       for _ in range(rng.randrange(6))] for _ in range(4)]
            self.assertEqual(list(join_equal_sums(*arrays, buffer_capacity=2)), reference_join(*arrays))

    def test_snapshot_includes_lookahead_and_is_independent(self):
        stream = PairSums([0, 1, 1], [1, 0, 0])
        stream.pop()
        clone = stream.clone()
        expected = list(clone.clone())
        stream.pop()
        self.assertEqual(list(clone), expected)
        self.assertEqual(list(stream), expected[1:])
        self.assertEqual(list(clone.clone()), [])

    def test_inputs_are_snapshotted(self):
        first, second = [1, 2], [3, 4]
        stream = PairSums(first, second)
        first[:] = [100]
        second[:] = []
        self.assertEqual(list(stream), reference_pairs([1, 2], [3, 4]))

    def test_interrupted_join_is_a_prefix_and_fresh_run_is_complete(self):
        arrays = ([0, 1, 0], [1, 0], [0, 1, 0], [1, 0])
        expected = reference_join(*arrays)
        iterator = join_equal_sums(*arrays, buffer_capacity=1)
        self.assertEqual(list(itertools.islice(iterator, 5)), expected[:5])
        iterator.close()
        self.assertEqual(list(join_equal_sums(*arrays, buffer_capacity=1)), expected)

    def test_started_join_is_isolated_from_input_mutation(self):
        arrays = [[0, 1, 0], [1, 0], [0, 1, 0], [1, 0]]
        expected = reference_join(*arrays)
        iterator = join_equal_sums(*arrays, buffer_capacity=1)
        head = next(iterator)
        for values in arrays:
            values[:] = [999]
        self.assertEqual([head, *iterator], expected)

    def test_rejects_invalid_domains_and_capacities(self):
        for value in (True, 1.0, "1"):
            with self.assertRaises(TypeError):
                PairSums([value], [0])
        for capacity in (0, -1, True, 1.0):
            with self.assertRaises(ValueError):
                list(join_equal_sums([0], [0], [0], [0], buffer_capacity=capacity))


if __name__ == "__main__":
    unittest.main()
