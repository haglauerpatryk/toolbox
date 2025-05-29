import unittest
from unittest.mock import patch, call
import os
import yaml

from toolbox.core import ToolBox, _load_config
from toolbox.logger import flush_logs  # If you want to test file logging too

TEST_CONFIG_PATH = "toolbox/test_config.yaml"

def write_test_config(display=None, on_error=None):
    config = {}
    if display is not None:
        config["display"] = display
    if on_error is not None:
        config["on_error"] = on_error
    with open(TEST_CONFIG_PATH, 'w') as f:
        yaml.dump(config, f)

class TestToolBox(unittest.TestCase):

    def tearDown(self):
        if os.path.exists(TEST_CONFIG_PATH):
            os.remove(TEST_CONFIG_PATH)
        if os.path.exists("logs.txt"):
            os.remove("logs.txt")

    def test_track_info_hooks(self):
        write_test_config(display=['track_info'])

        @ToolBox(config=_load_config(TEST_CONFIG_PATH)).wrap
        def sample_func():
            print("Function running")
            return "done"

        with patch("builtins.print") as mock_print:
            sample_func()

        mock_print.assert_has_calls([
            call("[BEFORE] Path set to: /fake/path/example.txt"),
            call("Function running"),
            call("[AFTER] Result summary: done, path was: /fake/path/example.txt")
        ], any_order=False)

    def test_track_time_hooks(self):
        write_test_config(display=['track_time'])

        @ToolBox(config=_load_config(TEST_CONFIG_PATH)).wrap
        def sample_func():
            return "timed result"

        with patch("builtins.print") as mock_print:
            sample_func()

        mock_print.assert_any_call("[BEFORE] Timer started")
        self.assertTrue(any("Duration" in str(c.args[0]) for c in mock_print.call_args_list))

    def test_combined_hooks(self):
        write_test_config(display=['track_info', 'track_time'])

        @ToolBox(config=_load_config(TEST_CONFIG_PATH)).wrap
        def sample_func():
            return "mixed"

        with patch("builtins.print") as mock_print:
            sample_func()

        mock_print.assert_any_call("[BEFORE] Path set to: /fake/path/example.txt")
        mock_print.assert_any_call("[BEFORE] Timer started")
        mock_print.assert_any_call("[AFTER] Result summary: mixed, path was: /fake/path/example.txt")
        self.assertTrue(any("Duration" in str(c.args[0]) for c in mock_print.call_args_list))

    def test_on_error_hook(self):
        write_test_config(on_error=['handle_problem'])

        @ToolBox(config=_load_config(TEST_CONFIG_PATH)).wrap
        def faulty_func():
            raise ValueError("fail")

        with patch("builtins.print") as mock_print:
            with self.assertRaises(ValueError):
                faulty_func()

            mock_print.assert_any_call("[ERROR] Caught: fail")

    def test_no_hooks(self):
        write_test_config(display=[], on_error=[])

        @ToolBox(config=_load_config(TEST_CONFIG_PATH)).wrap
        def simple_func():
            return 42

        with patch("builtins.print") as mock_print:
            result = simple_func()

        self.assertEqual(result, 42)
        mock_print.assert_not_called()
