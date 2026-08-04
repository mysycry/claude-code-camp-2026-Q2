import os
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
sys.path.insert(0, os.path.join(HERE, "..", "..", "week1_baseline", "python", "12_context"))
sys.path.insert(0, os.path.join(HERE, "..", ".."))

if __name__ == "__main__":
    suite = unittest.defaultTestLoader.discover(os.path.dirname(__file__), pattern="test_*.py")
    runner = unittest.TextTestRunner(verbosity=2)
    result = runner.run(suite)
    sys.exit(0 if result.wasSuccessful() else 1)
