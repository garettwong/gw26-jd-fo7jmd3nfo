import json
from pathlib import Path


ROOT = Path(__file__).resolve().parent
CONTEXT_PATH = ROOT / "class_context.json"
VERSIONS_PATH = ROOT / "versions.json"
VERSION_ID = "2026-08-28-V20ac"

EXPECTED = [
    ("2026-11-11", "09:00-13:00", 1),
    ("2026-11-12", "09:00-13:00", 2),
    ("2026-11-13", "09:00-13:00", 3),
    ("2026-11-16", "09:00-13:00", 4),
    ("2026-11-17", "09:00-12:30", 5),
    ("2026-11-18", "09:00-12:30", 6),
    ("2026-11-19", "09:00-12:30", 7),
    ("2026-11-20", "09:00-12:30", 8),
]

CONFIRMATION_SOURCE = (
    "Calvin WhatsApp confirmation 2026-08-28 13:24; "
    "all eight HK267HG CW2 lessons confirmed for Garett."
)


def write_json(path: Path, value) -> None:
    path.write_text(
        json.dumps(value, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )


def main() -> None:
    context = json.loads(CONTEXT_PATH.read_text(encoding="utf-8"))
    versions = json.loads(VERSIONS_PATH.read_text(encoding="utf-8"))

    if len(context) != 174:
        raise SystemExit(f"Expected locked V20ab total of 174 rows, found {len(context)}")

    latest = next((row.get("id") for row in versions if row.get("latest")), None)
    if latest != "2026-08-28-V20ab":
        raise SystemExit(f"Expected V20ab as latest, found {latest!r}")
    if any(row.get("id") == VERSION_ID for row in versions):
        raise SystemExit(f"Version already exists: {VERSION_ID}")

    rows = [row for row in context if "HK267HG" in row.get("text", "")]
    if len(rows) != len(EXPECTED):
        raise SystemExit(f"Expected 8 HK267HG rows, found {len(rows)}")

    by_date = {row["date"]: row for row in rows}
    if len(by_date) != len(EXPECTED):
        raise SystemExit("HK267HG dates are not unique")

    for date, time_text, lesson in EXPECTED:
        row = by_date.get(date)
        if row is None:
            raise SystemExit(f"Missing HK267HG lesson date: {date}")
        text = row.get("text", "")
        required = [
            "HK267HG, Class CW2",
            time_text,
            f"L{lesson}",
            "[未確認查詢]",
        ]
        if any(token not in text for token in required):
            raise SystemExit(f"Unexpected HK267HG L{lesson} text: {text}")
        if row.get("status") != "unconfirmed":
            raise SystemExit(f"HK267HG L{lesson} was not unconfirmed")
        if row.get("teacher") != "Garett":
            raise SystemExit(f"Unexpected teacher for HK267HG L{lesson}")
        if str(row.get("teaching_room")) != "104":
            raise SystemExit(f"Unexpected room for HK267HG L{lesson}")

        row["status"] = "confirmed"
        row["text"] = text.replace(" [未確認查詢]", "")
        row["source"] = CONFIRMATION_SOURCE

    for row in versions:
        row["latest"] = False
    versions.insert(
        0,
        {
            "id": VERSION_ID,
            "label": "2026-08-28 - V20ac",
            "summary": (
                "Calvin 確認 HK267HG CW2 全 8 節由 Garett 任教；"
                "11 月 11 至 20 日、30 小時、彩雲二邨 104 室。"
            ),
            "latest": True,
        },
    )

    write_json(CONTEXT_PATH, context)
    write_json(VERSIONS_PATH, versions)
    print("V20ac prepared: 8 HK267HG CW2 lessons confirmed for Garett.")


if __name__ == "__main__":
    main()
