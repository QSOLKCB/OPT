# SQLite query-planning and safe-observation source notes

**Status:** reviewed reference documentation, 9 November 2026. OPT-DB-001 implements a first-party Python standard-library observatory rather than importing an external optimizer.

## Authoritative upstream references

- SQLite project, [EXPLAIN QUERY PLAN](https://www.sqlite.org/eqp.html): the reported detail format is for human inspection, can change between SQLite releases and must not be treated as a stable bytecode/interface or correctness proof.
- SQLite project, [EXPLAIN statement](https://www.sqlite.org/lang_explain.html): EXPLAIN affects statement execution but some PRAGMAs have preparation-time effects, so untrusted arbitrary SQL is **not** made safe merely by prefixing EXPLAIN.
- SQLite project, [PRAGMA query_only](https://www.sqlite.org/pragma.html#pragma_query_only): connection-level prohibition of CREATE/DELETE/DROP/INSERT/UPDATE is useful defense in depth, but does not make a database physically immutable or prevent all checkpoint behavior.
- SQLite project, [WAL read-only behavior](https://www.sqlite.org/wal.html): read-only WAL opening may create -wal/-shm coordination files; immutable mode is not suitable for an actively mutated database.
- Python, [sqlite3 authorizer and progress handler](https://docs.python.org/3/library/sqlite3.html): the authorizer rejects restricted operations at compilation/execution boundaries; the progress handler interrupts long-running SQLite VM operations but is not an independent wall-clock process kill.

## OPT evidence boundary

The source mechanism consists of: deny-by-default SQL admission, observer-only plan inspection, bounded optional SELECT measurements, private exact result digests and explicit refusal to promote schema changes. The official sources define SQLite behavior but do **not** prove the OPT program immune to all path/engine attacks or establish a universal index benefit.

The independent adapter code and synthetic benchmark are maintained in this repository under Apache-2.0. Trinite's SQLite PR #145 informs the need for WAL-safe boundaries, but no private Trinite data, model output, schema change or other third-party implementation code is imported.

**Future phases:** OPT-DB-002 may create indexes **only on disposable, verified SQLite snapshots** and require exact query equivalence plus measured write/storage penalties. OPT-DB-003 would propose reviewed migrations and deterministic rollback; those are not implemented by this record.
