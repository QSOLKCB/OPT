# OPT-INC-001 — Signature-bound incremental execution

**Status:** Implemented external reference; historical donor, target validation required  
**Domains:** builds, CI, generated artifacts, preprocessing, scientific pipelines

## Source evidence

- `psycledelics/wonderbuild` commit `021d5ed7c298c6c34b091cf5e6d9802e200028a6`
- `sources/WONDERBUILD.md`

## Problem

Expensive work is rerun even though every input capable of affecting its result is unchanged.

## Optimization problem contract

- X: target-supported signature definitions, persistence scopes, invalidation granularities, output-validity policies, and crash-consistent state-publication mechanisms
- F: configurations whose signature covers every output-affecting input, whose reuse validates required outputs, whose persisted signature/output metadata form one committed generation, and whose failed/interrupted executions never publish reusable partial state
- f: measured repeated-work cost including stage runtime plus signature/metadata/output-validation/publication I/O overhead
- d: minimize
- C: every reused output is semantically equivalent to a fresh execution for the same effective inputs, with the same failure and output-validity semantics; reuse metadata cannot mix fields from different generations
- B: target-specific benchmark/evaluation budget declared before tuning; no portable value is supplied by this record
- S: stop when the declared budget is exhausted or a validated configuration meets the predeclared improvement threshold without violating C

## Preserved contract

Reused output must be semantically equivalent to a fresh execution for the same effective inputs. Failed executions must not bless a new signature, an unchanged input signature alone is insufficient when an existing output can be corrupted or overwritten externally, and interrupted publication must not expose a signature paired with output identities from another generation.

## Optimization

Compute a deterministic signature over the effective inputs and compare it with successfully persisted prior state. Reuse is allowed only when that signature still matches **and** every required output satisfies a declared validity predicate. Depending on the target, that predicate may be a content digest/version manifest, a trusted immutable/protected artifact identity, or another reproducible integrity check strong enough to detect external mutation. Mere file presence is not sufficient unless the target explicitly guarantees that reused outputs are immutable and protected from modification. Execute when the input signature differs, any required output is missing, or any output-validity check fails.

Publish incremental state as one crash-consistent **generation** that binds the input signature to the complete output identity/validity metadata. Do not persist the signature and output metadata as independently authoritative updates. Use an atomic rename/swap of a complete manifest, a transactional store, a content-addressed generation pointer, or another mechanism where readers observe either the previous complete generation or the new complete generation—never a mixture. Only publish the new generation after every output has been produced and validated successfully; an interrupted or failed publication leaves the previous committed generation authoritative and the partial generation non-reusable.

Reuse filesystem/configuration metadata lazily only while its own validity predicate still holds.

## Evidence boundary

Wonderbuild demonstrates the mechanism and benchmark shapes, but its historical timings and timestamp/hash choices are not transferable targets.

## Before / after evidence

- Environment: No controlled target-repository benchmark has been run for this OPT record.
- Baseline: Not established in a target repository.
- Optimized: Not established in a target repository.
- Speedup / memory reduction: No transferable claim. Wonderbuild observations are historical source evidence only.
- Variance / repetitions: Not available for a controlled OPT target benchmark.

## Validation

Test unchanged inputs with valid outputs, changed inputs, missing outputs, failed runs, corrupted persistent state, externally overwritten/corrupted outputs, and stale output-version metadata against a forced-fresh reference path. A mutated output must force reconstruction unless the target's immutable/protected-output contract proves such mutation impossible. Exercise interruption/crash injection at every publication boundary: before outputs complete, after outputs complete but before manifest publication, during temporary-manifest write, immediately before/after the atomic generation switch, and during cleanup. After each interruption, prove readers observe only a self-consistent old or new generation and can never pair signature A with output identities/metadata from generation B.

## Target-repo adaptation

Re-profile signature and output-validation cost, hash/version choice, metadata granularity, persistence format, and generation-publication mechanism. Include environment/toolchain inputs when they affect output. Explicitly choose whether outputs are integrity-checked on reuse or are stored behind an enforceable immutable/protected boundary, and define the crash-consistency guarantee for committing the signature plus output identities.

## Failure modes

Incomplete signatures create stale reuse; existence-only output checks can return corrupted artifacts; weak output-validity predicates can miss external mutation; independently persisted signature/output metadata can create cross-generation false hits after interruption; overly broad signatures erase the benefit; persistence corruption can create false hits; timestamp-only schemes may be unsuitable where timestamp semantics are weak.

## Rollback trigger

Disable reuse immediately if any signature/output-validity hit diverges from the forced-fresh reference, if external output mutation can bypass the declared validity predicate, if crash/interruption testing can expose mixed-generation state, or if signature/integrity/publication maintenance costs more than the avoided work.
