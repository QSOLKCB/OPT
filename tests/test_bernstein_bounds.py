"""Regression and mutation tests for full-domain exact certificates."""
import copy
from fractions import Fraction
import json
from pathlib import Path
import random
import unittest

from examples.bernstein_bounds import certify, coefficients, evaluate, reconstruct, verify

ROOT = Path(__file__).resolve().parents[1]


def problem(n, lower='0', strict=False, d=None, domain=None):
    return {'numerator': n, 'denominator': d or ['1'], 'domain': domain or ['0', '1'],
            'lower': lower, 'strict': strict}


class BernsteinTests(unittest.TestCase):
    def test_direct_and_subdivision(self):
        self.assertEqual(certify(problem(['1', '1']), 0)['status'], 'certified')
        p = problem(['13/50', '-1', '1'], '1/100')
        self.assertEqual(certify(p, 0)['status'], 'inconclusive')
        result = certify(p, 1)
        self.assertEqual(result['status'], 'certified')
        self.assertEqual([v['path'] for v in result['leaves']], ['0', '1'])
        self.assertEqual(certify(p, 1), result)  # no process-global state

    def test_violation_and_boundary(self):
        self.assertEqual(certify(problem(['-1', '1']))['status'], 'violated')
        self.assertEqual(certify(problem(['0', '0', '1']))['status'], 'certified')
        result = certify(problem(['0', '0', '1'], strict=True))
        self.assertEqual(result['status'], 'violated')
        self.assertEqual(result['witness']['x'], '0')

    def test_denominator(self):
        self.assertEqual(certify(problem(['1'], d=['1', '1']))['status'], 'certified')
        for d in (['-1', '2'], ['0', '1'], ['0']):
            self.assertEqual(certify(problem(['0'], d=d))['status'], 'invalid_domain')
        # Positive denominator needs subdivision; no invented pole/violation.
        p = problem(['1'], d=['13/50', '-1', '1'])
        self.assertEqual(certify(p, 0)['status'], 'inconclusive')
        self.assertEqual(certify(p, 1)['status'], 'certified')
        self.assertEqual(certify(problem(['1'], d=['1/1000000', '1']))['status'], 'certified')

    def test_certificate_mutations(self):
        p = problem(['13/50', '-1', '1'], '1/100')
        c = certify(p, 1)
        mutations = []
        def mutated(fn):
            candidate = copy.deepcopy(c)
            fn(candidate)
            mutations.append(candidate)
        mutated(lambda c: c['leaves'].pop())
        mutated(lambda c: c['leaves'].reverse())
        mutated(lambda c: c['leaves'][1].update(path='0'))
        mutated(lambda c: c['leaves'][0]['residual'].__setitem__(1, '1'))
        mutated(lambda c: c['leaves'][0]['residual'].pop())
        mutated(lambda c: c['leaves'][0]['denominator'].__setitem__(0, '-1'))
        mutated(lambda c: c.update(status='violated'))
        mutated(lambda c: c.update(witness={'x':'1/2', 'kind':'violation'}))
        mutated(lambda c: c.update(witness={'x':'1/2', 'kind':'invalid_domain'}))
        mutated(lambda c: c.update(witness={'x':'2', 'kind':'violation'}))
        mutated(lambda c: c.update(max_splits=0))
        mutated(lambda c: c.update(max_splits=True))
        mutated(lambda c: c.update(problem_sha256='0'*64))
        mutated(lambda c: c['leaves'][0].update(path='0'*13))
        for candidate in mutations:
            with self.subTest(candidate=candidate), self.assertRaises(ValueError):
                verify(p, candidate)
        for key, value in [('lower','1/50'), ('domain',['0','2']), ('strict',True),
                           ('numerator',['1']), ('denominator',['2'])]:
            changed = copy.deepcopy(p)
            changed[key] = value
            with self.assertRaises(ValueError):
                verify(changed, c)

    def test_input_limits(self):
        for n in ([0.1], [True], ['1.0'], ['2/2'], ['1/0'], ['0','0'],
                  ['1']*14, [str(1<<129)], ['9'*1000]):
            with self.subTest(n=n), self.assertRaises(ValueError):
                certify(problem(n))
        for budget in (-1, 257, True, 1.0):
            with self.assertRaises(ValueError):
                certify(problem(['1']), budget)
        for domain in (['1','0'], ['0','0']):
            with self.assertRaises(ValueError):
                certify(problem(['1'],domain=domain))

    def test_independent_evaluation_and_reconstruction(self):
        rng = random.Random(5162013)
        for degree in range(13):
            for _ in range(10):
                p = [Fraction(rng.randrange(-8,9), rng.randrange(1,10)) for _ in range(degree+1)]
                a = Fraction(rng.randrange(-8,1), 3)
                b = a + Fraction(rng.randrange(1,9), 5)
                c = coefficients(p,a,b)
                self.assertEqual(reconstruct(p,a,b,list(map(str,c))), c)
                from math import comb
                for k in range(9):
                    t = Fraction(k,8)
                    expanded = sum(c[i]*comb(degree,i)*t**i*(1-t)**(degree-i)
                                   for i in range(degree+1))
                    self.assertEqual(evaluate(p,a+(b-a)*t), expanded)

    def test_frozen_fixtures(self):
        fixtures = json.loads((ROOT/'examples/evidence/bernstein-fixtures-v1.json').read_text())
        for case in fixtures['cases']:
            with self.subTest(case=case['name']):
                self.assertEqual(verify(case['problem'], case['certificate']), case['expected_status'])
                self.assertEqual(certify(case['problem'], case['certificate']['max_splits']), case['certificate'])

    def test_receipt_source_bindings(self):
        from hashlib import sha256
        receipt = json.loads((ROOT/'examples/evidence/bernstein-receipt-v1.json').read_text())
        for path, expected in receipt['sha256'].items():
            self.assertEqual(sha256((ROOT/path).read_bytes()).hexdigest(), expected, path)


if __name__ == '__main__':
    unittest.main()
