namespace OPTFormal

/-- Evidence states used by the frozen OPT v1.0.0 catalog. -/
inductive EvidenceStatus where
  | sourceCandidate
  | proposed
  | implementedReference
  | verifiedMechanism
  | verifiedEnvironmentSpecific
  | verified
  deriving DecidableEq, Repr

/-- Only evidence explicitly carrying measurement support may back a measured-performance claim. -/
def measuredClaimAllowed : EvidenceStatus → Bool
  | .verifiedEnvironmentSpecific => true
  | .verified => true
  | _ => false

theorem sourceCandidateCannotSupportMeasuredClaim :
    measuredClaimAllowed .sourceCandidate = false := rfl

theorem proposedCannotSupportMeasuredClaim :
    measuredClaimAllowed .proposed = false := rfl

theorem implementedReferenceCannotSupportMeasuredClaim :
    measuredClaimAllowed .implementedReference = false := rfl

theorem verifiedMechanismWithoutBenchmarkContextCannotSupportMeasuredClaim :
    measuredClaimAllowed .verifiedMechanism = false := rfl

/-- Minimal semantic/performance assessment of a proposed optimization. -/
structure OptimizationAssessment where
  semanticsPreserved : Prop
  performanceImproved : Prop

/-- OPT calls a change an optimization only when semantics are preserved and performance improves. -/
def IsOptimization (a : OptimizationAssessment) : Prop :=
  a.semanticsPreserved ∧ a.performanceImproved

theorem optimizationRequiresSemanticPreservation
    {a : OptimizationAssessment} (h : IsOptimization a) :
    a.semanticsPreserved := h.1

theorem fasterButWrongIsNotOptimization
    (a : OptimizationAssessment)
    (_hFast : a.performanceImproved)
    (hWrong : ¬ a.semanticsPreserved) :
    ¬ IsOptimization a := by
  intro h
  exact hWrong h.1

/-- Contract surface that an adaptation must preserve. -/
structure OptimizationContract where
  semanticsPreserved : Prop
  validationPreserved : Prop
  provenancePreserved : Prop
  evidenceBoundaryPreserved : Prop

/-- An adaptation is admissible only when every frozen v1.0.0 contract boundary is retained. -/
def Admissible (c : OptimizationContract) : Prop :=
  c.semanticsPreserved ∧
  c.validationPreserved ∧
  c.provenancePreserved ∧
  c.evidenceBoundaryPreserved

theorem admissiblePreservesSemantics
    {c : OptimizationContract} (h : Admissible c) :
    c.semanticsPreserved := h.1

theorem admissiblePreservesValidation
    {c : OptimizationContract} (h : Admissible c) :
    c.validationPreserved := h.2.1

theorem admissiblePreservesProvenance
    {c : OptimizationContract} (h : Admissible c) :
    c.provenancePreserved := h.2.2.1

theorem admissiblePreservesEvidenceBoundary
    {c : OptimizationContract} (h : Admissible c) :
    c.evidenceBoundaryPreserved := h.2.2.2

/-- Generic reference/optimized pair with a pointwise equivalence witness. -/
structure SemanticOptimization (α β : Type) where
  reference : α → β
  optimized : α → β
  equivalent : ∀ x, optimized x = reference x

theorem witnessedOptimizationPreservesSemantics
    {α β : Type} (o : SemanticOptimization α β) (x : α) :
    o.optimized x = o.reference x := o.equivalent x

/-- OPT-INV-001: reuse the reference result only at states covered by a named invariant. -/
def invariantReuse
    {α β : Type}
    (reference candidate : α → β)
    (P : α → Prop)
    [DecidablePred P]
    (x : α) : β :=
  if P x then reference x else candidate x

/-- Equivalence-gated reuse is semantics-preserving. -/
theorem invariantReusePreservesSemantics
    {α β : Type}
    (reference candidate : α → β)
    (P : α → Prop)
    [DecidablePred P]
    (hEq : ∀ x, P x → reference x = candidate x) :
    ∀ x, invariantReuse reference candidate P x = candidate x := by
  intro x
  by_cases h : P x
  · simp [invariantReuse, h, hEq x h]
  · simp [invariantReuse, h]

/-- OPT-PAR-001: parallel execution is admissible only with a scalar-equivalence witness. -/
structure DeterministicParallelPlan (α β : Type) where
  scalar : List α → List β
  parallel : List α → List β
  equivalent : ∀ xs, parallel xs = scalar xs

theorem deterministicParallelPreservesScalarResult
    {α β : Type}
    (p : DeterministicParallelPlan α β)
    (xs : List α) :
    p.parallel xs = p.scalar xs := p.equivalent xs

/-- Trust lanes explicitly distinguished by OPT-LEAN-001. -/
inductive TrustLane where
  | verifiedReuse
  | coldReconstruction
  deriving DecidableEq, Repr

inductive TrustClaim where
  | dependencyReuse
  | coldReconstruction
  deriving DecidableEq, Repr

/-- A verified-cache lane can support a reuse claim, not a cold-reconstruction claim. -/
def supportsTrustClaim : TrustLane → TrustClaim → Bool
  | .verifiedReuse, .dependencyReuse => true
  | .coldReconstruction, .coldReconstruction => true
  | _, _ => false

theorem verifiedReuseDoesNotProveColdReconstruction :
    supportsTrustClaim .verifiedReuse .coldReconstruction = false := rfl

theorem coldReconstructionSupportsColdClaim :
    supportsTrustClaim .coldReconstruction .coldReconstruction = true := rfl

/-- Explicit correctness contract required before promoting a DSP approximation. -/
structure ApproximationContract where
  errorBoundDefined : Prop
  toleranceValidated : Prop
  referenceComparison : Prop

/-- Mirrors v1.0.0's refusal to promote the whole-block DSP shortcut without an error contract. -/
def ApproximationAdmissible (c : ApproximationContract) : Prop :=
  c.errorBoundDefined ∧ c.toleranceValidated ∧ c.referenceComparison

theorem missingErrorBoundBlocksApproximation
    (c : ApproximationContract)
    (hMissing : ¬ c.errorBoundDefined) :
    ¬ ApproximationAdmissible c := by
  intro h
  exact hMissing h.1

/-- Coarse resource model for checking whether independently valid optimizations compose. -/
structure ResourceUse where
  cpu : Nat
  memory : Nat
  io : Nat
  deriving DecidableEq, Repr

namespace ResourceUse

def add (a b : ResourceUse) : ResourceUse where
  cpu := a.cpu + b.cpu
  memory := a.memory + b.memory
  io := a.io + b.io

end ResourceUse

/-- A resource use fits a target capacity componentwise. -/
def Fits (use capacity : ResourceUse) : Prop :=
  use.cpu ≤ capacity.cpu ∧
  use.memory ≤ capacity.memory ∧
  use.io ≤ capacity.io

/-- Composition is safe only when the combined resource model fits. -/
def Composable (a b capacity : ResourceUse) : Prop :=
  Fits (ResourceUse.add a b) capacity

theorem composableIsSymmetric
    (a b capacity : ResourceUse) :
    Composable a b capacity ↔ Composable b a capacity := by
  simp [Composable, Fits, ResourceUse.add, Nat.add_comm]

end OPTFormal
