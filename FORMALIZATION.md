# OPT v1.0.0 Lean 4 Formalization

This directory formalizes the **contract invariants** frozen by the immutable `v1.0.0` release of OPT.

## Frozen target

- release: `v1.0.0`
- immutable release target / merge commit: `41e2fc3677469839fb298dedefd0ce72caebcc68`
- final reviewed PR #1 source head recorded by the release: `9fa4164cf1ce8d4be6568db28e33c5242391278b`
- Lean: `4.33.1`

CI independently verifies that the Git tag resolves to the frozen merge commit. During PR #2 only, CI additionally proves that the original v1.0.0 repository surface is unchanged outside the new formalization/trust files. That construction-time check is deliberately not a permanent freeze on later OPT releases.

The constructed v1 formal model itself is permanently content-pinned by Git blob identity:

- `Lean/OPTFormal/Core.lean`: `b475c372af35c9ccbe00b9ffb96b269dcf9046a4`
- `Lean/OPTFormal/FrozenV100.lean`: `54679a032d1f0e83ddb1b344b9d53d1c11ea84cf`
- `Lean/OPTFormal.lean`: `7a19560f3447ad2e8bfaedb7268be48e2c642c18`

Future versions may add separately versioned formal modules, but those three v1 model files must remain byte-identical for the persistent v1 gate to pass.

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

## Trust surface

The formal package has no third-party Lean dependencies and no mathlib dependency graph. CI:

1. always checks that `v1.0.0` resolves to the frozen merge commit and that the current revision descends from it;
2. always verifies the three constructed v1 formal-model files against their pinned Git blob identities;
3. during PR #2 only, rejects modifications to the inherited v1.0.0 surface outside the new formalization files;
4. verifies the exact `lean-toolchain` declaration;
5. downloads Lean 4.33.1 from the official Lean release and verifies its SHA-256 before use;
6. rejects `sorry`, `admit`, user `axiom`/`constant` declarations, and `unsafe` in Lean source outside inert comments/string/character-literal text;
7. self-tests the source scanner against interpolation-body bypasses, nested/message interpolators, and character literals containing interpolation-closing braces;
8. builds the library with the pinned compiler;
9. has `Lean/TrustAudit.lean` discover every exported `OPTFormal.*` declaration from Lean's imported module metadata;
10. uses `Lean.Meta.isProp` to select every exported proposition-valued declaration, including proof-returning definitions rather than only `.thmInfo` declarations;
11. runs `Lean.collectAxioms` on every discovered logical export and fails inside Lean if any dependency lies outside the explicit `propext` allowlist;
12. emits the completion marker only after the dynamic proposition-type and axiom checks finish.

Because the logical export set is discovered from the compiled environment, changing a proof from `theorem` syntax to a proposition-valued `def` does not escape the axiom audit.

## Local build

```bash
lake build
lake env lean Lean/TrustAudit.lean
python3 scripts/check_lean_source.py Lean --self-test
```

## Formalization boundary

PR #2 extends OPT with a formal verification layer. It does not rewrite the frozen v1.0.0 optimization records. Future OPT versions may add records or separately versioned formal modules normally; they must not mutate the pinned v1 formal model. If a future contract is to be frozen formally, it should receive its own release-bound module rather than silently changing the meaning of the v1.0.0 model.
