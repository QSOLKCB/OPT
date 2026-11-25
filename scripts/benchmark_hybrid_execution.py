#!/usr/bin/env python3
"""Optional OPT-HYBRID-001 full-work characterization, never a timing gate.

Run from an immutable checkout with a trusted Python installation. Calibration
is a separate research phase; not evidence of cheap in-invocation selection.
"""
from contextlib import contextmanager
from dataclasses import asdict
from hashlib import sha256
from pathlib import Path, PurePosixPath
import argparse
import json
import os
import platform
import re
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


# Bind the process's actual cgroup hierarchy, not the conventional mount root.
V2_LIMITS = ("cpu.max", "cpu.max.burst", "cpu.weight", "cpuset.cpus",
             "cpuset.cpus.effective", "cpuset.mems", "cpuset.mems.effective",
             "memory.max", "memory.high", "memory.swap.max", "pids.max", "io.max")
V1_LIMITS = {
    "cpu": ("cpu.cfs_quota_us", "cpu.cfs_period_us", "cpu.shares"),
    "cpuset": ("cpuset.cpus", "cpuset.effective_cpus", "cpuset.mems",
               "cpuset.effective_mems"),
    "memory": ("memory.limit_in_bytes", "memory.soft_limit_in_bytes",
               "memory.memsw.limit_in_bytes", "memory.use_hierarchy"),
    "pids": ("pids.max",),
}


def _mount_path(value):
    # proc mountinfo encodes spaces, tabs, newlines and backslashes in octal.
    return re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), value)


def _absolute_path(value):
    path = PurePosixPath(value)
    if path.root != "/" or ".." in path.parts:
        raise RuntimeError("invalid or unmappable cgroup path")
    return path


def cgroup_limits(proc=Path("/proc/self")):
    """Read v2 and applicable v1 memberships, mounts and visible ancestry.

    A non-root mount exposes only a subtree; do not claim its hidden ancestors
    are unrestricted. Missing individual control files are not zero/unlimited.
    Unmapped memberships and unreadable hierarchy data fail characterization.
    """
    memberships = []
    for line in (proc / "cgroup").read_text().splitlines():
        hierarchy, controllers, member = line.split(":", 2)
        names = set(controllers.split(",")) if controllers else set()
        if hierarchy == "0" and not names:
            memberships.append(("cgroup2", (), _absolute_path(member), V2_LIMITS))
        else:
            relevant = tuple(sorted(names & V1_LIMITS.keys()))
            if relevant:
                files = tuple(sorted({f for name in relevant for f in V1_LIMITS[name]}))
                memberships.append(("cgroup", relevant, _absolute_path(member), files))

    mounts = []
    for line in (proc / "mountinfo").read_text().splitlines():
        before, after = line.split(" - ", 1)
        fields, filesystem = before.split(), after.split()
        if filesystem[0] not in ("cgroup", "cgroup2"):
            continue
        mounts.append((filesystem[0], set(filesystem[2].split(",")),
                       _absolute_path(_mount_path(fields[3])),
                       Path(_absolute_path(_mount_path(fields[4])))))

    hierarchies = []
    for kind, controllers, member, files in memberships:
        matches = [(root, mount) for fs, options, root, mount in mounts
                   if fs == kind and set(controllers) <= options
                   and member.is_relative_to(root)]
        if not matches:
            raise RuntimeError(f"no visible mount for cgroup membership {member}")
        # Prefer the mount exposing the broadest ancestry. Resolve ties
        # deterministically, but never substitute a different membership.
        root, mount = min(matches, key=lambda pair: (len(pair[0].parts), str(pair[1])))
        levels = []
        current = member
        while True:
            directory = mount / current.relative_to(root)
            if not directory.is_dir():
                raise RuntimeError(f"cgroup membership/ancestor is not accessible: {directory}")
            values = {}
            for name in files:
                try:
                    values[name] = (directory / name).read_text().strip()
                except FileNotFoundError:
                    pass  # a controller/file may not exist at this level
            levels.append({"path": str(current), "limits": values})
            if current == root:
                break
            current = current.parent
        hierarchies.append({"version": 2 if kind == "cgroup2" else 1,
                            "controllers": controllers, "membership": str(member),
                            "mount_root": str(root), "mount_point": str(mount),
                            "visible_to_namespace_root": str(root) == "/",
                            "leaf_to_mount_root": levels})
    hierarchies.sort(key=lambda item: (item["version"], item["controllers"], item["membership"]))
    return {"status": "resolved_visible" if hierarchies else "no_resource_hierarchies",
            "hierarchies": hierarchies}


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
            "cgroup": (cgroup_limits() if sys.platform.startswith("linux")
                       else {"status": "not_linux", "hierarchies": []})}
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


@contextmanager
def timed_phase(record):
    """Retain attempted cost even when the operation fails; never retry."""
    start = time.monotonic_ns()
    cpu_start = h._cpu_ns()
    record["status"] = "running"
    try:
        yield
    except BaseException as exc:
        record["status"] = "failed"
        record["error"] = {"type": type(exc).__name__, "message": str(exc)}
        raise
    else:
        record["status"] = "passed"
    finally:
        cpu_end = h._cpu_ns()
        record["wall_ns"] = time.monotonic_ns()-start
        record["cpu_ns"] = (None if cpu_start is None or cpu_end is None
                            else max(0, cpu_end-cpu_start))


def characterize(repetitions, workers, *, report=None):
    """Populate the caller's report incrementally, including on failure.

    Only a returned, fully successful report is eligible for characterization
    claims. Failed attempts carry diagnostic timings, never verified Samples.
    """
    if report is None:
        report = {}
    report.update({"schema": h.BOUNDARY, "repetitions": repetitions,
                   "requested_workers": workers, "fixtures": {},
                   "scope": "already established immutable context; out-of-band calibration; no portable crossover"})
    with timed_phase(report):
        h.integer(repetitions, 2, 8)
        h.integer(workers, 2, h.MAX_WORKERS)
        capture = report["identity_capture"] = {}
        with timed_phase(capture):
            ctx, manifests = context(str(time.time_ns()))
            report.update({"context": asdict(ctx), "manifests": manifests})
        for name, workload in fixtures().items():
            candidate_plans = plans(workload, workers)
            rows = {p.id: [] for p in candidate_plans}
            entry = report["fixtures"][name] = {
                "workload": asdict(workload), "candidates": [asdict(p) for p in candidate_plans],
                "raw": rows, "calibration": {}}
            with timed_phase(entry["calibration"]):
                # Deterministic rotation limits fixed-order bias; retain every attempt.
                for repetition in range(repetitions):
                    offset = repetition % len(candidate_plans)
                    order = candidate_plans[offset:] + candidate_plans[:offset]
                    for plan in order:
                        row = {"repetition": repetition+1, "attempt": {},
                               "sample": None, "execution": None, "rss_observation": None}
                        rows[plan.id].append(row)
                        with timed_phase(row["attempt"]):
                            _, sample, receipt = h.run_verified(workload, ctx, plan)
                            row.update({"sample": asdict(sample), "execution": receipt})
                            row["rss_observation"] = rss_observation()
                # Reached only if every calibration attempt succeeded.
                ledger = tuple(h.Evidence(plan, h.identity(workload, ctx, plan),
                                          rows[plan.id][0]["execution"]["result_digest"],
                                          tuple(h.Sample(**r["sample"]) for r in rows[plan.id]))
                               for plan in candidate_plans)
            policy = h.Policy(max_workers=workers, min_repetitions=repetitions,
                              max_trials=len(candidate_plans)*repetitions, margin_bps=500)
            entry["selection_attempt"] = {}
            with timed_phase(entry["selection_attempt"]):
                _, entry["selection"] = h.select(workload, ctx, ledger, policy)
            entry["selection_wall_ns"] = entry["selection_attempt"]["wall_ns"]
            # The paid live receipt includes selection + execution + oracle;
            # capture and calibration are separately retained research costs.
            entry["selected_execution_attempt"] = {}
            with timed_phase(entry["selected_execution_attempt"]):
                _, _, entry["selected_full_execution"] = h.execute_selected(workload, ctx, ledger, policy)
        # Endpoint checks are diagnostics only, not A-B-A witnesses.
        report["endpoint_check"] = {}
        with timed_phase(report["endpoint_check"]):
            for p, expected in manifests["source"].items():
                if file_digest(ROOT / p) != expected:
                    raise RuntimeError("materialized source changed; discard benchmark")
            if sys.platform.startswith("linux") and cgroup_limits() != manifests["host"]["cgroup"]:
                raise RuntimeError("cgroup resource identity changed; discard benchmark")
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--repetitions", type=int, default=2)
    parser.add_argument("--workers", type=int, default=7)
    args = parser.parse_args()
    report = {}
    try:
        characterize(args.repetitions, args.workers, report=report)
    finally:
        # Flush partial JSON before the original exception leaves main.
        print(json.dumps(report, sort_keys=True, indent=2), flush=True)


if __name__ == "__main__":
    main()
