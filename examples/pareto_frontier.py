"""Deterministic Pareto selection over an already evaluated, finite trial ledger.

Original QSOL-IMC reference, informed by Kochenderfer & Wheeler (2026),
Algorithms for Optimization, second edition, section 15.1. No book code copied.

This selects among observed feasible trials; it does not search for, certify,
or approximate an unobserved global Pareto frontier.
"""

from math import isfinite


MAX_CANDIDATES = 4096
MAX_OBJECTIVES = 8


def _validated(candidates, directions, max_candidates):
    if type(max_candidates) is not int or not 1 <= max_candidates <= MAX_CANDIDATES:
        raise ValueError("max_candidates must be an integer from 1 to 4096")
    if type(candidates) not in (list, tuple) or len(candidates) > max_candidates:
        raise ValueError("candidates must be a bounded list or tuple")
    if type(directions) not in (list, tuple) or not 2 <= len(directions) <= MAX_OBJECTIVES:
        raise ValueError("directions must have 2 to 8 objectives")
    if any(d not in ("minimize", "maximize") or type(d) is not str for d in directions):
        raise ValueError("each objective direction must be minimize or maximize")

    # Validate the *entire* input, including infeasible and dominated entries,
    # before doing any ranking. No partial acceptance of corrupt ledgers.
    seen = set()
    validated = []
    for candidate in candidates:
        if type(candidate) is not dict or set(candidate) != {"id", "metrics", "feasible"}:
            raise ValueError("each candidate must have id, metrics and feasible")
        key = candidate["id"]
        if type(key) is not str or not key or key in seen:
            raise ValueError("candidate ids must be nonempty and unique strings")
        seen.add(key)
        metrics = candidate["metrics"]
        if type(metrics) not in (tuple, list) or len(metrics) != len(directions):
            raise ValueError("candidate metrics must match objective count")
        if type(candidate["feasible"]) is not bool:
            raise ValueError("feasible must be an explicit boolean")
        for value in metrics:
            if type(value) is int:
                continue  # retain arbitrary-precision integer comparisons
            if type(value) is not float or not isfinite(value):
                raise ValueError("metrics must be finite numeric values (not booleans)")
        validated.append((key, tuple(metrics), candidate["feasible"]))
    return validated


def _dominates(a, b, directions):
    """Strict Pareto dominance, with mixed minimization/maximization."""
    strictly_better = False
    for av, bv, direction in zip(a, b, directions):
        if direction == "minimize":
            if av > bv:
                return False
            if av < bv:
                strictly_better = True
        else:
            if av < bv:
                return False
            if av > bv:
                strictly_better = True
    return strictly_better


def pareto_frontier(candidates, directions, *, max_candidates=MAX_CANDIDATES):
    """Return a tuple of nondominated feasible records in original ledger order.

    Input: [{"id": str, "metrics": list[int|float], "feasible": bool}, ...].
    Direction per metric: "minimize" or "maximize". Duplicate metric vectors
    with different IDs are all retained: a tie is not strict dominance.
    Complexity: O(n^2*k) time, O(n*k) memory, with n <= max_candidates <= 4096
    and 2 <= k <= 8. The caller verifies feasibility independently.
    """
    ledger = _validated(candidates, directions, max_candidates)
    feasible = [(key, vector) for key, vector, ok in ledger if ok]
    result = []
    for index, (key, vector) in enumerate(feasible):
        if not any(
            other != index and _dominates(other_vector, vector, directions)
            for other, (_, other_vector) in enumerate(feasible)
        ):
            result.append({"id": key, "metrics": vector})
    return tuple(result)


if __name__ == "__main__":
    import json

    # Illustrative synthetic measurements only; NOT measured VANILLAJS evidence.
    trials = [
        {"id": "fast", "metrics": [10.0, 220, 4], "feasible": True},
        {"id": "balanced", "metrics": [12.0, 180, 7], "feasible": True},
        {"id": "detailed", "metrics": [16.0, 250, 10], "feasible": True},
        {"id": "inferior", "metrics": [18.0, 300, 3], "feasible": True},
        {"id": "invalid", "metrics": [8.0, 160, 9], "feasible": False},
    ]
    print(json.dumps(pareto_frontier(trials, ("minimize", "minimize", "maximize")), indent=2))
