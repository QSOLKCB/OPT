import Lake
open Lake DSL

package opt_formal where
  srcDir := "Lean"

@[default_target]
lean_lib OPTFormal

/-- Unpinned audit root covering all separately versioned OPT formal modules. -/
@[default_target]
lean_lib OPTFormalAll
