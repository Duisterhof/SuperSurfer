"""Run the real Python suite in a reproducible randomized order."""
import argparse
import os
from pathlib import Path
import random
import sys
import unittest

parser = argparse.ArgumentParser()
parser.add_argument('--seed', type=int, required=True)
parser.add_argument('--pattern', default='test*.py')
args = parser.parse_args()
root = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(root), str(root / 'tests')]
os.chdir(root)
os.environ['SUPERSURFER_QA_SEED'] = str(args.seed)

def cases(suite):
    for case in suite:
        if isinstance(case, unittest.TestSuite):
            yield from cases(case)
        else:
            yield case

suite = list(cases(unittest.defaultTestLoader.discover(str(root / 'tests'), pattern=args.pattern)))
random.Random(args.seed).shuffle(suite)
print('Randomized test order seed:', args.seed, 'cases:', len(suite), flush=True)
result = unittest.TextTestRunner(verbosity=2, failfast=True).run(unittest.TestSuite(suite))
raise SystemExit(0 if result.wasSuccessful() else 1)
