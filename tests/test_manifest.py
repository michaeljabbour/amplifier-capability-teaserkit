import json
import re
import tomllib
from importlib import metadata

import teaserkit
from teaserkit import _manifest

from conftest import ROOT

FIELDS = {"smart_tool_format", "name", "version", "description", "use_cases", "platforms", "requires"}


def test_manifest_accessor_reads_packaged_copy():
    m = teaserkit.manifest()
    assert set(m) == FIELDS | {"body"}
    assert m["smart_tool_format"] == 1
    assert m["name"] == "teaserkit"
    assert re.fullmatch(r"[a-z0-9-]+", m["name"])
    assert m["body"].strip() and not m["body"].startswith("---")
    for field in FIELDS - {"requires"}:
        assert m[field], field


def test_versions_agree():
    m = teaserkit.manifest()
    assert m["version"] == teaserkit.__version__ == metadata.version("teaserkit")
    py = tomllib.loads((ROOT / "pyproject.toml").read_text())
    assert py["project"]["version"] == m["version"]


def test_requires_entries_point_at_docs_not_commands():
    for r in teaserkit.manifest()["requires"]:
        assert set(r) <= {"name", "purpose", "install", "optional"}
        assert r["install"].endswith(".md") or r["install"].startswith("http")
        if not r["install"].startswith("http"):
            assert (ROOT / r["install"]).exists(), r["install"]


def test_descriptor_points_at_the_one_manifest():
    d = json.loads((ROOT / "smart-tool.json").read_text())
    assert (ROOT / d["manifest"]).name == "SMART_TOOL.md" and (ROOT / d["manifest"]).exists()
    assert d["cli_argv"] == ["teaserkit"]
    assert d["deterministic_smoke"][0] in {c["name"] for c in teaserkit.capabilities()}
    found = [p for p in ROOT.rglob("SMART_TOOL.md") if ".venv" not in p.parts]
    assert len(found) == 1


def test_skill_lists_every_capability_with_its_kind():
    s = teaserkit.skill()
    assert s.startswith('<skill_content name="teaserkit">') and s.rstrip().endswith("</skill_content>")
    for name, kind, _ in _manifest.CAPABILITIES:
        assert f"`{name}` [{kind}]" in s
        cs = teaserkit.capability_skill(name)
        assert f"teaserkit {name} [{kind}]" in cs
    assert len(s.splitlines()) < 500


def test_model_backed_capabilities_are_exactly_the_ai_ones():
    ai = {c["name"] for c in teaserkit.capabilities() if c["needs_ai_provider"]}
    assert ai == {"plan", "explore", "review"}
