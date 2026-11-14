"""CI must run crypto tests; one native Windows API test is inapplicable on Linux."""
import sys
import unittest

suite = unittest.defaultTestLoader.discover('tests')
result = unittest.TextTestRunner(verbosity=2).run(suite)
allowed = ('test_windows_control.ControlTests.test_native_timezone_conversion',
           'Windows local timezone conversion')
unexpected = [(test.id(), reason) for test, reason in result.skipped
              if sys.platform == 'win32' or (test.id(), reason) != allowed]
for test, reason in result.skipped:
    print('PLATFORM_NOT_APPLICABLE' if (test.id(), reason) == allowed and sys.platform!='win32'
          else 'ACCEPTANCE_FAIL_SKIPPED_TEST', test.id(), reason)
print('ZS015_TEST_COUNTS', dict(discovered=result.testsRun,
      executed=result.testsRun-len(result.skipped), skipped=len(result.skipped),
      unexpected_skips=len(unexpected)))
sys.exit(0 if result.wasSuccessful() and not unexpected else 1)
