# OPT v1.0.0 Lean 4 Formalization

This repository's `Lean/` package formalizes the **contract invariants** frozen by the immutable `v1.0.0` release of OPT.

## Frozen target

- release: `v1.0.0`
- immutable release target / merge commit: `41e2fc3677469839fb298dedefd0ce72caebcc68`
- final reviewed PR #1 source head recorded by the release: `9fa4164cf1ce8d4be6568db28e33c5242391278b`
- Lean: `4.33.1`

CI independently verifies that the Git tag resolves to the frozen merge commit. During PR #2 only, CI additionally proves that the original v1.0.0 repository surface is unchanged outside the new formalization/trust files. That construction-time check is deliberately not a permanent freeze on later OPT releases.

The constructed v1 formal model itself is permanently content-pinned by Git history. The workflow does **not** keep editable expected blob hashes beside the check. Instead it locates the first ancestor commit after v1.0.0 that established the `FORMAL_V1_MODEL_BLOBS_OK files=3` gate, reads the three expected blobs from that historical commit, and compares the current `HEAD:<path>` blobs against them:

- `Lean/OPTFormal/Core.lean`
- `Lean/OPTFormal/FrozenV100.lean`
- `Lean/OPTFormal.lean`

Future versions may add separately versioned formal modules, but those three v1 model files must remain byte-identical for the persistent v1 gate to pass. Future versioned modules are routed through the unpinned `Lean/OPTFormalAll.lean` audit root, and CI checks that every module under `Lean/OPTFormal/` appears in that root before the formal build or audit can succeed.

The Lean constants recording the release identity are documentation inside the formal model; the Git checks are the evidence binding.

## What is formalized

The proof layer covers the reusable logical contracts in the frozen catalog:

| Frozen rule / record | Lean statement |
| --- | --- |
| Correctness outranks speed | `fasterButWrongIsNotOptimization` |
| Adaptation boundaries: semantics, named invariants, determinism, validation, provenance, evidence boundary, public API | `Admissible` and its projection theorems |
| Reference/optimized semantic equivalence | `witnessedOptimizationPreservesSemantics` |
| OPT-INV-001 equivalence-gated reuse | `invariantReusePreservesSemantics` |
| OPT-PAR-001 scalar/parallel equivalence | `deterministicParallelPreservesScalarResult` |
| OPT-LEAN-001 cache claim boundary | `verifiedReuseDoesNotProveColdReconstruction` |
| DSP approximation requires an error contract | `missingErrorBoundBlocksApproximation` |
| Composition requires a combined resource model | `Composable` / `composableIsSymmetric` |
| Historical observations are distinct from transferable benchmark targets | `ClaimScope` plus the frozen-record claim theorems |
| Transferable claims require target-machine evidence | `TargetContextEvidence`, `TransferableClaimAllowed`, `transferableClaimRequiresTargetContext` |
| Frozen catalog contains exactly five unique records | `frozenCatalogHasFiveRecords`, `frozenCatalogHasNoDuplicateRecords` |
| `suxen.zip` remains a source candidate | `suxenInventoryHitsDoNotPromoteMeasuredPerformance` |

### Historical observations are not portable targets

The frozen catalog intentionally retains caveated historical timing observations for `OPT-PY-001` and `OPT-INV-001` even though their original benchmark environments are incomplete. The formal model therefore distinguishes:

- `historicalObservation`: a source observation may be retained with its caveats;
- `transferableTarget`: a number is being asserted as a target for another environment.

No `EvidenceStatus`, including `verified`, authorizes a transferable target by itself. Promotion requires explicit target-context premises: a target measurement, correctness validation, and provenance binding. This matches the v1.0.0 requirement to benchmark adaptations in their target environment rather than treating source-project timings as universal constants.

## What is deliberately not formalized as a theorem

This PR does **not** claim that Lean proves:

- historical wall-clock benchmark numbers;
- the external authenticity of QEC, SPECTRAL, NEXUS or GEO-REASON measurements;
- that a future optimization is faster on a new machine;
- that `suxen.zip` keyword hits establish an optimization claim;
- Git tag immutability from a Lean string literal.

Those are evidence/provenance questions. The formal layer proves implications once the relevant premises are supplied; CI binds those premises to the frozen repository identity where possible.

Data-valued declarations are not ignored by the trust audit. Every declaration originating in an audited formal source module, including `OPTFormalAll`, has its transitive axiom dependencies checked before proposition-valued declarations are counted as logical exports. Primitive `.axiomInfo` declarations from those modules are rejected outright. This catches generated data-valued axioms and data-valued definitions depending on `sorryAx`, even when source-level lexical scanning would not be sufficient on its own.

## Trust surface

The formal package has no third-party Lean dependencies and no mathlib dependency graph. CI:

1. always checks that `v1.0.0` resolves to the frozen merge commit and that the current revision descends from it;
2. derives the frozen v1 formal-model blobs from the first historical ancestor that established the three-file blob gate, then compares current committed blobs against that external historical baseline;
3. during PR #2 only, rejects modifications to the inherited v1.0.0 surface outside the new formalization files;
4. verifies the exact `lean-toolchain` declaration;
5. downloads Lean 4.33.1 from the official Lean release and verifies its SHA-256 before use;
6. rejects `sorry`, direct `sorryAx`, `admit`, user `axiom`/`constant` declarations, and `unsafe` in Lean source outside inert comments, ordinary strings, raw strings, character literals, and guillemet-quoted identifiers;
7. self-tests the source scanner against interpolation-body bypasses, nested/message interpolators, character literals containing interpolation-closing braces, hash-delimited raw strings, multiline raw strings, raw-string/comment-marker confusion, and quoted identifiers containing comment syntax;
8. checks that the unpinned `Lean/OPTFormalAll.lean` audit root imports every current module under `Lean/OPTFormal/`, including recursively nested or separately versioned modules;
9. builds both the pinned `OPTFormal` library and the unpinned `OPTFormalAll` audit root with the pinned compiler;
10. has `Lean/TrustAudit.lean` select declarations by **originating module**, covering `OPTFormal`, every `OPTFormal.*` source module, and `OPTFormalAll` itself regardless of declaration namespace;
11. rejects any primitive `.axiomInfo` declaration originating in that audited module set;
12. runs `Lean.collectAxioms` on **every declaration** in the audited module set and fails if any dependency lies outside the explicit `propext` allowlist;
13. uses `Lean.Meta.isProp` only to classify/count proposition-valued logical exports after the full declaration-level trust audit has already passed;
14. emits the completion marker only after audit-root coverage, full-declaration axiom checking, logical-export classification, and the allowlist checks finish.

Because CI checks the audit root against the on-disk module set, adding a new `Lean/OPTFormal/FrozenV200.lean`-style module without importing it into `OPTFormalAll` fails before audit completion. Because declarations are selected by their origin module rather than namespace, a future module cannot hide a proof in the root namespace or an alternate namespace. Because axiom dependencies are checked before Prop filtering, generated or data-valued primitive proof escapes do not receive a separate trust lane.

## Local build

```bash
python3 scripts/check_lean_source.py Lean --self-test
lake build
lake env lean Lean/TrustAudit.lean
```

## Formalization boundary

PR #2 extends OPT with a formal verification layer. It does not rewrite the frozen v1.0.0 optimization records. Future OPT versions may add records or separately versioned formal modules normally; they must not mutate the historically anchored v1 formal model. New formal modules must be registered in the unpinned `OPTFormalAll` root so the persistent audit covers them. If a future contract is to be frozen formally, it should receive its own release-bound module rather than silently changing the meaning of the v1.0.0 model.
