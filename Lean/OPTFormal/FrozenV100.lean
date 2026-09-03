import OPTFormal.Core

namespace OPTFormal

/-- The five optimization records frozen by OPT v1.0.0. -/
inductive RecordId where
  | py001
  | inv001
  | lean001
  | par001
  | dsp001
  deriving DecidableEq, Repr

/-- Frozen release identity. CI independently binds these names to Git. -/
def frozenReleaseTag : String := "v1.0.0"

def frozenReleaseCommit : String :=
  "41e2fc3677469839fb298dedefd0ce72caebcc68"

/-- Final reviewed PR #1 source head recorded in the immutable release notes. -/
def frozenReviewedHead : String :=
  "9fa4164cf1ce8d4be6568db28e33c5242391278b"

/-- Exact catalog surface formalized by PR #2. -/
def frozenCatalog : List RecordId :=
  [.py001, .inv001, .lean001, .par001, .dsp001]

theorem frozenCatalogHasFiveRecords : frozenCatalog.length = 5 := rfl

theorem frozenCatalogHasNoDuplicateRecords : frozenCatalog.Nodup := by
  decide

/-- Evidence classification carried into the formal layer from CATALOG.md. -/
def frozenStatus : RecordId → EvidenceStatus
  | .py001 => .verifiedMechanism
  | .inv001 => .verifiedMechanism
  | .lean001 => .verifiedEnvironmentSpecific
  | .par001 => .verifiedEnvironmentSpecific
  | .dsp001 => .implementedReference

theorem deterministicTestRecordDoesNotCreateTransferableBenchmarkClaim :
    measuredClaimAllowed (frozenStatus .py001) = false := rfl

theorem invariantReuseRecordDoesNotCreateTransferableBenchmarkClaim :
    measuredClaimAllowed (frozenStatus .inv001) = false := rfl

theorem dspImplementedReferenceDoesNotCreateMeasuredClaim :
    measuredClaimAllowed (frozenStatus .dsp001) = false := rfl

/-- The preserved SUXEN archive remains a source candidate at the frozen boundary. -/
def suxenStatus : EvidenceStatus := .sourceCandidate

theorem suxenInventoryHitsDoNotPromoteMeasuredPerformance :
    measuredClaimAllowed suxenStatus = false := rfl

end OPTFormal
