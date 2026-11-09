# OPT-DB-001 — Evidence-gated SQLite observatory

**Status:** Implemented reference; read-only software conformance, no target speedup established
**Domains:** SQLite query planning, database indexing, bounded diagnostic measurement, storage and working-set inspection

## Source evidence

- Repository: `QSOLKCB/OPT`, implemented independently in [scripts/inspect_sqlite.py](../scripts/inspect_sqlite.py), [synthetic fixture](../scripts/create_sqlite_fixture.py), [sample workload](../examples/sqlite_workload_v1.json), and [offline conformance tests](../tests/test_sqlite_observatory.py).
- Source base: OPT main commit `7556dd36acd53ed3ed538fd03b1db44e5c1ec869`; the PR merge head is the definitive new implementation identity.
- Source note: [SQLite query planning and WAL boundaries](../sources/SQLITE-QUERY-PLANNING.md) with official SQLite and Python documentation.
- Target inspiration: `QSOLKCB/Trinite`, standalone SQLite adapter reviewed through PRs #144 and #145. No target database is bundled, accessed or changed by this OPT implementation.
- Licensing: Apache-2.0 OPT first-party implementation using only Python standard-library sqlite3; this does not copy SQLite engine internals.

### Evidence scope

- Computational model: the installed host SQLite query planner, Python 3.11+ sqlite3 bindings and a bounded query workload; query plans are engine-version-dependent diagnostics, not semantic proofs.
- Hypotheses: owner-supplied, inspectable SQLite databases and finite read-only SELECT workloads; no unsupported extension functions, write operations, schema migrations or untrusted cross-host files.
- Guarantee: every accepted statement is compiled under SQLite read-only mode and a deny-by-default SQL authorizer; without the explicit measure flag, SELECT rows are not executed. With measurement, complete returned result sequences must fit explicit per-query row and time budgets.
- Formal coverage: none. OPT's immutable Lean v1 model does not contain this database record.
- Certificate replay: the report SHA-256, workload hash, schema hash, per-query hash, VM plan and result-stream digests permit scoped consistency checking but are not signed provenance or proof of correctness.
- Independent replay: software tests independently count synthetic SQL rows, compare database bytes before/after, challenge SQL write/DDL paths and verify bounded execution and private reports. No real Trinite latency or durability experiment is claimed.

## Problem

Database tuning routinely starts with guessed indexes or configuration changes that can increase write amplification, storage and contention. An optimizer needs a non-destructive inventory of actual schema/index usage, query-plan shape and bounded read latency before it can justify an experiment on a disposable snapshot. A faster-looking scan or lower read median is not sufficient evidence that an index improves total workload cost.

## Optimization problem contract

- X: a finite workload of parameterized SELECT statements, available existing index structures, SQLite engine version, and optional future read-equivalent index/layout candidates on isolated copies.
- F: investigations that open an existing database read-only, reject mutation attempts, preserve SQL semantics and private source rows, respect fixed execution/resource budgets, and never promote candidate DDL without independent parity and host measurements.
- f: workload-weighted end-to-end read latency, write penalty, storage overhead and resource consumption under a future predeclared target workload. This first phase records only read-only baseline samples and plan observations, not candidate scores.
- d: ultimately minimize target total workload cost within exact correctness and storage/write budgets; the observatory itself makes no automatic selection or claim of improvement.
- C: unchanged table/row/schema semantics, parameter identity, query result cardinality and values, explicit ordering where observable, read-only source connection, no automatic DDL, and no leakage of raw SQL parameters or row values into public reports.
- B: at most 16 queries of 2,048 UTF-8 SQL bytes, 16 parameters each, five repeated samples/query, 512 rows/sample, a declared positive total wall-clock budget no greater than 60 seconds, and SQLite per-result length limits. Planning and engine extensions still require external process/OS containment for hostile databases.
- S: finish complete schema and query-plan inventory; for measurements, finish every bounded sample consistently, or stop with a structured error on timeout, result drift, row limit, unsupported SQL, source mutation or failed security checks. No partial measurement is promoted to a successful report.

- Variables: categorical query/index candidate, integer index layout and measured workload parameters
- Search scope: local, evidence-gated database-specific investigation
- Objective behavior: deterministic SQL results under stable snapshot; noisy wall-clock latency
- Information: derivative-free measured runtime and SQLite planner introspection
- Evaluation cost: cheap for plan inspection; moderate for bounded SELECT benchmarks
- Constraints: exact SQL result semantics, safe file access, no data mutation and resource bounds
- Parallelism: sequential inspector; future write/read concurrency requires a new protocol
- Exactness: exact rows within complete bounded results, no approximation or hidden LIMIT truncation

## Preserved contract

`mode=ro` opens an **existing** database and disables SQLite extensions; `PRAGMA query_only=ON` and a whitelist authorizer reject writes, PRAGMAs in workload SQL and non-allowlisted functions. Query SQL is limited to single SELECT/WITH statements; unsupported syntax and multiple statements fail closed. The inspector itself does not issue `CREATE INDEX`, `ANALYZE`, `PRAGMA optimize`, `VACUUM`, `REINDEX`, `ATTACH`, checkpoint or other database-changing operations.

**Important WAL qualification:** opening a live WAL database in normal read-only mode can create `-wal`/`-shm` coordination files. This is not a promise of byte-for-byte filesystem immutability. An explicit immutable mode is permitted **only** for an offline, stable, standalone DELETE-journal snapshot with no sidecars. Never pass a mutable live source with `immutable=1`, because that bypasses SQLite locking and can yield mixed-page evidence under concurrent updates.

No workload SQL or result values are copied into the report. It contains private schema/index names, plan details and deterministic hashes, so the report itself is stored 0600 in an owner-private pre-existing directory. Hashes are not origin authentication.

## Optimization

1. Validate existing source path and strict bounded, duplicate-key-free JSON workload; reject symlinks and malformed parameters.
2. Open SQLite using locking-aware read-only mode; disable extensions, set connection-local query-only and trusted-schema controls, apply a result cell length limit and inspect schema/page/index metadata.
3. Install a deny-by-default authorizer. For each parameterized SELECT, collect `EXPLAIN QUERY PLAN` without fetching SELECT data. Treat scan details as **advisory**, not proof of an index deficiency.
4. Only when the user sets `--measure`, execute complete bounded SELECT streams, hash type-tagged rows without exporting the values and record individual microsecond samples and median. Abort rather than publishing truncated query results, timeouts, unstable results or changed `data_version`.
5. Write a canonical owner-only report with no overwrite, retained report SHA-256 and explicit evidence class. No DDL candidate is selected or applied in v1.

## Before / after evidence

- Environment: local Python and SQLite versions are recorded per observation; hosted synthetic tests run in GitHub Actions and do not measure the user's Ryzen/Trinite workload.
- Workload/fixture: 40 synthetic sessions and 480 synthetic messages with four fixed SQL queries, plus adversarial read-only validation cases.
- Cold baseline: no established Trinite baseline; synthetic fixture collection is a conformance example only.
- Warm/no-op baseline: the first and repeated read-only samples are retained separately; SQLite page cache and OS effects are not controlled by this implementation.
- Small invalidation/partial work: incomplete result sets are rejected, not silently measured as valid.
- Large/full workload: the inspector cannot claim complete target coverage from a four-query synthetic fixture.
- Optimized: **none yet**; OPT-DB-002 will evaluate hypothetical index candidates on disposable snapshots only.
- Speedup/memory/I/O/quality: **no speedup or storage reduction claim**; source database user tables remain unchanged under tested fixtures.
- Variance/repetitions/raw samples: explicit per-query observations; target-specific confidence and complete mixed read/write cost have not been established.

## Validation

Run `python3 -I -B -m unittest discover -s tests -p "test_sqlite_observatory.py" -v`, the full OPT test suite and `python3 scripts/check_catalog.py`. The independent synthetic fixtures test source byte equality, SELECT plan inspection, exact result digests, DML/DDL/extension rejection, parameter/schema limits, strict JSON, private exclusive reports, symlink refusal, row overflow and snapshot/WAL boundaries. These tests are not an adversarial-filesystem proof or engine-level fuzzing.

## Target-repo adaptation

For Trinite, use the actual reviewed v1 schema, read-only parameters and representative session workloads without exporting private conversations. Capture its SQLite version, WAL mode and query plans; measure warm/cold, active WAL, read/write ratio, and real cardinalities separately. Future index proposals must account for increased exchange insertion latency, WAL size, backups, disk-full cases and previously hardened security contracts. Do not change Trinite's native training evidence or SQLite schema in this OPT phase.

## Failure modes

Wrong SQL assumptions, planner version differences, virtual tables or expensive SELECTs, unstable live WAL state, small fixture bias, oversized result streams, cache warming, hidden operating-system I/O and inaccurate cost transfer. `EXPLAIN QUERY PLAN` output is not a stable machine contract across SQLite releases. An existing live WAL reader may create coordination sidecars. SQLite progress-handler deadlines are approximate and are not independently enforced wall-clock process deadlines.

## Rollback trigger

Reject a report if any source file validation, authorizer, query execution, row/time budget, schema read or data-version stability check fails. Keep the source database unchanged and discard any candidate recommendation that has no exact result parity or cannot beat the baseline under a separately frozen target budget.

## Composition notes

Combine with [OPT-AUTO-001](OPT-AUTO-001-calibrated-host-aware-path-promotion.md) for future evidence-gated candidate selection, [OPT-CACHE-001](OPT-CACHE-001-working-set-aware-cache-capacity.md) for measured query-cache working sets, [OPT-INV-001](OPT-INV-001-invariant-driven-reuse.md) for valid reusable results, and [OPT-BUDGET-001](OPT-BUDGET-001-performance-regression-budgets.md) for regression windows. None authorizes mutation of production database files.
