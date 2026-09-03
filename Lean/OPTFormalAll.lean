import OPTFormal
import OPTFormal.Core
import OPTFormal.FrozenV100

/-!
# OPT formal audit root

This module is intentionally **not** part of the permanently pinned v1 model.
Every module under `Lean/OPTFormal/` must be imported here. CI compares this
import list with the on-disk module set before building, so separately versioned
modules such as `OPTFormal.FrozenV200` cannot exist outside the logical audit.
-/
