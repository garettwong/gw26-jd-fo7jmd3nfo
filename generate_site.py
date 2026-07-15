from openpyxl import load_workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from pathlib import Path
import calendar, datetime, html, json, re, sys, zlib

try:
    sys.stdout.reconfigure(encoding="utf-8")
except (AttributeError, OSError):
    pass

SRC = Path(r"C:/Users/garet/OneDrive/桌面/Timetable/ERB Super Timetable 04_checking 11_20260715_V07_HK239HGCW10_REDO.xlsx")
OUTDIR = Path(r"D:/Claude Code/ERB Super Timetable/erb-super-timetable")
OUTDIR.mkdir(parents=True, exist_ok=True)
MONTH_SHEETS = ["June", "July New", "August New", "September New", "October New", "November New", "December New"]
YEAR = 2026
BUILD_ID = "hk239hg-cw10-additional-alternatives-20260716-v07b"
CONTEXT_SRC = OUTDIR / "class_context.json"
OVERRIDES_SRC = OUTDIR / "schedule_overrides.json"
COMPARE_BASELINE = OUTDIR / "versions" / "2026-07-15-V07a"
COMPARE_LABEL = "V07b"
COMPARE_BASELINE_LABEL = "V07a"
EXPECTED_COMPARISON_CHANGES = 8

wb = load_workbook(SRC, data_only=False, rich_text=True)
GROUPS = [
    (0, [3,4], 3, "Sunday"),
    (1, [5,6], 6, "Monday"),
    (2, [8,9], 9, "Tuesday"),
    (3, [11,12], 12, "Wednesday"),
    (4, [14,15], 15, "Thursday"),
    (5, [17,18], 18, "Friday"),
    (6, [20,21], 21, "Saturday"),
]
DAY_ROWS = [6,11,16,21,26,31]
MONTH_MAP = {"June":6, "July New":7, "August New":8, "September New":9, "October New":10, "November New":11, "December New":12}

def raw_text(v):
    if v is None:
        return ""
    if isinstance(v, CellRichText):
        return "".join(str(part.text if isinstance(part, TextBlock) else part) for part in v)
    return str(v)

def norm_text(v):
    s = raw_text(v).replace("\r", "\n")
    s = re.sub(r"\n+", " / ", s)
    s = re.sub(r"\s+", " ", s).strip()
    return s

def color_rgb(font):
    col = getattr(font, "color", None)
    if not col:
        return ""
    try:
        if col.type == "rgb" and col.rgb:
            return str(col.rgb).upper()
    except Exception:
        pass
    return ""

def is_red_font(font):
    rgb = color_rgb(font)
    return bool(rgb and rgb.endswith("FF0000"))

def cell_text_runs(cell):
    value = cell.value
    whole_red = is_red_font(cell.font)
    runs = []
    if isinstance(value, CellRichText):
        for part in value:
            if isinstance(part, TextBlock):
                txt = str(part.text)
                red = whole_red or is_red_font(part.font)
            else:
                txt = str(part)
                red = whole_red
            if txt:
                runs.append((txt, red))
    else:
        txt = raw_text(value)
        if txt:
            runs.append((txt, whole_red))
    return normalize_runs(runs)

def normalize_runs(runs):
    out = []
    for txt, red in runs:
        txt = str(txt).replace("\r", "\n")
        txt = re.sub(r"\n+", " / ", txt)
        txt = re.sub(r"\s+", " ", txt)
        if not txt:
            continue
        if out and not out[-1][0].endswith((" ", "/")) and not txt.startswith((" ", "/")):
            out.append((" ", False))
        out.append((txt, red))
    while out and not out[0][0].strip():
        out.pop(0)
    while out and not out[-1][0].strip():
        out.pop()
    if out:
        first_txt, first_red = out[0]
        out[0] = (first_txt.lstrip(), first_red)
        last_txt, last_red = out[-1]
        out[-1] = (last_txt.rstrip(), last_red)
    merged = []
    for txt, red in out:
        if not txt:
            continue
        if merged and merged[-1][1] == red:
            merged[-1] = (merged[-1][0] + txt, red)
        else:
            merged.append((txt, red))
    return merged

def runs_plain(runs):
    return "".join(txt for txt, _ in runs)

def split_runs(runs):
    before, after = [], []
    found = False
    for txt, red in runs:
        if found:
            after.append((txt, red))
            continue
        idx = txt.find(" / ")
        if idx >= 0:
            if txt[:idx].strip():
                before.append((txt[:idx].rstrip(), red))
            rem = txt[idx+3:].lstrip()
            if rem:
                after.append((rem, red))
            found = True
        else:
            before.append((txt, red))
    if not before:
        before = runs[:]
    return before, after

def runs_html(runs):
    bits = []
    for txt, red in runs:
        esc = html.escape(str(txt), quote=True)
        if red:
            bits.append(f'<span class="xl-red">{esc}</span>')
        else:
            bits.append(esc)
    return "".join(bits)

def border_status(cell):
    sides = [getattr(cell.border, edge, None) for edge in ("top", "right", "bottom", "left")]
    styles = [getattr(side, "style", None) for side in sides]
    styles = [s for s in styles if s]
    if not styles:
        return "note"
    dashed = sum("dash" in str(style).lower() for style in styles)
    solid = len(styles) - dashed
    if dashed >= solid:
        return "unconfirmed"
    return "confirmed"

def fill_rgb(cell):
    try:
        fg = cell.fill.fgColor
        if fg.type == "rgb" and fg.rgb:
            return fg.rgb
    except Exception:
        pass
    return ""

def group_for_col(col):
    for idx, cols, day_col, name in GROUPS:
        if col in cols:
            return idx, day_col, name
    return None

def date_for(ws, row, col, month):
    g = group_for_col(col)
    if not g:
        return None
    idx, day_col, name = g
    day_row = max([r for r in DAY_ROWS if r <= row], default=None)
    if day_row is None:
        return None
    day_val = ws.cell(day_row, day_col).value
    if day_val in (None, ""):
        for c in GROUPS[idx][1]:
            v = ws.cell(day_row, c).value
            if isinstance(v, (int, float)) or (isinstance(v, str) and v.strip().isdigit()):
                day_val = v
                break
    if day_val in (None, ""):
        return None
    try:
        day = int(float(day_val))
        return datetime.date(YEAR, month, day)
    except Exception:
        return None

def category(text):
    if "Public Holiday" in text or "假期" in text:
        return "holiday", "Holiday"
    if "YMCA" in text:
        return "ymca", "YMCA SEN"
    if "DGS" in text or "Unreal" in text:
        return "dgs", "DGS / UE"
    if "循道" in text or "MC0106" in text:
        return "methodist", "循道"
    if "勵行" in text or "HK244" in text or "HK239" in text or "HK265" in text or "HK280" in text or "HK281" in text:
        return "erb", "勵行 / ERB"
    if "Mike" in text:
        return "mike", "Mike Sir"
    if "佛教" in text or "Canva" in text:
        return "school", "School"
    return "other", "Other"

def slash_parts(text):
    parts = []
    current = []
    depth = 0
    for char in str(text or ""):
        if char in "([":
            depth += 1
        elif char in ")]" and depth:
            depth -= 1
        if char == "/" and depth == 0:
            value = "".join(current).strip()
            if value:
                parts.append(value)
            current = []
        else:
            current.append(char)
    value = "".join(current).strip()
    if value:
        parts.append(value)
    return parts


def split_title(text):
    parts = slash_parts(text)
    if not parts:
        return text, ""
    return parts[0], " / ".join(parts[1:])

COURSE_CODE_RE = re.compile(r"(?<![A-Z0-9])(?:HK\d+[A-Z]+|MC\d+[A-Z]+|PFSA\d+|QAT\d+|DGS)(?![A-Z0-9])", re.I)
CLASS_RE = re.compile(r"(?<![A-Z0-9])Class\s+([^,/()]+)", re.I)
CODE_PAREN_CLASS_RE = re.compile(r"(?<![A-Z0-9])(?:HK\d+[A-Z]+|MC\d+[A-Z]+|PFSA\d+|QAT\d+)\s*\(([^)]+)\)", re.I)
NAMED_CLASS_RE = re.compile(r"\(([^()]*班)\)", re.I)
LESSON_RE = re.compile(r"(?:^|[\s/\-])L\s*(\d+)(?!\d)", re.I)
TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:：]?([0-5]\d)\s*(am|pm)?\s*(?:-|–|至|to)", re.I)
TIMEISH_RE = re.compile(r"\d{1,2}\s*:?\s*\d{2}|\d{3,4}\s*-|[-–]\s*\d{3,4}")
NAME_WORDS = {"GARETT", "GARRETT", "ANDY", "CALVIN", "MIKE"}


def natural_key(value):
    value = str(value or "").strip().upper()
    parts = re.split(r"(\d+)", value)
    return tuple(int(p) if p.isdigit() else p for p in parts if p != "")


def clean_class(value):
    value = re.sub(r"\s+", " ", str(value or "").strip())
    value = re.sub(r"\s*-\s*L\s*\d+(?!\d).*$", "", value, flags=re.I).strip()
    return value


def parenthetical_class(text):
    text = str(text or "")
    m = CODE_PAREN_CLASS_RE.search(text)
    if not m:
        m = NAMED_CLASS_RE.search(text)
    if not m:
        return ""
    value = clean_class(m.group(1))
    upper = value.upper()
    if not value or upper in NAME_WORDS or TIMEISH_RE.search(value) or len(value) > 12:
        return ""
    return value


def course_sort_parts(text):
    text = str(text or "")
    code_m = COURSE_CODE_RE.search(text)
    code = code_m.group(0).upper() if code_m else ""
    cls = ""
    cls_m = CLASS_RE.search(text)
    if cls_m:
        cls = clean_class(cls_m.group(1))
    if not cls:
        cls = parenthetical_class(text)
    lesson_m = LESSON_RE.search(text)
    lesson = int(lesson_m.group(1)) if lesson_m else 999
    time_m = TIME_RE.search(text)
    if time_m:
        hour = int(time_m.group(1))
        minute = int(time_m.group(2))
        marker = (time_m.group(3) or "").lower()
        if marker == "pm" and hour < 12:
            hour += 12
        elif marker == "am" and hour == 12:
            hour = 0
        start = hour * 60 + minute
    else:
        start = 9999
    return code, cls.upper(), lesson, start


def course_group_label(text, category_label):
    text = str(text or "")
    code, cls, _lesson, _start = course_sort_parts(text)
    if code and not cls:
        cls = INFERRED_CLASS_BY_CODE.get(code, "")
    if code:
        return f"{code} · {cls}" if cls else code
    if "Mike Sir" in text:
        return "Mike Sir"
    return category_label or "Other"


def event_sort_key(ev):
    code, cls, lesson, start = course_sort_parts(ev.get("text", ""))
    return (start, 0 if code else 1, natural_key(code), natural_key(cls), lesson, ev.get("row", 999), ev.get("col", 999), ev.get("text", ""))


events = []
context_events = []
by_date = {}
INFERRED_CLASS_BY_CODE = {}

for sheet in MONTH_SHEETS:
    ws = wb[sheet]
    month = MONTH_MAP[sheet]
    seen = set()
    for row in range(1, ws.max_row + 1):
        for col in range(1, ws.max_column + 1):
            cell = ws.cell(row, col)
            text_runs = cell_text_runs(cell)
            text = runs_plain(text_runs)
            if not text:
                continue
            if row in (1,2,3,4,5):
                continue
            if row in DAY_ROWS and text.isdigit():
                continue
            dt = date_for(ws, row, col, month)
            if not dt:
                continue
            key = (dt.isoformat(), row, text)
            if key in seen:
                continue
            seen.add(key)
            status = border_status(cell)
            cat, cat_label = category(text)
            title_runs, detail_runs = split_runs(text_runs)
            title, detail = runs_plain(title_runs), runs_plain(detail_runs)
            ev = {
                "date": dt.isoformat(), "month": sheet, "row": row, "col": col, "cell": cell.coordinate,
                "text": text, "title": title, "detail": detail, "status": status, "fill": fill_rgb(cell),
                "category": cat, "category_label": cat_label,
                "html": runs_html(text_runs), "title_html": runs_html(title_runs), "detail_html": runs_html(detail_runs),
                "red": any(red for _, red in text_runs),
            }
            events.append(ev)
            by_date.setdefault(dt.isoformat(), []).append(ev)

override_revision = ""
override_confirmation = ""
if OVERRIDES_SRC.exists():
    override_data = json.loads(OVERRIDES_SRC.read_text(encoding="utf-8"))
    override_revision = str(override_data.get("revision", ""))
    override_confirmation = str(override_data.get("confirmation", ""))
    override_default_status = override_data.get("default_status")
    if override_default_status not in {None, "confirmed", "unconfirmed", "note"}:
        raise ValueError(f"Invalid override default status: {override_default_status}")
    override_index = {}
    for event in events:
        code, cls, lesson, _start = course_sort_parts(event["text"])
        if code and cls:
            key = (event["date"], code.upper(), cls.upper(), lesson)
            if key in override_index:
                raise ValueError(f"Duplicate workbook override target: {key}")
            override_index[key] = event

    for index, item in enumerate(override_data.get("overrides", []), 1):
        match_lesson = item.get("match_lesson", item.get("lesson"))
        key = (
            item["date"],
            str(item.get("match_course_code", item["course_code"])).upper(),
            str(item.get("match_class", item["class"])).upper(),
            999 if match_lesson is None else int(match_lesson),
        )
        event = override_index.get(key)
        if event is None:
            raise ValueError(f"Override entry {index} has no workbook lesson: {key}")
        text = norm_text(item["text"])
        code, cls, lesson, _start = course_sort_parts(text)
        output_lesson = item.get("lesson")
        output_key = (
            item["date"],
            str(item["course_code"]).upper(),
            str(item["class"]).upper(),
            999 if output_lesson is None else int(output_lesson),
        )
        if (event["date"], code.upper(), cls.upper(), lesson) != output_key:
            raise ValueError(f"Override entry {index} text does not match its output key: {output_key}")
        title, detail = split_title(text)
        cat, cat_label = category(text)
        status = item.get("status", override_default_status or event["status"])
        if status not in {"confirmed", "unconfirmed", "note"}:
            raise ValueError(f"Override entry {index} has invalid status: {status}")
        event.update({
            "text": text,
            "title": title,
            "detail": detail,
            "category": cat,
            "category_label": cat_label,
            "html": html.escape(text, quote=True),
            "title_html": html.escape(title, quote=True),
            "detail_html": html.escape(detail, quote=True),
            "red": False,
            "status": status,
            "teacher": item.get("teacher", ""),
            "source": item.get("source", ""),
        })

if CONTEXT_SRC.exists():
    raw_context = json.loads(CONTEXT_SRC.read_text(encoding="utf-8"))
    baseline_keys = {
        (event["date"],) + course_sort_parts(event["text"])[:3]
        for event in events
    }
    for index, item in enumerate(raw_context, 1):
        dt = datetime.date.fromisoformat(item["date"])
        text = norm_text(item["text"])
        cat, cat_label = category(text)
        if cat not in {"erb", "methodist"}:
            raise ValueError(f"Context entry {index} must be an ERB or Methodist lesson")
        key = (dt.isoformat(),) + course_sort_parts(text)[:3]
        if key in baseline_keys:
            raise ValueError(f"Context entry {index} duplicates a workbook lesson: {key}")
        title, detail = split_title(text)
        layer = item.get("layer", "class")
        if layer not in {"mine", "class"}:
            raise ValueError(f"Context entry {index} has invalid layer: {layer}")
        ev = {
            "date": dt.isoformat(), "month": calendar.month_name[dt.month], "row": 999, "col": 999,
            "cell": f"context-{index}", "text": text, "title": title, "detail": detail,
            "status": item.get("status", "unconfirmed"), "fill": "", "category": cat,
            "category_label": cat_label, "html": html.escape(text, quote=True),
            "title_html": html.escape(title, quote=True), "detail_html": html.escape(detail, quote=True),
            "red": bool(item.get("red", False)), "layer": layer,
            "teacher": item.get("teacher", "Other tutor / TBC"), "source": item.get("source", ""),
        }
        context_events.append(ev)
        by_date.setdefault(dt.isoformat(), []).append(ev)

display_events = events + context_events

baseline_events = json.loads((COMPARE_BASELINE / "events.json").read_text(encoding="utf-8"))
baseline_context = json.loads((COMPARE_BASELINE / "class_context.json").read_text(encoding="utf-8"))

def workbook_identity(item):
    return tuple(item.get(key) for key in ("date", "month", "row", "col", "cell"))

def context_identity(item):
    return item.get("date"), item.get("source", "")

baseline_event_map = {workbook_identity(item): item for item in baseline_events}
baseline_context_map = {context_identity(item): item for item in baseline_context}

for current in events:
    previous = baseline_event_map.get(workbook_identity(current))
    changed = previous is None or any(current.get(key) != previous.get(key) for key in ("text", "status"))
    current["changed_in_version"] = changed
    current["change_kind"] = "new" if previous is None else "changed" if changed else ""
    current["previous_text"] = previous.get("text", "") if previous else ""
    current["previous_status"] = previous.get("status", "") if previous else ""

for current in context_events:
    previous = baseline_context_map.get(context_identity(current))
    changed = previous is None or any(current.get(key) != previous.get(key) for key in ("text", "status", "teacher"))
    current["changed_in_version"] = changed
    current["change_kind"] = "new" if previous is None else "changed" if changed else ""
    current["previous_text"] = previous.get("text", "") if previous else ""
    current["previous_status"] = previous.get("status", "") if previous else ""

changed_events = [event for event in display_events if event.get("changed_in_version")]
if len(changed_events) != EXPECTED_COMPARISON_CHANGES:
    raise ValueError(
        f"Expected {EXPECTED_COMPARISON_CHANGES} changes in {COMPARE_LABEL}, found {len(changed_events)}"
    )

comparison_legend_html = (
    f'<div class="legend-card"><span class="sample changed-sample"></span> Changed in {COMPARE_LABEL}</div>'
    if changed_events else ""
)
comparison_filter_html = (
    f'<button class="filter course-filter change-filter" data-filter="changed" '
    f'data-first-date="{min(event["date"] for event in changed_events)}">'
    f'Changed in {COMPARE_LABEL} ({len(changed_events)})</button>'
    if changed_events else ""
)

for ds in by_date:
    by_date[ds].sort(key=event_sort_key)

classes_by_code = {}
for event in display_events:
    code, cls, _lesson, _start = course_sort_parts(event["text"])
    if code and cls:
        classes_by_code.setdefault(code, set()).add(cls)
INFERRED_CLASS_BY_CODE = {
    code: next(iter(classes))
    for code, classes in classes_by_code.items()
    if len(classes) == 1
}

_group_labels = sorted({course_group_label(e["text"], e["category_label"]) for e in display_events}, key=lambda label: (0 if COURSE_CODE_RE.fullmatch(label.split(" · ", 1)[0]) or label == "DGS" else 1, natural_key(label.split(" · ", 1)[0]), natural_key(label.split(" · ", 1)[1] if " · " in label else ""), label))
_group_slugs = {label: f"g{i:02d}" for i, label in enumerate(_group_labels, 1)}
for ev in display_events:
    ev["group_label"] = course_group_label(ev["text"], ev["category_label"])
    ev["group"] = _group_slugs[ev["group_label"]]

def ehtml(s):
    return html.escape(str(s or ""), quote=True)

GROUPS = []
for label in _group_labels:
    slug = _group_slugs[label]
    group_events = [e for e in display_events if e["group"] == slug]
    statuses = {e["status"] for e in group_events}
    if statuses == {"confirmed"}:
        group_status = "confirmed"
    elif statuses == {"unconfirmed"}:
        group_status = "unconfirmed"
    elif statuses == {"note"}:
        group_status = "note"
    else:
        group_status = "mixed"
    first_date = min(e["date"] for e in group_events)
    GROUPS.append((label, slug, group_status, first_date))

CSS = r'''
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}body{margin:0;font-family:"Segoe UI Variable","Segoe UI",-apple-system,BlinkMacSystemFont,Roboto,"Noto Sans TC","Microsoft JhengHei",Arial,sans-serif;background:#eef1f6;color:#1d2734;line-height:1.42}.xl-red{color:#d60000;font-weight:700}.chip .xl-red{color:#d60000}.modal-body .xl-red{color:#d60000;font-weight:750}.wrap{max-width:1280px;margin:0 auto;padding:28px 16px 70px}.hero{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.title{font-size:30px;font-weight:850;letter-spacing:-.45px;margin:0}.title .y{color:#0f7d7d}.sub{color:#64707f;margin:6px 0 0;font-size:14px}.actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.btn{border:1px solid #d8e0ea;background:#fff;color:#344153;border-radius:10px;padding:8px 12px;font-weight:750;font-size:13px;text-decoration:none;box-shadow:0 1px 2px rgba(20,30,50,.05)}.btn:hover{border-color:#8bb8bd}.stats,.legend{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 6px}.stat,.legend-card{background:#fff;border:1px solid #e2e7ef;border-radius:12px;padding:8px 13px;font-size:13px;color:#46505e;box-shadow:0 1px 2px rgba(20,30,50,.05)}.stat b{color:#1d2734;font-size:15px}.legend-card{display:flex;align-items:center;gap:8px}.sample{width:28px;height:18px;border-radius:6px;background:#f9fcff}.sample.confirmed{border:3px solid #1d2734}.sample.unconfirmed{border:3px dashed #1d2734}.sample.note{border:2px solid #b8c1ce}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.filter{border:2px solid #dbe3ed;background:#fff;border-radius:999px;padding:7px 11px;font-weight:750;font-size:12px;color:#4c5a6b;cursor:pointer}.filter.confirmed{border:3px solid #1d2734}.filter.unconfirmed{border:3px dashed #1d2734}.filter.mixed{border:3px dashed #1d2734;box-shadow:inset 0 0 0 2px rgba(29,39,52,.18),0 1px 2px rgba(20,30,50,.05)}.filter.note{border:2px solid #b8c1ce;color:#69737f}.filter.active{background:#0f7d7d;color:#fff;border-color:#1d2734}.filter.active.confirmed{border-style:solid}.filter.active.unconfirmed,.filter.active.mixed{border-style:dashed}.filter.active.note{border-color:#b8c1ce}.section-h{font-size:13px;text-transform:uppercase;letter-spacing:.8px;color:#8a94a2;font-weight:800;margin:24px 2px 10px}.month{background:#fff;border:1px solid #e2e7ef;border-radius:16px;padding:16px;margin-top:18px;box-shadow:0 1px 3px rgba(20,30,50,.06)}.month h2{margin:0 0 12px;font-size:20px;font-weight:850;letter-spacing:-.2px}.gridwrap{overflow-x:auto}.grid{display:grid;grid-template-columns:repeat(7,minmax(124px,1fr));gap:7px;min-width:868px}.dow{font-size:11.5px;font-weight:800;color:#98a2af;text-align:center;padding:2px 0;text-transform:uppercase;letter-spacing:.5px}.cell{min-height:132px;border:1px solid #e8ecf3;border-radius:10px;padding:6px;background:#fcfdff;display:flex;flex-direction:column;gap:4px}.cell.out{background:#f4f6f9;border-style:dashed;opacity:.5}.cell.wknd{background:#f7f9fc}.cell.today{outline:3px solid #0f7d7d;outline-offset:1px}.dnum{font-size:12px;font-weight:850;color:#9aa4b1}.cell.has .dnum{color:#2d3948}.dnum{display:flex;align-items:baseline;gap:3px;white-space:nowrap}.dnum .dmon{font-size:13px;font-weight:900;color:#667384;text-transform:uppercase}.dnum .dday{font-size:12px;font-weight:900;color:inherit}.dnum .dweekday{margin-left:auto;font-size:10.5px;font-weight:850;color:#8792a0;text-transform:uppercase}.chip{border-radius:8px;padding:5px 7px 6px;background:#fff;box-shadow:0 1px 1px rgba(20,30,50,.04);cursor:pointer;overflow:visible}.chip.confirmed{border-style:solid!important;border-width:2.5px!important;border-color:#1d2734!important;box-shadow:0 0 0 1px rgba(29,39,52,.10) inset,0 1px 1px rgba(20,30,50,.04)}.chip.unconfirmed{border-style:dashed!important;border-width:2.5px!important;border-color:#1d2734!important;box-shadow:0 0 0 1px rgba(29,39,52,.10) inset,0 1px 1px rgba(20,30,50,.04)}.chip.note{border-style:solid!important;border-width:1.5px!important;border-color:#9aa4b2!important;background:#f8fafc}.chip .top{display:flex;justify-content:space-between;gap:6px;align-items:flex-start}.chip .cat{font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.35px;opacity:.82}.chip .status{font-size:9.5px;font-weight:850;white-space:nowrap}.class-id{display:inline-flex;align-items:center;align-self:flex-start;gap:4px;max-width:100%;margin-top:3px;padding:2px 5px;border:1.5px solid hsl(var(--class-hue),72%,14%);border-radius:4px;background:hsl(var(--class-hue),72%,22%);color:#fff;font-size:9.3px;font-weight:900;line-height:1.15;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;box-shadow:0 1px 1px rgba(12,18,28,.22)}.class-dot{width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:#fff;box-shadow:0 0 0 1px rgba(255,255,255,.45)}.chip .ttl{font-size:11.5px;font-weight:850;margin-top:2px;color:#172232;line-height:1.22}.chip .det{font-size:10.2px;color:#596676;margin-top:2px;line-height:1.22;display:block;white-space:normal;overflow:visible}.chip .fulltxt{display:none}.cat-ymca{background:#e3f7fa}.cat-erb{background:#fff1e6}.cat-methodist{background:#eef0ff}.cat-dgs{background:#ecfdf3}.cat-holiday{background:#f3f4f6}.cat-mike{background:#fff8db}.cat-school{background:#fce7f3}.cat-other{background:#f6f7fb}.agenda{display:none}.aday{display:flex;gap:10px;align-items:flex-start;padding:9px 2px;border-top:1px solid #eef1f6}.aday.empty-day{display:none}.aday:first-child{border-top:none}.adate{flex:0 0 48px;text-align:center}.adate .adow{display:block;font-size:11px;font-weight:800;color:#98a2af;text-transform:uppercase}.adate .amon{display:block;font-size:10px;font-weight:900;color:#0f7d7d;text-transform:uppercase;letter-spacing:.05em;line-height:1}.adate .anum{display:block;font-size:20px;font-weight:850;color:#3a4452;line-height:1.05}.achips{flex:1;min-width:0;display:flex;flex-direction:column;gap:6px}.foot{margin-top:28px;color:#7a8492;font-size:12.5px;border-top:1px solid #e2e7ef;padding-top:14px}.modal{position:fixed;inset:0;background:rgba(18,26,38,.56);display:flex;align-items:center;justify-content:center;padding:18px;z-index:50}.modal[hidden]{display:none}.modal-card{background:#fff;border-radius:16px;max-width:560px;width:100%;padding:20px 20px 22px;box-shadow:0 14px 44px rgba(15,25,45,.32);position:relative;max-height:88vh;overflow:auto}.modal-x{position:absolute;top:8px;right:12px;border:none;background:transparent;font-size:26px;line-height:1;color:#98a2af;cursor:pointer}.modal-h{font-size:20px;font-weight:850;padding-right:24px}.modal-date{color:#69737f;font-size:13px;margin-top:2px}.modal-body{white-space:pre-wrap;margin-top:14px;font-size:15px}.pill{display:inline-block;border-radius:999px;padding:4px 9px;font-size:12px;font-weight:850;margin-top:10px;margin-right:6px}.pill.confirmed{background:#e7f6ee;color:#16623d}.pill.unconfirmed{background:#fff3df;color:#a25600}.pill.note{background:#eef2f7;color:#596676}@media (max-width:820px){.wrap{padding:14px 10px 48px}.hero{display:block}.title{font-size:22px}.sub{font-size:13px}.actions{justify-content:flex-start;margin-top:10px}.month{padding:12px 10px 14px}.month h2{font-size:17px}.stats,.legend{gap:7px}.stat,.legend-card{font-size:12px;padding:7px 10px}}@media (orientation:portrait) and (max-width:820px){.gridwrap{display:none}.agenda{display:block}.aday{scroll-margin-top:18px}.aday.today{background:linear-gradient(90deg,rgba(15,125,125,.10),transparent);border-radius:14px}}@media (orientation:landscape) and (max-height:540px){.sub,.stats,.legend,.filters,.foot{display:none}.month{padding:8px;margin-top:10px}.month h2{font-size:15px;margin:0 0 6px}.gridwrap{overflow:visible}.grid{min-width:0;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px}.dow{font-size:8.5px;letter-spacing:0;padding:0;text-transform:uppercase}.cell{min-height:98px;height:auto;padding:2px;border-radius:5px;overflow:visible}.dnum{font-size:8.5px;gap:2px}.dnum .dmon{font-size:9px}.dnum .dday{font-size:8.5px}.dnum .dweekday{font-size:6.8px}.chip{padding:2px 3px 3px;border-radius:4px;overflow:visible}.chip.confirmed{border-width:1.8px!important}.chip.unconfirmed{border-width:1.8px!important}.chip.note{border-width:1.3px!important}.chip .top{margin-bottom:1px}.chip .cat,.chip .status{font-size:5.8px;font-weight:550;letter-spacing:0}.class-id{margin-top:1px;padding:1px 2px;gap:2px;font-size:5.8px;border-radius:2px}.class-dot{width:4px;height:4px;flex-basis:4px}.chip .ttl,.chip .det{display:none}.chip .fulltxt{display:block;font-size:6.6px;font-weight:400;line-height:1.14;color:#172232;white-space:normal;overflow:visible;word-break:break-word;overflow-wrap:anywhere}}@media print{body{background:#fff}.month,.stat,.legend-card{box-shadow:none}.actions,.filters{display:none}.gridwrap{overflow:visible}.grid{min-width:0}.chip{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
'''

CSS += r'''
.foot{overflow-wrap:anywhere}
@media (min-width:821px){.wrap{width:100%;max-width:none;margin:0;padding:28px clamp(16px,1.6vw,36px) 70px}}
.title,.month h2{letter-spacing:0}
.layer-controls{margin:16px 0 2px}.layer-controls .section-h{margin:0 0 8px}.layer-switch{display:inline-grid;grid-template-columns:repeat(3,minmax(104px,1fr));padding:3px;border:1px solid #cfd8e5;border-radius:8px;background:#e5eaf1;box-shadow:0 1px 2px rgba(20,30,50,.06)}.mode-filter{min-height:34px;border:0;border-radius:6px;padding:6px 11px;background:transparent;color:#4c5a6b;font:inherit;font-size:12px;font-weight:800;cursor:pointer}.mode-filter.active{background:#fff;color:#145f63;box-shadow:0 1px 3px rgba(20,30,50,.18)}.sample.class-layer{border:2px solid #8b80aa;background:#fff1e6;box-shadow:inset 4px 0 0 #a99bc7}.chip.layer-class.confirmed{box-shadow:inset 3px 0 0 #a99bc7,0 0 0 1px rgba(29,39,52,.10),0 1px 1px rgba(20,30,50,.04)}.chip.layer-class.unconfirmed{box-shadow:inset 3px 0 0 #a99bc7,0 0 0 1px rgba(29,39,52,.10),0 1px 1px rgba(20,30,50,.04)}.modal-source{margin-top:14px;padding-top:10px;border-top:1px solid #e4e9f0;color:#6c7786;font-size:12px}.pill.class-layer{background:#eeeaf7;color:#5d537a}
.chip.erb-compact{position:relative;display:grid;justify-items:center;gap:2px;padding:6px 7px 7px;text-align:center}
.chip.erb-compact .status{position:absolute;top:4px;right:6px;z-index:1}
.chip.erb-compact .class-id{display:inline-flex;align-items:center;align-self:center;justify-content:center;gap:4px;max-width:calc(100% - 24px);min-height:18px;margin:0;padding:2px 6px;border:2px solid hsl(var(--class-hue),72%,38%);border-radius:4px;background:#fff;color:hsl(var(--class-hue),72%,24%);font-size:9.3px;font-weight:900;line-height:1.1;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;box-shadow:0 1px 2px rgba(12,18,28,.12)}
.chip.erb-compact .class-dot{width:7px;height:7px;flex:0 0 7px;border-radius:50%;background:hsl(var(--class-hue),72%,38%);box-shadow:none}
.erb-meta,.erb-course,.erb-foot{width:100%;text-align:center;overflow-wrap:anywhere}
.erb-meta{font-size:10px;font-weight:850;line-height:1.15;color:#172232}
.erb-teacher{color:#0f6868}
.erb-teacher.is-alert{color:#d60000}
.erb-course{font-size:10.3px;font-weight:750;line-height:1.17;color:#263343}
.erb-foot{font-size:9.9px;font-weight:800;line-height:1.15;color:#4d5b6c;font-variant-numeric:tabular-nums}
.erb-sep{padding:0 3px;color:#8d97a4}
.card-note{color:#d60000;font-weight:850}
.chip.erb-compact .fulltxt{display:none!important}
@media (orientation:landscape) and (max-height:540px){.chip.erb-compact{gap:1px;padding:3px 4px 4px}.chip.erb-compact .class-id{min-height:10px;max-width:calc(100% - 14px);padding:1px 3px;font-size:6px;border-width:1.3px;border-radius:2px}.chip.erb-compact .class-dot{width:4px;height:4px;flex-basis:4px}.erb-meta,.erb-course,.erb-foot{font-size:6px;line-height:1.08}.chip.erb-compact .status{top:2px;right:3px;font-size:5.8px}}
@media (max-width:520px){.layer-switch{display:grid;width:100%;grid-template-columns:repeat(3,minmax(0,1fr))}.mode-filter{padding:6px 4px}}
@media (orientation:landscape) and (max-height:540px){.layer-controls{display:none}}
'''

CSS += r'''
.course-code-legend{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:8px;margin:0 0 8px}.code-key{display:grid;grid-template-columns:auto minmax(0,1fr);align-items:start;gap:9px;padding:8px 10px;border:1px solid #dbe2ec;border-left:5px solid #0f7d7d;border-radius:6px;background:#fff;color:#465364;font-size:12px;line-height:1.3}.code-key b{color:#1d2734;white-space:nowrap}.sample.class-layer{box-shadow:inset 8px 0 0 #8c78b5}.chip.layer-class{padding-left:14px}.chip.layer-class.confirmed{box-shadow:inset 8px 0 0 #8c78b5,0 0 0 1px rgba(29,39,52,.10),0 1px 1px rgba(20,30,50,.04)}.chip.layer-class.unconfirmed{box-shadow:inset 8px 0 0 #8c78b5,0 0 0 1px rgba(29,39,52,.10),0 1px 1px rgba(20,30,50,.04)}.chip.layer-class.note{box-shadow:inset 8px 0 0 #8c78b5,0 1px 1px rgba(20,30,50,.04)}.chip.erb-compact.layer-class{padding-left:14px}.context-teacher{font-weight:850;color:#6c568f}.overlap-group{position:relative;display:flex;flex-direction:column;gap:4px;min-width:0}.overlap-group.overlap-active{padding:3px 12px 3px 0}.overlap-group.overlap-active::after{content:"";position:absolute;top:1px;right:1px;bottom:1px;width:8px;border:2.5px solid #536170;border-left:0;border-radius:0 5px 5px 0;pointer-events:none}.overlap-group.overlap-active>.chip.layer-mine:first-child{outline:2px solid rgba(15,125,125,.20);outline-offset:1px}
@media (max-width:820px){.course-code-legend{grid-template-columns:1fr}.code-key{font-size:11.5px}.overlap-group.overlap-active{padding-right:13px}}
@media (orientation:landscape) and (max-height:540px){.course-code-legend{display:none}.chip.layer-class,.chip.erb-compact.layer-class{padding-left:7px}.chip.layer-class.confirmed,.chip.layer-class.unconfirmed,.chip.layer-class.note{box-shadow:inset 4px 0 0 #8c78b5,0 1px 1px rgba(20,30,50,.04)}.overlap-group{gap:2px}.overlap-group.overlap-active{padding:1px 6px 1px 0}.overlap-group.overlap-active::after{width:4px;border-width:1.4px}}
'''

CSS += r'''
.chip.layer-class{--context-color:#8c78b5}.chip.cat-erb.layer-class{--context-color:#d9772e}.chip.cat-methodist.layer-class{--context-color:#7567b9}.chip.cat-ymca.layer-class{--context-color:#238a99}.chip.cat-dgs.layer-class{--context-color:#31865c}.sample.class-layer{box-shadow:inset 7px 0 0 #d9772e,inset -7px 0 0 #7567b9}.chip.layer-class.confirmed{box-shadow:inset 8px 0 0 var(--context-color),0 0 0 1px rgba(29,39,52,.10),0 1px 1px rgba(20,30,50,.04)}.chip.layer-class.unconfirmed{box-shadow:inset 8px 0 0 var(--context-color),0 0 0 1px rgba(29,39,52,.10),0 1px 1px rgba(20,30,50,.04)}.chip.layer-class.note{box-shadow:inset 8px 0 0 var(--context-color),0 1px 1px rgba(20,30,50,.04)}.floating-mode-switch{position:fixed;z-index:40;left:clamp(58px,3.6vw,138px);bottom:24px;display:grid;grid-template-columns:repeat(3,48px);gap:3px;padding:4px;border:2px solid #fff;border-radius:12px;background:#dfe6ec;box-shadow:0 5px 18px rgba(25,38,55,.30);font-family:inherit}.mode-option,.today-option{width:48px;height:44px;border:0;border-radius:8px;background:#fff;color:#405064;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px;cursor:pointer;font-family:inherit}.mode-option:hover,.today-option:hover{background:#eef7f7}.mode-option:focus-visible,.today-option:focus-visible{outline:3px solid #ffc857;outline-offset:1px}.mode-option.active{background:#0f7074;color:#fff}.today-option{color:#0f7074}.today-option .mode-main{font-size:8px}.mode-main{font-size:12px;font-weight:900;line-height:1}.mode-sub{font-size:7px;font-weight:850;line-height:1;text-transform:uppercase}.grid .holiday-cell{background:#f1f3f6}.grid .holiday-cell .chip.cat-holiday{position:relative;flex:1;min-height:92px;display:flex;flex-direction:column;align-items:center;justify-content:center;text-align:center;border-radius:7px}.grid .holiday-cell .chip.cat-holiday .top{position:absolute;top:7px;left:8px;right:8px;width:auto}.grid .holiday-cell .chip.cat-holiday .ttl{font-size:14px;margin:0}.grid .holiday-cell .chip.cat-holiday .det{display:none}
@media (max-width:820px){.floating-mode-switch{left:14px;right:auto;bottom:14px;grid-template-columns:repeat(3,42px)}.mode-option,.today-option{width:42px;height:42px}.mode-main{font-size:10px}.today-option .mode-main{font-size:7px}}
@media (min-width:821px) and (max-width:1400px){.floating-mode-switch{left:32px;grid-template-columns:repeat(3,36px)}.mode-option,.today-option{width:36px;height:34px}.mode-main{font-size:9px}.mode-sub{font-size:5.5px}.today-option .mode-main{font-size:7px}}
@media (orientation:landscape) and (max-height:540px){.chip.layer-class.confirmed,.chip.layer-class.unconfirmed,.chip.layer-class.note{box-shadow:inset 4px 0 0 var(--context-color),0 1px 1px rgba(20,30,50,.04)}.floating-mode-switch{left:clamp(42px,3vw,112px);bottom:8px;grid-template-columns:repeat(3,34px);gap:2px;padding:3px}.mode-option,.today-option{width:34px;height:32px;border-radius:6px}.mode-main{font-size:8px}.today-option .mode-main{font-size:6px}.mode-sub{font-size:5px}.grid .holiday-cell .chip.cat-holiday{min-height:58px}.grid .holiday-cell .chip.cat-holiday .ttl{display:block;font-size:7px}}
@media print{.floating-mode-switch{display:none}}
.filter-jump-target{scroll-margin-top:12px}.top-option,.version-option{width:48px;height:44px;border:0;border-radius:8px;background:#fff;color:#0f7074;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:1px;cursor:pointer;font-family:inherit}.top-option:hover,.version-option:hover{background:#eef7f7}.top-option:focus-visible,.version-option:focus-visible{outline:3px solid #ffc857;outline-offset:1px}.top-option .mode-main,.version-option .mode-main{font-size:18px;line-height:.85}.top-option .mode-sub,.version-option .mode-sub{font-size:7px;font-weight:850;line-height:1}@media (max-width:820px){.top-option,.version-option{width:42px;height:42px}}@media (min-width:821px) and (max-width:1400px){.top-option,.version-option{width:36px;height:34px}.top-option .mode-main,.version-option .mode-main{font-size:13px}.top-option .mode-sub,.version-option .mode-sub{font-size:5.5px}}@media (orientation:landscape) and (max-height:540px){.top-option,.version-option{width:34px;height:32px;border-radius:6px}.top-option .mode-main,.version-option .mode-main{font-size:12px}.top-option .mode-sub,.version-option .mode-sub{font-size:5px}}
'''

CSS += r'''
.chip.changed-in-version{position:relative;outline:3px solid #f2a900;outline-offset:1px}.change-badge{position:absolute;z-index:3;top:4px;left:5px;padding:1px 4px;border:1px solid #8a5200;border-radius:3px;background:#ffd84d;color:#312300;font-size:7.5px;font-weight:950;line-height:1.15;white-space:nowrap;box-shadow:0 1px 2px rgba(35,27,0,.22)}.chip.erb-compact.changed-in-version .class-id{max-width:calc(100% - 76px)}.sample.changed-sample{border:3px solid #f2a900;background:#ffd84d}.filter.change-filter{border-color:#a96700;background:#fff4bd;color:#684000}.filter.change-filter.active{border-color:#6c4200;background:#f2a900;color:#241800}.pill.changed-pill{background:#ffd84d;color:#4d3200}.comparison-old{margin-top:16px;padding:12px;border:2px solid #e3aa24;border-radius:7px;background:#fff8d8;color:#3a3428;white-space:normal}.comparison-old strong{display:block;margin-bottom:5px;color:#6b4500}.comparison-old .old-status{margin-top:7px;color:#75694e;font-size:12px}.comparison-new{font-weight:800;color:#8a5300}.modal-current-label{display:block;margin-bottom:5px;color:#566273;font-size:11px;font-weight:850;text-transform:uppercase}.modal-current{white-space:pre-wrap}
@media (orientation:landscape) and (max-height:540px){.chip.changed-in-version{outline-width:1.5px}.change-badge{top:2px;left:2px;padding:0 2px;border-width:1px;font-size:4.7px}.chip.erb-compact.changed-in-version .class-id{max-width:calc(100% - 38px)}}
@media print{.change-badge{background:#ffd84d!important}.chip.changed-in-version{outline-color:#a96700}}
'''

CSS += r'''
@media (orientation:landscape) and (max-height:700px) and (max-width:1400px){
  html,body{-webkit-text-size-adjust:100%!important;text-size-adjust:100%!important}
  .wrap{padding:6px 5px 48px}.hero,.sub,.stats,.legend,.filters,.foot,.layer-controls,.course-code-legend{display:none}
  .month{padding:8px;margin-top:8px}.month h2{font-size:15px;margin:0 0 6px}
  .gridwrap{overflow:visible}.grid{min-width:0;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px}
  .dow{font-size:8.5px;letter-spacing:0;padding:0}.cell{min-height:98px;height:auto;padding:2px;border-radius:5px;overflow:visible}
  .dnum{font-size:8.5px;gap:2px}.dnum .dmon{font-size:9px}.dnum .dday{font-size:8.5px}.dnum .dweekday{font-size:6.8px}
  .chip{padding:2px 3px 3px;border-radius:4px;overflow:visible}.chip.confirmed,.chip.unconfirmed{border-width:1.8px!important}.chip.note{border-width:1.3px!important}
  .chip .top{margin-bottom:1px}.chip .cat,.chip .status{font-size:5.8px;font-weight:550;letter-spacing:0}
  .class-id{margin-top:1px;padding:1px 2px;gap:2px;font-size:5.8px;border-radius:2px}.class-dot{width:4px;height:4px;flex-basis:4px}
  .chip .ttl,.chip .det{display:none}.chip .fulltxt{display:block;font-size:6.6px;font-weight:400;line-height:1.14;white-space:normal;overflow:visible;word-break:break-word;overflow-wrap:anywhere}
  .chip.erb-compact{gap:1px;padding:3px 4px 4px}.chip.erb-compact .class-id{min-height:10px;max-width:calc(100% - 14px);padding:1px 3px;font-size:6px;border-width:1.3px;border-radius:2px}
  .chip.erb-compact .class-dot{width:4px;height:4px;flex-basis:4px}.erb-meta,.erb-course,.erb-foot{font-size:6px;line-height:1.08}.chip.erb-compact .status{top:2px;right:3px;font-size:5.8px}
  .chip.layer-class,.chip.erb-compact.layer-class{padding-left:7px}.chip.layer-class.confirmed,.chip.layer-class.unconfirmed,.chip.layer-class.note{box-shadow:inset 4px 0 0 var(--context-color),0 1px 1px rgba(20,30,50,.04)}
  .overlap-group{gap:2px}.overlap-group.overlap-active{padding:1px 6px 1px 0}.overlap-group.overlap-active::after{width:4px;border-width:1.4px}
  .floating-mode-switch{left:clamp(42px,3vw,112px);bottom:8px;grid-template-columns:repeat(3,34px);gap:2px;padding:3px}
  .mode-option,.today-option,.top-option,.version-option{width:34px;height:32px;border-radius:6px}.mode-main{font-size:8px}.today-option .mode-main{font-size:6px}.mode-sub{font-size:5px}
  .top-option .mode-main,.version-option .mode-main{font-size:12px}.top-option .mode-sub,.version-option .mode-sub{font-size:5px}
  .grid .holiday-cell .chip.cat-holiday{min-height:58px}.grid .holiday-cell .chip.cat-holiday .ttl{display:block;font-size:7px}
  .chip.changed-in-version{outline-width:1.5px}.change-badge{top:2px;left:2px;padding:0 2px;border-width:1px;font-size:4.7px}.chip.erb-compact.changed-in-version .class-id{max-width:calc(100% - 38px)}
}
'''

TIME_RANGE_RE = re.compile(r"(?<!\d)(2[0-3]|[01]?\d):?([0-5]\d)\s*(am|pm)?\s*-\s*(2[0-3]|[01]?\d):?([0-5]\d)(?!\d)\s*(am|pm)?", re.I)
TEACHER_RE = re.compile(r"\b(Garett|Garrett|Andy|Calvin|Mike(?:\s+Sir)?)\b", re.I)
NOTE_WORD_RE = re.compile(r"test|exam|presentation|discussion|cancel|substitut", re.I)


def clean_location(title, category):
    if category == "ymca":
        return "YMCA"
    if category == "dgs":
        return "DGS"
    if category in {"holiday", "mike"}:
        return "-"
    value = str(title or "")
    code_m = COURSE_CODE_RE.search(value)
    if code_m:
        value = value[:code_m.start()]
    value = re.sub(r"\([^)]*\)|\[[^\]]*\]", "", value)
    value = re.sub(r"\s*-\s*L\s*\d+.*$", "", value, flags=re.I)
    value = re.sub(r"\s*-\s*", "-", value)
    return value.strip(" ,-/") or "-"


def display_clock(hour, minute, marker):
    hour = int(hour)
    minute = int(minute)
    marker = (marker or "").lower()
    if marker == "pm" and hour < 12:
        hour += 12
    elif marker == "am" and hour == 12:
        hour = 0
    return f"{hour:02d}:{minute:02d}"


def display_times(text):
    ranges = []
    for match in TIME_RANGE_RE.finditer(str(text or "")):
        start = display_clock(match.group(1), match.group(2), match.group(3))
        end = display_clock(match.group(4), match.group(5), match.group(6))
        ranges.append(f"{start}-{end}")
    return " / ".join(ranges) or "-"


def display_notes(text):
    notes = re.findall(r"\[([^\]]+)\]", str(text or ""))
    for value in re.findall(r"\(([^)]+)\)", str(text or "")):
        if NOTE_WORD_RE.search(value):
            notes.append(value)
    return list(dict.fromkeys(note.strip() for note in notes if note.strip()))


def event_fields(ev):
    text = str(ev.get("text") or "")
    title = str(ev.get("title") or "")
    category = ev.get("category")
    parts = slash_parts(text)

    teacher_m = TEACHER_RE.search(text)
    teacher = str(ev.get("teacher") or (teacher_m.group(1) if teacher_m else "-"))
    if teacher.lower() in {"garett", "garrett"}:
        teacher = "Garett"
    elif teacher.lower().startswith("mike"):
        teacher = "Mike Sir"

    if category == "ymca":
        course_name = "SEN"
    elif category == "dgs":
        course_name = re.sub(r"^DGS\s*", "", title, flags=re.I).strip() or "Unreal"
    elif category == "holiday":
        course_name = title or "Public Holiday"
    elif category == "mike":
        course_name = re.sub(r"^Mike\s+Sir\s*", "", title, flags=re.I)
        course_name = re.sub(r"\s*-\s*L\s*\d+.*$", "", course_name, flags=re.I).strip() or "AI Lesson"
    else:
        course_name = parts[1] if len(parts) > 1 else (ev.get("detail") or title)
        code_m = COURSE_CODE_RE.search(course_name)
        if code_m:
            course_name = course_name[:code_m.start()]
        time_m = TIME_RANGE_RE.search(course_name)
        if time_m:
            course_name = course_name[:time_m.start()]
        course_name = course_name.strip(" ,-/") or "-"

    class_label = ev.get("group_label") or "-"
    if category in {"holiday", "school", "mike"}:
        class_label = "-"
    lesson_m = LESSON_RE.search(text)
    lesson = f"Lesson {lesson_m.group(1)}" if lesson_m else "Lesson -"
    return {
        "class_label": class_label,
        "location": clean_location(title, category),
        "teacher": teacher,
        "course_name": course_name,
        "time": display_times(text),
        "lesson": lesson,
        "notes": display_notes(text),
    }


def event_layer(ev):
    if ev.get("layer") == "class":
        return "class"
    if ev.get("category") == "mike":
        return "other"
    if ev.get("category") != "erb":
        return "mine"
    return "class" if event_fields(ev)["teacher"] not in {"Garett", "-"} else "mine"


def event_interval(ev):
    match = TIME_RANGE_RE.search(str(ev.get("text") or ""))
    if not match:
        return None

    def minutes(hour, minute, marker):
        hour = int(hour)
        minute = int(minute)
        marker = (marker or "").lower()
        if marker == "pm" and hour < 12:
            hour += 12
        elif marker == "am" and hour == 12:
            hour = 0
        return hour * 60 + minute

    start = minutes(match.group(1), match.group(2), match.group(3))
    end = minutes(match.group(4), match.group(5), match.group(6))
    return start, end


def event_slot(ev):
    interval = event_interval(ev)
    if interval is None:
        return "other"
    start, _end = interval
    if start < 13 * 60:
        return "morning"
    if start < 18 * 60:
        return "afternoon"
    return "night"


def chip(ev):
    st = ev['status']
    mark = '✓' if st == 'confirmed' else '?' if st == 'unconfirmed' else '•'
    title_html = ev.get("title_html") or ehtml(ev["title"])
    detail_html = ev.get("detail_html") or ehtml(ev["detail"])
    full_html = ev.get("html") or ehtml(ev["text"])
    red_cls = " has-red" if ev.get("red") else ""
    layer = event_layer(ev)
    layer_cls = f" layer-{layer}"
    layer_attrs = (f' data-layer="{layer}" data-erb="{1 if ev["category"] == "erb" else 0}"'
                   f' data-course="{1 if ev["category"] in {"erb", "methodist"} else 0}"'
                   f' data-source="{ehtml(ev.get("source", ""))}"')
    changed = bool(ev.get("changed_in_version"))
    comparison_cls = " changed-in-version" if changed else ""
    comparison_attrs = (
        f' data-changed="{1 if changed else 0}"'
        f' data-change-kind="{ehtml(ev.get("change_kind", ""))}"'
        f' data-previous="{ehtml(ev.get("previous_text", ""))}"'
        f' data-previous-status="{ehtml(ev.get("previous_status", ""))}"'
    )
    comparison_badge = f'<span class="change-badge" title="Changed in {COMPARE_LABEL}">Δ {COMPARE_LABEL}</span>' if changed else ""
    if ev["category"] != "erb":
        teacher_suffix = ""
        if layer == "class" and ev.get("teacher"):
            teacher_suffix = f' / <span class="context-teacher">Teacher: {ehtml(ev["teacher"])}</span>'
        return (f'<div class="chip {st} cat-{ev["category"]} grp-{ev["group"]}{red_cls}{layer_cls}{comparison_cls}" tabindex="0" role="button" '
                f'data-date="{ehtml(ev["date"])}" data-status="{ehtml(st)}" data-cat="{ehtml(ev["category_label"])}" data-group="{ehtml(ev["group"])}" data-group-label="{ehtml(ev["group_label"])}" data-text="{ehtml(ev["text"])}" data-html="{ehtml(full_html)}"{layer_attrs}{comparison_attrs}>'
                f'{comparison_badge}<div class="top"><span class="cat">{ehtml(ev["category_label"])}</span><span class="status">{mark}</span></div>'
                f'<div class="ttl">{title_html}</div><div class="det">{detail_html}{teacher_suffix}</div><div class="fulltxt">{full_html}</div></div>')

    fields = event_fields(ev)
    class_label = fields["class_label"]
    class_hue = zlib.crc32(class_label.encode("utf-8")) % 360
    identity_html = (f'<div class="class-id" style="--class-hue:{class_hue}" title="Course / class: {ehtml(class_label)}">'
                     f'<span class="class-dot" aria-hidden="true"></span>{ehtml(class_label)}</div>')
    teacher_cls = " is-missing" if fields["teacher"] == "-" else " is-alert" if fields["teacher"] in {"Andy", "Calvin"} else ""
    note_html = "".join(f' <span class="card-note">[{ehtml(note)}]</span>' for note in fields["notes"])
    return (f'<div class="chip erb-compact {st} cat-{ev["category"]} grp-{ev["group"]}{red_cls}{layer_cls}{comparison_cls}" tabindex="0" role="button" '
            f'data-date="{ehtml(ev["date"])}" data-status="{ehtml(st)}" data-cat="{ehtml(ev["category_label"])}" data-group="{ehtml(ev["group"])}" data-group-label="{ehtml(ev["group_label"])}" data-text="{ehtml(ev["text"])}" data-html="{ehtml(full_html)}"{layer_attrs}{comparison_attrs}>'
            f'{comparison_badge}<span class="status" aria-label="{ehtml(st)}">{mark}</span>{identity_html}'
            f'<div class="erb-meta"><span class="erb-location">{ehtml(fields["location"])}</span><span class="erb-sep">&middot;</span>'
            f'<span class="erb-teacher{teacher_cls}">Teacher: {ehtml(fields["teacher"])}</span></div>'
            f'<div class="erb-course">{ehtml(fields["course_name"])}</div>'
            f'<div class="erb-foot"><span class="erb-time">{ehtml(fields["time"])}</span><span class="erb-sep">&middot;</span>'
            f'<span class="erb-lesson">{ehtml(fields["lesson"])}{note_html}</span></div>'
            f'<div class="fulltxt">{full_html}</div></div>')


def render_day_events(day_events):
    slot_order = ["morning", "afternoon", "night", "other"]
    groups = {slot: [] for slot in slot_order}
    for ev in sorted(day_events, key=event_sort_key):
        groups[event_slot(ev)].append(ev)
    rendered = []
    for slot in slot_order:
        group = groups[slot]
        if not group:
            continue
        if len(group) == 1:
            rendered.append(chip(group[0]))
            continue
        ordered = sorted(group, key=lambda ev: (0 if event_layer(ev) == "mine" else 1, event_sort_key(ev)))
        rendered.append('<div class="overlap-group overlap-active slot-{}" data-slot="{}" data-overlap-count="{}">{}</div>'.format(
            slot, slot, len(ordered), ''.join(chip(ev) for ev in ordered)
        ))
    return ''.join(rendered)

def month_html(year, month):
    cal = calendar.Calendar(firstweekday=6)
    cells = [f'<div class="dow">{d}</div>' for d in ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]]
    for week in cal.monthdatescalendar(year, month):
        for day in week:
            ds = day.isoformat()
            evs = [] if day.month != month else by_date.get(ds, [])
            cls = "cell" + (" out" if day.month != month else "") + (" wknd" if day.weekday() >= 5 and day.month == month else "") + (" has" if evs else "") + (" holiday-cell" if any(e["category"] == "holiday" for e in evs) else "")
            cell_id = f"d-{ds}" if day.month == month else f"d-out-m{month}-{ds}"
            mon = calendar.month_abbr[day.month]
            weekday = day.strftime("%a")
            cells.append(f'<div class="{cls}" id="{cell_id}"><div class="dnum"><span class="dmon">{mon}</span><span class="dday">{day.day}</span><span class="dweekday">{weekday}</span></div>' + render_day_events(evs) + '</div>')
    grid = '<div class="gridwrap"><div class="grid">' + ''.join(cells) + '</div></div>'
    daykeys = [datetime.date(year, month, day) for day in range(1, calendar.monthrange(year, month)[1] + 1)]
    agenda_bits = []
    for day in daykeys:
        ds = day.isoformat()
        mon = calendar.month_abbr[day.month]
        day_events = by_date.get(ds, [])
        empty_class = " empty-day" if not day_events else ""
        agenda_bits.append(f'<div class="aday{empty_class}" id="a-d-{ds}" data-date="{ds}"><div class="adate"><span class="adow">{day.strftime("%a")}</span><span class="amon">{mon}</span><span class="anum">{day.day}</span></div><div class="achips">' + render_day_events(day_events) + '</div></div>')
    agenda = ''.join(agenda_bits)
    return f'<section class="month" id="m{month}"><h2>{calendar.month_name[month]} {year}</h2>{grid}<div class="agenda">{agenda}</div></section>'

counts = {"confirmed": 0, "unconfirmed": 0, "note": 0}
for e in display_events:
    counts[e['status']] = counts.get(e['status'], 0) + 1
cat_counts = {}
for e in display_events:
    cat_counts[e['category_label']] = cat_counts.get(e['category_label'], 0) + 1
layer_counts = {"mine": 0, "class": 0, "other": 0}
for e in display_events:
    layer_counts[event_layer(e)] += 1
months_html = ''.join(month_html(YEAR, m) for m in range(5, 13))
cat_filters = ''.join(f'<button class="filter course-filter {ehtml(group_status)}" data-filter="{ehtml(slug)}" data-first-date="{ehtml(first_date)}" data-status-summary="{ehtml(group_status)}" title="{ehtml(label)} · {ehtml(group_status)}">{ehtml(label)} ({sum(1 for e in display_events if e["group"] == slug)})</button>' for label, slug, group_status, first_date in GROUPS)
erb_code_legend = ''.join(
    f'<div class="code-key"><b>{ehtml(code)}</b><span>{ehtml(name)}</span></div>'
    for code, name in [
        ("HK239HG", "人工智能知識及應用證書（兼讀制）"),
        ("HK244EG", "人工智能創作營銷社交媒體內容技巧證書（兼讀制）"),
        ("HK244HG", "人工智能創作營銷社交媒體內容技巧證書（兼讀制）"),
        ("HK265HG", "Certificate in AI-enhanced Social Media Content"),
        ("HK281DS", "創意數碼媒體設計及製作助理證書"),
    ]
)

HTML = f'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, minimum-scale=1, maximum-scale=6, user-scalable=yes">
<title>Garett's ERB — Super Timetable</title>
<meta name="description" content="ERB / YMCA / school teaching timetable, May to December 2026. Solid frame = confirmed; dotted frame = unconfirmed.">
<link rel="apple-touch-icon" sizes="180x180" href="icon-180.png"><link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png"><link rel="icon" type="image/png" sizes="192x192" href="icon-192.png"><link rel="manifest" href="manifest.webmanifest">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="Garett's ERB"><meta name="application-name" content="Garett's ERB"><meta name="apple-mobile-web-app-status-bar-style" content="default"><meta name="theme-color" content="#0f7074">
<meta name="erb-build" content="{BUILD_ID}">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<script>window.ERB_BUILD_ID='{BUILD_ID}';(function(){{if(!/^https?:$/.test(location.protocol))return;var p=new URLSearchParams(location.search);if(p.get('build')!==window.ERB_BUILD_ID){{p.set('build',window.ERB_BUILD_ID);location.replace(location.pathname+'?'+p.toString()+location.hash);}}}})();</script>
<style>{CSS}</style></head><body><main class="wrap">
<div class="hero"><div><h1 class="title"><span class="y">ERB</span> Super Timetable</h1><p class="sub">May–December 2026 · personal timetable plus complete ERB class context · solid frame = confirmed, dotted frame = unconfirmed</p></div><div class="actions"><a class="btn" href="#today" id="todayBtn">Today</a><a class="btn" href="#m5">May</a><a class="btn" href="#m6">Jun</a><a class="btn" href="#m7">Jul</a><a class="btn" href="#m8">Aug</a><a class="btn" href="#m9">Sep</a><a class="btn" href="#m10">Oct</a><a class="btn" href="#m11">Nov</a><a class="btn" href="#m12">Dec</a></div></div>
<div class="stats"><div class="stat"><b>{len(display_events)}</b> total entries</div><div class="stat"><b>{layer_counts['mine']}</b> my schedule</div><div class="stat"><b>{layer_counts['class']}</b> other class lessons</div><div class="stat"><b>{counts.get('confirmed',0)}</b> confirmed</div><div class="stat"><b>{counts.get('unconfirmed',0)}</b> unconfirmed</div></div>
<div class="legend"><div class="legend-card"><span class="sample confirmed"></span> Confirmed / 已確認</div><div class="legend-card"><span class="sample unconfirmed"></span> Unconfirmed / 未確認</div><div class="legend-card"><span class="sample class-layer"></span> Full class context</div>{comparison_legend_html}<div class="legend-card"><span class="sample note"></span> Note / holiday</div></div>
<div class="section-h">ERB course codes</div><div class="course-code-legend">{erb_code_legend}</div>
<div id="filterArea" class="section-h filter-jump-target">Filter by course / class</div><div class="filters"><button class="filter course-filter active" data-filter="all">All ({len(display_events)})</button>{comparison_filter_html}{cat_filters}</div>
{months_html}
<div class="foot">Sources: <b>{ehtml(SRC.name)}</b>, <b>{ehtml(OVERRIDES_SRC.name)}</b>, and <b>{ehtml(CONTEXT_SRC.name)}</b>. The supplemental layer never overwrites a workbook entry. Generated from Excel border styles: solid/medium = confirmed, dashed = unconfirmed.</div>
</main><div id="modeSwitch" class="floating-mode-switch" role="group" aria-label="Timetable view and navigation"><button id="floatingToday" class="today-option" type="button" aria-label="Go to today" title="Go to today"><span class="mode-main">TODAY</span></button><button id="floatingTop" class="top-option" type="button" aria-label="Back to course filters" title="Back to course filters"><span class="mode-main" aria-hidden="true">&uarr;</span><span class="mode-sub">FILTER</span></button><button id="floatingVersions" class="version-option" type="button" aria-label="Back to version selector" title="Back to version selector"><span class="mode-main" aria-hidden="true">&#9776;</span><span class="mode-sub">VERS</span></button><button class="mode-option" type="button" data-mode="mine-confirmed" aria-label="Me: confirmed lessons" title="Me: confirmed lessons"><span class="mode-main">ME</span><span class="mode-sub">CONF</span></button><button class="mode-option" type="button" data-mode="mine-all" aria-label="Me: confirmed and unconfirmed lessons" title="Me: confirmed and unconfirmed lessons"><span class="mode-main">ME</span><span class="mode-sub">ALL</span></button><button class="mode-option active" type="button" data-mode="both" aria-label="All: full timetable" title="All: full timetable"><span class="mode-main">ALL</span><span class="mode-sub">FULL</span></button></div><div id="modal" class="modal" hidden><div class="modal-card"><button class="modal-x" aria-label="Close">×</button><div class="modal-h"></div><div class="modal-date"></div><div class="modal-body"></div></div></div>
<script>
if('serviceWorker' in navigator&&/^https?:$/.test(location.protocol)){{window.addEventListener('load',()=>navigator.serviceWorker.register('./sw.js?build='+window.ERB_BUILD_ID).then(r=>r.update()).catch(()=>{{}}));}}
const modal=document.getElementById('modal');
function openChip(el){{
  const st=el.dataset.status, cat=el.dataset.cat, txt=el.dataset.text, html=el.dataset.html||'', date=el.dataset.date, source=el.dataset.source||'', layer=el.dataset.layer;
  const changed=el.dataset.changed==='1', previous=el.dataset.previous||'', previousStatus=el.dataset.previousStatus||'', changeKind=el.dataset.changeKind||'';
  const esc=value=>String(value||'').replace(/[&<>"']/g,c=>({{'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}}[c]));
  modal.querySelector('.modal-h').textContent=cat;
  modal.querySelector('.modal-date').innerHTML=date+' · <span class="pill '+st+'">'+(st==='confirmed'?'Confirmed / 已確認':st==='unconfirmed'?'Unconfirmed / 未確認':'Note / 備註')+'</span>'+(layer==='class'?' <span class="pill class-layer">Full class context</span>':'')+(changed?' <span class="pill changed-pill">Changed in {COMPARE_LABEL}</span>':'');
  const oldContent=changeKind==='new'?'<span class="comparison-new">Not present in {COMPARE_BASELINE_LABEL}</span>':esc(previous)+(previousStatus?'<div class="old-status">Status in {COMPARE_BASELINE_LABEL}: '+esc(previousStatus)+'</div>':'');
  const comparison=changed?'<div class="comparison-old"><strong>{COMPARE_BASELINE_LABEL} content</strong><div>'+oldContent+'</div></div>':'';
  modal.querySelector('.modal-body').innerHTML='<span class="modal-current-label">Current {COMPARE_LABEL} content</span><div class="modal-current">'+(html||txt)+'</div>'+comparison+(source?'<div class="modal-source">Source: '+esc(source)+'</div>':'');
  modal.hidden=false;
}}
document.querySelectorAll('.chip').forEach(el=>{{el.addEventListener('click',()=>openChip(el));el.addEventListener('keydown',e=>{{if(e.key==='Enter'||e.key===' '){{e.preventDefault();openChip(el)}}}})}});
modal.querySelector('.modal-x').onclick=()=>modal.hidden=true; modal.addEventListener('click',e=>{{if(e.target===modal) modal.hidden=true}}); document.addEventListener('keydown',e=>{{if(e.key==='Escape') modal.hidden=true}});
function isPortraitAgenda(){{return window.matchMedia('(orientation: portrait) and (max-width: 820px)').matches;}}
function jumpToFilter(btn){{
  const f=btn.dataset.filter;
  const candidates=Array.from(document.querySelectorAll(f==='changed'?'.chip[data-changed="1"]':'.chip.grp-'+f)).filter(ch=>ch.style.display!=='none');
  const preferred=candidates.find(ch=>isPortraitAgenda()?ch.closest('.agenda'):ch.closest('.grid'))||candidates[0];
  const ds=preferred&&preferred.dataset.date;
  if(!ds) return;
  const target=document.getElementById((isPortraitAgenda()?'a-d-':'d-')+ds)||document.getElementById('a-d-'+ds)||document.getElementById('d-'+ds);
  if(!target) return;
  setTimeout(()=>{{
    if(isPortraitAgenda()){{
      const y=window.pageYOffset + target.getBoundingClientRect().top - 10;
      window.scrollTo(0, Math.max(0, y));
    }} else {{
      target.scrollIntoView({{block:'center', inline:'center', behavior:'auto'}});
    }}
  }}, 40);
}}
window.__courseFilter='all';
window.__layerMode='both';
function applyFilters(){{
  const f=window.__courseFilter, mode=window.__layerMode;
  window.__filterActive = f !== 'all';
  document.querySelectorAll('.chip').forEach(ch=>{{
    const courseMatch=f==='all'||(f==='changed'?ch.dataset.changed==='1':ch.classList.contains('grp-'+f));
    const isMike=ch.dataset.cat==='Mike Sir';
    const isHoliday=ch.dataset.cat==='Holiday';
    const isMine=ch.dataset.layer==='mine';
    const layerMatch=mode==='both'||(mode==='mine-all'&&(isMine||isMike))||(mode==='mine-confirmed'&&(isMike||isHoliday||(isMine&&ch.dataset.status==='confirmed')));
    ch.style.display=courseMatch&&layerMatch?'':'none';
  }});
  document.querySelectorAll('.overlap-group').forEach(group=>{{
    const visible=Array.from(group.querySelectorAll('.chip')).filter(ch=>ch.style.display!=='none').length;
    group.classList.toggle('overlap-active',visible>=2);
  }});
  document.querySelectorAll('.cell').forEach(cell=>{{ const visible=Array.from(cell.querySelectorAll('.chip')).some(ch=>ch.style.display!=='none'); if(cell.querySelector('.chip')) cell.classList.toggle('has', visible); }});
  document.querySelectorAll('.aday').forEach(day=>{{ const chips=Array.from(day.querySelectorAll('.chip')); if(chips.length) day.style.display=chips.some(ch=>ch.style.display!=='none')?'':'none'; }});
}}
document.querySelectorAll('.course-filter').forEach(btn=>btn.addEventListener('click',()=>{{
  document.querySelectorAll('.course-filter').forEach(b=>b.classList.remove('active')); btn.classList.add('active');
  const f=btn.dataset.filter;
  window.__courseFilter=f;
  applyFilters();
  if(f!=='all') jumpToFilter(btn);
}}));
function captureModeAnchor(){{
  const selector=isPortraitAgenda()?'.agenda .aday':'.grid .cell:not(.out)';
  const candidates=Array.from(document.querySelectorAll(selector)).filter(el=>{{
    const style=getComputedStyle(el), rect=el.getBoundingClientRect();
    return style.display!=='none'&&rect.bottom>0&&rect.top<innerHeight;
  }});
  if(!candidates.length) return null;
  const anchorY=innerHeight/2;
  const distance=el=>{{const rect=el.getBoundingClientRect();return rect.top<=anchorY&&rect.bottom>=anchorY?0:Math.min(Math.abs(rect.top-anchorY),Math.abs(rect.bottom-anchorY));}};
  const target=candidates.reduce((best,el)=>distance(el)<distance(best)?el:best);
  return {{id:target.id,top:target.getBoundingClientRect().top}};
}}
function restoreModeAnchor(anchor){{
  if(!anchor){{window.__restoringModeAnchor=false;return;}}
  requestAnimationFrame(()=>setTimeout(()=>{{
    const target=document.getElementById(anchor.id);
    if(!target){{window.__restoringModeAnchor=false;return;}}
    if(isPortraitAgenda()){{target.classList.remove('empty-day');target.style.display='';}}
    const delta=target.getBoundingClientRect().top-anchor.top;
    const previousScrollBehavior=document.documentElement.style.scrollBehavior;
    document.documentElement.style.scrollBehavior='auto';
    window.__restoringModeAnchor=true;
    window.scrollTo(0,Math.max(0,window.scrollY+delta));
    document.documentElement.style.scrollBehavior=previousScrollBehavior;
    setTimeout(()=>{{window.__restoringModeAnchor=false;}},80);
  }},30));
}}
window.__modeCompareAnchor=null;
window.__restoringModeAnchor=false;
window.addEventListener('scroll',()=>{{if(!window.__restoringModeAnchor) window.__modeCompareAnchor=null;}},{{passive:true}});
document.getElementById('floatingTop').addEventListener('click',()=>{{window.__modeCompareAnchor=null;document.getElementById('filterArea').scrollIntoView({{block:'start',behavior:'smooth'}});}});
document.getElementById('floatingVersions').addEventListener('click',()=>{{
  const target=location.pathname.includes('/versions/')?'../../master/?v=redtext1':'./master/?v=redtext1';
  location.assign(target);
}});
document.querySelectorAll('.mode-option').forEach(btn=>btn.addEventListener('click',()=>{{
  const anchor=window.__modeCompareAnchor||captureModeAnchor();
  window.__modeCompareAnchor=anchor;
  document.querySelectorAll('.mode-option').forEach(option=>option.classList.toggle('active',option===btn));
  window.__layerMode=btn.dataset.mode;
  window.__restoringModeAnchor=true;
  applyFilters();
  restoreModeAnchor(anchor);
}}));
applyFilters();
(function(){{
 const pad=n=>String(n).padStart(2,'0');
 const localDate=d=>`${{d.getFullYear()}}-${{pad(d.getMonth()+1)}}-${{pad(d.getDate())}}`;
 const params=new URLSearchParams(location.search);
 const override=params.get('today');
 const ds=/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(override||'') ? override : localDate(new Date());
 const gridToday=document.getElementById('d-'+ds);
 const agendaToday=document.getElementById('a-d-'+ds);
 if(gridToday) gridToday.classList.add('today');
 if(agendaToday){{agendaToday.classList.add('today');agendaToday.classList.remove('empty-day');}}
 const todayBtn=document.getElementById('todayBtn');
 function isPortraitAgenda(){{return window.matchMedia('(orientation: portrait) and (max-width: 820px)').matches;}}
 function focusToday(force=false){{
   if(window.__filterActive&&!force) return;
   const portrait=isPortraitAgenda();
   const target=portrait ? agendaToday : gridToday;
   if(!target){{todayBtn.href='#m6'; return;}}
   todayBtn.href='#';
   if(portrait){{
     agendaToday.style.display='';
     const y=window.pageYOffset + target.getBoundingClientRect().top - 10;
     const previousScrollBehavior=document.documentElement.style.scrollBehavior;
     document.documentElement.style.scrollBehavior='auto';
     window.scrollTo(0, Math.max(0, y));
     document.documentElement.style.scrollBehavior=previousScrollBehavior;
   }} else {{
     target.scrollIntoView({{block:'center', inline:'center', behavior:'auto'}});
   }}
 }}
 window.focusTimetableToday=()=>focusToday(true);
 document.getElementById('floatingToday').addEventListener('click',()=>{{window.__modeCompareAnchor=null;window.focusTimetableToday();}});
 todayBtn.addEventListener('click', e=>{{e.preventDefault(); window.__filterActive=false; window.__modeCompareAnchor=null; focusToday();}});
 focusToday();
 requestAnimationFrame(focusToday);
 window.addEventListener('load', ()=>setTimeout(focusToday,80));
 window.addEventListener('orientationchange', ()=>setTimeout(focusToday,450));
 setTimeout(focusToday,300);
 setTimeout(focusToday,900);
}})();
</script></body></html>'''

SW = f'''const BUILD_ID = '{BUILD_ID}';

self.addEventListener('install', event => {{
  self.skipWaiting();
}});

self.addEventListener('activate', event => {{
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
}});

self.addEventListener('fetch', event => {{
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (event.request.method !== 'GET') return;
  const req = new Request(event.request, {{ cache: 'no-store' }});
  event.respondWith(fetch(req).catch(() => fetch(event.request)));
}});
'''

(OUTDIR / 'index.html').write_text(HTML, encoding='utf-8')
(OUTDIR / '.nojekyll').write_text('', encoding='utf-8')
(OUTDIR / 'sw.js').write_text(SW, encoding='utf-8')
(OUTDIR / 'events.json').write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')
(OUTDIR / 'summary.json').write_text(json.dumps({"source": str(SRC), "override_source": str(OVERRIDES_SRC), "override_revision": override_revision, "override_confirmation": override_confirmation, "events": len(events), "display_events": len(display_events), "context_events": len(context_events), "comparison_baseline": str(COMPARE_BASELINE), "comparison_label": COMPARE_LABEL, "changed_in_version": len(changed_events), "counts": counts, "layers": layer_counts, "categories": cat_counts, "months": MONTH_SHEETS}, ensure_ascii=False, indent=2), encoding='utf-8')
(OUTDIR / 'manifest.webmanifest').write_text(json.dumps({"id":"./","name":"Garett's ERB","short_name":"Garett's ERB","description":"Garett's ERB teaching timetable","start_url":"./?v=redtext1&build=" + BUILD_ID,"scope":"./","display":"standalone","background_color":"#eef1f6","theme_color":"#0f7074","icons":[{"src":"icon-192.png","sizes":"192x192","type":"image/png","purpose":"any maskable"},{"src":"icon-512.png","sizes":"512x512","type":"image/png","purpose":"any maskable"}]}, ensure_ascii=False, indent=2), encoding='utf-8')
try:
    from PIL import Image, ImageDraw, ImageFont
    def make_icon(size, filename):
        output_path = OUTDIR / filename
        img = Image.new('RGB', (size, size), '#0f7074')
        d = ImageDraw.Draw(img)
        pad = max(2, size // 12)
        radius = max(4, size // 6)
        d.rounded_rectangle([pad, pad, size-pad, size-pad], radius=radius, fill='#ffffff')
        d.rounded_rectangle([pad, pad, size-pad, size//3], radius=radius, fill='#f2a33a')
        d.rectangle([pad, size//5, size-pad, size//3], fill='#f2a33a')
        font_path = r'C:/Windows/Fonts/segoeuib.ttf'
        g_font = ImageFont.truetype(font_path, max(9, int(size*.37)))
        erb_font = ImageFont.truetype(font_path, max(6, int(size*.16)))
        d.text((size//2, int(size*.54)), 'G', anchor='mm', font=g_font, fill='#0f7074')
        d.text((size//2, int(size*.80)), 'ERB', anchor='mm', font=erb_font, fill='#1d2734')
        img.save(output_path)
    make_icon(32, 'favicon-32.png')
    make_icon(180, 'icon-180.png')
    make_icon(192, 'icon-192.png')
    make_icon(512, 'icon-512.png')
except Exception as e:
    print('icon generation skipped', e)
print('generated', OUTDIR)
print('events', len(events), counts)
for k, v in sorted(cat_counts.items()):
    print(k, v)
