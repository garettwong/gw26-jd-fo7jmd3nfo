from __future__ import annotations

import json
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASELINE_ID = "2026-07-29-V20a"
VERSION_ID = "2026-07-30-V20b"
VERSION_LABEL = "2026-07-30 - V20b"
BUILD_ID = "v20b-hk239hg-ss-replacement-dates-confirmed-20260730a"
VERSION_SUMMARY = "HK239HG SS - six replacement mornings confirmed."

SITE_FILES = (
    "class_context.json",
    "events.json",
    "favicon-32.png",
    "icon-180.png",
    "icon-192.png",
    "icon-512.png",
    "index.html",
    "manifest.webmanifest",
    "payment_context.json",
    "schedule_overrides.json",
    "summary.json",
    "sw.js",
)

EXPECTED_DATES = {
    1: "2026-09-23",
    2: "2026-09-28",
    3: "2026-09-30",
    4: "2026-10-05",
    5: "2026-10-07",
    6: "2026-10-12",
}
LESSON_NOTES = {
    5: "持續評估 / 小組討論及專題報告",
    6: "期末筆試 10:30-11:30",
}


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def lesson_text(lesson: int) -> str:
    note = LESSON_NOTES.get(lesson)
    suffix = f" [{note}]" if note else ""
    return (
        "勵行-上水彩園 - HK239HG (Garett), Class SS / "
        "人工智能知識及應用證書 (兼讀制) / "
        f"0900-1200 - L{lesson}{suffix}"
    )


def patch_generator() -> None:
    path = ROOT / "generate_site.py"
    text = path.read_text(encoding="utf-8")
    replacements = {
        'BUILD_ID = "v20a-hk239hg-ss-room-gap-checked-hk280hg-ss-unavailable-20260729a"':
            f'BUILD_ID = "{BUILD_ID}"',
        'COMPARE_BASELINE = OUTDIR / "versions" / "2026-07-29-V20"':
            f'COMPARE_BASELINE = OUTDIR / "versions" / "{BASELINE_ID}"',
        'COMPARE_LABEL = "V20a"': 'COMPARE_LABEL = "V20b"',
        'COMPARE_BASELINE_LABEL = "V20"': 'COMPARE_BASELINE_LABEL = "V20a"',
    }
    for old, new in replacements.items():
        if text.count(old) != 1:
            raise ValueError(f"Expected exactly one generator marker: {old!r}")
        text = text.replace(old, new)
    path.write_text(text, encoding="utf-8")


def update_versions() -> None:
    versions = [
        row for row in read_json(ROOT / "versions.json")
        if row["id"] != VERSION_ID
    ]
    for row in versions:
        row["latest"] = False
    versions.insert(
        0,
        {
            "id": VERSION_ID,
            "label": VERSION_LABEL,
            "summary": VERSION_SUMMARY,
            "latest": True,
        },
    )
    write_json(ROOT / "versions.json", versions)


def snapshot() -> None:
    destination = ROOT / "versions" / VERSION_ID
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite immutable snapshot: {destination}")
    destination.mkdir(parents=True)
    for name in SITE_FILES:
        source = ROOT / name
        if not source.exists():
            raise FileNotFoundError(source)
        shutil.copy2(source, destination / name)


def main() -> None:
    baseline = ROOT / "versions" / BASELINE_ID
    if not baseline.exists():
        raise FileNotFoundError(baseline)
    if (ROOT / "versions" / VERSION_ID).exists():
        raise FileExistsError(f"V20b already exists: {VERSION_ID}")

    for name in ("class_context.json", "schedule_overrides.json", "payment_context.json"):
        shutil.copy2(baseline / name, ROOT / name)

    context = read_json(ROOT / "class_context.json")
    rows = [
        row
        for row in context
        if "HK239HG" in row.get("text", "")
        and "Class SS" in row.get("text", "")
    ]
    if len(rows) != 6:
        raise ValueError(f"Expected six HK239HG SS rows, found {len(rows)}")

    for row in rows:
        lesson = int(row["text"].split(" - L", 1)[1].split("[", 1)[0].strip())
        if row["date"] != EXPECTED_DATES[lesson]:
            raise ValueError(
                f"HK239HG SS L{lesson} date {row['date']} != {EXPECTED_DATES[lesson]}"
            )
        row["status"] = "confirmed"
        row["text"] = lesson_text(lesson)
        row["teacher"] = "Garett"
        row["layer"] = "mine"
        row["red"] = lesson in LESSON_NOTES
        row["source"] = (
            "HK239HG_SS_R2_CHECKED_REPLACEMENT_DATES_PROPOSED R1_OK.docx; "
            "Calvin WhatsApp confirmation 2026-07-30"
        )
    write_json(ROOT / "class_context.json", context)

    overrides = read_json(ROOT / "schedule_overrides.json")
    overrides["revision"] = "V20b"
    overrides["source"] = (
        "V20a plus Calvin WhatsApp confirmation on 2026-07-30 accepting "
        "Garett's six HK239HG SS replacement mornings."
    )
    overrides["confirmation"] = (
        "HK239HG SS is confirmed for Garett on Sep 23, Sep 28, Sep 30, "
        "Oct 5, Oct 7, and Oct 12, all 09:00-12:00. HK280HG SS remains "
        "unassigned to Garett; Calvin will arrange another tutor/class."
    )
    write_json(ROOT / "schedule_overrides.json", overrides)

    update_versions()
    patch_generator()
    subprocess.run([sys.executable, "generate_site.py"], cwd=ROOT, check=True)
    snapshot()

    summary = read_json(ROOT / "summary.json")
    if summary.get("override_revision") != "V20b":
        raise ValueError(summary)
    if summary.get("changed_in_version") != 6:
        raise ValueError(summary)

    print(VERSION_ID)
    print(BUILD_ID)


if __name__ == "__main__":
    main()
