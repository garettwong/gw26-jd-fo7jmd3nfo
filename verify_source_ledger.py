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
    3: ("2026-08-14", "1400", "1800", "Calvin"),
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
assert_status(st, "confirmed", "HK239HG ST")
assert_status(lt, "confirmed", "HK239HG LT")
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
    assert match.groups() == ("0900", "1200")
    assert "上水彩園" in row["text"]
    assert "TIGHT TRAVEL" not in row["text"]
    assert "Calvin WhatsApp 2026-07-18 23:46" in row.get("source", "")
assert all("Calvin WhatsApp 2026-07-18 23:46" in row.get("source", "") for row in st)
assert all("Calvin WhatsApp 2026-07-18 23:46" in row.get("source", "") for row in lt)
assert not rows_with("人工智能知識2應用")

hk265 = rows_with("HK265HG", "Class FS", rows=EVENTS)
assert len(hk265) == 24
assert Counter(lesson(row) for row in hk265) == Counter({number: 2 for number in range(1, 13)})
assert all(row["status"] == "confirmed" for row in hk265)
assert sum("1420-1720" in row["text"] for row in hk265) == 2
hk265_jul = [row for row in hk265 if row["date"] < "2026-09-01"]
hk265_sep = [row for row in hk265 if row["date"] >= "2026-09-01"]
assert len(hk265_jul) == 12 and len(hk265_sep) == 12
assert_lessons(hk265_jul, range(1, 13), "HK265HG FS July cohort")
assert_lessons(hk265_sep, range(1, 13), "HK265HG FS September cohort")
assert_status(hk265_jul, "confirmed", "HK265HG FS July cohort")
assert_status(hk265_sep, "confirmed", "HK265HG FS September cohort")
assert min(row["date"] for row in hk265_jul) == "2026-07-24"
assert min(row["date"] for row in hk265_sep) == "2026-09-16"
assert {row.get("group_label") for row in hk265_jul} == {"HK265HG · FS · JUL 2026"}
assert {row.get("group_label") for row in hk265_sep} == {"HK265HG · FS · SEP 2026"}
oct7_hk265_l9 = [row for row in hk265 if row["date"] == "2026-10-07" and lesson(row) == 9]
assert len(oct7_hk265_l9) == 1
assert "TIGHT TRAVEL ~40-47m" in oct7_hk265_l9[0]["text"]

# Latest Excel-based proposals plus all currently assigned class context.
hk281 = [
    row for row in rows_with("HK281DS", "CW7")
    if "PROPOSED availability only" not in row["text"]
]
assert len(hk281) == 54
assert_lessons(hk281, range(1, 55), "HK281DS CW7")
assert sum(teacher(row) == "Garett" for row in hk281) == 0
assert all(row["status"] == "unconfirmed" for row in hk281)
released_hk281_lessons = {5, 16, 17, 19, 22, 23, 24, 25, 28, 29, 30, 31}
released_hk281 = [row for row in hk281 if lesson(row) in released_hk281_lessons]
assert len(released_hk281) == 12
assert all(teacher(row) == "Other tutor / TBC" for row in released_hk281)
assert all(row.get("layer") in {None, "class"} for row in released_hk281)
assert all(row.get("red") for row in released_hk281)
assert all("CALVIN: GARETT NOT REQUIRED" in row["text"] for row in released_hk281)
hk281_reassigned = [row for row in hk281 if lesson(row) in {4, 18}]
assert [(row["date"], lesson(row), teacher(row), row.get("layer")) for row in hk281_reassigned] == [
    ("2026-08-29", 4, "Other tutor / TBC", "class"),
    ("2026-09-07", 18, "Other tutor / TBC", "class"),
]
hk281_sep14 = [row for row in hk281 if lesson(row) in {30, 31}]
assert [(row["date"], lesson(row), teacher(row)) for row in hk281_sep14] == [
    ("2026-09-14", 30, "Other tutor / TBC"),
    ("2026-09-14", 31, "Other tutor / TBC"),
]
assert all("CALVIN: GARETT NOT REQUIRED" in row["text"] for row in hk281_sep14)
assert all(row.get("red") for row in hk281_sep14)

mc = rows_with("MC0106DS", "Class 第2班")
assert len(mc) == 47
assert_lessons(mc, range(1, 48), "MC0106DS Class 2")
assert sum(teacher(row) == "Garett" for row in mc) == 6
assert all(row["status"] == "confirmed" for row in mc)
mc_garett = [row for row in mc if teacher(row) == "Garett"]
assert [(row["date"], lesson(row)) for row in mc_garett] == [
    ("2026-08-01", 3),
    ("2026-08-01", 4),
    ("2026-08-08", 7),
    ("2026-08-08", 8),
    ("2026-08-15", 15),
    ("2026-08-15", 16),
]
assert all(row in EVENTS for row in mc_garett)
mc_room306_calvin = [
    row for row in mc
    if teacher(row) == "Calvin" and "Calvin takes all Room 306 enquiry lessons" in row.get("source", "")
]
assert [lesson(row) for row in mc_room306_calvin] == [18, 21, 25, 27, 29, 33]
assert not any(teacher(row) == "Other tutor / TBC" for row in mc)
assert all(row.get("layer") == "class" for row in mc if row in CONTEXT)
assert not any(lesson(row) in {48, 49} for row in mc)

# Rejected or not-yet-accepted proposals must not enter the active timetable.
for excluded in ("BK151HG", "BK155HG"):
    assert not rows_with(excluded), f"Unexpected active timetable entry: {excluded}"

# HK280HG SS is a finalized class schedule, but Calvin reassigned it away from Garett.
# Keep it in All Full as confirmed class context and exclude it from Garett's views and salary.
hk280hg_ss = rows_with("HK280HG", "Class SS")
assert len(hk280hg_ss) == 5
assert [(row["date"], lesson(row)) for row in hk280hg_ss] == [
    ("2026-09-18", 1),
    ("2026-09-21", 2),
    ("2026-09-23", 3),
    ("2026-09-28", 4),
    ("2026-09-30", 5),
]
assert all(row["status"] == "confirmed" for row in hk280hg_ss)
assert all(teacher(row) == "Other tutor / TBC" for row in hk280hg_ss)
assert all(row.get("layer") == "class" for row in hk280hg_ss)
hk239_cw10 = rows_with("HK239HG", "Class CW10", rows=EVENTS)
assert len(hk239_cw10) == 6
assert [(row["date"], lesson(row)) for row in hk239_cw10] == [
    ("2026-08-27", 1),
    ("2026-08-29", 2),
    ("2026-08-31", 3),
    ("2026-09-02", 4),
    ("2026-09-03", 5),
    ("2026-09-07", 6),
]
assert all(row["status"] == "confirmed" for row in hk239_cw10)
assert all(teacher(row) == "Garett" for row in hk239_cw10)
assert all("0900-1200" in row["text"] for row in hk239_cw10)
assert all("HK239HG(CW10)_R3.docx" in row.get("source", "") for row in hk239_cw10)

# HK239HG FS: confirmed Garett substitution on Aug 14 and 19; another tutor covers Aug 21.
hk239_fs = rows_with("HK239HG", "Class FS")
assert len(hk239_fs) == 6
assert_lessons(hk239_fs, range(1, 7), "HK239HG FS")
hk239_fs_expected = {
    1: ("2026-08-14", "1000", "1300", "Garett"),
    2: ("2026-08-14", "1400", "1700", "Garett"),
    3: ("2026-08-19", "1000", "1300", "Garett"),
    4: ("2026-08-19", "1400", "1700", "Garett"),
    5: ("2026-08-21", "1000", "1300", "Other tutor / TBC"),
    6: ("2026-08-21", "1400", "1700", "Other tutor / TBC"),
}
for row in hk239_fs:
    number = lesson(row)
    match = TIME_RE.search(row["text"])
    assert match
    assert (row["date"], match.group(1), match.group(2), teacher(row)) == hk239_fs_expected[number]
    assert row["status"] == "confirmed"
    assert "四海大廈" in row["text"]
    expected_layer = "mine" if number <= 4 else "class"
    assert row.get("layer") == expected_layer, (
        f"HK239HG FS L{number}: layer {row.get('layer')!r}, expected {expected_layer!r}"
    )

# HK280HS SS remains an enquiry. These five records are availability only.
hk280hs_ss = rows_with("HK280HS", "Class SS")
assert len(hk280hs_ss) == 5
assert [row["date"] for row in hk280hs_ss] == [
    "2026-09-09",
    "2026-09-10",
    "2026-09-12",
    "2026-09-14",
    "2026-09-19",
]
assert all(teacher(row) == "Garett" for row in hk280hs_ss)
assert all(row["status"] == "unconfirmed" for row in hk280hs_ss)
assert all(row.get("layer") == "mine" for row in hk280hs_ss)
assert all(row.get("red") for row in hk280hs_ss)
assert all("PROPOSED availability only" in row["text"] for row in hk280hs_ss)
assert all("Lesson TBC" in row["text"] for row in hk280hs_ss)
assert all("EXACT LESSON DATE/TIME PENDING CALVIN" in row["text"] for row in hk280hs_ss)
sep14 = next(row for row in hk280hs_ss if row["date"] == "2026-09-14")
assert "AM / PM OK UNTIL 17:00 - NO NIGHT" in sep14["text"]
assert all(
    "AM / PM / NIGHT OK" in row["text"]
    for row in hk280hs_ss
    if row["date"] != "2026-09-14"
)
assert all("0900 - 1300" not in row["text"] for row in hk280hs_ss)

# V18a does not displace any confirmed SEN, HK265HG, or HK244EG assignment.
hk244_cw_l10 = next(row for row in cw if lesson(row) == 10)
assert hk244_cw_l10["status"] == "confirmed"
assert teacher(hk244_cw_l10) == "Garett"
assert "REPLACEMENT REQUESTED" not in hk244_cw_l10["text"]
assert not hk244_cw_l10.get("red")
hk265_sep_l1_l3 = [
    row for row in hk265
    if row["date"] >= "2026-09-01" and lesson(row) in {1, 2, 3}
]
assert len(hk265_sep_l1_l3) == 3
assert all(row["status"] == "confirmed" for row in hk265_sep_l1_l3)
assert all(teacher(row) == "Garett" for row in hk265_sep_l1_l3)
assert all("REPLACEMENT REQUESTED" not in row["text"] for row in hk265_sep_l1_l3)
assert all(not row.get("red") for row in hk265_sep_l1_l3)
assert not any("PROPOSED replacement option" in row["text"] for row in ALL)
assert not any(
    re.search(r"Class CW(?!10\b)", row["text"])
    for row in rows_with("HK239HG")
)

index = (ROOT / "index.html").read_text(encoding="utf-8")
assert "May 2026" in index and "HK244HG" in index
assert index.count('class="span-row"') == 19
assert 'data-first="2026-07-24" data-last="2026-08-12"' in index
assert 'data-first="2026-09-16" data-last="2026-10-14"' in index
assert 'data-first="2026-08-14" data-last="2026-08-21"' in index
assert "HK265HG · FS · JUL 2026" in index and "HK265HG · FS · SEP 2026" in index
assert index.count('data-span-course="') == 19
assert all(control in index for control in (
    'id="spanLabelsToggle"', 'id="spanZoomOut"', 'id="spanZoomReset"', 'id="spanZoomIn"',
    'data-span-course-action="all"', 'data-span-course-action="none"',
))
filter_positions = [
    index.index('<div class="filter-group-label">ERB</div>'),
    index.index('<div class="filter-group-label">SEN</div>'),
    index.index('<div class="filter-group-label">Other jobs</div>'),
]
assert filter_positions == sorted(filter_positions)
erb_filter_section = index[filter_positions[0]:filter_positions[1]]
erb_codes = re.findall(r'>(HK\d+[A-Z]+)', erb_filter_section)
assert erb_codes == sorted(erb_codes)
assert '@media (pointer:fine) and (min-width:821px)' in index
assert '.span-month:first-child{border-left:0}' in index
assert 'id="transitNotice"' in index
assert 'NO MEAL BUFFER' in index
assert "'sheung_shui|four_seas':64" in index
assert '<span class="mode-main">VER</span>' in index
assert "&#9776;" not in index
assert "v18h-filter-status-span-labels-20260719a" in index
versions = json.loads((ROOT / "versions.json").read_text(encoding="utf-8"))
assert index.count('class="version-menu-item') == len(versions)
assert '<details id="topVersionSelector" class="version-menu">' in index
assert 'Web - status-coloured filters and always-visible class-span labels.' in index
assert 'data-version-id="2026-07-19-V18h"' in index
assert 'class="version-menu-item current"' in index
version_selector_start = index.index('<details id="topVersionSelector"')
version_selector_end = index.index('</details>', version_selector_start)
assert 'earnings' not in index[version_selector_start:version_selector_end].lower()
assert 'data-filter="changed"' not in index
assert '<span class="sample changed-sample"></span> Changed in V18h' not in index
assert index.count('class="change-badge"') == 0
assert index.count('class="filter course-filter upcoming"') == 13
assert index.count('class="filter course-filter pending"') == 1
assert index.count('class="filter course-filter completed"') >= 2
assert index.count('class="filter course-filter context"') >= 2
assert '<span class="filter-status-total">17 tracked ERB classes</span>' in index
assert '<span class="filter-status-swatch upcoming"></span>Upcoming 12' in index
assert '<span class="filter-status-swatch pending"></span>Pending 1' in index
assert '<span class="filter-status-swatch completed"></span>Completed 2' in index
assert '<span class="filter-status-swatch context"></span>Full-class context 2' in index
assert '<span class="span-course-breakdown">19 total = 17 ERB + 2 SEN</span>' in index
assert index.count('class="span-bar-label"') == 19
assert index.count('class="span-course-toggle ') == 19
assert index.count("Lesson TBC") >= 5
assert index.count('data-day-hours hidden') >= 400
assert 'data-teaching-intervals="480-590,660-780"' in index
assert 'function refreshDailyHours()' in index
assert 'function mergeTeachingMinutes(intervals)' in index
assert "mode==='mine-confirmed'?status==='confirmed'" in index
assert "' teaching time; travel excluded'" in index
assert '<div class="code-key"><b>MC0106DS</b><span>' in index
assert 'ERB course code legend' in index and '8 course families' in index
assert '.class-summary-card.unconfirmed{border-width:3px;border-style:dashed' in index
assert "window.__courseFilter='all';" in index
assert "window.__upcomingFilterState=null;" in index
assert "window.__cardCourseFilter=null;" in index
assert 'aria-label="All full timetable and clear course filter"' in index
assert '<div id="upcomingHeading" class="section-h">Upcoming ERB classes</div>' in index
upcoming_start = index.index('<section class="class-summary upcoming-summary"')
upcoming_end = index.index('</section>', upcoming_start)
upcoming = index[upcoming_start:upcoming_end]
upcoming_labels = re.findall(r'<span class="upcoming-date">([^<]+)</span>.*?<strong>(HK[^<]+|MC[^<]+)</strong>', upcoming)
assert upcoming_labels[:3] == [
    ("Jul 24", "HK265HG · FS · JUL 2026"),
    ("Aug 1", "MC0106DS · 第2班"),
    ("Aug 6", "HK244HG · CW8"),
]
assert ("Sep 16", "HK265HG · FS · SEP 2026") in upcoming_labels
assert "英文授課／兼讀制" in upcoming and ">ENG<" in upcoming
assert "HK281DS · CW7" not in upcoming
assert "基督教勵行會" in upcoming
assert "HK280HS · SS" in upcoming and "上水彩園邨彩湖樓2座地下129舖02室" in upcoming
assert 'data-toggle-filter="1"' in upcoming
assert '>CONFIRMED</span>' in upcoming and '>UNCONFIRMED</span>' in upcoming
assert upcoming.count('>CONFIRMED</span>') == 12
assert upcoming.count('>UNCONFIRMED</span>') == 1
assert 'HK239HG · ST' in upcoming and 'HK239HG · LT' in upcoming
assert re.findall(r'class="filter course-filter pending"[^>]*>([^<]+)</button>', index) == [
    'HK280HS · SS (5)'
]
assert 'class="filter course-filter context"' in index
assert '<div id="completedHeading" class="section-h">Completed ERB classes</div>' in index
completed_start = index.index('<section class="class-summary completed-summary"')
completed_end = index.index('</section>', completed_start)
completed = index[completed_start:completed_end]
assert 'HK244EG' in completed and 'HF2' in completed and '>COMPLETED</span>' in completed
assert index.count('data-span-month-toggle="') == 8
assert index.count('<input type="checkbox" data-span-month-toggle="') == 8
assert index.count('data-span-row-toggle="') == 0
assert '<section id="spanCoursePicker" class="span-course-picker" aria-label="Class visibility">' in index
assert index.count('data-span-course="') == 19
assert "spanCourseCount.textContent=enabled+'/'+spanCourseInputs.length+' ON'" in index
assert index.count('class="span-day"') == 245
assert 'const spanZoomLevels=[8,12,16,22,30,40]' in index
assert 'function layoutSpanTimeline()' in index

# The eleven confirmed Christian Action course instances are independently present.
confirmed_ca_specs = [
    ("HK265HG", "Class FS", "2026-07-24", 12),
    ("HK244HG", "Class CW8", "2026-08-06", 12),
    ("HK239HG", "Class FS", "2026-08-14", 6),
    ("HK239HG", "Class CW10", "2026-08-27", 6),
    ("HK244EG", "Class CW", "2026-08-24", 18),
    ("HK239HG", "Class SS", "2026-09-16", 6),
    ("HK239HG", "Class ST", "2026-10-03", 6),
    ("HK239HG", "Class LT", "2026-11-23", 6),
    ("HK265HG", "Class FS", "2026-09-16", 12),
    ("HK244EG", "Class FS", "2026-09-21", 18),
    ("HK239HG", "Class 城巿一條龍", "2026-11-11", 6),
]
for code, class_name, first_date, count in confirmed_ca_specs:
    matches = [
        row for row in ALL
        if code in row["text"]
        and class_name in row["text"]
        and row["date"] >= first_date
        and (code != "HK244EG" or class_name != "Class FS" or "Class FS-1" not in row["text"])
    ]
    if code == "HK265HG":
        matches = [
            row for row in matches
            if (first_date == "2026-07-24" and row["date"] < "2026-09-01")
            or (first_date == "2026-09-16" and row["date"] >= "2026-09-01")
        ]
    assert len(matches) == count, (code, class_name, first_date, len(matches))
    assert min(row["date"] for row in matches) == first_date
    assert_status(matches, "confirmed", f"{code} {class_name} {first_date}")

# Compact calendar cards must expose every assessment note in red, not only the full text.
assessment_cards = [
    ("2026-08-07", "HK265HG · FS · JUL 2026", "Lesson 10", "Written Test"),
    ("2026-08-12", "HK265HG · FS · JUL 2026", "Lesson 11", "Group Presentation"),
    ("2026-08-12", "HK265HG · FS · JUL 2026", "Lesson 12", "Final Practical Exam"),
    ("2026-08-21", "HK239HG · FS", "Lesson 5", "小組討論及專題報告"),
    ("2026-08-21", "HK239HG · FS", "Lesson 6", "期末筆試"),
    ("2026-09-03", "HK239HG · CW10", "Lesson 5", "小組討論及專題報告"),
    ("2026-09-07", "HK239HG · CW10", "Lesson 6", "期末筆試"),
    ("2026-09-02", "HK244HG · CW8", "Lesson 8", "持續評估小組匯報"),
    ("2026-09-07", "HK244HG · CW8", "Lesson 11", "持續筆試"),
    ("2026-09-08", "HK244HG · CW8", "Lesson 12", "期末實務試"),
    ("2026-10-08", "HK265HG · FS · SEP 2026", "Lesson 10", "Written Test"),
    ("2026-10-12", "HK265HG · FS · SEP 2026", "Lesson 11", "Group Presentation"),
    ("2026-10-14", "HK265HG · FS · SEP 2026", "Lesson 12", "Final Practical Exam"),
    ("2026-10-14", "HK239HG · SS", "Lesson 5", "小組討論及專題報告"),
    ("2026-10-21", "HK239HG · SS", "Lesson 6", "期末筆試"),
    ("2026-10-05", "HK244EG · CW", "Lesson 16", "持續評估小組匯報"),
    ("2026-10-07", "HK244EG · CW", "Lesson 17", "持續筆試"),
    ("2026-10-08", "HK244EG · CW", "Lesson 18", "期末實務試"),
    ("2026-10-29", "HK244EG · FS", "Lesson 16", "小組匯報"),
    ("2026-11-02", "HK244EG · FS", "Lesson 17", "持續筆試"),
    ("2026-11-03", "HK244EG · FS", "Lesson 18", "期末實務試"),
    ("2026-11-13", "HK239HG · 城巿一條龍", "Lesson 5", "Group Discussion"),
    ("2026-11-13", "HK239HG · 城巿一條龍", "Lesson 6", "Final Exam"),
    ("2026-10-31", "HK239HG · ST", "Lesson 5", "小組討論及專題報告"),
    ("2026-11-07", "HK239HG · ST", "Lesson 6", "期末筆試"),
    ("2026-11-27", "HK239HG · LT", "Lesson 5", "小組討論及專題報告"),
    ("2026-11-30", "HK239HG · LT", "Lesson 6", "期末筆試"),
]
for date, group_label, lesson_label, note in assessment_cards:
    openings = list(re.finditer(
        rf'<div class="chip [^"]*"[^>]*data-date="{re.escape(date)}"[^>]*'
        rf'data-group-label="{re.escape(group_label)}"[^>]*>',
        index,
    ))
    assert openings, (date, group_label, "card missing")
    matching_cards = []
    for opening in openings:
        card_start = opening.start()
        card_end = index.find('<div class="chip ', opening.end())
        if card_end < 0:
            card_end = min(len(index), card_start + 6000)
        card = index[card_start:card_end]
        if lesson_label in card:
            matching_cards.append(card)
    assert matching_cards, (date, group_label, lesson_label)
    assert any(
        re.search(
            rf'<span class="card-note">\[[^\]]*{re.escape(note)}[^\]]*\]</span>',
            card,
        )
        for card in matching_cards
    ), (date, group_label, note)
assert '.card-note{color:#d60000' in index
print("source ledger verification passed")
print(f"events={len(EVENTS)} context={len(CONTEXT)} display={len(ALL)}")
