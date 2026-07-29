from __future__ import annotations

import csv
import json
import re
from collections import defaultdict
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "qa_v20c_full_audit"
TODAY = "2026-07-30"
TIME_RE = re.compile(
    r"(?<!\d)(\d{1,2}):?(\d{2})\s*[-–]\s*(\d{1,2}):?(\d{2})(?!\d)"
)
LESSON_RE = re.compile(r"\bL\s*(\d+)\b", re.I)

EXPECTED = {
    "HK265HG · FS · JUL 2026": (12, 12),
    "MC0106DS · 第2班": (47, 6),
    "HK244HG · CW8": (12, 8),
    "HK239HG · FS": (6, 3),
    "HK239HG · CW10": (6, 6),
    "HK244EG · CW": (18, 11),
    "HK280HG · CW1": (5, 5),
    "HK239HG · SS": (6, 6),
    "HK265HG · FS · SEP 2026": (12, 12),
    "HK244EG · FS": (18, 18),
    "HK281DS · CW7": (62, 1),
    "HK239HG · ST": (6, 6),
    "HK239HG · 城巿一條龍": (6, 6),
    "HK239HG · LT": (6, 6),
}


def read_json(name: str):
    return json.loads((ROOT / name).read_text(encoding="utf-8"))


def group_for(row: dict) -> str | None:
    text = row.get("text", "")
    if "MC0106DS" in text:
        return "MC0106DS · 第2班"
    if "HK281DS" in text and "CW7" in text:
        return "HK281DS · CW7"
    if "HK280HG" in text and "CW1" in text:
        return "HK280HG · CW1"
    if "HK265HG" in text and "Class FS" in text:
        return (
            "HK265HG · FS · JUL 2026"
            if row["date"] < "2026-09-01"
            else "HK265HG · FS · SEP 2026"
        )
    if "HK244HG" in text and "Class CW8" in text:
        return "HK244HG · CW8"
    if "HK244EG" in text and "Class CW" in text:
        return "HK244EG · CW"
    if "HK244EG" in text and "Class FS" in text and "FS-1" not in text:
        return "HK244EG · FS"
    if "HK239HG" not in text:
        return None
    for class_name, label in (
        ("Class CW10", "HK239HG · CW10"),
        ("Class FS", "HK239HG · FS"),
        ("Class SS", "HK239HG · SS"),
        ("Class ST", "HK239HG · ST"),
        ("Class LT", "HK239HG · LT"),
        ("Class 城巿一條龍", "HK239HG · 城巿一條龍"),
    ):
        if class_name in text:
            return label
    return None


def is_mine(row: dict) -> bool:
    teacher = str(row.get("teacher", "")).lower()
    text = row.get("text", "").lower()
    return (
        row.get("layer") == "mine"
        or "garett" in teacher
        or "(garett)" in text
    )


def parse_interval(row: dict) -> tuple[int, int] | None:
    match = TIME_RE.search(row.get("text", ""))
    if not match:
        return None
    sh, sm, eh, em = (int(value) for value in match.groups())
    return sh * 60 + sm, eh * 60 + em


def main() -> None:
    OUT.mkdir(exist_ok=True)
    events = read_json("events.json")
    context = read_json("class_context.json")
    payment = read_json("payment_context.json")
    rows = events + context

    grouped: dict[str, list[dict]] = defaultdict(list)
    for row in rows:
        group = group_for(row)
        if group in EXPECTED:
            grouped[group].append(row)

    payment_by_label = {item["label"]: item for item in payment}
    ledger = []
    for label, (expected_total, expected_mine) in EXPECTED.items():
        class_rows = grouped[label]
        numbered = [
            row for row in class_rows if LESSON_RE.search(row.get("text", ""))
        ]
        mine = [row for row in numbered if is_mine(row)]
        lesson_numbers = sorted(
            int(LESSON_RE.search(row["text"]).group(1)) for row in numbered
        )
        assert len(numbered) == expected_total, (label, len(numbered), expected_total)
        assert lesson_numbers == list(range(1, expected_total + 1)), (
            label,
            lesson_numbers,
        )
        assert len(mine) == expected_mine, (label, len(mine), expected_mine)
        assert all(row["status"] == "confirmed" for row in mine), label
        metadata = payment_by_label[label]
        source_files = sorted(
            {
                str(row.get("source", "")).split(";", 1)[0]
                for row in numbered
                if row.get("source")
            }
        )
        ledger.append(
            {
                "class": label,
                "provider": metadata["provider"],
                "full_course_start": metadata["full_course_start"],
                "full_course_end": metadata["full_course_end"],
                "first_garett_lesson": min(row["date"] for row in mine),
                "last_garett_lesson": max(row["date"] for row in mine),
                "garett_lessons": len(mine),
                "full_lessons": len(numbered),
                "garett_status": "confirmed",
                "source_count": len(source_files),
                "sources": " | ".join(source_files),
            }
        )

    ledger.sort(key=lambda item: (item["first_garett_lesson"], item["class"]))
    with (OUT / "upcoming_course_ledger.csv").open(
        "w", encoding="utf-8-sig", newline=""
    ) as handle:
        writer = csv.DictWriter(handle, fieldnames=ledger[0].keys())
        writer.writeheader()
        writer.writerows(ledger)

    mine_confirmed = [
        row
        for row in rows
        if row.get("date", "") >= TODAY
        and row.get("status") == "confirmed"
        and is_mine(row)
        and parse_interval(row)
    ]
    by_date: dict[str, list[dict]] = defaultdict(list)
    for row in mine_confirmed:
        by_date[row["date"]].append(row)

    overlaps = []
    short_gaps = []
    for day, day_rows in sorted(by_date.items()):
        timed = sorted(
            ((parse_interval(row), row) for row in day_rows),
            key=lambda item: item[0],
        )
        for index, ((start, end), row) in enumerate(timed):
            for (next_start, next_end), next_row in timed[index + 1 :]:
                if next_start < end:
                    overlaps.append(
                        {
                            "date": day,
                            "first": row["text"],
                            "second": next_row["text"],
                            "overlap_minutes": end - next_start,
                        }
                    )
            if index + 1 < len(timed):
                (next_start, _), next_row = timed[index + 1]
                gap = next_start - end
                if 0 <= gap <= 90:
                    short_gaps.append(
                        {
                            "date": day,
                            "gap_minutes": gap,
                            "first": row["text"],
                            "second": next_row["text"],
                        }
                    )
    assert not overlaps, overlaps

    identities: dict[tuple, dict] = {}
    duplicates = []
    for row in rows:
        identity = (row.get("date"), row.get("text"))
        if identity in identities:
            duplicates.append(
                {
                    "date": row.get("date"),
                    "text": row.get("text"),
                }
            )
        identities[identity] = row
    assert not duplicates, duplicates

    active_hk280_ss = [
        row
        for row in rows
        if "HK280HG" in row.get("text", "")
        and "Class SS" in row.get("text", "")
    ]
    assert not active_hk280_ss

    findings = {
        "version": "2026-07-30-V20c",
        "upcoming_course_count": len(ledger),
        "upcoming_course_ledger": ledger,
        "future_confirmed_garett_timed_entries": len(mine_confirmed),
        "confirmed_garett_overlaps": overlaps,
        "same_or_nearby_lunch_dinner_gaps_at_most_90_minutes": short_gaps,
        "exact_duplicate_entries": duplicates,
        "active_superseded_hk280hg_ss_rows": active_hk280_ss,
        "known_source_defects_requiring_no_invention": [
            (
                "MC106DS workbook header says 49 lessons / 196 hours, but the "
                "actual finalized assignment rows stop at L47 / 188 hours."
            ),
            (
                "HK281DS CW7 L62 lists a 14:00-18:00 lesson but an "
                "11:30-12:30 final exam; the conflict stays visibly flagged."
            ),
            (
                "HK239HG 城巿一條龍 has a confirmed derived TXT source rather "
                "than the original Calvin timetable document."
            ),
        ],
    }
    (OUT / "operational_audit.json").write_text(
        json.dumps(findings, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "# V20c Upcoming Course Audit",
        "",
        f"- Active upcoming ERB classes: {len(ledger)}",
        f"- Future confirmed Garett timed entries: {len(mine_confirmed)}",
        "- Confirmed Garett time overlaps: 0",
        "- Exact duplicate display entries: 0",
        "- Superseded HK280HG SS active entries: 0",
        "",
        "## Course Ledger",
        "",
        "| First mine | Class | Mine / Full | Status |",
        "|---|---|---:|---|",
    ]
    lines.extend(
        f'| {item["first_garett_lesson"]} | {item["class"]} | '
        f'{item["garett_lessons"]} / {item["full_lessons"]} | '
        f'{item["garett_status"]} |'
        for item in ledger
    )
    lines.extend(
        [
            "",
            "## Known Source Defects",
            "",
            *[
                f"- {item}"
                for item in findings["known_source_defects_requiring_no_invention"]
            ],
            "",
        ]
    )
    (OUT / "findings.md").write_text("\n".join(lines), encoding="utf-8")
    print(json.dumps(findings, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
