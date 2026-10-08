"""Exact residue-filtered pair sums, ordered by actual sum and original indices.

Independent adaptation of the residue-slice idea in OPT-STREAM-001. This
does not implement modular-key ordering, a randomized solver, or a join.
Residue equality is not exact sum equality. Working storage is linear in
input lengths, with no allocation proportional to the modulus.
"""

from __future__ import annotations

from heapq import heapify, heappop, heappush
from typing import Iterator, Sequence

from examples.bounded_pair_streams import Pair


class FilteredPairSums:
    """Emit exactly the indexed pairs with (a+b) % modulus == residue % modulus.

    Inputs are snapshotted on construction. Each row traverses only its
    eligible bucket, sorted by (second value, original index). Heap keys
    retain actual sums, so filtering preserves PairSums' ordering. Clones
    share immutable row/input tuples and copy the next-occurrence heap.
    Exhaustion establishes completeness; a stopped prefix is incomplete.
    """

    def __init__(self, first: Sequence[int], second: Sequence[int], *,
                 modulus: int, residue: int) -> None:
        if type(modulus) is not int or modulus < 1:
            raise ValueError("modulus must be a positive exact Python integer")
        if type(residue) is not int:
            raise TypeError("residue must be an exact Python integer")
        self._first = tuple(first)
        values = tuple(second)
        if any(type(value) is not int for value in self._first + values):
            raise TypeError("pair streams require exact Python integers")
        self._modulus = modulus
        self._residue = residue % modulus

        # Store only observed residues, never a dense array of modulus entries.
        buckets = {}
        for index, value in enumerate(values):
            buckets.setdefault(value % modulus, []).append((value, index))
        ordered = {key: tuple(sorted(items)) for key, items in buckets.items()}
        self._rows = tuple(ordered.get((self._residue - value) % modulus, ())
                           for value in self._first)
        self._heap = []
        for row, partners in enumerate(self._rows):
            if partners:
                value, original_index = partners[0]
                self._heap.append((self._first[row] + value, row, original_index, 0))
        heapify(self._heap)

    @property
    def modulus(self) -> int:
        return self._modulus

    @property
    def residue(self) -> int:
        return self._residue

    def peek(self) -> Pair | None:
        if not self._heap:
            return None
        key, row, original_index, _column = self._heap[0]
        return Pair(key, row, original_index)

    def pop(self) -> Pair:
        if not self._heap:
            raise StopIteration
        key, row, original_index, column = heappop(self._heap)
        column += 1
        partners = self._rows[row]
        if column < len(partners):
            value, index = partners[column]
            heappush(self._heap, (self._first[row] + value, row, index, column))
        return Pair(key, row, original_index)

    def clone(self) -> FilteredPairSums:
        copy = object.__new__(FilteredPairSums)
        copy._first = self._first
        copy._rows = self._rows
        copy._modulus = self._modulus
        copy._residue = self._residue
        copy._heap = self._heap.copy()
        return copy

    def __iter__(self) -> Iterator[Pair]:
        while self._heap:
            yield self.pop()
