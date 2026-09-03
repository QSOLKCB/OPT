import Lean.Elab.Command
import Lean.Meta.Basic
import Lean.Util.CollectAxioms
import OPTFormal

open Lean
open Lean.Elab Command

private def allowedAxioms : Array Name := #[
  `propext
]

/--
Collect every exported declaration in the OPTFormal namespace from the imported
module graph. Private declarations use private names and therefore do not match
the public `OPTFormal.` prefix.
-/
private def exportedDeclarations (env : Environment) : Array Name := Id.run do
  let mut targets : Array Name := #[]
  for moduleData in env.header.moduleData do
    for info in moduleData.constants do
      if info.name.toString.startsWith "OPTFormal." then
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
  let candidates := exportedDeclarations env
  let mut targets : Array Name := #[]

  -- A logical export is any public declaration whose complete type is a Prop.
  -- This includes ordinary theorem declarations and proof-valued `def`/opaque
  -- declarations, so changing declaration syntax cannot escape axiom review.
  for target in candidates do
    let some info := env.find? target
      | throwError "missing exported declaration {target}"
    if ← liftTermElabM <| Meta.isProp info.type then
      targets := targets.push target

  if targets.isEmpty then
    throwError "OPT formal audit found no exported proposition-valued declarations"

  for target in targets do
    let some info := env.find? target
      | throwError "missing exported logical declaration {target}"

    let axioms ← Lean.collectAxioms target
    for ax in axioms do
      unless allowedAxioms.contains ax do
        throwError "{target} depends on disallowed axiom {ax}"

    logInfo m!"audited logical export {target} kind={declarationKind info}"
    for ax in axioms do
      logInfo m!"  allowed axiom: {ax}"

  logInfo m!"OPT_FORMAL_AUDIT_COMPLETE release=v1.0.0 records=5 logical_exports={targets.size} logical_export_types=verified axiom_allowlist=verified"
