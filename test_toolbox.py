import unittest
from unittest.mock import patch, call
import os
import yaml

from toolbox.core import ToolBox, _load_config

TEST_CONFIG_PATH = "toolbox/test_config.yaml"

def write_test_config(before=None, after=None, on_error=None):
    config = {
        "before": before or [],
        "after": after or [],
        "on_error": on_error or []
    }
    with open(TEST_CONFIG_PATH, 'w') as f:
        yaml.dump(config, f)

class TestToolBox(unittest.TestCase):

    def tearDown(self):
        if os.path.exists(TEST_CONFIG_PATH):
            os.remove(TEST_CONFIG_PATH)

    def test_before_and_after_hooks(self):
        write_test_config(before=['get_path'], after=['print_summary'])

        @ToolBox(config=_load_config(TEST_CONFIG_PATH)).wrap
        def sample_func():
            print("Function running")
            return "done"

        with patch("builtins.print") as mock_print:
            sample_func()

        mock_print.assert_has_calls([
            call("[BEFORE] Extracting path info..."),
            call("Function running"),
            call("[AFTER] Result summary: done")
        ], any_order=False)

    def test_on_error_hook(self):
        write_test_config(on_error=['handle_exception'])

        @ToolBox(config=_load_config(TEST_CONFIG_PATH)).wrap
        def faulty_func():
            raise ValueError("fail")

        with patch("builtins.print") as mock_print:
            with self.assertRaises(ValueError):
                faulty_func()

            mock_print.assert_any_call("[ERROR] Exception caught: fail")

    def test_missing_hooks(self):
        write_test_config(before=[], after=[], on_error=[])

        @ToolBox(config=_load_config(TEST_CONFIG_PATH)).wrap
        def simple_func():
            return 42

        with patch("builtins.print") as mock_print:
            result = simple_func()

        self.assertEqual(result, 42)
        mock_print.assert_not_called()
