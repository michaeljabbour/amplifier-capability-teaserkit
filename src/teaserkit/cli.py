"""The `teaserkit` command: argument parsing and I/O conventions over the library, nothing more.

- Results go to stdout (text by default, JSON with --json). Progress and warnings go to stderr.
- Failures exit non-zero and print the problem and its remedy (and a JSON envelope with --json).
- Nothing ever prompts; with stdin closed every command completes or fails.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from . import _manifest
from .errors import TeaserkitError

EXIT_BAD_INVOCATION = 2
EXIT_FINDINGS = 7


def _progress(msg: str) -> None:
    print(msg, file=sys.stderr, flush=True)


def _emit(args, data, text: str | None = None) -> None:
    if getattr(args, "json", False):
        json.dump(data, sys.stdout, indent=1, default=str)
        sys.stdout.write("\n")
    else:
        sys.stdout.write((text if text is not None else json.dumps(data, indent=1, default=str)) + "\n")


def _read_opt_file(path: str | None) -> str | None:
    return Path(path).read_text() if path else None


# ─────────────────────────────── commands ───────────────────────────────


def cmd_manifest(a) -> int:
    m = _manifest.manifest()
    body = m.pop("body")
    m["capabilities"] = _manifest.capabilities()
    if a.body:
        m["body"] = body
    if a.json or not a.body:
        _emit(a, m, json.dumps(m, indent=1))
    else:
        _emit(a, m, body)
    return 0


def cmd_doctor(a) -> int:
    from .prereqs import doctor

    d = doctor()
    lines = []
    for k, v in d.items():
        lines.append(f"{k:9} {'ok' if v.get('ok') else 'MISSING'}  {v.get('path') or v.get('remedy') or v.get('note', '')}")
    _emit(a, d, "\n".join(lines))
    required_ok = all(d[k]["ok"] for k in ("ffmpeg", "ffprobe", "chromium"))
    return 0 if required_ok else 4


def cmd_init(a) -> int:
    from .project import init_project

    r = init_project(a.directory, a.name, force=a.force)
    _emit(a, r, "\n".join([f"wrote {f}" for f in r["files"]] + ["next:"] + [f"  {n}" for n in r["next"]]))
    return 0


def cmd_validate(a) -> int:
    from .rules import validate
    from .storyboard import load

    rep = validate(load(a.storyboard), strict=a.strict)
    _emit(a, rep.to_dict(), rep.text())
    return 0 if rep.ok else 5


def cmd_record(a) -> int:
    from .pipeline import check, work_for
    from .recorder import record
    from .storyboard import load

    sb = load(a.storyboard)
    check(sb)
    work = work_for(sb, a.work)
    res = record(sb, work["raw"], takes=a.take or None, log=_progress)
    data = {"work_dir": str(work["root"]), "takes": [{**r.__dict__, "video": str(r.video), "marks": str(r.marks)} for r in res]}
    _emit(a, data, "\n".join(f"{r.take}: {r.video} ({r.seconds:.1f} s, {r.frames} frames)" for r in res))
    return 0


def cmd_captions(a) -> int:
    from .pipeline import render_captions, work_for
    from .storyboard import load

    sb = load(a.storyboard)
    work = work_for(sb, a.work)
    paths = render_captions(sb, work, videos=a.video or None, aspects=a.aspect or None, force=a.force, log=_progress)
    _emit(a, {"gfx_dir": str(work["gfx"]), "files": [str(p) for p in paths]}, "\n".join(str(p) for p in paths))
    return 0


def cmd_compose(a) -> int:
    from .pipeline import compose_videos, render_captions, work_for
    from .storyboard import load

    sb = load(a.storyboard)
    work = work_for(sb, a.work)
    render_captions(sb, work, videos=a.video or None, aspects=a.aspect or None, log=_progress)
    res = compose_videos(sb, work, videos=a.video or None, aspects=a.aspect or None, preview=a.preview, log=_progress)
    _emit(a, {"renders": res}, "\n".join(f"{r['path']} ({r['seconds']:.1f} s)" for r in res))
    return 0


def cmd_music(a) -> int:
    from . import music

    if a.seconds is not None:
        if not a.out:
            raise TeaserkitError("--seconds needs --out <file.wav>.", "Pass --out, e.g. --out track.wav.")
        r = music.make_track(a.seconds, a.out, bpm=a.bpm, seed=a.seed, progression=a.progression)
        _emit(a, r, r["path"])
        return 0
    if not a.storyboard:
        raise TeaserkitError("Pass a storyboard, or --seconds and --out for a standalone track.", "See `teaserkit music --help`.")
    from .finishing import probe
    from .pipeline import make_music, work_for
    from .storyboard import load

    sb = load(a.storyboard)
    work = work_for(sb, a.work)
    secs = {}
    for v in sb.videos:
        f = next(iter(sorted(work["silent"].glob(f"{v.id}-*.mp4"))), None)
        if f is None:
            raise TeaserkitError(f"No silent render for video '{v.id}' yet.", "Run `teaserkit compose <storyboard>` first.")
        secs[v.id] = probe(f)["seconds"]
    r = make_music(sb, work, secs, _progress)
    _emit(a, r, "\n".join(f"{k}: {v['path']} ({v['seconds']:.1f} s)" for k, v in r.items()) or "music is disabled (style.music: none)")
    return 0


def cmd_finalize(a) -> int:
    from .finishing import finalize, probe
    from .pipeline import default_poster_at, work_for
    from .storyboard import load

    sb = load(a.storyboard)
    work = work_for(sb, a.work)
    vids = [sb.video(v) for v in a.video] if a.video else sb.videos
    aspects = a.aspect or sb.outputs.aspects
    out = []
    for v in vids:
        wav = work["audio"] / f"{v.id}.wav"
        if sb.style.get("music") != "none" and not wav.exists():
            raise TeaserkitError(f"No soundtrack for '{v.id}' in the work directory.", "Run `teaserkit music <storyboard>` first.")
        for asp in aspects:
            silent = work["silent"] / f"{v.id}-{asp}.mp4"
            if not silent.exists():
                raise TeaserkitError(f"Missing silent render {silent}.", "Run `teaserkit compose <storyboard>` first.")
            secs = probe(silent)["seconds"]
            at = v.poster_at if v.poster_at is not None else round(secs * 0.4, 2)
            no_audio = sb.outputs.no_audio == "all" or (sb.outputs.no_audio == "main" and v.kind == "main")
            r = finalize(silent, wav if wav.exists() else None, a.out, f"{v.id}-{asp}", poster_at=at if sb.outputs.posters else None,
                         no_audio=no_audio, lufs=sb.style["loudness_lufs"], tp=sb.style["true_peak_db"], lra=sb.style["loudness_range"])
            out.append(r)
    _emit(a, {"outputs": out}, "\n".join(p for r in out for p in r.values()))
    return 0


def cmd_sheet(a) -> int:
    from .sheets import contact_sheet, roi_grid

    if a.grid:
        times = [float(t) for t in (a.times or "1").split(",")]
        r = roi_grid(a.video, times, a.out, viewport_width=a.viewport_width)
    else:
        r = contact_sheet(a.video, a.out, every=a.every, cols=a.cols)
    _emit(a, r, r["path"])
    return 0


def cmd_build(a) -> int:
    from .pipeline import build

    r = build(a.storyboard, a.out, work_dir=a.work, videos=a.video or None, aspects=a.aspect or None,
              preview=a.preview, skip_record=a.skip_record, log=_progress)
    lines = []
    for o in r["outputs"]:
        lines.append(f"{o['video']}  ({o['probe']['seconds']:.1f} s, {o['probe']['width']}x{o['probe']['height']})")
        for k in ("no_audio", "poster", "sheet"):
            if o.get(k):
                lines.append(f"  {o[k]}")
    lines += [f"storyboard table: {r['storyboard_table']}", f"work directory: {r['work_dir']}"]
    _emit(a, r, "\n".join(lines))
    return 0


def cmd_plan(a) -> int:
    from .planner import plan

    desc = a.description or _read_opt_file(a.description_file)
    if not desc:
        raise TeaserkitError("plan needs --description or --description-file.", "Describe the product in a sentence or two.")
    feats = list(a.feature or [])
    if a.features_file:
        feats += [ln.strip("-* \t") for ln in Path(a.features_file).read_text().splitlines() if ln.strip()]
    if not feats:
        raise TeaserkitError("plan needs at least one --feature (or --features-file).", "List the features to show, in order.")
    r = plan(desc, feats, base_url=a.base_url, kind=a.kind, name=a.name, context=_read_opt_file(a.context_file), attempts=a.attempts)
    data = {"storyboard_yaml": r.storyboard_yaml, "notes": r.notes, "attempts": r.attempts, "report": r.report}
    if a.out:
        Path(a.out).write_text(r.storyboard_yaml)
        data["path"] = str(Path(a.out).resolve())
        _progress(f"wrote {data['path']}")
    _emit(a, data, r.storyboard_yaml if not a.out else f"{data['path']}\n\nnotes: {r.notes}")
    return 0


def cmd_explore(a) -> int:
    from .explorer import explore

    ctx = _read_opt_file(a.context_file)
    kw = dict(start=a.start, max_steps=a.max_steps, storage_state=a.storage_state, context=ctx, screenshots_dir=a.screenshots, log=_progress)
    if a.storyboard:
        from .serve import serve_static
        from .storyboard import load

        sb = load(a.storyboard)
        kw["viewport"] = sb.project.viewport
        if sb.project.serve_dir and not a.base_url:
            with serve_static(sb.project.serve_dir, sb.project.serve_port) as url:
                r = explore(url, a.intent, **kw)
        else:
            r = explore(a.base_url or sb.project.base_url, a.intent, **kw)
    else:
        if not a.base_url:
            raise TeaserkitError("explore needs --base-url or --storyboard.", "Point it at the running app.")
        r = explore(a.base_url, a.intent, **kw)
    _emit(a, r, r["beat_yaml"])
    return 0


def cmd_review(a) -> int:
    from .reviewer import review

    deny = list(a.deny or [])
    if a.storyboard:
        from .storyboard import load

        deny += load(a.storyboard).project.deny_list
    r = review(a.inputs, deny_list=deny, every=a.every, max_frames=a.max_frames, context=_read_opt_file(a.context_file),
               fail_on=a.fail_on, log=_progress)
    lines = [f"{f['severity'].upper():6} {f['category']:16} {f['frame']}: {f['description']} ({f['evidence']})" for f in r["findings"]]
    lines.append(f"{r['frames_reviewed']} frame(s) reviewed. {r['summary']}")
    _emit(a, r, "\n".join(lines))
    return 0 if r["ok"] else EXIT_FINDINGS


# ─────────────────────────────── parser ───────────────────────────────


class _Print(argparse.Action):
    def __init__(self, option_strings, render, dest=argparse.SUPPRESS, default=argparse.SUPPRESS, help=None):
        super().__init__(option_strings=option_strings, dest=dest, default=default, nargs=0, help=help)
        self.render = render

    def __call__(self, parser, namespace, values, option_string=None):
        sys.stdout.write(self.render(parser) + "\n")
        parser.exit(0)


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        sys.stderr.write(f"teaserkit: {message}\nRun `teaserkit -h` for the capabilities, `teaserkit <capability> -h` for its options.\n")
        raise SystemExit(EXIT_BAD_INVOCATION)


def _sub(sp, name: str, func, doc: str):
    kind = dict((n, k) for n, k, _ in _manifest.CAPABILITIES)[name]
    p = sp.add_parser(name, add_help=False, description=f"[{kind}] {doc}", help=doc)
    p.add_argument("-h", action=_Print, render=lambda parser: parser.format_help(), help="terse usage")
    p.add_argument("--help", action=_Print, render=lambda parser, n=name: _manifest.capability_skill(n), help="the full guide for this capability")
    p.add_argument("--json", action="store_true", help="structured result on stdout")
    p.set_defaults(func=func)
    return p


def build_parser() -> argparse.ArgumentParser:
    ap = _Parser(prog="teaserkit", add_help=False)
    ap.add_argument("-h", action=_Print, render=lambda p: _manifest.short_help(), help="terse summary")
    ap.add_argument("--help", action=_Print, render=lambda p: _manifest.skill(), help="the full guide")
    ap.add_argument("--version", action=_Print, render=lambda p: _manifest.manifest()["version"], help="print the version")
    sp = ap.add_subparsers(dest="command", parser_class=_Parser)
    docs = {n: s for n, _, s in _manifest.CAPABILITIES}

    p = _sub(sp, "manifest", cmd_manifest, docs["manifest"])
    p.add_argument("--body", action="store_true", help="include (or print) the Markdown guide")

    _sub(sp, "doctor", cmd_doctor, docs["doctor"])

    p = _sub(sp, "init", cmd_init, docs["init"])
    p.add_argument("directory")
    p.add_argument("--name", default="My Product", help="product name used in the templates")
    p.add_argument("--force", action="store_true", help="overwrite existing files")

    p = _sub(sp, "validate", cmd_validate, docs["validate"])
    p.add_argument("storyboard")
    p.add_argument("--strict", action="store_true", help="treat warnings as errors")

    def common(p, videos=True):
        p.add_argument("storyboard")
        p.add_argument("--work", help="work directory (default: per-storyboard under the user cache dir)")
        if videos:
            p.add_argument("--video", action="append", help="only this video id (repeatable)")
            p.add_argument("--aspect", action="append", choices=["16x9", "9x16", "1x1"], help="only this aspect (repeatable)")

    p = _sub(sp, "record", cmd_record, docs["record"])
    common(p, videos=False)
    p.add_argument("--take", action="append", help="only this take (repeatable)")

    p = _sub(sp, "captions", cmd_captions, docs["captions"])
    common(p)
    p.add_argument("--force", action="store_true", help="re-render graphics that already exist")

    p = _sub(sp, "compose", cmd_compose, docs["compose"])
    common(p)
    p.add_argument("--preview", action="store_true", help="half resolution, fast encode")

    p = _sub(sp, "music", cmd_music, docs["music"])
    p.add_argument("storyboard", nargs="?")
    p.add_argument("--work")
    p.add_argument("--seconds", type=float, help="standalone: track length")
    p.add_argument("--out", help="standalone: output .wav")
    p.add_argument("--bpm", type=float, default=96)
    p.add_argument("--seed", type=int, default=7)
    p.add_argument("--progression", default="warm", choices=["warm", "bright", "calm"])

    p = _sub(sp, "finalize", cmd_finalize, docs["finalize"])
    common(p)
    p.add_argument("--out", required=True, help="output directory for the finished videos")

    p = _sub(sp, "sheet", cmd_sheet, docs["sheet"])
    p.add_argument("video")
    p.add_argument("--out", required=True, help="output PNG")
    p.add_argument("--every", type=float, default=2.0, help="seconds between frames")
    p.add_argument("--cols", type=int, default=6)
    p.add_argument("--grid", action="store_true", help="ROI grid over a raw take instead of a contact sheet")
    p.add_argument("--times", help="with --grid: comma-separated seconds, e.g. 1,4.5,9")
    p.add_argument("--viewport-width", type=int, default=1440, help="with --grid: CSS width of the recording")

    p = _sub(sp, "build", cmd_build, docs["build"])
    common(p)
    p.add_argument("--out", required=True, help="output directory for the finished videos")
    p.add_argument("--preview", action="store_true", help="half resolution, fast encode")
    p.add_argument("--skip-record", action="store_true", help="reuse the takes already in the work directory")

    p = _sub(sp, "plan", cmd_plan, docs["plan"])
    p.add_argument("--description", help="what the product does")
    p.add_argument("--description-file")
    p.add_argument("--feature", action="append", help="a feature to show, in order (repeatable)")
    p.add_argument("--features-file", help="one feature per line")
    p.add_argument("--name", help="product name")
    p.add_argument("--base-url")
    p.add_argument("--kind", default="main", choices=["main", "clip", "free"])
    p.add_argument("--context-file", help="extra material passed to the model verbatim")
    p.add_argument("--attempts", type=int, default=3)
    p.add_argument("--out", help="write the storyboard YAML here")

    p = _sub(sp, "explore", cmd_explore, docs["explore"])
    p.add_argument("--intent", required=True, help="what the beat should show")
    p.add_argument("--base-url")
    p.add_argument("--storyboard", help="take base_url/serve/viewport from a storyboard")
    p.add_argument("--start", default="/", help="path to open first")
    p.add_argument("--max-steps", type=int, default=8)
    p.add_argument("--storage-state", help="signed-in session JSON for the browser context")
    p.add_argument("--context-file")
    p.add_argument("--screenshots", help="directory to keep the screenshots the model saw")

    p = _sub(sp, "review", cmd_review, docs["review"])
    p.add_argument("inputs", nargs="+", help="videos and/or images")
    p.add_argument("--deny", action="append", help="deny-listed string (repeatable)")
    p.add_argument("--storyboard", help="add the storyboard's deny list")
    p.add_argument("--every", type=float, default=2.0)
    p.add_argument("--max-frames", type=int, default=24)
    p.add_argument("--fail-on", default="high", choices=["high", "medium", "low", "never"])
    p.add_argument("--context-file")
    return ap


def main(argv: list[str] | None = None) -> int:
    ap = build_parser()
    args = ap.parse_args(argv)
    if not getattr(args, "func", None):
        sys.stderr.write(_manifest.short_help() + "\n")
        return EXIT_BAD_INVOCATION
    try:
        return int(args.func(args) or 0)
    except TeaserkitError as e:
        sys.stderr.write(f"teaserkit {args.command}: {e.message}\n")
        if e.remedy:
            sys.stderr.write(f"remedy: {e.remedy}\n")
        if getattr(args, "json", False):
            json.dump({"ok": False, "error": e.to_dict()}, sys.stdout, indent=1, default=str)
            sys.stdout.write("\n")
        return e.exit_code
    except KeyboardInterrupt:
        sys.stderr.write("interrupted\n")
        return 130
    except OSError as e:
        sys.stderr.write(f"teaserkit {args.command}: {e}\n")
        return 1


if __name__ == "__main__":  # pragma: no cover
    sys.exit(main())
