"""Direct exhaustive oracles and residue-stream failure modes."""

from heapq import heapify, heappush
import itertools
import random
import unittest
from unittest.mock import patch

from examples.bounded_pair_streams import Pair, PairSums
from examples import modular_pair_streams as module
from examples.modular_pair_streams import FilteredPairSums


def oracle(first, second, modulus, residue):
    return sorted(Pair(a + b, i, j) for i, a in enumerate(first)
                  for j, b in enumerate(second)
                  if (a + b) % modulus == residue % modulus)


class ModularPairStreamTests(unittest.TestCase):
    def test_exhaustive_composite_and_normalized_residues(self):
        arrays = [p for n in range(4) for p in itertools.product((-1, 0, 1), repeat=n)]
        for first, second in itertools.product(arrays, repeat=2):
            for modulus in (1, 2, 4, 6):
                for residue in range(modulus):
                    supplied = residue - 2 * modulus
                    stream = FilteredPairSums(first, second, modulus=modulus, residue=supplied)
                    self.assertEqual(stream.residue, residue)
                    self.assertEqual(list(stream), oracle(first, second, modulus, supplied))

    def test_modulus_one_matches_unfiltered_order(self):
        first, second = [3, -1, 3, 0], [4, -8, 4, 1]
        self.assertEqual(list(FilteredPairSums(first, second, modulus=1, residue=100)),
                         list(PairSums(first, second)))

    def test_signed_large_integers_and_huge_sparse_modulus(self):
        rng = random.Random(20261008)
        for _ in range(60):
            first, second = ([rng.choice((-10**80, -7, 0, 7, 10**80))
                              for _ in range(rng.randrange(6))] for _ in range(2))
            modulus = rng.choice((3, 8, 15, 10**81 + 12))
            residue = rng.choice((-10**82, -5, 0, 5, 10**82))
            self.assertEqual(list(FilteredPairSums(first, second, modulus=modulus, residue=residue)),
                             oracle(first, second, modulus, residue))

    def test_duplicates_and_congruence_collisions_are_not_deduplicated(self):
        first, second = [0] * 7, [0] * 5
        self.assertEqual(len(list(FilteredPairSums(first, second, modulus=12, residue=0))), 35)
        stream = FilteredPairSums([0, 4], [0, 4], modulus=4, residue=0)
        # Congruence alone does not restrict these actual sums to zero.
        self.assertEqual(list(stream), [Pair(0, 0, 0), Pair(4, 0, 1),
                                        Pair(4, 1, 0), Pair(8, 1, 1)])

    def test_heap_contains_only_eligible_occurrences(self):
        entries = []
        def initialize(heap):
            entries.extend(heap)
            heapify(heap)
        def advance(heap, item):
            entries.append(item)
            heappush(heap, item)
        first, second, modulus, residue = tuple(range(9)), tuple(range(-8, 9)), 6, 2
        expected = oracle(first, second, modulus, residue)
        with patch.object(module, "heapify", side_effect=initialize), \
                patch.object(module, "heappush", side_effect=advance):
            actual = list(FilteredPairSums(first, second, modulus=modulus, residue=residue))
        self.assertEqual(actual, expected)
        self.assertEqual(sorted(Pair(key, i, j) for key, i, j, _ in entries), expected)
        self.assertLess(len(entries), len(first) * len(second))

    def test_lookahead_and_clones_are_independent(self):
        stream = FilteredPairSums([0, 3, 3], [3, 0, 0, 1], modulus=3, residue=0)
        stream.pop()
        expected = list(stream.clone())
        self.assertEqual(stream.peek(), expected[0])
        self.assertEqual(stream.peek(), expected[0])
        clone = stream.clone()
        self.assertEqual(stream.pop(), expected[0])
        self.assertEqual(clone.pop(), expected[0])
        branch = clone.clone()
        stream.pop()
        self.assertEqual(list(clone), expected[1:])
        self.assertEqual(list(branch), expected[1:])
        self.assertEqual(list(stream), expected[2:])
        self.assertIsNone(stream.peek())
        self.assertEqual(list(stream.clone()), [])
        with self.assertRaises(StopIteration):
            stream.pop()

    def test_snapshots_and_interrupted_prefix(self):
        first, second = [0, 3, 1, 0], [0, 3, 2, 0]
        expected = oracle(first, second, 3, 0)
        stream = FilteredPairSums(first, second, modulus=3, residue=0)
        iterator = iter(stream)
        self.assertEqual(list(itertools.islice(iterator, 3)), expected[:3])
        iterator.close()
        first[:] = [999]
        second[:] = []
        self.assertEqual(list(stream), expected[3:])
        self.assertEqual(list(FilteredPairSums([0, 3, 1, 0], [0, 3, 2, 0],
                                             modulus=3, residue=0)), expected)

    def test_empty_and_no_eligible_rows(self):
        for first, second in (([], [1]), ([1], []), ([], []), ([0, 2], [0, 2])):
            stream = FilteredPairSums(first, second, modulus=2, residue=1)
            self.assertIsNone(stream.peek())
            self.assertEqual(list(stream), [])

    def test_rejects_invalid_inputs_even_when_other_array_is_empty(self):
        for modulus in (0, -1, True, 2.0, "2"):
            with self.assertRaises(ValueError):
                FilteredPairSums([], [], modulus=modulus, residue=0)
        for residue in (True, 0.0, "0"):
            with self.assertRaises(TypeError):
                FilteredPairSums([], [], modulus=1, residue=residue)
        for value in (True, 1.0, "1"):
            for first, second in (([value], []), ([], [value]), ([0], [value])):
                with self.assertRaises(TypeError):
                    FilteredPairSums(first, second, modulus=1, residue=0)


if __name__ == "__main__":
    unittest.main()
