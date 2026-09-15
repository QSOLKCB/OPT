# OPT-XXX-000 — Optimization Name

**Status:**  
**Domains:** ...

Choose one documented status category from `README4AI.md` and replace every placeholder below before promoting this file into `optimizations/`.

## Source evidence

- Repository / publication / article:
- Release/commit/PR/DOI/date:
- Exact files/sections where applicable:
- Licensing/provenance boundary where code reuse may matter:

## Problem

What dominates runtime, latency, memory, I/O, CI cost, quality budget or optimization-evaluation cost?

## Optimization problem contract

Define the target using `OPTIMIZATION-PROBLEM.md`. Keep these seven canonical fields as exact list prefixes so catalog integrity can verify the contract. **They are intentionally empty in this template and must be filled with record-specific values.**

- X:
- F:
- f:
- d:
- C:
- B:
- S:

Then record useful classification detail:

- Variables: continuous / integer / categorical / conditional / mixed
- Objective behavior: deterministic / noisy / stochastic
- Search scope: local / global
- Information: gradient / derivative-free / black-box
- Exactness: exact / approximation permitted under explicit error contract

## Preserved contract

State exactly what must remain unchanged: output bytes, theorem targets, assertions, API, numerical tolerance, ordering, statistical guarantee, evidence boundary, trust model, etc.

If the optimization changes the contract (for example exact → approximate), state the new contract explicitly instead of claiming preservation.

## Optimization

Describe the reusable mechanism, not only the source-project patch.

## Before / after evidence

- Environment:
- Workload/fixture:
- Cold baseline:
- Warm/no-op baseline where relevant:
- Small invalidation / partial-work case where relevant:
- Large invalidation / full-work case where relevant:
- Optimized:
- Speedup / memory / I/O / quality change:
- Variance / repetitions / raw samples:

If no controlled benchmark exists, say so explicitly.

## Validation

How was equivalence, correctness, bound soundness, approximation error or other contract compliance established?

## Target-repo adaptation

Which source constants, thresholds, worker counts, bit splits, cache keys, search budgets or tolerances must be re-profiled rather than copied?

## Failure modes

What can make this optimization invalid, slower, less robust or misleading?

## Rollback trigger

Define the measured or semantic condition that disables/reverts the optimization.

## Composition notes

Which other OPT records compose safely, and which resource/semantic interactions must be re-measured?
