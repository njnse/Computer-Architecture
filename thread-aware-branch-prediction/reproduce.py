"""Run correctness tests, then regenerate the full experiment."""
import unittest
from experiment import run

if __name__=="__main__":
    result=unittest.TextTestRunner(verbosity=2).run(
        unittest.defaultTestLoader.discover(".",pattern="test_predictor.py"))
    if not result.wasSuccessful():
        raise SystemExit(1)
    run()
