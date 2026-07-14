from __future__ import annotations

import json
import re
from collections import Counter
from pathlib import Path


ROOT = Path(__file__).resolve().parent
EVENTS = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
CONTEXT = json.loads((ROOT / "class_context.json").read_text(encoding="utf-8"))
ALL = EVENTS + CONTEXT
LESSON_RE = re.compile(r"\bL\s*(\d+)\b", re.I)
TIME_RE = re.compile(r"(?<!\d)(\d{3,4})\s*-\s*(\d{3,4})(?!\d)")


def lesson(row: dict) -> int | None:
    match = LESSON_RE.search(row["text"])
    return int(match.group(1)) if match else None


def teacher(row: dict) -> str:
    explicit = str(row.get("teacher", "")).strip()
    if explicit:
        return explicit
    match = re.search(r"\((Garett|Andy|Calvin)\)", row["text"], re.I)
    if match:
        return match.group(1).title()
    match = re.search(r"\b(Garett|Andy|Calvin)\b", row["text"], re.I)
    return match.group(1).title() if match else ""


def rows_with(*needles: str, rows: list[dict] = ALL) -> list[dict]:
    return [row for row in rows if all(needle in row["text"] for needle in needles)]


def assert_lessons(rows: list[dict], expected: range, label: str) -> None:
    actual = sorted(value for row in rows if (value := lesson(row)) is not None)
    wanted = list(expected)
    assert actual == wanted, f"{label}: lessons {actual}, expected {wanted}"


def assert_status(rows: list[dict], status: str, label: str) -> None:
    actual = {row["status"] for row in rows}
    assert actual == {status}, f"{label}: statuses {actual}, expected {status}"


# HK244EG HF2: 17 numbered lessons plus one unnumbered cancellation.
hf2 = rows_with("HK244EG", "HF2", rows=EVENTS)
assert len(hf2) == 18
assert_lessons(hf2, range(1, 18), "HK244EG HF2")
hf2_cancelled = [row for row in hf2 if "cancelled" in row["text"].lower()]
assert len(hf2_cancelled) == 1 and lesson(hf2_cancelled[0]) is None
hf2_teachers = {lesson(row): teacher(row) for row in hf2 if lesson(row)}
assert hf2_teachers[6] == "Andy" and hf2_teachers[15] == "Andy"
assert hf2_teachers[7] == "Garett" and hf2_teachers[10] == "Garett"

# HK244EG FS-1: complete L1-L18 history plus the cancelled June 18 slot.
fs1 = rows_with("HK244EG", "FS-1")
assert len(fs1) == 19
assert_lessons(fs1, range(1, 19), "HK244EG FS-1")
assert {row["date"] for row in fs1 if lesson(row) in range(1, 7)} == {
    "2026-05-14", "2026-05-18", "2026-05-19", "2026-05-21", "2026-05-26", "2026-05-28"
}
fs1_cancelled = [row for row in fs1 if "cancelled" in row["text"].lower()]
assert len(fs1_cancelled) == 1 and lesson(fs1_cancelled[0]) is None
assert teacher(next(row for row in fs1 if lesson(row) == 17)) == "Garett"
assert all(
    teacher(row) == "Carlos / Andy"
    for row in fs1
    if row in CONTEXT and "cancelled" not in row["text"].lower()
)

# HK244HG CW8: official code, final R3 time column, and chat-confirmed teacher split.
cw8 = rows_with("HK244HG", "Class CW8", rows=EVENTS)
assert len(cw8) == 12
assert_lessons(cw8, range(1, 13), "HK244HG CW8")
cw8_expected = {
    1: ("2026-08-06", "1400", "1800", "Garett"),
    2: ("2026-08-13", "1400", "1730", "Garett"),
    3: ("2026-08-14", "1400", "1800", "Garett"),
    4: ("2026-08-24", "1400", "1800", "Garett"),
    5: ("2026-08-26", "1400", "1800", "Garett"),
    6: ("2026-08-27", "1400", "1730", "Garett"),
    7: ("2026-08-31", "1400", "1800", "Garett"),
    8: ("2026-09-02", "1400", "1800", "Garett"),
    9: ("2026-09-03", "1400", "1800", "Garett"),
    10: ("2026-09-04", "1400", "1730", "Calvin"),
    11: ("2026-09-07", "1400", "1800", "Calvin"),
    12: ("2026-09-08", "1400", "1800", "Calvin"),
}
for row in cw8:
    number = lesson(row)
    match = TIME_RE.search(row["text"])
    assert match
    assert (row["date"], match.group(1), match.group(2), teacher(row)) == cw8_expected[number]
    assert "?" not in row["text"]
assert "1515-1715" in next(row["text"] for row in cw8 if lesson(row) == 12)

# Other complete ERB course sequences.
cw = rows_with("HK244EG", "Class CW")
assert len(cw) == 18
assert_lessons(cw, range(1, 19), "HK244EG CW")
assert {lesson(row): teacher(row) for row in cw} == {
    **{number: "Andy" for number in range(1, 5)},
    **{number: "Garett" for number in range(5, 15)},
    15: "Calvin", 16: "Calvin", 17: "Garett", 18: "Calvin",
}

fs = [
    row for row in rows_with("HK244EG", "Class FS", rows=EVENTS)
    if "Class FS-1" not in row["text"]
]
assert len(fs) == 18
assert_lessons(fs, range(1, 19), "HK244EG FS")
assert_status(fs, "confirmed", "HK244EG FS")

ss = rows_with("HK239HG", "Class SS", rows=EVENTS)
st = rows_with("HK239HG", "Class ST", rows=EVENTS)
lt = rows_with("HK239HG", "Class LT", rows=EVENTS)
assert_lessons(ss, range(1, 7), "HK239HG SS")
assert_lessons(st, range(1, 7), "HK239HG ST")
assert_lessons(lt, range(1, 7), "HK239HG LT")
assert_status(ss, "confirmed", "HK239HG SS")
assert_status(st, "unconfirmed", "HK239HG ST")
assert_status(lt, "unconfirmed", "HK239HG LT")
ss_expected_dates = {
    1: "2026-09-16",
    2: "2026-09-23",
    3: "2026-09-30",
    4: "2026-10-07",
    5: "2026-10-14",
    6: "2026-10-21",
}
for row in ss:
    number = lesson(row)
    match = TIME_RE.search(row["text"])
    assert match
    assert row["date"] == ss_expected_dates[number]
    assert match.groups() == ("0830", "1230")
    assert "上水彩園" in row["text"]
assert not rows_with("人工智能知識2應用")

hk265 = rows_with("HK265HG", "Class FS", rows=EVENTS)
assert len(hk265) == 24
assert Counter(lesson(row) for row in hk265) == Counter({number: 2 for number in range(1, 13)})
assert all(row["status"] == "confirmed" for row in hk265)
assert sum("1420-1720" in row["text"] for row in hk265) == 2

# Latest Excel-based proposals: Garett selections plus all currently assigned class context.
hk281 = rows_with("HK281DS", "CW7")
assert len(hk281) == 54
assert_lessons(hk281, range(1, 55), "HK281DS CW7")
assert sum(teacher(row) == "Garett" for row in hk281) == 17
assert all(row["status"] == "unconfirmed" for row in hk281)

mc = rows_with("MC0106DS", "Class 第2班")
assert len(mc) == 44
assert_lessons(mc, range(1, 45), "MC0106DS Class 2")
assert sum(teacher(row) == "Garett" for row in mc) == 6
assert all(row["status"] == "unconfirmed" for row in mc)

# Rejected, reassigned, or not-yet-accepted proposals must not enter the active timetable.
for excluded in ("HK280HG", "BK151HG", "BK155HG"):
    assert not rows_with(excluded), f"Unexpected active timetable entry: {excluded}"
assert not rows_with("HK239HG", "Class CW")

index = (ROOT / "index.html").read_text(encoding="utf-8")
assert "May 2026" in index and "HK244HG" in index
print("source ledger verification passed")
print(f"events={len(EVENTS)} context={len(CONTEXT)} display={len(ALL)}")
