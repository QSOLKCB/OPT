#!/usr/bin/env python3
"""OPT-DB-001: bounded, observation-only SQLite query and index audit.

No SQL or database mutations are authorized. A normal SQLite read-only WAL
connection may nevertheless create -wal/-shm coordination files; use the
explicit immutable mode only on a frozen standalone snapshot in DELETE mode.
"""
from __future__ import annotations

import argparse
import base64
import hashlib
import json
import math
import os
from pathlib import Path
import re
import sqlite3
import stat
import statistics
import sys
import time

SCHEMA = "opt.sqlite.workload.v1"
REPORT = "opt.sqlite.observation.v1"
MAX_WORKLOAD_BYTES = 32768
MAX_QUERIES = 16
MAX_SQL_BYTES = 2048
MAX_PARAMS = 16
MAX_ROWS = 512
MAX_SAMPLES = 5
MAX_BUDGET = 60.0
NAME = re.compile(r"[A-Za-z][A-Za-z0-9_-]{0,63}\Z")
START = re.compile(r"\s*(?:SELECT|WITH)\b", re.IGNORECASE)
FUNCTIONS = frozenset({
    "abs", "avg", "coalesce", "count", "hex", "ifnull", "length",
    "lower", "max", "min", "round", "substr", "sum", "trim",
    "typeof", "upper",
})


class ObservationError(ValueError):
    """Invalid, unsafe or unbounded observation contract."""


def canonical(value):
    return (json.dumps(value, sort_keys=True, separators=(",", ":"),
                       ensure_ascii=True, allow_nan=False) + "\n").encode("ascii")


def digest(raw):
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def no_duplicates(pairs):
    result = {}
    for k, v in pairs:
        if k in result:
            raise ObservationError("duplicate_json_key")
        result[k] = v
    return result


def strict_json(raw):
    try:
        return json.loads(
            raw, object_pairs_hook=no_duplicates,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ObservationError("nonfinite_json"))
        )
    except (UnicodeError, RecursionError, json.JSONDecodeError) as exc:
        raise ObservationError("malformed_json") from None


def safe_existing_file(path):
    raw = Path(path).expanduser()
    if ".." in raw.parts:
        raise ObservationError("path_traversal")
    path = raw.absolute()
    for part in (path, *path.parents):
        try:
            mode = part.lstat().st_mode
        except FileNotFoundError:
            raise ObservationError("missing_path") from None
        if stat.S_ISLNK(mode):
            raise ObservationError("symlink_path")
    if not stat.S_ISREG(path.stat().st_mode):
        raise ObservationError("not_regular_file")
    return path


def read_workload(path):
    path = safe_existing_file(path)
    flags = os.O_RDONLY | getattr(os, "O_NOFOLLOW", 0)
    fd = os.open(path, flags)
    with os.fdopen(fd, "rb") as inp:
        if not stat.S_ISREG(os.fstat(inp.fileno()).st_mode):
            raise ObservationError("not_regular_file")
        raw = inp.read(MAX_WORKLOAD_BYTES + 1)
    if len(raw) > MAX_WORKLOAD_BYTES:
        raise ObservationError("workload_size_limit")
    obj = strict_json(raw)
    if type(obj) is not dict or set(obj) != {"schema", "queries"} or obj["schema"] != SCHEMA:
        raise ObservationError("invalid_workload_schema")
    queries = obj["queries"]
    if type(queries) is not list or not 1 <= len(queries) <= MAX_QUERIES:
        raise ObservationError("invalid_query_count")
    seen = set()
    for query in queries:
        if type(query) is not dict or set(query) != {"name", "sql", "params"}:
            raise ObservationError("invalid_query_fields")
        name, sql, params = query["name"], query["sql"], query["params"]
        if type(name) is not str or NAME.fullmatch(name) is None or name in seen:
            raise ObservationError("invalid_query_name")
        seen.add(name)
        if (type(sql) is not str or len(sql.encode("utf-8")) > MAX_SQL_BYTES or
                ";" in sql or "--" in sql or "/*" in sql or
                START.match(sql) is None):
            raise ObservationError("query_must_be_bounded_select")
        if type(params) is not list or len(params) > MAX_PARAMS:
            raise ObservationError("invalid_parameters")
        for param in params:
            if param is None or type(param) in (int, str):
                if type(param) is str and len(param.encode("utf-8")) > 1024:
                    raise ObservationError("parameter_limit")
                if type(param) is int and not -(1 << 63) <= param < (1 << 63):
                    raise ObservationError("parameter_integer_limit")
            elif type(param) is float and math.isfinite(param):
                pass
            else:
                raise ObservationError("invalid_parameter_type")
    return obj, raw


def read_only_authorizer(action, a, b, _db, _trigger):
    if action in (sqlite3.SQLITE_READ, sqlite3.SQLITE_SELECT):
        return sqlite3.SQLITE_OK
    if action == sqlite3.SQLITE_FUNCTION and isinstance(b, str) and b.lower() in FUNCTIONS:
        return sqlite3.SQLITE_OK
    return sqlite3.SQLITE_DENY


def schema_inventory(conn):
    objects = conn.execute(
        "SELECT type, name, tbl_name, sql FROM sqlite_schema "
        "WHERE name NOT GLOB 'sqlite_*' ORDER BY type, name"
    ).fetchall()
    schema_hash = digest(canonical(objects))
    indexes = []
    for typ, name, table, _sql in objects:
        if typ != "index":
            continue
        # PRAGMA identifier quoting uses double quotes, never string SQL input.
        quoted = name.replace('"', '""')
        cols = conn.execute(f'PRAGMA index_xinfo("{quoted}")').fetchall()
        indexes.append({
            "name": name, "table": table,
            "columns": [
                {"position": x[0], "column": x[2], "descending": bool(x[3]),
                 "collation": x[4], "key": bool(x[5])} for x in cols
            ],
        })
    meta = {
        "schema_sha256": schema_hash,
        "object_count": len(objects),
        "tables": sorted(row[1] for row in objects if row[0] == "table"),
        "indexes": indexes,
        "page_count": conn.execute("PRAGMA page_count").fetchone()[0],
        "freelist_count": conn.execute("PRAGMA freelist_count").fetchone()[0],
        "page_size": conn.execute("PRAGMA page_size").fetchone()[0],
        "journal_mode": conn.execute("PRAGMA journal_mode").fetchone()[0],
        "schema_version": conn.execute("PRAGMA schema_version").fetchone()[0],
    }
    return meta


def encoded_cell(value):
    if value is None:
        return ["null", None]
    if type(value) is int:
        return ["integer", str(value)]
    if type(value) is float:
        return ["float", value.hex()]
    if type(value) is str:
        return ["text", value]
    if type(value) is bytes:
        return ["blob", base64.b64encode(value).decode("ascii")]
    raise ObservationError("unsupported_sqlite_result_type")


def limited_run(conn, sql, params, max_rows, deadline):
    h = hashlib.sha256()
    rows = 0
    conn.set_progress_handler(lambda: int(time.monotonic() >= deadline), 1000)
    start = time.perf_counter_ns()
    try:
        cursor = conn.execute(sql, params)
        try:
            for row in cursor:
                if time.monotonic() >= deadline:
                    raise ObservationError("evaluation_deadline")
                rows += 1
                if rows > max_rows:
                    raise ObservationError("row_count_limit")
                h.update(canonical([encoded_cell(x) for x in row]))
        finally:
            cursor.close()
    except sqlite3.OperationalError as exc:
        if "interrupted" in str(exc).lower():
            raise ObservationError("evaluation_deadline") from None
        raise
    finally:
        conn.set_progress_handler(None, 0)
    elapsed = (time.perf_counter_ns() - start) // 1000
    return {"row_count": rows, "result_sha256": "sha256:" + h.hexdigest(),
            "elapsed_us": elapsed}


def inspect(database, workload, *, measure=False, samples=3, max_rows=128,
            budget_seconds=10.0, immutable_snapshot=False):
    if type(samples) is not int or not 1 <= samples <= MAX_SAMPLES:
        raise ObservationError("invalid_sample_count")
    if type(max_rows) is not int or not 1 <= max_rows <= MAX_ROWS:
        raise ObservationError("invalid_row_budget")
    if not isinstance(budget_seconds, (float, int)) or not math.isfinite(
            budget_seconds) or not 0 < budget_seconds <= MAX_BUDGET:
        raise ObservationError("invalid_time_budget")
    db = safe_existing_file(database)
    if immutable_snapshot and any(Path(str(db) + suffix).exists()
                                  for suffix in ("-wal", "-shm", "-journal")):
        raise ObservationError("snapshot_has_sidecars")
    work, work_bytes = read_workload(workload)
    uri = db.as_uri() + "?mode=ro" + ("&immutable=1" if immutable_snapshot else "")
    conn = sqlite3.connect(uri, uri=True, timeout=2.0, isolation_level=None)
    deadline = time.monotonic() + budget_seconds
    try:
        conn.enable_load_extension(False)
        conn.execute("PRAGMA query_only=ON")
        conn.execute("PRAGMA trusted_schema=OFF")
        if hasattr(conn, "setlimit"):
            conn.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, 65536)
            conn.setlimit(sqlite3.SQLITE_LIMIT_SQL_LENGTH, 4096)
        info = schema_inventory(conn)
        if immutable_snapshot and info["journal_mode"].lower() == "wal":
            raise ObservationError("mutable_wal_not_immutable_snapshot")
        original_version = conn.execute("PRAGMA data_version").fetchone()[0]
        conn.set_authorizer(read_only_authorizer)
        results = []
        for query in work["queries"]:
            if time.monotonic() >= deadline:
                raise ObservationError("observation_deadline")
            sql, params = query["sql"], query["params"]
            # EXPLAIN QUERY PLAN compiles but does not execute the SELECT.
            plan = conn.execute("EXPLAIN QUERY PLAN " + sql, params).fetchall()
            if len(plan) > 128:
                raise ObservationError("query_plan_size_limit")
            details = [str(p[3]) for p in plan]
            result = {
                "name": query["name"],
                "query_sha256": digest(canonical(query)),
                "plan": [{"id": p[0], "parent": p[1], "detail": p[3]} for p in plan],
                "advisories": [
                    "Review scan against real table cardinality; a scan can be optimal."
                ] if any("SCAN " in d.upper() for d in details) else [],
                "execution": "not_executed",
            }
            if measure:
                observations = []
                for _ in range(samples):
                    if time.monotonic() >= deadline:
                        raise ObservationError("observation_deadline")
                    observations.append(limited_run(
                        conn, sql, params, max_rows,
                        min(deadline, time.monotonic() + 3.0)
                    ))
                if len({(x["row_count"], x["result_sha256"]) for x in observations}) != 1:
                    raise ObservationError("nonrepeatable_results")
                result["execution"] = {
                    "samples": observations,
                    "median_us": statistics.median(x["elapsed_us"] for x in observations),
                    "scope": "bounded_read_only_baseline_not_optimization_speedup",
                }
            results.append(result)
        conn.set_authorizer(None)
        if conn.execute("PRAGMA data_version").fetchone()[0] != original_version:
            raise ObservationError("database_changed_during_observation")
        return {
            "schema": REPORT,
            "environment": {
                "sqlite_version": sqlite3.sqlite_version,
                "python_version": sys.version.split()[0],
                "database_mode": "immutable_standalone_snapshot" if immutable_snapshot
                                 else "locking_aware_read_only",
                "main_file_bytes_at_start": db.stat().st_size,
            },
            "workload_sha256": digest(work_bytes),
            "database": info,
            "queries": results,
            "classification": "OBSERVED_LOCAL_BASELINE_NOT_CERTIFIED_OPTIMIZATION",
            "writes_authorized": False,
        }
    finally:
        conn.close()


def save_report(path, report):
    raw_path = Path(path).expanduser()
    if ".." in raw_path.parts:
        raise ObservationError("path_traversal")
    path = raw_path.absolute()
    if path.is_symlink() or path.exists():
        raise ObservationError("report_destination_exists")
    parent = path.parent
    info = parent.lstat()
    if (not stat.S_ISDIR(info.st_mode) or
            (os.name == "posix" and
             (info.st_uid != os.geteuid() or stat.S_IMODE(info.st_mode) & 0o077))):
        raise ObservationError("private_output_directory_required")
    fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL |
                 getattr(os, "O_NOFOLLOW", 0), 0o600)
    raw = canonical(report)
    with os.fdopen(fd, "wb") as out:
        out.write(raw)
        out.flush()
        os.fsync(out.fileno())
    if hasattr(os, "O_DIRECTORY"):
        parent_fd = os.open(parent, os.O_RDONLY | os.O_DIRECTORY)
        try:
            os.fsync(parent_fd)
        finally:
            os.close(parent_fd)
    return digest(raw)


def main(argv=None):
    ap = argparse.ArgumentParser(description="OPT-DB-001 SQLite observation (no DDL or DML)")
    ap.add_argument("--db", required=True, type=Path)
    ap.add_argument("--workload", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--measure", action="store_true",
                    help="execute bounded SELECT baselines; off by default")
    ap.add_argument("--samples", type=int, default=3)
    ap.add_argument("--max-rows", type=int, default=128)
    ap.add_argument("--budget-seconds", type=float, default=10.0)
    ap.add_argument("--immutable-snapshot", action="store_true",
                    help="ONLY for frozen standalone DELETE-journal copies")
    args = ap.parse_args(argv)
    try:
        report = inspect(args.db, args.workload, measure=args.measure,
                         samples=args.samples, max_rows=args.max_rows,
                         budget_seconds=args.budget_seconds,
                         immutable_snapshot=args.immutable_snapshot)
        identity = save_report(args.output, report)
        print("report_identity=" + identity)
        print("query_count=" + str(len(report["queries"])))
        print("measure=" + str(args.measure).lower())
        print("writes_authorized=false")
    except (ObservationError, OSError, sqlite3.Error, UnicodeError) as exc:
        ap.exit(2, "OPT-DB-001: " + type(exc).__name__ + ": " +
                str(exc)[:140] + "\n")


if __name__ == "__main__":
    main()
