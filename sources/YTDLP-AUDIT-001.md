# YTDLP-AUDIT-001 — Historical hybrid-execution motivation

- Repository: QSOLKCB/yt-dlp-enhanced.
- Pull request: https://github.com/QSOLKCB/yt-dlp-enhanced/pull/1
- Audited candidate commit: 42e72529d839d2e862373386c611896fef602d3d.
- Original baseline commit: 29490a6c9b53e1b9d2c2471c48303afbc44c4796.
- Independent report ID: YTDLP-AUDIT-001.
- Audit archive SHA-256 (mission-supplied): 07c37167a6688f7a0d071fea65fb8d38037779fa2f92b22be69fb310e25d0abb.
- OPT revision consulted: 8dc06e99e48711497380fb11237f5fe12b6c556d.
- Verdict: BLOCK — CORRECTNESS OR SECURITY DEFECT. Unresolved source provenance and outcome equivalence; no production implementation promotion. No donor code copied.
- Archive/report not supplied with this mission; checksum not independently verified, raw sample data and detailed host/runtime metadata not available. All figures below are historical audit-reported observations supplied in the mission, not independently reproduced OPT measurements.

| Local 250-test configuration | Reported mean seconds (two runs) |
| --- | ---: |
| Ordinary serial | 4.6835 |
| OPT one worker | 7.8835 |
| OPT two workers | 8.1710 |
| OPT four workers | 8.4415 |
| OPT seven workers | 8.9065 |

246 passed, four skipped. Full CI workload: approximately 148 s serial, 111 s seven workers. Workload and environment differ; the two observations do not establish a crossover threshold.

Reported redundant preparation: 7,142 items discovered during complete collection, 1,301 selected core IDs, repeated complete collection across eight processes, approximately 9,720 tracked-file copies and 87 MiB logical copied storage. Exact-module collection reportedly preserved the 250 selected IDs while reducing collection latency from approximately 2.9–3.2 s to 0.951–0.965 s. Do not infer complete outcome equivalence from counts or this narrower collection observation.

Transfer only the principle: prove unnecessary work removable, then measure complete serial/parallel/hybrid lifecycle costs under identical boundaries and verify full-work outcomes before promotion. Do not disclose sensitive defect details here. No formal theorem or universal worker policy follows.
