import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONTEXT_PATH = ROOT / "class_context.json"
VERSIONS_PATH = ROOT / "versions.json"
VERSION_ID = "2026-08-28-V20ab"

LESSONS = [
    ("2026-11-11", "09:00-13:00", 1, ""),
    ("2026-11-12", "09:00-13:00", 2, ""),
    ("2026-11-13", "09:00-13:00", 3, ""),
    ("2026-11-16", "09:00-13:00", 4, ""),
    ("2026-11-17", "09:00-12:30", 5, ""),
    ("2026-11-18", "09:00-12:30", 6, " [持續評估 - 實務試]"),
    ("2026-11-19", "09:00-12:30", 7, ""),
    ("2026-11-20", "09:00-12:30", 8, " [期末實務試 10:00-12:00]"),
]

COURSE_NAME = "生成式人工智能圖像及影片創作技巧證書（英語授課／兼讀制）"
SOURCE_NOTE = (
    "Calvin new class enquiry HK267HG(CW2)_.docx received 2026-08-28; "
    "all eight proposed Garett lessons pending confirmation."
)
ROOM_SOURCE = "HK267HG(CW2)_.docx supplied by Calvin on 2026-08-28"


def write_json(path: Path, value) -> None:
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def main() -> None:
    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    versions = json.loads(VERSIONS_PATH.read_text(encoding="utf-8"))

    existing = [row for row in context if "HK267HG" in row.get("text", "")]
    if existing:
        if len(existing) != len(LESSONS):
            raise SystemExit(f"Refusing unexpected HK267HG rows: {len(existing)} present")
        context = [row for row in context if "HK267HG" not in row.get("text", "")]
        versions = [row for row in versions if row.get("id") != VERSION_ID]
        for row in versions:
            row["latest"] = row.get("id") == "2026-08-27-V20aa"
    if len(context) != 166:
        raise SystemExit(f"Expected locked V20aa baseline of 166 rows, found {len(context)}")
    latest = next((row.get("id") for row in versions if row.get("latest")), None)
    if latest != "2026-08-27-V20aa":
        raise SystemExit(f"Expected V20aa as latest, found {latest!r}")

    for date, time_text, lesson, assessment in LESSONS:
        context.append(
            {
                "date": date,
                "status": "unconfirmed",
                "text": (
                    "勵行-彩雲二邨 (Garett) - HK267HG, Class CW2 / "
                    f"{COURSE_NAME} / {time_text} - L{lesson}{assessment} [未確認查詢]"
                ),
                "teacher": "Garett",
                "helper": "",
                "layer": "mine",
                "teaching_room": "104",
                "room_source": ROOM_SOURCE,
                "red": False,
                "source": SOURCE_NOTE,
            }
        )

    for row in versions:
        row["latest"] = False
    versions.insert(
        0,
        {
            "id": VERSION_ID,
            "label": "2026-08-28 - V20ab",
            "summary": (
                "新增 HK267HG CW2 查詢：11 月 11 至 20 日共 8 節、30 小時，"
                "彩雲二邨 104 室；暫列未確認，沒有撞期，亦不計入薪酬。"
            ),
            "latest": True,
        },
    )

    write_json(CONTEXT_PATH, context)
    write_json(VERSIONS_PATH, versions)
    print(f"Prepared {VERSION_ID}: {len(context)} context rows, {len(versions)} versions")


if __name__ == "__main__":
    main()
