"""Exact integer pair streams and bounded equal-key joins (OPT-STREAM-001).

This is a small reference adaptation, not the donor's Subset Sum algorithm.
Inputs and output indices refer to immutable snapshots. Working storage is
linear in input lengths plus buffer capacity; retained consumer output is extra.
Python integer operations have bit-dependent costs. No modular filters or
hard byte/time budget are implemented here.
"""

from __future__ import annotations

from dataclasses import dataclass
from heapq import heapify, heappop, heappush
from typing import Iterator, Sequence


@dataclass(frozen=True, order=True)
class Pair:
    key: int
    left: int
    right: int


class PairSums:
    """Enumerate every indexed pair once, ordered by (sum, left, right).

    Heap merge holds one entry per first-array row. Clones share immutable
    inputs but copy all mutable heap state, including the next occurrence.
    """

    def __init__(self, first: Sequence[int], second: Sequence[int]) -> None:
        self._first = tuple(first)
        values = tuple(second)
        if any(type(value) is not int for value in self._first + values):
            raise TypeError("pair streams require exact Python integers")
        self._second = tuple(sorted((value, index) for index, value in enumerate(values)))
        self._heap = []
        if self._second:
            value, original_index = self._second[0]
            self._heap = [(item + value, row, original_index, 0)
                          for row, item in enumerate(self._first)]
            heapify(self._heap)

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
        if column < len(self._second):
            value, index = self._second[column]
            heappush(self._heap, (self._first[row] + value, row, index, column))
        return Pair(key, row, original_index)

    def clone(self) -> PairSums:
        copy = object.__new__(PairSums)
        copy._first = self._first
        copy._second = self._second
        copy._heap = self._heap.copy()
        return copy

    def __iter__(self) -> Iterator[Pair]:
        while self._heap:
            yield self.pop()


def join_equal_sums(
    first: Sequence[int], second: Sequence[int],
    third: Sequence[int], fourth: Sequence[int], *, buffer_capacity: int,
) -> Iterator[tuple[Pair, Pair]]:
    """Yield the full indexed Cartesian join where a+b == c+d.

    Order is key, first pair indices, second pair indices. Duplicate values
    preserve all indexed occurrences. Oversized right ties are replayed from
    a heap snapshot; they are never truncated. Closing this iterator means
    incomplete enumeration, not an infeasibility or no-more-matches proof.
    As with ordinary Python generators, input snapshots are taken on the
    first advance, not when the generator object is created.
    """
    if type(buffer_capacity) is not int or buffer_capacity < 1:
        raise ValueError("buffer_capacity must be a positive integer")
    left = PairSums(first, second)
    right = PairSums(third, fourth)
    while (left_item := left.peek()) is not None and (right_item := right.peek()) is not None:
        if left_item.key < right_item.key:
            left.pop()
            continue
        if right_item.key < left_item.key:
            right.pop()
            continue

        key = left_item.key
        buffer = []
        while len(buffer) < buffer_capacity and (item := right.peek()) is not None and item.key == key:
            buffer.append(right.pop())
        # Include the next suffix occurrence in the snapshot, if there is one.
        item = right.peek()
        suffix = right.clone() if item is not None and item.key == key else None
        while (item := left.peek()) is not None and item.key == key:
            left_pair = left.pop()
            for right_pair in buffer:
                yield left_pair, right_pair
            if suffix is not None:
                replay = suffix.clone()
                while (item := replay.peek()) is not None and item.key == key:
                    yield left_pair, replay.pop()
        # Advance the authoritative stream to the next key without storing
        # the suffix. This extra pass is part of total work, not free replay.
        while (item := right.peek()) is not None and item.key == key:
            right.pop()
