"""Viewport input boundaries: no browser, renderer, network or model calls."""
import json
import os
import subprocess
import sys

import pytest
import yaml

from teaserkit.errors import StoryboardError
from teaserkit.rules import validate
from teaserkit.storyboard import parse

from conftest import minimal


INVALID = [
    [0, 810], [1440, 0], [-1, 810], [1440, -1],
    [float("nan"), 810], [1440, float("inf")], [float("-inf"), 810],
    [True, 810], [1440, False], ["1440", 810], [1440, "810"],
    [1.5, 810], [1440, 810.0], [], [1440], [1440, 810, 2],
    None, {"width": 1440, "height": 810}, "1440x810", 123,
]


@pytest.mark.parametrize("viewport", INVALID)
def test_parse_rejects_invalid_viewport_with_schema_error(viewport):
    data = minimal()
    data["project"]["viewport"] = viewport
    with pytest.raises(StoryboardError, match=r"project\.viewport") as error:
        parse(data)
    assert error.value.code == "storyboard_invalid"
    assert error.value.exit_code == 5
    assert error.value.remedy


@pytest.mark.parametrize("viewport", INVALID)
def test_validate_reports_invalid_mutated_viewport(viewport):
    sb = parse(minimal())
    sb.project.viewport = viewport
    report = validate(sb)
    assert not report.ok
    assert any(issue.rule == "viewport" and issue.where == "project.viewport"
               for issue in report.errors)


@pytest.mark.parametrize("viewport", [[720, 1280], (640, 360), [512, 512], [1, 1]])
def test_valid_viewport_keeps_dimensions_and_aspects(viewport):
    data = minimal()
    data["project"]["viewport"] = viewport
    data["outputs"] = {"aspects": ["16x9", "9x16", "1x1"]}
    sb = parse(data)
    assert sb.project.viewport == tuple(viewport)
    assert validate(sb).ok
    assert sb.outputs.aspects == data["outputs"]["aspects"]
    assert data["project"]["viewport"] == viewport


def test_omitted_viewport_preserves_default():
    sb = parse(minimal())
    assert sb.project.viewport == (1440, 810)
    assert validate(sb).ok


@pytest.mark.parametrize("viewport", [[0, 810], [1440, float("nan")]])
def test_invalid_viewport_cli_has_typed_json_failure(tmp_path, viewport):
    data = minimal()
    data["project"]["viewport"] = viewport
    fixture = tmp_path / "invalid-viewport.yaml"
    fixture.write_text(yaml.safe_dump(data))
    result = subprocess.run(
        [sys.executable, "-m", "teaserkit.cli", "validate", str(fixture), "--json"],
        capture_output=True, text=True, stdin=subprocess.DEVNULL,
        timeout=10, env=os.environ.copy(),
    )
    assert result.returncode == 5
    error = json.loads(result.stdout)["error"]
    assert error["code"] == "storyboard_invalid"
    assert "project.viewport" in error["message"]
