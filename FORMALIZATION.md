# OPT v1.0.0 Lean 4 Formalization

This directory formalizes the **contract invariants** frozen by the immutable `v1.0.0` release of OPT.

## Frozen target

- release: `v1.0.0`
- immutable release target / merge commit: `41e2fc3677469839fb298dedefd0ce72caebcc68`
- final reviewed PR #1 source head recorded by the release: `9fa4164cf1ce8d4be6568db28e33c5242391278b`
- Lean: `4.33.1`

CI independently verifies that the Git tag resolves to the frozen merge commit and that PR #2 does not alter the v1.0.0 contract/source surface. The Lean constants recording the release identity are documentation inside the formal model; the Git checks are the evidence binding.

## What is formalized

The proof layer covers the reusable logical contracts in the frozen catalog:

| Frozen rule / record | Lean statement |
| --- | --- |
| Correctness outranks speed | `fasterButWrongIsNotOptimization` |
| All adaptation boundaries remain intact | `Admissible` and its projection theorems |
| Reference/optimized semantic equivalence | `witnessedOptimizationPreservesSemantics` |
| OPT-INV-001 equivalence-gated reuse | `invariantReusePreservesSemantics` |
| OPT-PAR-001 scalar/parallel equivalence | `deterministicParallelPreservesScalarResult` |
| OPT-LEAN-001 cache claim boundary | `verifiedReuseDoesNotProveColdReconstruction` |
| DSP approximation requires an error contract | `missingErrorBoundBlocksApproximation` |
| Composition requires a combined resource model | `Composable` / `composableIsSymmetric` |
| Frozen catalog contains exactly five unique records | `frozenCatalogHasFiveRecords`, `frozenCatalogHasNoDuplicateRecords` |
| `suxen.zip` remains a source candidate | `suxenInventoryHitsDoNotPromoteMeasuredPerformance` |

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

1. checks `v1.0.0` resolves to the frozen merge commit;
2. rejects modifications to the v1.0.0 repository surface outside the new formalization files;
3. verifies the exact `lean-toolchain` declaration;
4. downloads Lean 4.33.1 from the official Lean release and verifies its SHA-256 before use;
5. rejects `sorry`, `admit`, user `axiom`, and `unsafe` tokens in Lean source outside comments/strings;
6. builds the library with the pinned compiler;
7. runs `Lean/TrustAudit.lean` to print the axiom dependencies of the exported theorem surface and require the completion marker;
8. permits only Lean's core `propext` axiom in those exported dependencies and fails closed on any additional axiom such as `Classical.choice` or `Quot.sound`.

The current audit surface contains theorems with no axioms and theorems whose only reported dependency is `propext`. No user-declared axioms are permitted.

## Local build

```bash
lake build
lake env lean Lean/TrustAudit.lean
python3 scripts/check_lean_source.py Lean
```

## Formalization boundary

PR #2 extends OPT with a formal verification layer. It does not rewrite or reinterpret the frozen v1.0.0 optimization records. Any future catalog change should be formalized against a new frozen release identity rather than silently changing the meaning of this baseline.
