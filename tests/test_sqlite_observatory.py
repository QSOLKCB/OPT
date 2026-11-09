"""OPT-DB-001: exact SQLite observation boundaries on synthetic data only."""
from __future__ import annotations

from contextlib import closing
import hashlib
import importlib.util
import json
import os
from pathlib import Path
import sqlite3
import tempfile
import unittest

ROOT = Path(__file__).resolve().parents[1]


def import_script(name, filename):
    spec = importlib.util.spec_from_file_location(name, ROOT / "scripts" / filename)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


observe = import_script("opt_db_observe", "inspect_sqlite.py")
fixture = import_script("opt_db_fixture", "create_sqlite_fixture.py")
EXAMPLE = ROOT / "examples" / "sqlite_workload_v1.json"


class SQLiteObservatoryContracts(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.db = self.root / "fixture.db"
        fixture.create_fixture(self.db)

    def tearDown(self):
        self.temp.cleanup()

    def workload(self, queries):
        path = self.root / ("work-" + str(len(list(self.root.glob("work-*")))) + ".json")
        path.write_bytes(observe.canonical({"schema": observe.SCHEMA, "queries": queries}))
        return path

    def q(self, sql, params=None, name="trial"):
        return {"name": name, "sql": sql, "params": [] if params is None else params}

    def test_explain_only_never_executes_user_query_or_changes_main_db_bytes(self):
        before = hashlib.sha256(self.db.read_bytes()).hexdigest()
        self.assertFalse((self.root / "fixture.db-wal").exists())
        report = observe.inspect(self.db, EXAMPLE)
        self.assertEqual(report["schema"], observe.REPORT)
        self.assertFalse(report["writes_authorized"])
        self.assertEqual(report["classification"],
                         "OBSERVED_LOCAL_BASELINE_NOT_CERTIFIED_OPTIMIZATION")
        self.assertEqual(len(report["queries"]), 4)
        self.assertTrue(all(x["execution"] == "not_executed" for x in report["queries"]))
        self.assertTrue(all(isinstance(x["plan"], list) for x in report["queries"]))
        self.assertIn("messages_by_conversation",
                      [x["name"] for x in report["database"]["indexes"]])
        self.assertEqual(report["database"]["journal_mode"], "delete")
        self.assertEqual(before, hashlib.sha256(self.db.read_bytes()).hexdigest())
        self.assertFalse((self.root / "fixture.db-wal").exists())

    def test_bounded_measurement_hashes_exact_rows_without_exporting_them(self):
        report = observe.inspect(self.db, EXAMPLE, measure=True, samples=3,
                                 max_rows=128, budget_seconds=8)
        for item in report["queries"]:
            measurement = item["execution"]
            self.assertEqual(len(measurement["samples"]), 3)
            self.assertEqual(len({x["result_sha256"] for x in measurement["samples"]}), 1)
            self.assertGreaterEqual(measurement["median_us"], 0)
            self.assertNotIn("synthetic record", json.dumps(item))
        self.assertTrue(any("scan" in x.lower() for item in report["queries"]
                            for x in item["advisories"]))

    def test_sql_write_and_ddl_attempts_refused_before_execution(self):
        for sql in (
            "DELETE FROM messages", "DROP TABLE messages",
            "PRAGMA journal_mode=OFF", "INSERT INTO messages VALUES (1)",
            "UPDATE conversations SET consent=0",
            "SELECT 1; DROP TABLE messages", "SELECT 1 -- and trailing comment",
            "SELECT load_extension('x')", "SELECT random()",
        ):
            with self.subTest(sql=sql):
                path = self.workload([self.q(sql)])
                if sql.startswith("SELECT ") and ";" not in sql and "--" not in sql:
                    with self.assertRaises(sqlite3.DatabaseError):
                        observe.inspect(self.db, path, measure=True)
                else:
                    with self.assertRaises(observe.ObservationError):
                        observe.inspect(self.db, path, measure=True)
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(conn.execute("SELECT count(*) FROM messages").fetchone()[0],
                             40 * 12)

    def test_query_workload_validation_duplicate_fields_and_limits(self):
        for raw in (
            b'{"schema":"opt.sqlite.workload.v1","queries":[]}',
            b'{"schema":"opt.sqlite.workload.v1","queries":[],"queries":[]}',
            b'{"schema":"opt.sqlite.workload.v1","queries":NaN}',
            b'{"schema":"opt.sqlite.workload.v1","queries":[{"name":"n","sql":"SELECT 1","params":[true]}]}',
        ):
            with self.subTest(raw=raw):
                path = self.root / "invalid.json"
                path.write_bytes(raw)
                with self.assertRaises(observe.ObservationError):
                    observe.inspect(self.db, path)
        q = self.q("SELECT count(*) FROM messages", name="many")
        path = self.workload([q] * 2)
        with self.assertRaisesRegex(observe.ObservationError, "invalid_query_name"):
            observe.inspect(self.db, path)
        path = self.workload([self.q("SELECT 1", ["x" * 1025])])
        with self.assertRaisesRegex(observe.ObservationError, "parameter_limit"):
            observe.inspect(self.db, path)

    def test_no_partial_benchmark_pass_on_row_budget_overflow(self):
        path = self.workload([
            self.q("SELECT message_id FROM messages ORDER BY message_id")
        ])
        with self.assertRaisesRegex(observe.ObservationError, "row_count_limit"):
            observe.inspect(self.db, path, measure=True, max_rows=3)

    def test_measurement_and_global_budgets_reject_invalid_values(self):
        for kwargs in ({"samples": 0}, {"samples": 6},
                       {"max_rows": 0}, {"max_rows": 513},
                       {"budget_seconds": 0}, {"budget_seconds": 61},
                       {"budget_seconds": float("inf")}):
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(observe.ObservationError):
                    observe.inspect(self.db, EXAMPLE, **kwargs)

    def test_output_private_exclusive_and_no_source_data_in_report(self):
        report = observe.inspect(self.db, EXAMPLE, measure=True)
        output = self.root / "report.json"
        identity = observe.save_report(output, report)
        self.assertEqual(identity, observe.digest(output.read_bytes()))
        self.assertEqual(output.stat().st_mode & 0o077, 0)
        self.assertNotIn("synthetic record", output.read_text())
        self.assertNotIn(str(self.db), output.read_text())
        with self.assertRaisesRegex(observe.ObservationError, "report_destination_exists"):
            observe.save_report(output, report)
        other = self.root / "other"
        other.mkdir(mode=0o700)
        other.chmod(0o777)
        with self.assertRaisesRegex(observe.ObservationError, "private_output_directory_required"):
            observe.save_report(other / "report.json", report)

    def test_symlink_database_and_workload_rejected(self):
        other = self.root / "symlink.db"
        other.symlink_to(self.db)
        with self.assertRaisesRegex(observe.ObservationError, "symlink_path"):
            observe.inspect(other, EXAMPLE)
        workload_link = self.root / "work-link.json"
        workload_link.symlink_to(EXAMPLE)
        with self.assertRaisesRegex(observe.ObservationError, "symlink_path"):
            observe.inspect(self.db, workload_link)

    def test_standalone_snapshot_mode_rejects_wal_and_sidecars(self):
        report = observe.inspect(self.db, EXAMPLE, immutable_snapshot=True)
        self.assertEqual(report["environment"]["database_mode"],
                         "immutable_standalone_snapshot")
        with closing(sqlite3.connect(self.db)) as writer:
            writer.execute("PRAGMA journal_mode=WAL")
            writer.execute(
                "INSERT INTO conversations VALUES ('new','now','now',1)"
            )
            writer.commit()
            with self.assertRaises(observe.ObservationError):
                observe.inspect(self.db, EXAMPLE, immutable_snapshot=True)
        self.assertEqual(
            observe.inspect(self.db, EXAMPLE)["environment"]["database_mode"],
            "locking_aware_read_only"
        )

    def test_fixture_is_synthetic_and_refuses_overwrite(self):
        with closing(sqlite3.connect(self.db)) as conn:
            self.assertEqual(
                conn.execute("SELECT count(*) FROM conversations").fetchone()[0], 40
            )
            self.assertEqual(conn.execute("PRAGMA quick_check").fetchone()[0], "ok")
        before = self.db.read_bytes()
        with self.assertRaises(FileExistsError):
            fixture.create_fixture(self.db)
        self.assertEqual(self.db.read_bytes(), before)

    def test_result_digest_distinguishes_bytes_text_and_integer(self):
        items = [observe.encoded_cell(x) for x in (None, b"1", "1", 1, 1.0)]
        self.assertEqual(len({json.dumps(x) for x in items}), len(items))


if __name__ == "__main__":
    unittest.main()
