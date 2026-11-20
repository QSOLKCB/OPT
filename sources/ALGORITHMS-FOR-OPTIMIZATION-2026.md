# Source note — Algorithms for Optimization (second edition, 2026)

- **Authors:** Mykel J. Kochenderfer and Tim A. Wheeler.
- **Publication:** *Algorithms for Optimization*, second edition, MIT Press, 2026.
- **Relevant sections:** §15.1 (Pareto optimality and strict dominance), §15.2–15.5 (multiobjective methods), §16 (sampling plans), §19 (surrogate optimization).
- **Book page:** http://mitpress.mit.edu/algorithms-for-optimization
- **Source inspected:** owner-supplied 633-page PDF, internally dated 2026-09-05. Neither the book nor its figures are distributed here.

## Licensing boundary

The book PDF is marked **CC BY-NC-ND 4.0**, not Apache-2.0. The preface separately grants permission to use code snippets with source acknowledgement. OPT's reference is original Python implementing the classical mathematical definition of strict Pareto dominance; it does not copy the book's Julia implementation, text, figures or page layouts. Preserve the bibliographic acknowledgement; consult the applicable rights terms before reproducing book material.

## Technical extraction

Section 15.1 defines dominance for minimization objectives: candidate A dominates B when A is no worse in every objective and strictly better in at least one. Equal objective vectors do not strictly dominate one another. A Pareto frontier over a **finite observed ledger** is therefore exactly computable by comparing each candidate against all other observed feasible candidates, provided the numeric comparisons and feasibility flags are trustworthy.

A finite-ledger selection is **not** a global Pareto proof over an unsearched continuous or discrete design space. The mechanism does not propose trials, optimize objective functions, prove feasibility, certify a statistical performance gain or select a unique preferred trade-off. Hard correctness constraints are evaluated before ranking, independently of this algorithm.

## Downstream application ideas (not measured gains)

- OPT: reference for multiobjective selections in adaptive search, preserving objective directions and stable IDs.
- VANILLAJS: offline profile analysis for measured FPS Lab frame-time, memory and graphics-quality trade-offs, after parity and workload checks.
- Future: sampling plans (§16) and surrogate acquisition (§19) under explicit trial and compute budgets.

See [OPT-PARETO-001](../optimizations/OPT-PARETO-001-bounded-pareto-frontier.md) and [the executable reference](../examples/pareto_frontier.py).
