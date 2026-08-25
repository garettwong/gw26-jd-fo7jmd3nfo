from __future__ import annotations

import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
BASELINE_ID = "2026-08-25-V20x"
VERSION_ID = "2026-08-25-V20y"
BUILD_ID = "v20y-hk239-city-dec-first-lesson-marker-20260825a"
SUMMARY = (
    "HK239HG 城市一條龍六堂由 11 月 11 至 13 日改至 12 月 16 至 18 日，"
    "課室 102；所有 ERB 班別首堂加入「此班第一堂」標示。"
    "18 小時薪金由 11 月移至 12 月，總額不變。"
)
SOURCE_NOTE = (
    "Garett explicit user evidence 2026-08-25: HK239HG 城市一條龍 moved "
    "from 2026-11-11 to 2026-11-13 onto 2026-12-16 to 2026-12-18; "
    "all six lessons are taught by Garett in room 102."
)


def read_json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def write_json(name: str, value) -> None:
    (ROOT / name).write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def replacement_lesson(date: str, time: str, lesson: int, note: str = "") -> dict:
    note_text = f" [{note}]" if note else ""
    return {
        "date": date,
        "status": "confirmed",
        "text": (
            "勵行-彩雲 (Garett) - HK239HG, Class 城市一條龍 / "
            "人工智能知識及應用證書 (兼讀制) / "
            f"{time} - L{lesson}{note_text}"
        ),
        "teacher": "Garett",
        "helper": "",
        "layer": "mine",
        "teaching_room": "102",
        "room_source": "Garett explicit user evidence 2026-08-25: room 102",
        "red": False,
        "source": SOURCE_NOTE,
    }


REPLACEMENT_LESSONS = [
    replacement_lesson("2026-12-16", "09:00-12:00", 1),
    replacement_lesson("2026-12-16", "13:00-16:00", 2),
    replacement_lesson("2026-12-17", "09:00-12:00", 3),
    replacement_lesson("2026-12-17", "13:00-16:00", 4),
    replacement_lesson(
        "2026-12-18",
        "09:00-12:00",
        5,
        "持續評估／小組討論／專題報告",
    ),
    replacement_lesson(
        "2026-12-18",
        "13:00-16:00",
        6,
        "期末考試 15:30-16:30",
    ),
]


OLD_LESSONS = [
    (
        "2026-11-11",
        "K12",
        1,
        "勵行-彩雲 (Garett) / 人工智能知識及應用證書(兼讀制) / "
        "HK239HG, Class 城巿一條龍, (0900 - 1200) - L1 /",
    ),
    (
        "2026-11-11",
        "K13",
        2,
        "勵行-彩雲 (Garett) / 人工智能知識及應用證書(兼讀制) / "
        "HK239HG, Class 城巿一條龍, (1300 - 1600) - L2 /",
    ),
    (
        "2026-11-12",
        "N12",
        3,
        "勵行-彩雲 (Garett) / 人工智能知識及應用證書(兼讀制) / "
        "HK239HG, Class 城巿一條龍, (0900 - 1200) - L3",
    ),
    (
        "2026-11-12",
        "N13",
        4,
        "勵行-彩雲 (Garett) / 人工智能知識及應用證書(兼讀制) / "
        "HK239HG, Class 城巿一條龍, (1300 - 1600) - L4",
    ),
    (
        "2026-11-13",
        "Q12",
        5,
        "勵行-彩雲 (Garett) [Group Discussion] / "
        "人工智能知識及應用證書(兼讀制) / "
        "HK239HG, Class 城巿一條龍, (0900 - 1200) - L5",
    ),
    (
        "2026-11-13",
        "Q13",
        6,
        "勵行-彩雲 (Garett) [Final Exam] / 人工智能知識及應用證書(兼讀制) / "
        "HK239HG, Class 城巿一條龍, (1300 - 1600) - L6",
    ),
]


def update_context() -> None:
    context = read_json("class_context.json")
    existing = [
        item
        for item in context
        if "HK239HG" in item.get("text", "")
        and ("城市一條龍" in item.get("text", "") or "城巿一條龍" in item.get("text", ""))
    ]
    if existing:
        raise ValueError(f"Unexpected existing city-course context rows: {existing}")
    context.extend(REPLACEMENT_LESSONS)
    write_json("class_context.json", context)


def update_overrides() -> None:
    data = read_json("schedule_overrides.json")
    if data.get("revision") != "V20x":
        raise ValueError(f"Expected V20x override source, found {data.get('revision')!r}")
    target_cells = {(row[0], row[1]) for row in OLD_LESSONS}
    existing_targets = [
        item
        for item in data["overrides"]
        if (item.get("date"), item.get("match_cell")) in target_cells
    ]
    if existing_targets:
        raise ValueError(f"Old city-course rows already have overrides: {existing_targets}")

    data["revision"] = "V20y"
    data["source"] = (
        "V20x plus Garett explicit user evidence 2026-08-25 moving HK239HG "
        "城市一條龍 to 2026-12-16 through 2026-12-18 in room 102, plus a "
        "responsive first-lesson marker for every ERB cohort."
    )
    data["confirmation"] = (
        "HK239HG 城市一條龍 is confirmed for Garett: L1-L2 on 2026-12-16, "
        "L3-L4 on 2026-12-17, and L5-L6 on 2026-12-18, room 102, exactly "
        "18 hours. The superseded 2026-11-11 to 2026-11-13 rows are excluded. "
        "Salary moves from November to December with no grand-total change."
    )
    for date, cell, lesson, text in OLD_LESSONS:
        data["overrides"].append({
            "date": date,
            "match_cell": cell,
            "course_code": "HK239HG",
            "class": "城巿一條龍",
            "lesson": lesson,
            "teacher": "Garett",
            "status": "confirmed",
            "source": SOURCE_NOTE,
            "text": text,
            "exclude": True,
        })
    write_json("schedule_overrides.json", data)


def update_versions() -> None:
    versions = read_json("versions.json")
    latest = [item for item in versions if item.get("latest")]
    if len(latest) != 1 or latest[0]["id"] != BASELINE_ID:
        raise ValueError(f"Expected one V20x latest release, found {latest}")
    if any(item["id"] == VERSION_ID for item in versions):
        raise ValueError(f"{VERSION_ID} already exists")
    for item in versions:
        item["latest"] = False
    versions.insert(0, {
        "id": VERSION_ID,
        "label": "2026-08-25 - V20y",
        "summary": SUMMARY,
        "latest": True,
    })
    write_json("versions.json", versions)


def main() -> None:
    if (ROOT / "versions" / VERSION_ID).exists():
        raise FileExistsError(f"Refusing to overwrite {VERSION_ID}")
    if (ROOT / "earnings" / "versions" / VERSION_ID).exists():
        raise FileExistsError(f"Refusing to overwrite salary {VERSION_ID}")
    update_context()
    update_overrides()
    update_versions()
    print(VERSION_ID)
    print(BUILD_ID)


if __name__ == "__main__":
    main()
