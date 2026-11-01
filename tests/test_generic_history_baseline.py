"""Exact public metadata baselines must never become broad privacy exceptions."""
import hashlib
import importlib.util
import json
import re
import subprocess
import sys

import pytest

from conftest import ROOT

SPEC = importlib.util.spec_from_file_location("generic_checker", ROOT / "scripts/check_generic.py")
checker = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(checker)


def metadata():
    return "Fixture Actor <" + "fixture@" + "private.invalid>"


def baseline_for(value):
    return {("a" * 40, "author"): hashlib.sha256(value.encode()).hexdigest()}


def test_exact_author_field_only_baselines_its_existing_email():
    value = metadata()
    assert checker.scan_history_field(value, "a" * 40, "author", [], baseline_for(value)) == ([], 1)


@pytest.mark.parametrize("commit,field,value", [
    ("b" * 40, "author", metadata()),
    ("a" * 40, "committer", metadata()),
    ("a" * 40, "message", metadata()),
    ("a" * 40, "author", metadata().replace("fixture", "changed")),
])
def test_changed_commit_field_or_value_still_fails(commit, field, value):
    hits, accepted = checker.scan_history_field(value, commit, field, [], baseline_for(metadata()))
    assert hits and accepted == 0


def test_file_content_is_never_covered_by_history_baseline():
    assert checker.scan(metadata(), "notes.txt")


def test_local_denied_terms_still_fail_exact_baselined_metadata():
    value = metadata()
    hits, accepted = checker.scan_history_field(
        value, "a" * 40, "author", [re.compile("Fixture Actor")], baseline_for(value)
    )
    assert hits and accepted == 1
    assert any("Fixture Actor" in hit for hit in hits)


def test_public_noreply_exception_does_not_cover_commit_messages():
    value = "123" + "+example-user@" + "users.noreply.github.com"
    hits, accepted = checker.scan_history_field(value, "a" * 40, "message", [], {})
    assert hits and accepted == 0


def write_baseline(root, *, version=1, fields=None):
    folder = root / "scripts"
    folder.mkdir(exist_ok=True)
    (folder / "generic-history-baseline.json").write_text(json.dumps({
        "version": version, "public_revision": "a" * 40,
        "scope": "Fictional negative fixture only", "fields": fields or [],
    }))


@pytest.mark.parametrize("version", [True, "1", 2])
def test_baseline_version_is_explicit_and_not_boolean(tmp_path, version):
    write_baseline(tmp_path, version=version)
    with pytest.raises(ValueError):
        checker.load_history_baseline(tmp_path)


def test_baseline_cannot_cover_messages(tmp_path):
    write_baseline(tmp_path, fields=[{"commit": "a" * 40, "field": "message", "sha256": "b" * 64}])
    with pytest.raises(ValueError):
        checker.load_history_baseline(tmp_path)


def test_unreachable_commit_baseline_is_rejected(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    write_baseline(tmp_path, fields=[{"commit": "b" * 40, "field": "author", "sha256": "c" * 64}])
    with pytest.raises(ValueError):
        checker.load_history_baseline(tmp_path)


def test_new_commit_with_same_old_email_and_new_file_content_are_rejected(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / "README.md").write_text("Fictional repository.\n")
    identity = ["-c", "user.name=Fixture Actor", "-c", "user.email=" + "fixture@" + "private.invalid"]
    def commit():
        subprocess.run(["git", "-C", str(tmp_path), "add", "."], check=True)
        subprocess.run(["git", "-C", str(tmp_path), *identity, "commit", "--no-gpg-sign", "-qm", "Fictional fixture"], check=True)
        return subprocess.check_output(["git", "-C", str(tmp_path), "rev-parse", "HEAD"], text=True).strip()
    first = commit()
    folder = tmp_path / "scripts"
    folder.mkdir()
    (folder / "generic-history-baseline.json").write_text(json.dumps({
        "version": 1, "public_revision": first, "scope": "Fictional public baseline",
        "fields": [{"commit": first, "field": f, "sha256": hashlib.sha256(metadata().encode()).hexdigest()}
                   for f in ["author", "committer"]],
    }))
    command = [sys.executable, str(ROOT / "scripts/check_generic.py"), str(tmp_path)]
    clean = subprocess.run(command, capture_output=True, text=True)
    assert clean.returncode == 0, clean.stdout + clean.stderr
    second = commit()
    assert second != first
    new_metadata = subprocess.run(command, capture_output=True, text=True)
    assert new_metadata.returncode == 1 and second in new_metadata.stdout
    (tmp_path / "new.txt").write_text(metadata())
    new_content = subprocess.run(command, capture_output=True, text=True)
    assert new_content.returncode == 1 and "new.txt" in new_content.stdout


def test_public_noreply_attribution_trailer_retains_existing_exception():
    address = "123" + "+example-user@" + "users.noreply.github.com"
    value = "Co-authored-by: Fixture Actor <" + address + ">"
    hits, accepted = checker.scan_history_field(value, "a" * 40, "message", [], {})
    assert hits == [] and accepted == 0
    assert checker.scan(value, "notes.txt")


def test_private_email_attribution_trailer_is_not_exempt():
    value = "Co-authored-by: " + metadata()
    hits, accepted = checker.scan_history_field(value, "a" * 40, "message", [], {})
    assert hits and accepted == 0


def test_shallow_checkout_fails_closed_with_history_remedy(tmp_path):
    origin = tmp_path / "origin"
    origin.mkdir()
    subprocess.run(["git", "init", "-q", str(origin)], check=True)
    def commit():
        subprocess.run(["git", "-C", str(origin), "add", "."], check=True)
        subprocess.run(["git", "-C", str(origin), "-c", "user.name=Fixture", "-c",
                        "user.email=noreply@example.com", "commit", "--no-gpg-sign", "-qm", "Fixture"], check=True)
        return subprocess.check_output(["git", "-C", str(origin), "rev-parse", "HEAD"], text=True).strip()
    (origin / "README.md").write_text("First fixture.\n")
    old = commit()
    (origin / "README.md").write_text("Second fixture.\n")
    public = commit()
    folder = origin / "scripts"
    folder.mkdir()
    (folder / "generic-history-baseline.json").write_text(json.dumps({
        "version": 1, "public_revision": public, "scope": "Fictional history boundary",
        "fields": [{"commit": old, "field": "author", "sha256": hashlib.sha256(b"Fixture <noreply@example.com>").hexdigest()}],
    }))
    commit()
    shallow = tmp_path / "shallow"
    subprocess.run(["git", "clone", "--quiet", "--no-local", "--depth=1", str(origin), str(shallow)], check=True)
    assert subprocess.check_output(["git", "-C", str(shallow), "rev-parse", "--is-shallow-repository"], text=True).strip() == "true"
    result = subprocess.run([sys.executable, str(ROOT / "scripts/check_generic.py"), str(shallow)], capture_output=True, text=True)
    assert result.returncode == 1 and "full-history" in result.stdout


def test_only_exact_known_project_url_aliases_avoid_local_owner_terms():
    terms = [re.compile("zorblat")]
    for name in ["teaserkit", "amplifier-smart-tool-teaserkit", "amplifier-capability-teaserkit"]:
        for suffix in ["", ".git", "/releases/tag/v0.1.1"]:
            assert checker.scan("https://github.com/zorblat/" + name + suffix, "README.md", terms) == []
    for name in ["another-project", "teaserkit-unrelated", "amplifier-capability-teaserkit-unrelated"]:
        assert checker.scan("https://github.com/zorblat/" + name, "README.md", terms)
