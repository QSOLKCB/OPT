# OPT-XXX-000 — Optimization Name

**Status:** Proposed / Implemented reference / Verified / Verified, environment-specific  
**Domains:** ...

## Source evidence

- Repository:
- Release/commit/PR:
- Exact files:

## Problem

What dominates runtime, latency, memory, I/O or CI cost?

## Preserved contract

State exactly what must remain unchanged: output bytes, theorem targets, assertions, API, numerical tolerance, ordering, statistical guarantee, evidence boundary, etc.

## Optimization

Describe the reusable mechanism, not only the source-project patch.

## Before / after evidence

- Environment:
- Baseline:
- Optimized:
- Speedup / memory reduction:
- Variance / repetitions:

If no controlled benchmark exists, say so explicitly.

## Validation

How was equivalence/correctness established?

## Target-repo adaptation

Which source constants must be re-profiled rather than copied?

## Failure modes

What can make this optimization invalid or slower?

## Rollback trigger

Define the condition that disables or reverts the optimization.
