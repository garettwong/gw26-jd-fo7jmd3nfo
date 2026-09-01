from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASELINE_ID = "2026-09-01-V20ae"
VERSION_ID = "2026-09-01-V20af"
VERSION_LABEL = "2026-09-01 - V20af"
VERSION_SUMMARY = (
    "修復 8 月 31 日課後教學記錄；新版會自動找回仍保存在手機或電腦內的舊記錄，"
    "只會填補中央記錄的空白，不會覆蓋已同步的內容。課堂及薪酬資料不變。"
)


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    destination = ROOT / "versions" / VERSION_ID
    if destination.exists():
        raise FileExistsError(f"Refusing to overwrite fixed snapshot: {destination}")

    baseline = ROOT / "versions" / BASELINE_ID
    for name in ("events.json", "class_context.json", "payment_context.json"):
        if (ROOT / name).read_bytes() != (baseline / name).read_bytes():
            raise ValueError(f"Root {name} does not match locked {BASELINE_ID}")

    versions_path = ROOT / "versions.json"
    overrides_path = ROOT / "schedule_overrides.json"
    versions = read_json(versions_path)
    overrides = read_json(overrides_path)

    latest = next((item.get("id") for item in versions if item.get("latest")), None)
    if latest != BASELINE_ID:
        raise ValueError(f"Expected {BASELINE_ID} as latest, found {latest!r}")
    if any(item.get("id") == VERSION_ID for item in versions):
        raise ValueError(f"Version already exists: {VERSION_ID}")
    if overrides.get("revision") != "V20ae":
        raise ValueError(f"Unexpected override revision: {overrides.get('revision')!r}")

    for item in versions:
        item["latest"] = False
    versions.insert(
        0,
        {
            "id": VERSION_ID,
            "label": VERSION_LABEL,
            "summary": VERSION_SUMMARY,
            "latest": True,
        },
    )

    overrides["revision"] = "V20af"
    overrides["source"] = (
        "V20ae timetable data unchanged; legacy device-only lesson notes are migrated "
        "to the central lesson-log service only when the central row is empty."
    )
    overrides["confirmation"] = (
        "Recovered the 2026-08-31 HK239HG CW10 Lesson 3 note from Garett's preserved "
        "Chrome timetable and restored it to the central service. No lesson date, time, "
        "teacher, ownership, room, duration, or salary row changed."
    )

    write_json(versions_path, versions)
    write_json(overrides_path, overrides)
    print(json.dumps({"version": VERSION_ID, "lesson_rows_changed": 0}, indent=2))


if __name__ == "__main__":
    main()
