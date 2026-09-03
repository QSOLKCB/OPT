# OPT v1.0.0 Lean 4 Formalization

This directory formalizes the **contract invariants** frozen by the immutable `v1.0.0` release of OPT.

## Frozen target

- release: `v1.0.0`
- immutable release target / merge commit: `41e2fc3677469839fb298dedefd0ce72caebcc68`
- final reviewed PR #1 source head recorded by the release: `9fa4164cf1ce8d4be6568db28e33c5242391278b`
- Lean: `4.33.1`

CI independently verifies that the Git tag resolves to the frozen merge commit. During PR #2 only, CI additionally proves that the original v1.0.0 repository surface is unchanged outside the new formalization/trust files. That construction-time check is deliberately not a permanent freeze on later OPT releases.

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
| Frozen catalog contains exactly five unique records | `frozenCatalogHasFiveRecords`, `frozenCatalogHasNoDuplicateRecords` |
| `suxen.zip` remains a source candidate | `suxenInventoryHitsDoNotPromoteMeasuredPerformance` |

### Historical observations are not portable targets

The frozen catalog intentionally retains caveated historical timing observations for `OPT-PY-001` and `OPT-INV-001` even though their original benchmark environments are incomplete. The formal model therefore distinguishes:

- `historicalObservation`: a source observation may be retained with its caveats;
- `transferableTarget`: a number is being asserted as a target for another environment.

`verifiedMechanism` and `verifiedEnvironmentSpecific` may support the former, but do not by themselves support the latter. This matches the v1.0.0 requirement to re-measure adaptations instead of treating source-project timings as universal constants.

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
2. during PR #2 only, rejects modifications to the inherited v1.0.0 surface outside the new formalization files;
3. verifies the exact `lean-toolchain` declaration;
4. downloads Lean 4.33.1 from the official Lean release and verifies its SHA-256 before use;
5. rejects `sorry`, `admit`, user `axiom`/`constant` declarations, and `unsafe` in Lean source outside inert comments/string text;
6. self-tests that source scanner against interpolation-body bypasses such as `s!"{(sorry : Nat)}"` and nested/message interpolators;
7. builds the library with the pinned compiler;
8. has `Lean/TrustAudit.lean` discover **every exported theorem** in the `OPTFormal.` namespace from Lean's imported module metadata;
9. runs `Lean.collectAxioms` on every discovered theorem and fails inside Lean if any dependency lies outside the explicit `propext` allowlist;
10. emits the completion marker only after the dynamic theorem-kind and axiom checks finish.

Because the theorem set is discovered from the compiled environment, adding a new exported theorem automatically places it under the axiom audit without maintaining a second hard-coded theorem table.

## Local build

```bash
lake build
lake env lean Lean/TrustAudit.lean
python3 scripts/check_lean_source.py Lean --self-test
```

## Formalization boundary

PR #2 extends OPT with a formal verification layer. It does not rewrite the frozen v1.0.0 optimization records. Future OPT versions may add records or evolve the non-formal repository surface normally; if their contract changes are to be frozen formally, they should receive a new release-bound formalization rather than silently changing the meaning of the v1.0.0 model.
