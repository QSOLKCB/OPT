import Lean.Elab.Command
import Lean.Util.CollectAxioms
import OPTFormal

open Lean
open Lean.Elab Command

private def allowedAxioms : Array Name := #[
  `propext
]

/--
Collect every exported theorem in the OPTFormal namespace from the imported
module graph. Private declarations use private names and therefore do not match
the public `OPTFormal.` prefix.
-/
private def exportedTheorems (env : Environment) : Array Name := Id.run do
  let mut targets : Array Name := #[]
  for moduleData in env.header.moduleData do
    for info in moduleData.constants do
      if info.name.toString.startsWith "OPTFormal." then
        match info with
        | .thmInfo _ => targets := targets.push info.name
        | _ => pure ()
  return targets.qsort Name.lt

run_cmd do
  let env ← getEnv
  let targets := exportedTheorems env
  if targets.isEmpty then
    throwError "OPT formal audit found no exported theorems"

  for target in targets do
    let some info := env.find? target
      | throwError "missing exported theorem {target}"
    match info with
    | .thmInfo _ => pure ()
    | _ => throwError "exported audit target {target} is not a theorem"

    let axioms ← Lean.collectAxioms target
    for ax in axioms do
      unless allowedAxioms.contains ax do
        throwError "{target} depends on disallowed axiom {ax}"

    logInfo m!"audited theorem {target}"
    for ax in axioms do
      logInfo m!"  allowed axiom: {ax}"

  logInfo m!"OPT_FORMAL_AUDIT_COMPLETE release=v1.0.0 records=5 theorems={targets.size} theorem_kinds=verified axiom_allowlist=verified"
