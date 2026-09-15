# Source note — adaptive and nonlinear optimization libraries

These projects inform `OPT-SEARCH-001` and the problem-classification guidance. OPT does not vendor them.

## BayesianOptimization

- Repository: https://github.com/bayesian-optimization/BayesianOptimization
- inspected identity: `af8b928212f0eacd1ce20c20be72c1a7b1d8d421`
- license: MIT
- useful mechanisms: Gaussian-process surrogate search for expensive objectives; exploration/exploitation acquisition functions; sequential domain reduction; asynchronous diversification via `ConstantLiar`; acquisition-function portfolio selection via `GPHedge`.

## Hyperopt

- Repository: https://github.com/hyperopt/hyperopt
- inspected identity: `9834314879c09c13e0b8e93eb678408ba46441a8`
- license: BSD-style permissive license in `LICENSE.txt`
- useful mechanisms: search over real, discrete and conditional spaces; Tree of Parzen Estimators; distributed evaluation; explicit trade-off between adaptive information flow and parallel batch width.

## NLopt

- Repository: https://github.com/stevengj/nlopt
- inspected identity: `6e6593f131ba3a38bc9edbed0a357bc01526e54b`
- licensing: combined default build includes LGPL-governed components; build configurations without the Luksan code may use the documented MIT terms. See upstream `COPYING` before incorporating code.
- useful mechanisms: explicit taxonomy of global/local and gradient/derivative-free algorithms; hybrid global/local search; objective/parameter/evaluation/time stopping criteria.

## OPT extraction

The reusable rule is not "always use Bayesian optimization". First classify the problem, then choose a search mechanism that matches variable type, objective cost/noise, constraints, gradient availability, exactness requirement and evaluation budget.
