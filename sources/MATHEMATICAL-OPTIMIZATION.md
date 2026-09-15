# Source note — mathematical and combinatorial optimization foundations

This source note supplies vocabulary and problem structure, not benchmark evidence.

## Sources

- Wang, L., Zhao, J. (2023), "Mathematical Optimization", in *Architecture of Advanced Numerical Analysis Systems*, Apress. DOI: https://doi.org/10.1007/978-1-4842-8853-5_4
- Optimization problem overview: https://en.wikipedia.org/wiki/Optimization_problem
- Combinatorial optimization overview: https://en.wikipedia.org/wiki/Combinatorial_optimization
- NLopt algorithm taxonomy: https://github.com/stevengj/nlopt

## Extraction for OPT

OPT models a target problem using a search space, feasible set, objective, direction, correctness constraints, evaluation budget and stopping rule. The problem is classified before selecting the mechanism: continuous/discrete/mixed, local/global, deterministic/noisy, gradient/derivative-free, exact/approximate and sequential/parallel.

Combinatorial optimization contributes a distinct mechanism: maintain an incumbent feasible solution, compute optimistic bounds for subregions, and prune regions that provably cannot improve the incumbent. Relaxations may be used to obtain cheap bounds without treating the relaxed solution as the final answer.

See `OPTIMIZATION-PROBLEM.md` and `OPT-PRUNE-001`.
