import importlib.util
from pathlib import Path
import unittest
from unittest.mock import patch

class RetiredProbe016Tests(unittest.TestCase):
    def test_013_and_014_legacy_functions_cannot_start_network(self):
        for name in ['stage03-source-clock-probe.py','stage03-nts-probe.py']:
            spec=importlib.util.spec_from_file_location('legacy_probe',Path('scripts')/name)
            module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
            with patch('socket.socket',side_effect=AssertionError('network forbidden')):
                with self.assertRaisesRegex(RuntimeError,'HISTORICAL_PROBE_RETIRED'):
                    module.run(Path('unused-no-output-created'))
