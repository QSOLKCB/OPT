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
under the `OPTFormal.*` module hierarchy. `OPTFormalAll` is only the unpinned
audit aggregator and is deliberately excluded from the audited source set.
-/
private def isFormalSourceModule (moduleName : Name) : Bool :=
  let rendered := moduleName.toString
  rendered == "OPTFormal" || rendered.startsWith "OPTFormal."

/--
Collect declarations by their originating formal module, not by declaration
namespace. CI separately proves that `OPTFormalAll` imports every source module
under `Lean/OPTFormal/`, while the pinned `OPTFormal` root is imported too.

This means a future `OPTFormal.FrozenV200` module cannot evade the audit by
declaring a theorem in the root namespace or in an unrelated namespace such as
`OPTFormalV200`.
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
  let mut targets : Array Name := #[]

  if candidates.isEmpty then
    throwError "OPT formal audit found no declarations originating in formal source modules"

  -- A logical export is any declaration from an audited formal module whose
  -- complete type is a Prop. Selection is independent of declaration namespace
  -- and declaration syntax (`theorem`, proof-valued `def`, opaque, etc.).
  for target in candidates do
    let some info := env.find? target
      | throwError "missing formal-source declaration {target}"
    if ← liftTermElabM <| Meta.isProp info.type then
      targets := targets.push target

  if targets.isEmpty then
    throwError "OPT formal audit found no proposition-valued formal-source declarations"

  for target in targets do
    let some info := env.find? target
      | throwError "missing audited logical declaration {target}"
    let some modIdx := env.getModuleIdxFor? target
      | throwError "audited declaration {target} has no originating module"
    let moduleName := env.header.moduleNames[modIdx]!
    unless isFormalSourceModule moduleName do
      throwError "audited declaration {target} originated outside formal source modules: {moduleName}"

    let axioms ← Lean.collectAxioms target
    for ax in axioms do
      unless allowedAxioms.contains ax do
        throwError "{target} from {moduleName} depends on disallowed axiom {ax}"

    logInfo m!"audited logical declaration {target} module={moduleName} kind={declarationKind info}"
    for ax in axioms do
      logInfo m!"  allowed axiom: {ax}"

  logInfo m!"OPT_FORMAL_AUDIT_COMPLETE release=v1.0.0 records=5 logical_exports={targets.size} logical_export_types=verified axiom_allowlist=verified audit_root=OPTFormalAll declaration_scope=origin-module"
