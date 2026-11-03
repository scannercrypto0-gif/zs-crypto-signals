"""CI must run every deterministic test; skipped tests are not acceptance."""
import sys
import unittest

suite = unittest.defaultTestLoader.discover('tests')
result = unittest.TextTestRunner(verbosity=2).run(suite)
if result.skipped:
    print('ACCEPTANCE_FAIL_SKIPPED_TESTS', len(result.skipped))
sys.exit(0 if result.wasSuccessful() and not result.skipped else 1)
