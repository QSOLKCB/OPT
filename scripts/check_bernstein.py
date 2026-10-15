"""Replay frozen exact fixtures and verify their source-bound receipt."""
from hashlib import sha256
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from examples.bernstein_bounds import certify, verify


def main():
    evidence = ROOT/'examples/evidence'
    fixture = json.loads((evidence/'bernstein-fixtures-v1.json').read_text())
    receipt = json.loads((evidence/'bernstein-receipt-v1.json').read_text())
    expected_paths = {'examples/bernstein_bounds.py', 'tests/test_bernstein_bounds.py',
                      'scripts/check_bernstein.py', 'examples/evidence/bernstein-fixtures-v1.json'}
    if set(receipt['sha256']) != expected_paths:
        raise ValueError('receipt source inventory mismatch')
    for path, digest in receipt['sha256'].items():
        if sha256((ROOT/path).read_bytes()).hexdigest() != digest:
            raise ValueError('source binding mismatch: '+path)
    outcomes = {}
    for case in fixture['cases']:
        result = certify(case['problem'], case['certificate']['max_splits'])
        if result != case['certificate'] or verify(case['problem'], result) != case['expected_status']:
            raise ValueError('fixture mismatch: '+case['name'])
        outcomes[case['name']] = result['status']
    if outcomes != receipt['outcomes']:
        raise ValueError('receipt outcomes mismatch')
    print(json.dumps(outcomes, sort_keys=True))


if __name__ == '__main__':
    main()
