import subprocess
import sys

from conftest import ROOT


def test_repository_has_no_denied_references():
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_generic.py"), str(ROOT)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 0, r.stdout + r.stderr


def test_checker_catches_planted_leaks(tmp_path):
    (tmp_path / "notes.txt").write_text(
        "Mail someone" + "@realcompany.io, see /" + "Users/someone/x\n"
    )
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_generic.py"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "email" in r.stdout and "Users" in r.stdout


def test_local_terms_are_checked_and_repo_url_is_allowed(tmp_path):
    (tmp_path / ".check-generic.local").write_text("# private\nzorblat\n")
    (tmp_path / "a.md").write_text(
        "Install from https://github.com/zorblat/teaserkit\n"
    )
    ok = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_generic.py"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert ok.returncode == 0, ok.stdout
    (tmp_path / "b.md").write_text("Thanks, Zorblat.\n")
    bad = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_generic.py"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert bad.returncode == 1 and "b.md" in bad.stdout


def test_allow_marker_is_narrow(tmp_path):
    # A storyboard's own deny_list may need to name a home-path pattern, to protect against it
    # appearing on screen at record time -- that is a declaration, not a leak. Built from
    # fragments, like the fixture above, so this file does not trip the checker on itself.
    pattern = "/" + "Users/"
    (tmp_path / "sb.yaml").write_text(
        f'deny_list: ["{pattern}"]  # check-generic:allow\nnote: {pattern}someone/x\n'
    )
    r = subprocess.run(
        [sys.executable, str(ROOT / "scripts" / "check_generic.py"), str(tmp_path)],
        capture_output=True,
        text=True,
    )
    assert r.returncode == 1
    assert "sb.yaml:1" not in r.stdout  # the marked line is exempt
    assert "sb.yaml:2" in r.stdout  # an unmarked line with the same pattern still fails


def test_public_noreply_exception_is_limited_to_historical_metadata():
    import importlib.util
    spec = importlib.util.spec_from_file_location('generic_checker', ROOT / 'scripts/check_generic.py')
    checker = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(checker)
    public_id = '123' + '+example-user@' + 'users.noreply.github.com'
    assert checker.scan(public_id, 'git log') == []
    assert checker.scan(public_id, 'notes.md')
    private_email = 'someone@' + 'realcompany.io'
    assert checker.scan(private_email, 'git log')
