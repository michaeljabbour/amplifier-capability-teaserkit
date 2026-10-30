"""Prepare the optional live self-teaser shoot, or clean up its exact ownership receipt."""
from pathlib import Path
import argparse
import json
import os
import shlex
import shutil
import subprocess
import sys
import tempfile

from shoot_owner import OwnershipError, ShootOwner


def prepare(stage, repo, home):
    here = repo / "examples/self-teaser"
    for name in ["storyboard.yaml", "brand.yaml"]:
        shutil.copyfile(here / name, stage / name)
    shutil.copytree(here / "gallery", stage / "gallery")
    shutil.copytree(repo / "examples/demo-app", stage / "acme")
    for name in ["bin", "tkhome", "forgehome"]:
        (stage / name).mkdir()
    browsers = Path(os.environ.get("PLAYWRIGHT_BROWSERS_PATH", str(home / "Library/Caches/ms-playwright")))
    (stage / "browsers").symlink_to(browsers)
    q = shlex.quote
    (stage / "bin/teaserkit").write_text("#!/bin/sh\nexport HOME=" + q(str(stage / "tkhome")) + " PLAYWRIGHT_BROWSERS_PATH=" + q(str(stage / "browsers")) + "\nexec " + q(str(repo / ".venv/bin/teaserkit")) + ' "$@"\n')
    (stage / "bin/ls").write_text('#!/bin/sh\nexec /bin/ls -g "$@"\n')
    for path in (stage / "bin").iterdir():
        path.chmod(0o700)
    (stage / "env.sh").write_text("export HOME=" + q(str(home)) + " PATH=" + q(str(stage / "bin") + os.pathsep + os.environ.get("PATH", "")) + " PS1='acme % '\n")
    (stage / "nowatch.cjs").write_text('const fs = require("fs"); const { EventEmitter } = require("events");\nfs.watch = () => { const watcher = new EventEmitter(); watcher.close = () => {}; watcher.unref = () => watcher; return watcher; };\n')


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--cleanup", type=Path, help="Close only recorded sessions and then the verified empty owned daemon")
    args = parser.parse_args()
    home = Path.home()
    forge = Path(os.environ.get("FORGE", str(home / ".amplifier/skills/amplifier-skill-forge/tools/forge.py")))
    if not forge.is_file():
        parser.error("forge.py is unavailable; install the documented optional Forge skill or set FORGE")
    if args.cleanup:
        stage = args.cleanup.resolve()
        owner = ShootOwner(stage, forge, record=json.loads((stage / "shoot-owner.json").read_text()))
        try:
            owner.cleanup()
        except (OwnershipError, OSError, ValueError, subprocess.SubprocessError) as error:
            parser.exit(1, "Cleanup refused: " + str(error) + "\n")
        print("Owned shoot cleaned; stage retained: " + str(stage))
        return
    for command in ["forge", "lsof", "ps", "amplifier"]:
        if shutil.which(command) is None:
            parser.error("Required command is unavailable: " + command)
    repo = Path(__file__).resolve().parents[2]
    if not (repo / ".venv/bin/teaserkit").is_file():
        parser.error("The documented repository dev venv is unavailable")
    stage = Path(tempfile.mkdtemp(prefix="teaserkit-self-teaser-", dir="/tmp"))
    prepare(stage, repo, home)
    owner = ShootOwner(stage, forge)
    try:
        owner.start()
        sid = owner.new_session()
        owner.system.sleep(2)  # Let the freshly created PTY shell reach its prompt.
        owner.call("run", sid, ". " + shlex.quote(str(stage / "env.sh")) + "; clear", "--wait", "1")
        owner.call("type", sid, "amplifier run --bundle foundation --mode chat")
        owner.call("key", sid, "enter")
        for _ in range(8):
            try:
                owner.call("wait", sid, "Interactive Session", "--timeout", "29000")
                break
            except OwnershipError:
                owner.assert_owned()
        else:
            raise OwnershipError("Amplifier did not reach its interactive prompt")
        owner.call("key", sid, "ctrl+l")
        owner.record["status"] = "ready"
        owner.save()
    except (OwnershipError, OSError, ValueError, subprocess.SubprocessError, KeyboardInterrupt) as error:
        owner.record["status"] = "setup-failed"
        owner.record["error"] = str(error)
        owner.save()
        print("Shoot setup failed: " + str(error), file=sys.stderr)
        if owner.record.get("pid"):
            try:
                owner.cleanup()
            except (OwnershipError, OSError, ValueError, subprocess.SubprocessError) as cleanup_error:
                print("Cleanup retained the daemon: " + str(cleanup_error), file=sys.stderr)
        print("Inspect retained stage: " + str(stage), file=sys.stderr)
        return 1
    print("Ready. Session " + sid + " at http://127.0.0.1:3199/ ; now run:")
    print("  " + shlex.quote(str(repo / ".venv/bin/teaserkit")) + " build " + shlex.quote(str(stage / "storyboard.yaml")) + " --out /tmp/teaserkit-teaser")
    print("After filming, clean only this shoot:")
    print("  " + shlex.quote(str(repo / "examples/self-teaser/setup.sh")) + " --cleanup " + shlex.quote(str(stage)))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
