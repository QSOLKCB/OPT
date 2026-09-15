# Source note — Psycledelics Wonderbuild

**Source:** https://github.com/psycledelics/wonderbuild  
**Pinned source identity:** commit `021d5ed7c298c6c34b091cf5e6d9802e200028a6`  
**Role in OPT:** historical implementation donor, not a dependency.

Wonderbuild is an older Python build system from the Psycle/Psycledelics community. Its reusable value for OPT is architectural rather than its Python-2-era implementation.

## Mechanisms extracted

- persistent input signatures and selective invalidation;
- success-only persistence of updated task signatures;
- cached configuration checks keyed by their effective inputs;
- dependency-aware task scheduling with run-once semantics;
- filesystem metadata/state reuse to reduce repeated scans;
- benchmark separation between cold, no-op, small-partial and large-partial rebuilds;
- historical translation-unit batching as a compiler-process amortization idea.

## Evidence boundary

Wonderbuild's own benchmark material is historical and environment-specific. OPT does not promote those timings as modern targets. The reusable claim is the mechanism and test shape.

## Licensing boundary

Wonderbuild source files state GPL-2.0-or-later terms and credit Psycle project contributors including Johan Boule. OPT therefore records the design patterns and provenance without copying Wonderbuild implementation code into this Apache-2.0 repository.

## Records informed

- `OPT-INC-001`
- `OPT-PAR-001` (supporting scheduling evidence)
- future C/C++ batching experiments may cite this source, but no portable compiler speedup is claimed here.
