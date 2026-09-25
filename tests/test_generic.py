import subprocess
import sys

from conftest import ROOT


def test_repository_has_no_denied_references():
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_generic.py"), str(ROOT)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


def test_checker_catches_planted_leaks(tmp_path):
    (tmp_path / "notes.txt").write_text("Mail someone" + "@realcompany.io, see /" + "Users/someone/x\n")
    r = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_generic.py"), str(tmp_path)], capture_output=True, text=True)
    assert r.returncode == 1
    assert "email" in r.stdout and "Users" in r.stdout


def test_local_terms_are_checked_and_repo_url_is_allowed(tmp_path):
    (tmp_path / ".check-generic.local").write_text("# private\nzorblat\n")
    (tmp_path / "a.md").write_text("Install from https://github.com/zorblat/teaserkit\n")
    ok = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_generic.py"), str(tmp_path)], capture_output=True, text=True)
    assert ok.returncode == 0, ok.stdout
    (tmp_path / "b.md").write_text("Thanks, Zorblat.\n")
    bad = subprocess.run([sys.executable, str(ROOT / "scripts" / "check_generic.py"), str(tmp_path)], capture_output=True, text=True)
    assert bad.returncode == 1 and "b.md" in bad.stdout
