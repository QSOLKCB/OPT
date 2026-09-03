import Lean.Elab.Command
import Lean.Meta.Basic
import Lean.Util.CollectAxioms
import OPTFormalAll

open Lean
open Lean.Elab Command

private def allowedAxioms : Array Name := #[
  `propext
]

/--
The pinned root module is `OPTFormal`; separately versioned formal modules live
under the `OPTFormal.*` module hierarchy. `OPTFormalAll` is the unpinned audit
aggregator and is itself part of the audited trust surface.
-/
private def isFormalSourceModule (moduleName : Name) : Bool :=
  let rendered := moduleName.toString
  rendered == "OPTFormal" ||
    rendered == "OPTFormalAll" ||
    rendered.startsWith "OPTFormal."

/--
Collect declarations by their originating formal module, not by declaration
namespace. CI separately proves that `OPTFormalAll` imports every source module
under `Lean/OPTFormal/`, while the pinned `OPTFormal` root is imported too.

A future `OPTFormal.FrozenV200` module therefore cannot evade the audit by
using the root namespace or an unrelated namespace such as `OPTFormalV200`,
and helper declarations placed directly in `OPTFormalAll` are audited too.
-/
private def formalSourceDeclarations (env : Environment) : Array Name := Id.run do
  let mut targets : Array Name := #[]
  for moduleData in env.header.moduleData do
    for info in moduleData.constants do
      if let some modIdx := env.getModuleIdxFor? info.name then
        let moduleName := env.header.moduleNames[modIdx]!
        if isFormalSourceModule moduleName then
          targets := targets.push info.name
  return targets.qsort Name.lt

private def declarationKind : ConstantInfo → String
  | .axiomInfo _ => "axiom"
  | .defnInfo _ => "definition"
  | .thmInfo _ => "theorem"
  | .opaqueInfo _ => "opaque"
  | .quotInfo _ => "quotient"
  | .inductInfo _ => "inductive"
  | .ctorInfo _ => "constructor"
  | .recInfo _ => "recursor"

run_cmd do
  let env ← getEnv
  let candidates := formalSourceDeclarations env
  let mut logicalTargets : Array Name := #[]
  let mut declarationsAudited : Nat := 0

  if candidates.isEmpty then
    throwError "OPT formal audit found no declarations originating in formal source modules"

  -- Audit every declaration before any proposition-valued filtering. This
  -- catches generated primitive axioms and data-valued definitions that depend
  -- on `sorryAx`, `Classical.choice`, or any other disallowed axiom.
  for target in candidates do
    let some info := env.find? target
      | throwError "missing formal-source declaration {target}"
    let some modIdx := env.getModuleIdxFor? target
      | throwError "formal-source declaration {target} has no originating module"
    let moduleName := env.header.moduleNames[modIdx]!
    unless isFormalSourceModule moduleName do
      throwError "formal-source declaration {target} originated outside audited modules: {moduleName}"

    match info with
    | .axiomInfo _ =>
        throwError "formal source module {moduleName} exports primitive axiom declaration {target}"
    | _ => pure ()

    let axioms ← Lean.collectAxioms target
    for ax in axioms do
      unless allowedAxioms.contains ax do
        throwError "{target} from {moduleName} depends on disallowed axiom {ax}"

    let isLogical ← liftTermElabM <| Meta.isProp info.type
    if isLogical then
      logicalTargets := logicalTargets.push target

    declarationsAudited := declarationsAudited + 1
    logInfo m!"audited formal declaration {target} module={moduleName} kind={declarationKind info} logical={isLogical}"
    for ax in axioms do
      logInfo m!"  allowed axiom: {ax}"

  if logicalTargets.isEmpty then
    throwError "OPT formal audit found no proposition-valued formal-source declarations"

  logInfo m!"OPT_FORMAL_AUDIT_COMPLETE release=v1.0.0 records=5 declarations={declarationsAudited} logical_exports={logicalTargets.size} logical_export_types=verified axiom_allowlist=verified audit_root=OPTFormalAll declaration_scope=origin-module all_declaration_axioms=verified audit_root_included=verified"
