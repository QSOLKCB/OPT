# OPT-INC-001 — Signature-bound incremental execution

**Status:** Implemented historical reference; target validation required  
**Domains:** builds, CI, generated artifacts, preprocessing, scientific pipelines

## Source evidence

- `psycledelics/wonderbuild` commit `021d5ed7c298c6c34b091cf5e6d9802e200028a6`
- `sources/WONDERBUILD.md`

## Problem

Expensive work is rerun even though every input capable of affecting its result is unchanged.

## Optimization problem contract

- X: target-supported signature definitions, persistence scopes, invalidation granularities, and missing-output policies
- F: configurations whose signature covers every output-affecting input, whose reuse checks required outputs, and whose failed executions never commit new reusable state
- f: measured repeated-work cost including stage runtime plus signature/metadata I/O overhead
- d: minimize
- C: every reused output is semantically equivalent to a fresh execution for the same effective inputs, with the same failure/output-validity semantics
- B: target-specific benchmark/evaluation budget declared before tuning; no portable value is supplied by this record
- S: stop when the declared budget is exhausted or a validated configuration meets the predeclared improvement threshold without violating C

## Preserved contract

Reused output must be semantically equivalent to a fresh execution for the same effective inputs. Failed executions must not bless a new signature.

## Optimization

Compute a deterministic signature over the effective inputs, compare it with successfully persisted prior state, and execute only when the signature differs or required outputs are missing. Persist the new signature only after success. Reuse filesystem/configuration metadata lazily when its own validity predicate still holds.

## Evidence boundary

Wonderbuild demonstrates the mechanism and benchmark shapes, but its historical timings and timestamp/hash choices are not transferable targets.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim. Wonderbuild observations are historical source evidence only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Test unchanged, changed-input, missing-output, failed-run, and corrupted/stale-state cases against a forced-fresh reference path.

## Target-repo adaptation

Re-profile signature cost, hash choice, metadata granularity and persistence format. Include environment/toolchain inputs when they affect output.

## Failure modes

Incomplete signatures create stale reuse; overly broad signatures erase the benefit; persistence corruption can create false hits; timestamp-only schemes may be unsuitable where timestamp semantics are weak.

## Rollback trigger

Disable reuse if any cache/signature hit diverges from the fresh reference or if signature maintenance costs more than the avoided work.
