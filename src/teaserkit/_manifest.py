"""The manifest and the help text, both read from files shipped inside the package.

`SMART_TOOL.md` is the one manifest: YAML frontmatter (identity, platforms, prerequisites) and a
Markdown body (the guide an agent reads). `capabilities/<name>.md` hold one guide per capability.
The CLI prints what these functions return and adds nothing of its own.
"""

from __future__ import annotations

from importlib import metadata, resources
from pathlib import Path

import yaml

NAME = "teaserkit"

# (name, kind, one-line summary). Drives the capability list in --help, -h and the CLI subcommands.
CAPABILITIES: tuple[tuple[str, str, str], ...] = (
    ("manifest", "deterministic", "Print the manifest: identity, platforms, prerequisites, capabilities."),
    ("doctor", "deterministic", "Check ffmpeg, Chromium and the optional AI provider."),
    ("init", "deterministic", "Scaffold a teaser project (storyboard.yaml + brand.yaml)."),
    ("validate", "deterministic", "Check a storyboard against the style rules; report planned lengths."),
    ("record", "deterministic", "Film the raw takes in headless Chromium, with the leak scan."),
    ("captions", "deterministic", "Render captions, frame chrome and title/end cards to PNG."),
    ("compose", "deterministic", "Composite takes and graphics into silent MP4s per aspect."),
    ("music", "deterministic", "Synthesize original, duration-matched soundtracks."),
    ("finalize", "deterministic", "Mux audio at -18 LUFS; write posters and no-audio copies."),
    ("sheet", "deterministic", "Contact sheet of a video, or a CSS-pixel ROI grid of a raw take."),
    ("build", "deterministic", "Run the whole deterministic pipeline end to end."),
    ("plan", "model-backed", "Draft a storyboard that passes the style rules."),
    ("explore", "model-backed", "Find working steps, an ROI and a caption for one beat."),
    ("review", "model-backed", "Flag leaks, errors, spinners and broken layouts in frames."),
)


def package_dir() -> Path:
    return Path(str(resources.files(NAME)))


def _read(rel: str) -> str:
    return resources.files(NAME).joinpath(rel).read_text(encoding="utf-8")


def _split() -> tuple[dict, str]:
    text = _read("SMART_TOOL.md")
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        raise ValueError("SMART_TOOL.md does not start with a frontmatter fence")
    end = next(i for i in range(1, len(lines)) if lines[i].strip() == "---")
    return yaml.safe_load("\n".join(lines[1:end])) or {}, "\n".join(lines[end + 1:]).strip()


def manifest() -> dict:
    """The manifest's frontmatter fields plus `body` (the Markdown guide), from the packaged copy."""
    fields, body = _split()
    return {**fields, "body": body}


def capabilities() -> list[dict]:
    return [{"name": n, "kind": k, "summary": s, "needs_ai_provider": k == "model-backed"} for n, k, s in CAPABILITIES]


def repository() -> str | None:
    try:
        urls = metadata.metadata(NAME).get_all("Project-URL") or []
    except metadata.PackageNotFoundError:
        return None
    for u in urls:
        label, _, url = u.partition(",")
        if label.strip().lower() in ("repository", "source", "homepage"):
            return url.strip()
    return None


def skill_resources() -> list[str]:
    files = ["SMART_TOOL.md"] + [f"capabilities/{n}.md" for n, _, _ in CAPABILITIES]
    return [f for f in files if (package_dir() / f).exists()]


def _wrap(name: str, heading: str, body: str, extra: list[str], resources_: list[str]) -> str:
    out = [f'<skill_content name="{name}">', f"Skill directory: {package_dir()}"]
    repo = repository()
    if repo:
        out.append(f"Repository: {repo}")
    out += ["Relative paths in this skill are relative to the skill directory.", "", f"# {heading}", "", body.strip(), ""]
    out += extra
    if resources_:
        out += ["<skill_resources>", *[f"  <file>{r}</file>" for r in resources_], "</skill_resources>"]
    out.append("</skill_content>")
    return "\n".join(out)


def skill() -> str:
    """What `teaserkit --help` prints: the manifest body plus the generated capability list."""
    _, body = _split()
    caps = ["## Capabilities", "", f"Each capability has its own guide: `{NAME} <capability> --help`.", ""]
    caps += [f"- `{n}` [{k}] -- {s}" for n, k, s in CAPABILITIES]
    caps.append("")
    return _wrap(NAME, NAME, body, caps, skill_resources())


def capability_skill(name: str) -> str:
    """What `teaserkit <capability> --help` prints."""
    kinds = {n: k for n, k, _ in CAPABILITIES}
    if name not in kinds:
        raise KeyError(name)
    body = _read(f"capabilities/{name}.md")
    return _wrap(f"{NAME}-{name}", f"{NAME} {name} [{kinds[name]}]", body, [], [f"capabilities/{name}.md"])


def short_help() -> str:
    """What `teaserkit -h` prints: the capabilities, one line each."""
    fields, _ = _split()
    lines = [f"usage: {NAME} <capability> [options]      ({fields.get('version')})", "", "capabilities:"]
    lines += [f"  {n:<10} {('[' + ('AI' if k == 'model-backed' else 'det') + ']'):<6} {s}" for n, k, s in CAPABILITIES]
    lines += ["", "  -h            this summary", "  --help        the full guide, written for an agent driving the tool",
              f"  {NAME} <capability> --help   one capability in full", "",
              "[det] runs with no model provider; [AI] needs ANTHROPIC_API_KEY and the `ai` extra."]
    return "\n".join(lines)
