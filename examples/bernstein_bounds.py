"""Exact, bounded univariate lower-bound certificates. No floating-point inputs.

Original implementation of the classical Bernstein enclosure, following Muñoz
and Narkawicz (2013), Proposition 3 / Corollary 1. No external code is copied.
The checker reconstructs polynomials rather than trusting the producer.
"""
from fractions import Fraction
from hashlib import sha256
from math import comb
import json

MAX_DEGREE = 12
MAX_BITS = 128
MAX_SPLITS = 256
MAX_DEPTH = 12


def require(condition, message):
    if not condition:
        raise ValueError(message)


def rational(value):
    require(type(value) is str and len(value) <= 80, 'expected bounded canonical rational string')
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError('invalid rational') from exc
    require(str(result) == value, 'noncanonical rational')
    require(max(abs(result.numerator).bit_length(), result.denominator.bit_length()) <= MAX_BITS,
            'input rational exceeds bit budget')
    return result


def vector(values):
    require(type(values) is list and 1 <= len(values) <= MAX_DEGREE + 1, 'invalid polynomial degree')
    result = [rational(v) for v in values]
    require(len(result) == 1 or result[-1] != 0, 'polynomial must have canonical degree')
    return result


def parse(problem):
    require(type(problem) is dict and set(problem) == {'numerator', 'denominator', 'domain', 'lower', 'strict'},
            'invalid problem schema')
    n, d = vector(problem['numerator']), vector(problem['denominator'])
    require(type(problem['domain']) is list and len(problem['domain']) == 2, 'invalid domain')
    a, b = map(rational, problem['domain'])
    require(a < b, 'domain must be a nondegenerate closed interval')
    require(type(problem['strict']) is bool, 'strict must be boolean')
    lower = rational(problem['lower'])
    residual = [(n[i] if i < len(n) else 0) - lower * (d[i] if i < len(d) else 0)
                for i in range(max(len(n), len(d)))]
    while len(residual) > 1 and residual[-1] == 0:
        residual.pop()
    return residual, d, a, b, problem['strict']


def identity(problem):
    return sha256(json.dumps(problem, sort_keys=True, separators=(',', ':')).encode()).hexdigest()


def evaluate(p, x):
    out = Fraction(0)
    for c in reversed(p):
        out = out * x + c
    return out


def coefficients(p, a, b):
    """Producer: binomial affine substitution then power-to-Bernstein map."""
    degree = len(p) - 1
    power = [sum((p[i] * comb(i, k) * a ** (i-k) * (b-a) ** k
                  for i in range(k, degree+1)), Fraction(0)) for k in range(degree+1)]
    return [sum((power[k] * Fraction(comb(i, k), comb(degree, k))
                 for k in range(i+1)), Fraction(0)) for i in range(degree+1)]


def multiply(p, q):
    out = [Fraction(0)] * (len(p) + len(q) - 1)
    for i, c in enumerate(p):
        for j, d in enumerate(q):
            out[i+j] += c*d
    return out


def reconstruct(p, a, b, values):
    """Checker: expand basis polynomials, independently substitute by Horner."""
    degree = len(p)-1
    require(type(values) is list and len(values) == degree+1, 'coefficient degree mismatch')
    # Outputs can grow beyond input limits; a conservative bounded text limit
    # prevents giant Fraction parsing, while covering this degree/domain budget.
    decoded = []
    for v in values:
        require(type(v) is str and len(v) <= 10000, 'invalid witness coefficient')
        try:
            f = Fraction(v)
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError('invalid coefficient') from exc
        require(str(f) == v, 'noncanonical coefficient')
        decoded.append(f)
    expanded = [Fraction(0)] * (degree+1)
    for i, c in enumerate(decoded):
        term = [c * comb(degree, i)]
        for _ in range(i):
            term = multiply(term, [0, 1])
        for _ in range(degree-i):
            term = multiply(term, [1, -1])
        for k, v in enumerate(term):
            expanded[k] += v
    transformed = [Fraction(0)]
    for c in reversed(p):
        transformed = multiply(transformed, [a, b-a])
        transformed[0] += c
    while len(transformed) > degree+1:
        require(transformed.pop() == 0, 'unexpected affine degree')
    require(expanded == transformed, 'Bernstein reconstruction mismatch')
    return decoded


def interval(a, b, path):
    require(type(path) is str and len(path) <= MAX_DEPTH and set(path) <= {'0', '1'}, 'invalid subdivision path')
    for bit in path:
        middle = (a+b)/2
        if bit == '0':
            b = middle
        else:
            a = middle
    return a, b


def sufficient(residual, denominator, strict):
    return min(denominator) > 0 and (min(residual) > 0 if strict else min(residual) >= 0)


def certify(problem, max_splits=16):
    """Produce full-domain certificate, exact violation, or honest inconclusive.

    Denominator must be strictly positive on the entire closed domain. A
    witnessed nonpositive denominator yields invalid_domain, never violation.
    """
    p, d, a, b, strict = parse(problem)
    require(type(max_splits) is int and 0 <= max_splits <= MAX_SPLITS, 'invalid split budget')
    paths = ['']
    witness = None
    while True:
        leaves = []
        unresolved = []
        denominator_unresolved = []
        violation = None
        invalid_domain = None
        for path in paths:
            left, right = interval(a, b, path)
            pc, dc = coefficients(p, left, right), coefficients(d, left, right)
            leaves.append({'path': path, 'residual': list(map(str, pc)), 'denominator': list(map(str, dc))})
            if not sufficient(pc, dc, strict):
                unresolved.append(path)
            if min(dc) <= 0:
                denominator_unresolved.append(path)
            for x in (left, (left+right)/2, right):
                den, residual = evaluate(d, x), evaluate(p, x)
                if den <= 0 and invalid_domain is None:
                    invalid_domain = {'x': str(x), 'kind': 'invalid_domain'}
                elif den > 0 and (residual < 0 or (strict and residual == 0)) and violation is None:
                    violation = {'x': str(x), 'kind': 'violation'}
        if invalid_domain:
            witness, status = invalid_domain, 'invalid_domain'
            break
        if violation and not denominator_unresolved:
            witness, status = violation, 'violated'
            break
        # Resolve the global denominator precondition before classifying a
        # local bound failure. Never spend the budget refining negative R
        # while an unrelated denominator leaf still needs proof.
        if violation:
            unresolved = denominator_unresolved
        if not unresolved:
            status = 'certified'
            break
        candidates = [path for path in unresolved if len(path) < MAX_DEPTH]
        if len(paths)-1 >= max_splits or not candidates:
            status = 'inconclusive'
            break
        target = candidates[0]
        index = paths.index(target)
        paths[index:index+1] = [target+'0', target+'1']
    result = {'problem_sha256': identity(problem), 'max_splits': max_splits,
              'status': status, 'leaves': leaves, 'witness': witness}
    verify(problem, result)
    return result


def verify(problem, certificate):
    """Validate against caller-supplied problem; return checked status or raise."""
    p, d, a, b, strict = parse(problem)
    require(type(certificate) is dict and set(certificate) ==
            {'problem_sha256', 'max_splits', 'status', 'leaves', 'witness'}, 'invalid certificate schema')
    require(certificate['problem_sha256'] == identity(problem), 'source problem identity mismatch')
    budget = certificate['max_splits']
    require(type(budget) is int and 0 <= budget <= MAX_SPLITS, 'invalid split budget')
    leaves = certificate['leaves']
    require(type(leaves) is list and 1 <= len(leaves) <= budget+1, 'invalid leaf budget')
    cursor = a
    all_proved = True
    denominator_proved = True
    for leaf in leaves:
        require(type(leaf) is dict and set(leaf) == {'path', 'residual', 'denominator'}, 'invalid leaf schema')
        left, right = interval(a, b, leaf['path'])
        require(left == cursor, 'partition gap, overlap or wrong order')
        cursor = right
        pc = reconstruct(p, left, right, leaf['residual'])
        dc = reconstruct(d, left, right, leaf['denominator'])
        all_proved = all_proved and sufficient(pc, dc, strict)
        denominator_proved = denominator_proved and min(dc) > 0
    require(cursor == b, 'incomplete domain coverage')
    witness = certificate['witness']
    if witness is not None:
        require(type(witness) is dict and set(witness) == {'x', 'kind'}, 'invalid witness schema')
        # Midpoints may have more bits than input rationals.
        require(type(witness['x']) is str and len(witness['x']) <= 200, 'invalid witness coordinate')
        try:
            x = Fraction(witness['x'])
        except (ValueError, ZeroDivisionError) as exc:
            raise ValueError('invalid witness coordinate') from exc
        require(str(x) == witness['x'] and a <= x <= b, 'witness outside domain or noncanonical')
        den, residual = evaluate(d, x), evaluate(p, x)
        if witness['kind'] == 'invalid_domain':
            require(den <= 0, 'false denominator witness')
            status = 'invalid_domain'
        else:
            require(witness['kind'] == 'violation' and denominator_proved and den > 0 and
                    (residual < 0 or (strict and residual == 0)), 'false violation witness')
            status = 'violated'
    else:
        status = 'certified' if all_proved else 'inconclusive'
    require(certificate['status'] == status, 'unsupported claimed status')
    return status
