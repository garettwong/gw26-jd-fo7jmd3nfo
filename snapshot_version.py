from __future__ import annotations

import argparse
import shutil
import subprocess
import tempfile
import zipfile
from pathlib import Path


ROOT = Path(__file__).resolve().parent
SNAPSHOT_FILES = (
    "index.html",
    "events.json",
    "class_context.json",
    "summary.json",
    "schedule_overrides.json",
    "sw.js",
    "manifest.webmanifest",
    "favicon-32.png",
    "icon-180.png",
    "icon-192.png",
    "icon-512.png",
)


def main() -> None:
    parser = argparse.ArgumentParser(description="Create an immutable timetable version snapshot.")
    parser.add_argument("version", help="Version folder name, for example 2026-07-15-V06")
    parser.add_argument("--commit", help="Read the snapshot files from this Git commit")
    args = parser.parse_args()

    destination = ROOT / "versions" / args.version
    if destination.exists():
        raise SystemExit(f"Refusing to overwrite existing snapshot: {destination}")
    destination.mkdir(parents=True)

    if args.commit:
        with tempfile.TemporaryDirectory() as temp_dir:
            archive = Path(temp_dir) / "snapshot.zip"
            subprocess.run(
                ["git", "archive", "--format=zip", f"--output={archive}", args.commit, "--", *SNAPSHOT_FILES],
                cwd=ROOT,
                check=True,
            )
            with zipfile.ZipFile(archive) as bundle:
                bundle.extractall(destination)
    else:
        for filename in SNAPSHOT_FILES:
            source = ROOT / filename
            if not source.exists():
                raise SystemExit(f"Missing current-site file: {source}")
            shutil.copy2(source, destination / filename)

    print(destination)


if __name__ == "__main__":
    main()
