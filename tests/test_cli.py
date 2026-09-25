import json
import os
import subprocess
import sys

import pytest

from conftest import DEMO

SCRUB = ("ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN", "ANTHROPIC_PROFILE", "TEASERKIT_MODEL")


def run(*args, env_extra=None, home=None, timeout=60):
    env = {k: v for k, v in os.environ.items() if k not in SCRUB}
    if home:
        env["HOME"] = str(home)
    env.update(env_extra or {})
    return subprocess.run([sys.executable, "-m", "teaserkit.cli", *args], capture_output=True, text=True, env=env,
                          stdin=subprocess.DEVNULL, timeout=timeout)


def test_help_levels():
    short, full = run("-h"), run("--help")
    assert short.returncode == 0 and full.returncode == 0
    assert len(full.stdout) > len(short.stdout)
    assert full.stdout.startswith("<skill_content")
    cap = run("validate", "--help")
    assert cap.returncode == 0 and "caption-words" in cap.stdout
    assert run("validate", "-h").returncode == 0


def test_manifest_json():
    r = run("manifest", "--json")
    assert r.returncode == 0
    m = json.loads(r.stdout)
    assert m["name"] == "teaserkit" and any(c["needs_ai_provider"] for c in m["capabilities"])


def test_bad_invocation_exits_2():
    assert run("no-such-verb").returncode == 2
    assert run().returncode == 2
    assert run("validate").returncode == 2


def test_validate_exit_codes(tmp_path):
    assert run("validate", str(DEMO)).returncode == 0
    bad = tmp_path / "s.yaml"
    bad.write_text("project: {name: X, base_url: 'https://a.example.com'}\nbeats: [{id: a, steps: [], caption: 'one two three four five six seven eight'}]\nvideos: [{id: v, beats: [a]}]\n")
    r = run("validate", str(bad), "--json")
    assert r.returncode == 5
    assert json.loads(r.stdout)["errors"][0]["rule"] == "caption-words"
    assert run("validate", str(tmp_path / "missing.yaml")).returncode == 5


def test_ai_capability_without_provider_fails_loudly(tmp_path):
    r = run("plan", "--description", "A planner", "--feature", "add a task", "--json", home=tmp_path)
    assert r.returncode in (3, 4)
    err = json.loads(r.stdout)["error"]
    assert err["code"] in ("no_provider", "missing_prerequisite") and err["remedy"]


def test_init_refuses_to_overwrite(tmp_path):
    assert run("init", str(tmp_path / "p"), "--name", "Acme").returncode == 0
    assert run("validate", str(tmp_path / "p" / "storyboard.yaml")).returncode == 0
    assert run("init", str(tmp_path / "p")).returncode == 1


def test_music_standalone(tmp_path):
    r = run("music", "--seconds", "2", "--out", str(tmp_path / "a.wav"), "--json")
    assert r.returncode == 0 and json.loads(r.stdout)["seconds"] == 2


@pytest.mark.e2e
@pytest.mark.skipif(os.environ.get("TEASERKIT_E2E") != "1", reason="set TEASERKIT_E2E=1 to run the full demo build")
def test_demo_build(tmp_path):
    r = run("build", str(DEMO), "--out", str(tmp_path / "out"), "--work", str(tmp_path / "work"), "--aspect", "16x9", "--preview", "--json", timeout=900)
    assert r.returncode == 0, r.stderr
    out = json.loads(r.stdout)["outputs"][0]
    assert out["probe"]["audio_codec"] == "aac" and 30 <= out["probe"]["seconds"] <= 40
