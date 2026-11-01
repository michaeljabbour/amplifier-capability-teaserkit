#!/usr/bin/env python3
"""Fail if the repository mentions anything it must not: a home directory, a personal checkout
path, a real email address, or any term listed in the untracked file .check-generic.local (names,
codenames, source projects). Scans every tracked and untracked (non-ignored) file, and the
git history (author/committer names and emails, commit messages).

The project's own GitHub URL is allowed. A line ending `# check-generic:allow` is exempt -- for
a storyboard whose own deny_list must name one of the patterns below to protect against it at
record time, not a leak of one. Use it narrowly, on the exact line, never as a blanket escape.
A versioned exact-field baseline records already-public author/committer email findings.
It never exempts source files, messages, local denied terms or a different/new commit.
Everything else is assembled from fragments so that this file does not match itself.

    python3 scripts/check_generic.py [repo-root]
Exit 0 when clean, 1 when anything is found (each hit is printed).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import sys
from pathlib import Path

J = "".join
LOCAL_TERMS = ".check-generic.local"  # gitignored: one term per line, # for comments
REPO_URL = re.compile(
    r"github\.com/[A-Za-z0-9-]+/(?:amplifier-capability-teaserkit|amplifier-smart-tool-teaserkit|teaserkit)(?![A-Za-z0-9_-])", re.IGNORECASE
)  # the project's own home
ALLOW_LINE = re.compile(
    r"#\s*check-generic:allow\s*$"
)  # narrow, per-line, auditable suppression


def term_patterns(root: Path) -> list[re.Pattern]:
    """Terms that must never appear: read from the local, untracked file so the list itself is never published."""
    f = root / LOCAL_TERMS
    if not f.is_file():
        return []
    terms = [
        t.strip()
        for t in f.read_text().splitlines()
        if t.strip() and not t.lstrip().startswith("#")
    ]
    return [
        re.compile(
            r"\b" + re.escape(t) if t[0].isalnum() else re.escape(t), re.IGNORECASE
        )
        for t in terms
    ]


PATTERNS = [
    re.compile(J(["/", "Users", "/"])),  # macOS home directories
    re.compile(J(["/", "home", "/"]) + r"[a-z]"),  # Linux home directories
    re.compile(J(["~", "/dev", "/"])),  # personal checkout paths
    re.compile(r"[A-Za-z]:\\" + J(["Us", "ers"])),  # Windows home directories
]
EMAIL = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")
ALLOWED_EMAIL = re.compile(
    r"@(example\.(com|org|net)|anthropic\.com)$|^noreply@", re.IGNORECASE
)
PUBLIC_NOREPLY = re.compile(r"^[0-9]+\+[A-Za-z0-9-]+@users\.noreply\.github\.com$", re.IGNORECASE)
SKIP_DIRS = {
    ".git",
    ".venv",
    "venv",
    "node_modules",
    "__pycache__",
    ".pytest_cache",
    "dist",
    "build",
}


def files(root: Path) -> list[Path]:
    try:
        out = subprocess.run(
            ["git", "ls-files", "-co", "--exclude-standard"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        ).stdout
        return [root / f for f in out.splitlines() if f and (root / f).is_file()]
    except (subprocess.CalledProcessError, FileNotFoundError):
        return [
            p
            for p in root.rglob("*")
            if p.is_file()
            and p.name != LOCAL_TERMS
            and not (set(p.relative_to(root).parts) & SKIP_DIRS)
        ]


def scan(text: str, where: str, terms: list[re.Pattern] | None = None) -> list[str]:
    hits = []
    for n, line in enumerate(text.splitlines(), 1):
        if ALLOW_LINE.search(line):
            continue
        line = REPO_URL.sub("", line)
        for pat in [*PATTERNS, *(terms or [])]:
            m = pat.search(line)
            if m:
                hits.append(f"{where}:{n}: '{m.group(0)}'")
        for m in EMAIL.finditer(line):
            # Preserve public upstream attribution without allowing contact
            # addresses into source files or rewriting historical commits.
            historical_noreply = where == "git log" and PUBLIC_NOREPLY.fullmatch(m.group(0))
            if not ALLOWED_EMAIL.search(m.group(0)) and not historical_noreply:
                hits.append(f"{where}:{n}: email '{m.group(0)}'")
    return hits



def load_history_baseline(root: Path) -> dict[tuple[str, str], str]:
    path = root / "scripts" / "generic-history-baseline.json"
    if not path.exists():
        return {}
    data = json.loads(path.read_text())
    if (set(data) != {"version", "public_revision", "scope", "fields"}
            or type(data["version"]) is not int or data["version"] != 1
            or not re.fullmatch(r"[0-9a-f]{40}", data["public_revision"])
            or not isinstance(data["fields"], list)):
        raise ValueError("Invalid exact public-history baseline")
    baseline = {}
    for row in data["fields"]:
        if (set(row) != {"commit", "field", "sha256"}
                or not re.fullmatch(r"[0-9a-f]{40}", row["commit"])
                or row["field"] not in {"author", "committer"}
                or not re.fullmatch(r"[0-9a-f]{64}", row["sha256"])):
            raise ValueError("Invalid exact public-history field")
        key = (row["commit"], row["field"])
        if key in baseline:
            raise ValueError("Duplicate exact public-history field")
        reachable = subprocess.run(
            ["git", "merge-base", "--is-ancestor", row["commit"], data["public_revision"]],
            cwd=root, capture_output=True, check=False,
        )
        if reachable.returncode != 0:
            raise ValueError("Baseline field is outside the pinned public revision or history is missing; verify the pin and use a full-history checkout")
        baseline[key] = row["sha256"]
    return baseline


def history_field_matches(baseline, commit: str, field: str, value: str) -> bool:
    return (field in {"author", "committer"}
            and baseline.get((commit, field)) == hashlib.sha256(value.encode()).hexdigest())


def scan_history_field(value, commit, field, terms, baseline):
    # Only metadata retains the existing public no-reply exception. Messages do not.
    where = "git log" if field in {"author", "committer"} else "git message"
    if field == "message":
        # Preserve the existing public no-reply attribution exception only for
        # a structured trailer, never arbitrary message prose or file contents.
        found = []
        for number, line in enumerate(value.splitlines(), 1):
            trailer = re.fullmatch(r"(?:Co-authored-by|Signed-off-by):\s*[^<>\n]+ <([^<>]+)>\s*", line, re.I)
            line_where = "git log" if trailer and PUBLIC_NOREPLY.fullmatch(trailer.group(1)) else where
            found.extend(hit.replace(":1:", f":{number}:", 1)
                         for hit in scan(line, line_where, terms))
    else:
        found = scan(value, where, terms)
    accepted = 0
    if history_field_matches(baseline, commit, field, value):
        accepted = sum(": email " in hit for hit in found)
        found = [hit for hit in found if ": email " not in hit]
    return ([hit.replace(where, f"git {field} {commit}", 1) for hit in found], accepted)


def main() -> int:
    root = Path(
        sys.argv[1] if len(sys.argv) > 1 else Path(__file__).resolve().parent.parent
    ).resolve()
    terms = term_patterns(root)
    hits: list[str] = []
    n_files = 0
    for f in files(root):
        rel = f.relative_to(root)
        hits += scan(str(rel), f"path {rel}", terms)
        data = f.read_bytes()
        if b"\0" in data[:4096]:
            text = data.decode("latin-1")  # binary: still look for strings
        else:
            text = data.decode("utf-8", "replace")
        hits += scan(text, str(rel), terms)
        n_files += 1
    n_commits = 0
    baseline_findings = 0
    if (root / ".git").exists():
        try:
            baseline = load_history_baseline(root)
        except (ValueError, OSError, KeyError, TypeError) as error:
            hits.append(f"history baseline: {error}")
            baseline = {}
        log = subprocess.run(
            ["git", "log", "--all", "--format=%H%x00%an <%ae>%x00%cn <%ce>%x00%B%x00"],
            cwd=root, capture_output=True, text=True, check=False,
        ).stdout.split("\0")
        for index in range(0, len(log) - 1, 4):
            commit, author, committer, message = log[index:index + 4]
            commit = commit.strip()
            n_commits += 1
            for field, value in (("author", author), ("committer", committer), ("message", message)):
                found, accepted = scan_history_field(value, commit, field, terms, baseline)
                hits.extend(found)
                baseline_findings += accepted
    for h in hits:
        print(h)
    print(
        f"check-generic: {n_files} files, {n_commits} commits scanned, {len(hits)} finding(s); "
        f"{baseline_findings} exact pre-existing public metadata email finding(s) baselined",
        file=sys.stderr,
    )
    return 1 if hits else 0


if __name__ == "__main__":
    sys.exit(main())
