#!/usr/bin/env python3
"""Optional OPT-HYBRID-001 full-work characterization, never a timing gate.

Run from an immutable checkout with a trusted Python installation. Calibration
is a separate research phase; not evidence of cheap in-invocation selection.
"""
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path
import argparse
import json
import os
import platform
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "examples"))
import hybrid_execution as h


def fixtures():
    def units(steps):
        return tuple(h.Unit("u"+str(i), n) for i, n in enumerate(steps))
    return {
        "small": h.Workload(units([20]*8)),
        "large_cpu": h.Workload(units([1_000_000]*8)),
        "mixed": h.Workload(units([20, 500_000, 30, 700_000, 40, 900_000, 50, 600_000])),
        "preparation": h.Workload(units([20]*8), 2_000_000),
        "skewed": h.Workload(units([10, 10, 10, 10, 10, 10, 10, 3_000_000])),
        "dependencies": h.Workload((
            h.Unit("join", 100, ("left", "right")),
            h.Unit("left", 500_000, ("root",)),
            h.Unit("right", 500_000, ("root",)),
            h.Unit("root", 100), h.Unit("independent", 500_000))),
    }


def plans(workload, max_workers):
    # Declared experiment partitions, not an inferred portable crossover.
    ids = tuple(u.id for u in workload.units
                if not u.dependencies and u.steps >= 500_000)
    if not ids or len(ids) == len(workload.units):
        ids = tuple(u.id for u in workload.units[::2])
    counts = sorted({n for n in (2, 4, 7, max_workers) if n <= max_workers})
    return (h.SERIAL, *(h.Plan("PARALLEL", n) for n in counts),
            h.Plan("HYBRID", max_workers, ids))


def file_digest(path):
    with Path(path).open("rb") as handle:
        return sha256(handle.read()).hexdigest()


def context(generation):
    """Capture applicable manifests; assume immutable files/runtime for the run."""
    commit = subprocess.check_output(["git", "rev-parse", "HEAD"], cwd=ROOT,
                                     text=True).strip()
    source = {p: file_digest(ROOT / p) for p in (
        "examples/hybrid_execution.py", "examples/pareto_frontier.py",
        "scripts/benchmark_hybrid_execution.py")}
    runtime = {"version": sys.version, "implementation": platform.python_implementation(),
               "executable": str(Path(sys.executable).resolve()),
               "executable_sha256": file_digest(sys.executable),
               "flags": str(sys.flags), "platform": platform.platform()}
    # No third-party packages or plugins are used. Bind the trusted stdlib
    # installation via interpreter identity and the loaded stdlib modules.
    dependencies = {}
    for name, module in sorted(tuple(sys.modules.items())):
        path = getattr(module, "__file__", None)
        if path and Path(path).is_file() and not name.startswith(("hybrid_execution", "pareto_frontier")):
            dependencies[name] = {"path": path, "sha256": file_digest(path)}
    config = {"start_method": "spawn", "boundary": h.BOUNDARY,
              "isolated": bool(sys.flags.isolated), "environment": {
                  k: os.environ.get(k) for k in ("PYTHONHASHSEED", "PYTHONPATH", "PYTHONHOME",
                                                 "OMP_NUM_THREADS", "MKL_NUM_THREADS")}}
    host = {"machine": platform.machine(), "processor": platform.processor(),
            "logical_cpus": os.cpu_count(), "affinity": (
                sorted(os.sched_getaffinity(0)) if hasattr(os, "sched_getaffinity") else None),
            "cgroup": {}}
    for name in ("cpu.max", "cpuset.cpus.effective", "memory.max", "pids.max"):
        path = Path("/sys/fs/cgroup") / name
        if path.is_file():
            host["cgroup"][name] = path.read_text().strip()
    if h.resource is not None:
        host["rlimits"] = {name: h.resource.getrlimit(getattr(h.resource, name))
                           for name in ("RLIMIT_CPU", "RLIMIT_AS", "RLIMIT_NPROC", "RLIMIT_NOFILE")
                           if hasattr(h.resource, name)}
    manifests = {"source": source, "runtime": runtime, "dependencies": dependencies,
                 "configuration": config, "host": host, "generation": generation}
    identity = h.Context(commit, h.digest(source), h.digest(runtime), h.digest(dependencies),
                         h.digest(config), h.digest(host), h.digest(generation))
    return identity, manifests


def rss_observation():
    if h.resource is None:
        return None
    return {"self_maxrss_native": h.resource.getrusage(h.resource.RUSAGE_SELF).ru_maxrss,
            "children_maxrss_native": h.resource.getrusage(h.resource.RUSAGE_CHILDREN).ru_maxrss,
            "scope": "cumulative process high-water marks; not aggregate per-sample peak",
            "units": "bytes" if sys.platform == "darwin" else "KiB on Linux; platform-native elsewhere"}


def characterize(repetitions, workers):
    h.integer(repetitions, 2, 8)
    h.integer(workers, 2, h.MAX_WORKERS)
    # An identity generation is fresh for each experiment; receipt
    # determinism is with respect to the complete supplied ledger.
    capture_start = time.monotonic_ns()
    capture_cpu = h._cpu_ns()
    ctx, manifests = context(str(time.time_ns()))
    capture_end_cpu = h._cpu_ns()
    capture = {"wall_ns": time.monotonic_ns()-capture_start,
               "cpu_ns": None if capture_cpu is None else capture_end_cpu-capture_cpu}
    report = {"schema": h.BOUNDARY, "context": asdict(ctx), "manifests": manifests,
              "identity_capture": capture, "repetitions": repetitions,
              "scope": "already established immutable context; out-of-band calibration; no portable crossover",
              "fixtures": {}}
    for name, workload in fixtures().items():
        candidate_plans = plans(workload, workers)
        rows = {p.id: [] for p in candidate_plans}
        calibration_start = time.monotonic_ns()
        calibration_cpu = h._cpu_ns()
        # Deterministic rotation limits fixed-order bias; retain every sample.
        for repetition in range(repetitions):
            order = candidate_plans[repetition % len(candidate_plans):] + candidate_plans[:repetition % len(candidate_plans)]
            for plan in order:
                _, sample, receipt = h.run_verified(workload, ctx, plan)
                rows[plan.id].append({"sample": asdict(sample), "execution": receipt,
                                      "rss_observation": rss_observation()})
        ledger = tuple(h.Evidence(plan, h.identity(workload, ctx, plan),
                                  rows[plan.id][0]["execution"]["result_digest"],
                                  tuple(h.Sample(**r["sample"]) for r in rows[plan.id]))
                       for plan in candidate_plans)
        cpu_end = h._cpu_ns()
        calibration = {"wall_ns": time.monotonic_ns()-calibration_start,
                       "cpu_ns": None if calibration_cpu is None else cpu_end-calibration_cpu}
        policy = h.Policy(max_workers=workers, min_repetitions=repetitions,
                          max_trials=len(candidate_plans)*repetitions, margin_bps=500)
        selection_start = time.monotonic_ns()
        _, receipt = h.select(workload, ctx, ledger, policy)
        selection_wall = time.monotonic_ns()-selection_start
        # Also execute the selected full workload. The paid live selection
        # receipt includes selection + execution + oracle; calibration and
        # source capture are separately retained as research costs.
        _, _, selected = h.execute_selected(workload, ctx, ledger, policy)
        report["fixtures"][name] = {
            "workload": asdict(workload), "candidates": [asdict(p) for p in candidate_plans],
            "raw": rows, "calibration": calibration, "selection_wall_ns": selection_wall,
            "selection": receipt, "selected_full_execution": selected}
    # Detect endpoint changes as a diagnostic only (not an A-B-A witness).
    for p, expected in manifests["source"].items():
        if file_digest(ROOT / p) != expected:
            raise RuntimeError("materialized source changed; discard benchmark")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--workers", type=int, default=7)
    args = parser.parse_args()
    print(json.dumps(characterize(args.repetitions, args.workers), sort_keys=True, indent=2))


if __name__ == "__main__":
    main()
