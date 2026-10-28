#!/usr/bin/env python3
"""Validate fictional storyboard behavior without filming or model calls."""
import copy
from pathlib import Path
import unittest
import teaserkit as tk
ROOT=Path(__file__).resolve().parents[1]
class Gate(unittest.TestCase):
    def test_fictional_demo_validates_without_ai_or_browser(self):
        sb=tk.load_storyboard(ROOT/'examples/demo-app/storyboard.yaml')
        self.assertTrue(tk.validate(sb).ok)
    def test_deny_term_is_a_real_validation_failure(self):
        sb=tk.load_storyboard(ROOT/'examples/demo-app/storyboard.yaml')
        sb.project.deny_list.append('FictionalForbiddenToken')
        sb.videos[0].beats[0].caption='FictionalForbiddenToken'
        report=tk.validate(sb)
        self.assertFalse(report.ok)
        self.assertTrue(any('deny' in issue.rule for issue in report.errors))
if __name__=='__main__':unittest.main(verbosity=2)
