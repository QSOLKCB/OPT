# Exact continuous-domain Bernstein bound example

Status: **Implemented reference**. This worked instance of
[OPT-APPROX-001](../../optimizations/OPT-APPROX-001-contract-bounded-approximation.md)
certifies a stated exact bound over the **whole explicit closed rational interval**.
It does not certify a floating-point implementation or improve its runtime.

## Contract and supported scope

The input is a univariate rational polynomial numerator `N`, denominator `D`,
closed interval `[a,b]` with `a < b`, rational lower bound `L`, and strictness flag.
The claim is `N(x)/D(x) >= L` (or `> L`) for every real `x` in `[a,b]`, with
`D(x) > 0` throughout that interval. Ordinary polynomial claims use `D = 1`.
A range `[L,U]` can be established by two separate calls, the second with `-N`
and lower bound `-U`; both certificates must pass for the same domain/denominator.

The search space is dyadic partitions of the declared interval. The feasible
certificates preserve the exact polynomial, closed domain, denominator condition,
and inequality. The objective is to establish the requested bound, with no
optimization of the polynomial or claim of attaining its extremum. The budget
is at most 256 splits, depth 12, and input degree 12. Input coefficients/endpoints
are canonical rational strings, with numerator/denominator at most 128 bits.
The verifier checks at most 257 leaves. These caps bound work and intermediate
arithmetic for supported inputs; there is no wall-time SLA. Stop on a sound
certificate, exact witnessed failure, or finite-budget inconclusive result.
Caller problems, not certificate-supplied substitutions, are the source of truth.

This deliberately small target avoids claiming multivariate/global-optimization
completeness. It is an exact mathematical-polynomial guarantee, not a bound on
transcendental reference functions, floating-point evaluation, stateful horizons,
or any unrelated Lean theorem. Keep an exact/reference fallback whenever the
result is not `certified`. A failed parse or failed certificate verification is
an error, never permission to publish an approximation.

## Construction and independent checking

[Muñoz and Narkawicz, *Formalization of Bernstein Polynomials and Applications to
Global Optimization*](https://shemesh.larc.nasa.gov/fm/papers/jar-mn-2012-draft.pdf),
Journal of Automated Reasoning 51:151–196 (2013), DOI
[10.1007/s10817-012-9256-3](https://doi.org/10.1007/s10817-012-9256-3),
provides the method: Proposition 3 and Corollary 1 give coefficient enclosures;
Section 2.3 explains the benefit of subdivision. The implementation is original
Python using standard-library `Fraction`; no paper or donor implementation is
copied. No PVS or Lean proof was replayed for this example.

The producer forms `R = N - L D` with exact arithmetic, substitutes each leaf
interval into `[0,1]`, and converts its power coefficients into Bernstein form.
The checker instead expands each supplied Bernstein basis polynomial using
polynomial multiplication, and independently uses Horner substitution on `R`
and `D`. It requires exact coefficient-wise equality, including the actual
canonical degree. It also checks the caller problem's SHA-256 binding, every
subdivision path, contiguous ordered coverage from `a` through `b`, and the
finite leaf/depth budget. Gaps, overlaps, repeated leaves, reordered leaves,
truncated degrees, and changed coefficients are rejected.

Bernstein basis functions are nonnegative and sum to one on `[0,1]`. Therefore
all denominator coefficients strictly positive establish `D > 0`; all residual
coefficients nonnegative (strictly positive for strict claims) establish the
claimed inequality on each leaf. Full coverage extends this result to the
entire interval. Strict coefficient positivity is sufficient, not necessary.
An inconclusive enclosure does not imply the function violates the bound.

The producer probes endpoints and midpoints only to find exact witnesses.
Such samples never certify a universal bound. A `violated` result must include
a point in the domain with residual below zero (or zero for a strict claim),
plus strictly positive denominator coefficients on every leaf of the full
partition. An unresolved denominator precondition prevents a `violated` result;
a witnessed nonpositive denominator takes priority as `invalid_domain`. `invalid_domain` requires an exact nonpositive
denominator witness. This denotes failure of this API's positive-denominator
precondition, not necessarily a pole: a negative denominator also fails it.
The API does not cancel common factors to bypass a denominator zero.
If neither coefficient proof nor a witness is available, the result is
`inconclusive`, even if the function actually is unsafe or safe.

## Worked outcomes and controls

- `1+x >= 0` on `[0,1]` certifies directly.
- `(x-1/2)^2 + 1/100 >= 1/100` is inconclusive on the coarse interval. Splitting
  at `1/2` yields residual coefficients `[1/4,0,0]` and `[0,0,1/4]`, certifying
  the entire closed interval. The coarse negative coefficient is no counterexample.
- `x-1 >= 0` produces an exact violation at zero.
- `x^2 >= 0` certifies; `x^2 > 0` fails at the boundary zero.
- `1/(1+x) >= 0` certifies; crossing/zero denominators produce an exact invalid
  domain witness; a small positive denominator is handled without floats.
- Positive quadratic denominators demonstrate both coarse inconclusive and
  subdivision success. A zero numerator does not erase denominator obligations.

Frozen cases are in [bernstein-fixtures-v1.json](bernstein-fixtures-v1.json).
[bernstein-receipt-v1.json](bernstein-receipt-v1.json) binds the exact source,
tests, replay script and fixture bytes, and records outcomes, one observed
runtime/peak-memory measurement, coefficient bit growth and split count.
Runtime observations are not benchmark comparisons or universal guarantees.
Historical OPT fixtures are unchanged. Mutation tests independently reject
omitted subdomains, wrong degree/coefficient/denominator, changed input,
false/out-of-domain witnesses, changed status, and invalid resource budgets.
Finite evaluation comparisons help test arithmetic but are not the basis of
the universal claim.

Run from the repository root (no dependencies beyond Python standard library):

```sh
python3 scripts/check_bernstein.py
python3 -O scripts/check_bernstein.py
python3 -m unittest discover -s tests -p 'test_bernstein_bounds.py' -v
python3 -O -m unittest discover -s tests -p 'test_bernstein_bounds.py' -v
python3 -m unittest discover -s tests -v
python3 scripts/check_catalog.py
```

All proof checks use explicit exceptions, not removable Python assertions.
The source-bound replay checks frozen outputs; it does not silently rewrite
saved evidence to match current code. A future intentional source change needs
a reviewed replacement receipt and the full conformance/rejection suite.
