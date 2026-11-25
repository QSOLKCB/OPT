"""OPT-HYBRID-001: finite, exact, side-effect-free synthetic execution reference.

Evidence is supplied by a trusted measurement producer; a digest is identity,
not authentication or proof. No arbitrary user callbacks, shell, or I/O.
"""
from __future__ import annotations

from concurrent.futures import ProcessPoolExecutor
from dataclasses import asdict, dataclass
from hashlib import sha256
import json
import multiprocessing
import os
import re
from time import monotonic_ns, process_time_ns

try:
    import resource
except ImportError:  # CPU accounting is unavailable for child processes here.
    resource = None

if __package__:
    from .pareto_frontier import pareto_frontier
else:
    from pareto_frontier import pareto_frontier

MAX_UNITS = 128
MAX_WORKERS = 32
MAX_STEPS = 20_000_000
MAX_TRIALS = 256
BOUNDARY = "full-work-v1"
HEX = re.compile(r"[0-9a-f]{64}")


class CorrectnessError(RuntimeError):
    """Never recover from this by silently executing another candidate."""


class BudgetError(RuntimeError):
    """No admissible choice under the declared budget."""


def integer(value, low=0, high=2**63-1):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("integer outside declared bound")
    return value


def digest(value):
    return sha256(json.dumps(value, sort_keys=True, separators=(",", ":"),
                             ensure_ascii=True, allow_nan=False).encode("ascii")).hexdigest()


def check_digest(value):
    if type(value) is not str or not HEX.fullmatch(value):
        raise ValueError("expected SHA-256 digest")


@dataclass(frozen=True)
class Unit:
    id: str
    steps: int
    dependencies: tuple[str, ...] = ()


@dataclass(frozen=True)
class Workload:
    units: tuple[Unit, ...]
    preparation: int = 0


@dataclass(frozen=True)
class Context:
    # Digests of complete caller-provided immutable manifests, not labels.
    source_commit: str
    materialized_source: str
    runtime: str
    dependencies: str
    configuration: str
    host_limits: str
    generation: str  # caller-owned measurement generation/expiry boundary


@dataclass(frozen=True)
class Plan:
    mode: str
    workers: int
    parallel_ids: tuple[str, ...] = ()

    @property
    def id(self):
        if self.mode == "SERIAL":
            return "SERIAL"
        if self.mode == "PARALLEL":
            return f"PARALLEL-{self.workers}"
        # Include the partition itself, not just the requested worker count.
        return f"HYBRID-{self.workers}-{digest(self.parallel_ids)}"


SERIAL = Plan("SERIAL", 1)


@dataclass(frozen=True)
class Sample:
    wall_ns: int
    cpu_ns: int | None
    peak_memory_bytes: int | None = None  # aggregate peak, NOT max single PID


@dataclass(frozen=True)
class Evidence:
    plan: Plan
    identity: str
    result_digest: str | None  # None means correctness not established
    samples: tuple[Sample, ...]
    boundary: str = BOUNDARY


@dataclass(frozen=True)
class Policy:
    max_workers: int = 7
    max_trials: int = 64
    min_repetitions: int = 2
    margin_bps: int = 500
    max_wall_ns: int | None = None
    max_cpu_ns: int | None = None
    max_memory_bytes: int | None = None
    # Projected live selection overhead, absent from run_verified samples.
    # Actual elapsed selection is already inside execute_selected's timer.
    common_wall_ns: int = 0
    common_cpu_ns: int = 0
    # Paid costs outside that timer AND absent from the calibration samples
    # (e.g. pre-incurred capture/calibration). Never include live selection.
    # Zero for out-of-band research or costs already inside the interval.
    external_wall_ns: int = 0
    external_cpu_ns: int = 0


def levels(workload):
    if type(workload) is not Workload or type(workload.units) is not tuple:
        raise ValueError("workload must be immutable")
    integer(len(workload.units), 0, MAX_UNITS)
    integer(workload.preparation, 0, MAX_STEPS)
    seen = set()
    total = workload.preparation
    for unit in workload.units:
        if (type(unit) is not Unit or type(unit.id) is not str or
                not re.fullmatch(r"[A-Za-z0-9_.-]{1,64}", unit.id) or unit.id in seen):
            raise ValueError("invalid or duplicate work unit")
        seen.add(unit.id)
        total += integer(unit.steps, 0, MAX_STEPS)
        if (type(unit.dependencies) is not tuple or
                len(unit.dependencies) > MAX_UNITS or
                any(type(d) is not str for d in unit.dependencies) or
                len(set(unit.dependencies)) != len(unit.dependencies)):
            raise ValueError("invalid or duplicate dependency")
    integer(total, 0, MAX_STEPS)
    if any(d not in seen for u in workload.units for d in u.dependencies):
        raise ValueError("missing dependency")
    done = set()
    result = []
    while len(done) != len(seen):
        ready = tuple(u for u in workload.units
                      if u.id not in done and all(d in done for d in u.dependencies))
        if not ready:
            raise ValueError("cyclic dependency")
        result.append(ready)
        done.update(u.id for u in ready)
    return tuple(result)


def validate_plan(workload, plan):
    if type(plan) is not Plan or type(plan.parallel_ids) is not tuple:
        raise ValueError("invalid plan")
    integer(plan.workers, 1, MAX_WORKERS)
    ids = tuple(u.id for u in workload.units)
    if plan.mode == "SERIAL" and plan == SERIAL:
        return
    if plan.mode == "PARALLEL" and plan.workers >= 2 and not plan.parallel_ids:
        return
    if (plan.mode == "HYBRID" and plan.workers >= 2 and
            all(type(i) is str for i in plan.parallel_ids) and
            0 < len(plan.parallel_ids) < len(ids) and
            tuple(i for i in ids if i in plan.parallel_ids) == plan.parallel_ids):
        return
    raise ValueError("invalid plan or hybrid partition")


def identity(workload, context, plan):
    levels(workload)
    validate_plan(workload, plan)
    if type(context) is not Context:
        raise ValueError("missing context")
    if (type(context.source_commit) is not str or
            not re.fullmatch(r"[0-9a-f]{40}", context.source_commit)):
        raise ValueError("expected source commit SHA")
    for key, value in asdict(context).items():
        if key != "source_commit":
            check_digest(value)
    return digest({"schema": BOUNDARY, "workload": asdict(workload),
                   "context": asdict(context), "plan": asdict(plan)})


def oracle(workload):
    """Independent closed-form result; no executor or iterative kernel."""
    prepared = workload.preparation * (workload.preparation - 1) // 2
    values = {}
    # Independent dependency traversal, rather than reusing execution levels.
    def value(unit):
        if unit.id not in values:
            n = unit.steps
            values[unit.id] = (n * (n - 1) * (2 * n - 1) // 6 + prepared +
                               sum(value(by_id[d]) for d in unit.dependencies))
        return values[unit.id]
    levels(workload)
    by_id = {u.id: u for u in workload.units}
    return tuple((u.id, value(u)) for u in workload.units)


def _policy(policy):
    if type(policy) is not Policy:
        raise ValueError("invalid policy")
    integer(policy.max_workers, 1, MAX_WORKERS)
    integer(policy.max_trials, 1, MAX_TRIALS)
    integer(policy.min_repetitions, 1, 16)
    integer(policy.margin_bps, 0, 9999)
    for n in (policy.common_wall_ns, policy.common_cpu_ns,
              policy.external_wall_ns, policy.external_cpu_ns):
        integer(n)
    for n in (policy.max_wall_ns, policy.max_cpu_ns, policy.max_memory_bytes):
        if n is not None:
            integer(n)


def select(workload, context, ledger, policy=Policy(), *, override=None):
    """Pure deterministic selection. Invalid ledgers never partially rank.

    Stale or incomplete evidence is ineligible, not a current failure.
    Current explicit outcome mismatch raises even for budget-rejected plans.
    """
    _policy(policy)
    serial_identity = identity(workload, context, SERIAL)
    if type(ledger) is not tuple or len(ledger) > 32:
        raise ValueError("expected bounded immutable evidence ledger")
    expected = digest(oracle(workload))
    seen = set()
    rows = []
    trials = 0
    eligible = {}
    serial_qualified = False
    for item in ledger:
        if type(item) is not Evidence or type(item.samples) is not tuple:
            raise ValueError("malformed evidence")
        current = identity(workload, context, item.plan)
        name = item.plan.id
        if name in seen:
            raise ValueError("duplicate candidate evidence")
        seen.add(name)
        check_digest(item.identity)
        if item.boundary != BOUNDARY:
            raise ValueError("incomparable accounting boundary")
        if item.result_digest is not None:
            check_digest(item.result_digest)
        integer(len(item.samples), 0, 16)
        trials += len(item.samples)
        integer(trials, 0, policy.max_trials)
        for sample in item.samples:
            if type(sample) is not Sample:
                raise ValueError("malformed measurement")
            integer(sample.wall_ns, 1)
            if sample.cpu_ns is not None:
                integer(sample.cpu_ns)
            if sample.peak_memory_bytes is not None:
                integer(sample.peak_memory_bytes)
        reason = "qualified"
        wall = cpu = memory = best = None
        if item.identity != current:
            reason = "stale identity"
        elif item.result_digest is None:
            reason = "missing correctness evidence"
        elif item.result_digest != expected:
            raise CorrectnessError(f"current evidence mismatch: {name}")
        elif len(item.samples) < policy.min_repetitions:
            reason = "insufficient repetitions"
        else:
            common_wall = policy.common_wall_ns + policy.external_wall_ns
            common_cpu = policy.common_cpu_ns + policy.external_cpu_ns
            wall = max(s.wall_ns for s in item.samples) + common_wall
            best = min(s.wall_ns for s in item.samples) + common_wall
            cpu = (max(s.cpu_ns for s in item.samples) + common_cpu
                   if all(s.cpu_ns is not None for s in item.samples) else None)
            memory = (max(s.peak_memory_bytes for s in item.samples)
                      if all(s.peak_memory_bytes is not None for s in item.samples) else None)
            if name == SERIAL.id:
                serial_qualified = True
            if item.plan.workers > policy.max_workers:
                reason = "worker budget"
            else:
                for value, bound, label in (
                    (wall, policy.max_wall_ns, "wall"),
                    (cpu, policy.max_cpu_ns, "CPU"),
                    (memory, policy.max_memory_bytes, "memory"),
                ):
                    if bound is not None and (value is None or value > bound):
                        reason = label + " budget (exceeded or unknown)"
                        break
        if reason == "qualified":
            eligible[name] = (item.plan, wall, best, cpu, memory)
        rows.append({"id": name, "identity": item.identity, "reason": reason,
                     "worst_wall_ns": wall, "best_wall_ns": best,
                     "worst_cpu_ns": cpu, "peak_memory_bytes": memory})
    rows.sort(key=lambda r: r["id"])
    # No measurement means no demonstrated compliance with metric ceilings.
    unmeasured_serial = (not serial_qualified and all(
        b is None for b in (policy.max_wall_ns, policy.max_cpu_ns, policy.max_memory_bytes)))
    serial = eligible.get(SERIAL.id)
    candidates = []
    directions = ("minimize", "maximize")
    if serial is not None:
        # Conservative comparison: worst alternative vs best serial, with
        # a predeclared margin on total paid cost; equality retains serial.
        for name, value in eligible.items():
            if name != SERIAL.id and value[1] * 10000 < serial[2] * (10000-policy.margin_bps):
                candidates.append(name)
    elif serial_qualified:
        # A measured but budget-infeasible serial path cannot be selected.
        candidates = sorted(eligible)
    # No serial evidence: do not auto-promote a noncanonical candidate.
    candidates.sort()
    # One objective definition across the complete feasible ledger.
    use_cpu = all(v[3] is not None for v in eligible.values())
    objective = "wall_ns, negative_cpu_ns" if use_cpu else "wall_ns, negative_workers"
    trials_for_pareto = [{"id": n, "metrics": [
        eligible[n][1], -eligible[n][3] if use_cpu else -eligible[n][0].workers],
        "feasible": True} for n in sorted(eligible)]
    observed_frontier = pareto_frontier(trials_for_pareto, directions)
    frontier = pareto_frontier([r for r in trials_for_pareto if r["id"] in candidates],
                               directions)
    if override is not None:
        validate_plan(workload, override)
        if override.id in eligible and eligible[override.id][0] == override:
            chosen, why = override, "explicit correctness-qualified override"
        elif override == SERIAL and unmeasured_serial:
            chosen, why = SERIAL, "explicit canonical; full-work verification required"
        else:
            raise BudgetError("override lacks current feasible correctness evidence")
    elif frontier:
        # Lexicographic after retaining the complete eligible frontier; ties
        # prefer fewer workers then stable identifier, not input order.
        best = min(frontier, key=lambda r: (r["metrics"][0], -r["metrics"][1],
                                           eligible[r["id"]][0].workers, r["id"]))
        chosen = eligible[best["id"]][0]
        why = "material lifecycle advantage" if serial else "serial exceeds budget"
    elif serial is not None or unmeasured_serial:
        chosen = SERIAL
        why = "serial: near tie or insufficient comparative evidence"
    else:
        raise BudgetError("no justified feasible canonical or alternative plan")
    return chosen, {"schema": BOUNDARY, "serial_identity": serial_identity,
                    "selected_identity": identity(workload, context, chosen),
                    "selected_plan": asdict(chosen), "reason": why,
                    "policy": asdict(policy), "objective": objective,
                    "directions": directions, "frontier": frontier,
                    "observed_frontier": observed_frontier, "candidates": rows,
                    "ledger_digest": digest([asdict(i) for i in sorted(ledger, key=lambda i: i.plan.id)])}


def _kernel(unit, prepared, parents):
    start = monotonic_ns()
    result = sum(i*i for i in range(unit.steps)) + prepared + sum(parents)
    return unit.id, result, os.getpid(), start, monotonic_ns()


def _cpu_ns():
    if resource is None:
        return None
    children = resource.getrusage(resource.RUSAGE_CHILDREN)
    return process_time_ns() + int((children.ru_utime + children.ru_stime) * 1e9)


def _stage(workload, plan):
    waves = levels(workload)
    validate_plan(workload, plan)
    prepared = sum(range(workload.preparation))  # exactly once per invocation
    values = {}
    observed = []
    parent_pid = os.getpid()
    parallel = (set(u.id for u in workload.units) if plan.mode == "PARALLEL"
                else set(plan.parallel_ids))

    def args(u):
        return (u, prepared, tuple(values[d] for d in u.dependencies))

    def accept(u, row):
        key, value, pid, start, end = row
        if key != u.id or key in values or type(value) is not int:
            raise CorrectnessError("missing, duplicate or malformed worker outcome")
        values[key] = value
        observed.append((key, pid, start, end))

    def run(pool):
        for wave in waves:
            # Serial phase and worker phase do not overlap: bounded workers,
            # no hidden extra active parent kernel and no dependency race.
            for u in wave:
                if u.id not in parallel:
                    accept(u, _kernel(*args(u)))
            pending = [(u, pool.submit(_kernel, *args(u)))
                       for u in wave if u.id in parallel]
            for u, future in pending:
                accept(u, future.result())  # no fallback on exception

    if parallel:
        with ProcessPoolExecutor(max_workers=plan.workers,
                                 mp_context=multiprocessing.get_context("spawn")) as pool:
            run(pool)
    else:
        run(None)
    output = tuple((u.id, values[u.id]) for u in workload.units)
    worker_pids = {pid for _, pid, _, _ in observed if pid != parent_pid}
    events = sorted((t, delta) for _, pid, start, end in observed
                    if pid != parent_pid and end > start
                    for t, delta in ((start, 1), (end, -1)))
    active = peak = 0
    for _, delta in events:
        active += delta
        peak = max(peak, active)
    if len(worker_pids) > plan.workers or peak > plan.workers:
        raise CorrectnessError("worker budget contradicted by observation")
    return output, {"requested_workers": plan.workers, "observed_worker_pids": sorted(worker_pids),
                    "observed_worker_task_overlap": peak,
                    "parent_units": sum(pid == parent_pid for _, pid, _, _ in observed)}


def run_verified(workload, context, plan):
    """Explicit calibration execution; never returns unverified results.

    Full work: validation/identity, preparation, pool startup, scheduling,
    execution, aggregation, pool cleanup and independent oracle. Only this
    synthetic immutable workload is supported; no externally visible effects.
    """
    start = monotonic_ns()
    cpu_start = _cpu_ns()
    key = identity(workload, context, plan)
    output, observed = _stage(workload, plan)
    if output != oracle(workload):
        raise CorrectnessError("full-work oracle mismatch; staged output discarded")
    result_digest = digest(output)
    cpu_end = _cpu_ns()
    wall = monotonic_ns() - start
    return output, Sample(wall, None if cpu_end is None else max(0, cpu_end-cpu_start)), {
        "identity": key, "result_digest": result_digest, "verified": True, **observed}


def execute_selected(workload, context, ledger, policy=Policy(), *, override=None):
    """Re-select from the current immutable inputs, then verify full work."""
    start = monotonic_ns()
    cpu_start = _cpu_ns()
    plan, receipt = select(workload, context, ledger, policy, override=override)
    # Prior peak measurements do not enforce live aggregate memory.
    if policy.max_memory_bytes is not None:
        raise BudgetError("live aggregate memory verification unavailable")
    result, sample, run = run_verified(workload, context, plan)
    if run["identity"] != receipt["selected_identity"]:
        raise CorrectnessError("execution identity mismatch")
    cpu_end = _cpu_ns()
    measured_wall = monotonic_ns() - start
    measured_cpu = (None if cpu_start is None or cpu_end is None
                    else max(0, cpu_end-cpu_start))
    wall = measured_wall + policy.external_wall_ns
    cpu = None if measured_cpu is None else measured_cpu + policy.external_cpu_ns
    if ((policy.max_wall_ns is not None and wall > policy.max_wall_ns) or
            (policy.max_cpu_ns is not None and (cpu is None or cpu > policy.max_cpu_ns))):
        raise BudgetError("actual invocation exceeded measured budget; output discarded")
    return result, receipt, {"run": run, "sample": asdict(sample),
                             "measured_wall_ns": measured_wall,
                             "measured_cpu_ns": measured_cpu,
                             "external_wall_ns": policy.external_wall_ns,
                             "external_cpu_ns": policy.external_cpu_ns,
                             "paid_wall_ns": wall, "paid_cpu_ns": cpu}
