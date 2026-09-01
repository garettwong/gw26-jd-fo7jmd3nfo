from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASELINE_ID = "2026-08-31-V20ad"
VERSION_ID = "2026-09-01-V20ae"
VERSION_LABEL = "2026-09-01 - V20ae"
VERSION_SUMMARY = (
    "課後教學記錄改為中央同步：手機及電腦均只需按一次「整理並儲存」，"
    "不再顯示啟用設定；點按班別名稱會顯示該班 L1 至最後一課的完整記錄。"
    "薪酬頁亦確認首三班已收款。"
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
    if overrides.get("revision") != "V20ad":
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

    overrides["revision"] = "V20ae"
    overrides["source"] = (
        "V20ad timetable data unchanged; lesson-log editing now uses the central Sites "
        "application and class-name focus reveals the complete L1-to-final class context."
    )
    overrides["confirmation"] = (
        "No lesson date, time, teacher, ownership, room, duration, or salary row changed. "
        "Garett confirmed on 2026-09-01 that the first three ERB course payments were received."
    )

    write_json(versions_path, versions)
    write_json(overrides_path, overrides)
    print(json.dumps({"version": VERSION_ID, "lesson_rows_changed": 0}, indent=2))


if __name__ == "__main__":
    main()
