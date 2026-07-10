from openpyxl import load_workbook
from openpyxl.cell.rich_text import CellRichText, TextBlock
from pathlib import Path
import calendar, datetime, html, json, re

SRC = Path(r"C:/Users/garet/OneDrive/桌面/Timetable/ERB Super Timetable 04_checking 04.xlsx")
OUTDIR = Path(r"D:/Claude Code/ERB Super Timetable/erb-super-timetable")
OUTDIR.mkdir(parents=True, exist_ok=True)
MONTH_SHEETS = ["June", "July New", "August New", "September New", "October New", "November New", "December New"]
YEAR = 2026
BUILD_ID = "checked04-classnames-20260710a"

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
    styles = [cell.border.top.style, cell.border.right.style, cell.border.bottom.style, cell.border.left.style]
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
    if "勵行" in text or "HK244" in text or "HK239" in text or "HK265" in text or "HK280" in text:
        return "erb", "勵行 / ERB"
    if "Mike" in text:
        return "mike", "Mike Sir"
    if "佛教" in text or "Canva" in text:
        return "school", "School"
    return "other", "Other"

def split_title(text):
    parts = [p.strip() for p in text.split("/") if p.strip()]
    if not parts:
        return text, ""
    return parts[0], " / ".join(parts[1:])

COURSE_CODE_RE = re.compile(r"(?<![A-Z0-9])(?:HK\d+[A-Z]+|MC\d+[A-Z]+|PFSA\d+|QAT\d+|DGS)(?![A-Z0-9])", re.I)
CLASS_RE = re.compile(r"(?<![A-Z0-9])Class\s+([^,/()]+)", re.I)
CODE_PAREN_CLASS_RE = re.compile(r"(?<![A-Z0-9])(?:HK\d+[A-Z]+|MC\d+[A-Z]+|PFSA\d+|QAT\d+)\s*\(([^)]+)\)", re.I)
NAMED_CLASS_RE = re.compile(r"\(([^()]*班)\)", re.I)
LESSON_RE = re.compile(r"(?:^|[\s/\-])L\s*(\d+)(?!\d)", re.I)
TIME_RE = re.compile(r"(?<!\d)([01]?\d|2[0-3])[:：]?([0-5]\d)\s*(?:-|–|至|to)", re.I)
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
    start = int(time_m.group(1)) * 60 + int(time_m.group(2)) if time_m else 9999
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
    return (0 if code else 1, natural_key(code), natural_key(cls), lesson, start, ev.get("row", 999), ev.get("col", 999), ev.get("text", ""))


events = []
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

for ds in by_date:
    by_date[ds].sort(key=event_sort_key)

classes_by_code = {}
for event in events:
    code, cls, _lesson, _start = course_sort_parts(event["text"])
    if code and cls:
        classes_by_code.setdefault(code, set()).add(cls)
INFERRED_CLASS_BY_CODE = {
    code: next(iter(classes))
    for code, classes in classes_by_code.items()
    if len(classes) == 1
}

_group_labels = sorted({course_group_label(e["text"], e["category_label"]) for e in events}, key=lambda label: (0 if COURSE_CODE_RE.fullmatch(label.split(" · ", 1)[0]) or label == "DGS" else 1, natural_key(label.split(" · ", 1)[0]), natural_key(label.split(" · ", 1)[1] if " · " in label else ""), label))
_group_slugs = {label: f"g{i:02d}" for i, label in enumerate(_group_labels, 1)}
for ev in events:
    ev["group_label"] = course_group_label(ev["text"], ev["category_label"])
    ev["group"] = _group_slugs[ev["group_label"]]

def ehtml(s):
    return html.escape(str(s or ""), quote=True)

GROUPS = []
for label in _group_labels:
    slug = _group_slugs[label]
    group_events = [e for e in events if e["group"] == slug]
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
*{box-sizing:border-box}html{-webkit-text-size-adjust:100%;scroll-behavior:smooth}body{margin:0;font-family:"Segoe UI Variable","Segoe UI",-apple-system,BlinkMacSystemFont,Roboto,"Noto Sans TC","Microsoft JhengHei",Arial,sans-serif;background:#eef1f6;color:#1d2734;line-height:1.42}.xl-red{color:#d60000;font-weight:700}.chip .xl-red{color:#d60000}.modal-body .xl-red{color:#d60000;font-weight:750}.wrap{max-width:1280px;margin:0 auto;padding:28px 16px 70px}.hero{display:flex;justify-content:space-between;gap:16px;align-items:flex-start}.title{font-size:30px;font-weight:850;letter-spacing:-.45px;margin:0}.title .y{color:#0f7d7d}.sub{color:#64707f;margin:6px 0 0;font-size:14px}.actions{display:flex;gap:8px;flex-wrap:wrap;justify-content:flex-end}.btn{border:1px solid #d8e0ea;background:#fff;color:#344153;border-radius:10px;padding:8px 12px;font-weight:750;font-size:13px;text-decoration:none;box-shadow:0 1px 2px rgba(20,30,50,.05)}.btn:hover{border-color:#8bb8bd}.stats,.legend{display:flex;gap:10px;flex-wrap:wrap;margin:18px 0 6px}.stat,.legend-card{background:#fff;border:1px solid #e2e7ef;border-radius:12px;padding:8px 13px;font-size:13px;color:#46505e;box-shadow:0 1px 2px rgba(20,30,50,.05)}.stat b{color:#1d2734;font-size:15px}.legend-card{display:flex;align-items:center;gap:8px}.sample{width:28px;height:18px;border-radius:6px;background:#f9fcff}.sample.confirmed{border:3px solid #1d2734}.sample.unconfirmed{border:3px dashed #1d2734}.sample.note{border:2px solid #b8c1ce}.filters{display:flex;gap:8px;flex-wrap:wrap;margin:16px 0}.filter{border:2px solid #dbe3ed;background:#fff;border-radius:999px;padding:7px 11px;font-weight:750;font-size:12px;color:#4c5a6b;cursor:pointer}.filter.confirmed{border:3px solid #1d2734}.filter.unconfirmed{border:3px dashed #1d2734}.filter.mixed{border:3px dashed #1d2734;box-shadow:inset 0 0 0 2px rgba(29,39,52,.18),0 1px 2px rgba(20,30,50,.05)}.filter.note{border:2px solid #b8c1ce;color:#69737f}.filter.active{background:#0f7d7d;color:#fff;border-color:#1d2734}.filter.active.confirmed{border-style:solid}.filter.active.unconfirmed,.filter.active.mixed{border-style:dashed}.filter.active.note{border-color:#b8c1ce}.section-h{font-size:13px;text-transform:uppercase;letter-spacing:.8px;color:#8a94a2;font-weight:800;margin:24px 2px 10px}.month{background:#fff;border:1px solid #e2e7ef;border-radius:16px;padding:16px;margin-top:18px;box-shadow:0 1px 3px rgba(20,30,50,.06)}.month h2{margin:0 0 12px;font-size:20px;font-weight:850;letter-spacing:-.2px}.gridwrap{overflow-x:auto}.grid{display:grid;grid-template-columns:repeat(7,minmax(124px,1fr));gap:7px;min-width:868px}.dow{font-size:11.5px;font-weight:800;color:#98a2af;text-align:center;padding:2px 0;text-transform:uppercase;letter-spacing:.5px}.cell{min-height:132px;border:1px solid #e8ecf3;border-radius:10px;padding:6px;background:#fcfdff;display:flex;flex-direction:column;gap:4px}.cell.out{background:#f4f6f9;border-style:dashed;opacity:.5}.cell.wknd{background:#f7f9fc}.cell.today{outline:3px solid #0f7d7d;outline-offset:1px}.dnum{font-size:12px;font-weight:850;color:#9aa4b1}.cell.has .dnum{color:#2d3948}.dnum{display:flex;align-items:baseline;gap:3px;white-space:nowrap}.dnum .dmon{font-size:9.5px;font-weight:850;color:#7f8a98;text-transform:uppercase}.dnum .dday{font-size:12px;font-weight:900;color:inherit}.chip{border-radius:8px;padding:5px 7px 6px;background:#fff;box-shadow:0 1px 1px rgba(20,30,50,.04);cursor:pointer;overflow:visible}.chip.confirmed{border-style:solid!important;border-width:2.5px!important;border-color:#1d2734!important;box-shadow:0 0 0 1px rgba(29,39,52,.10) inset,0 1px 1px rgba(20,30,50,.04)}.chip.unconfirmed{border-style:dashed!important;border-width:2.5px!important;border-color:#1d2734!important;box-shadow:0 0 0 1px rgba(29,39,52,.10) inset,0 1px 1px rgba(20,30,50,.04)}.chip.note{border-style:solid!important;border-width:1.5px!important;border-color:#9aa4b2!important;background:#f8fafc}.chip .top{display:flex;justify-content:space-between;gap:6px;align-items:flex-start}.chip .cat{font-size:10px;font-weight:850;text-transform:uppercase;letter-spacing:.35px;opacity:.82}.chip .status{font-size:9.5px;font-weight:850;white-space:nowrap}.chip .ttl{font-size:11.5px;font-weight:850;margin-top:2px;color:#172232;line-height:1.22}.chip .det{font-size:10.2px;color:#596676;margin-top:2px;line-height:1.22;display:block;white-space:normal;overflow:visible}.chip .fulltxt{display:none}.cat-ymca{background:#e3f7fa}.cat-erb{background:#fff1e6}.cat-methodist{background:#eef0ff}.cat-dgs{background:#ecfdf3}.cat-holiday{background:#f3f4f6}.cat-mike{background:#fff8db}.cat-school{background:#fce7f3}.cat-other{background:#f6f7fb}.agenda{display:none}.aday{display:flex;gap:10px;align-items:flex-start;padding:9px 2px;border-top:1px solid #eef1f6}.aday:first-child{border-top:none}.adate{flex:0 0 48px;text-align:center}.adate .adow{display:block;font-size:11px;font-weight:800;color:#98a2af;text-transform:uppercase}.adate .amon{display:block;font-size:10px;font-weight:900;color:#0f7d7d;text-transform:uppercase;letter-spacing:.05em;line-height:1}.adate .anum{display:block;font-size:20px;font-weight:850;color:#3a4452;line-height:1.05}.achips{flex:1;min-width:0;display:flex;flex-direction:column;gap:6px}.foot{margin-top:28px;color:#7a8492;font-size:12.5px;border-top:1px solid #e2e7ef;padding-top:14px}.modal{position:fixed;inset:0;background:rgba(18,26,38,.56);display:flex;align-items:center;justify-content:center;padding:18px;z-index:50}.modal[hidden]{display:none}.modal-card{background:#fff;border-radius:16px;max-width:560px;width:100%;padding:20px 20px 22px;box-shadow:0 14px 44px rgba(15,25,45,.32);position:relative;max-height:88vh;overflow:auto}.modal-x{position:absolute;top:8px;right:12px;border:none;background:transparent;font-size:26px;line-height:1;color:#98a2af;cursor:pointer}.modal-h{font-size:20px;font-weight:850;padding-right:24px}.modal-date{color:#69737f;font-size:13px;margin-top:2px}.modal-body{white-space:pre-wrap;margin-top:14px;font-size:15px}.pill{display:inline-block;border-radius:999px;padding:4px 9px;font-size:12px;font-weight:850;margin-top:10px;margin-right:6px}.pill.confirmed{background:#e7f6ee;color:#16623d}.pill.unconfirmed{background:#fff3df;color:#a25600}.pill.note{background:#eef2f7;color:#596676}@media (max-width:820px){.wrap{padding:14px 10px 48px}.hero{display:block}.title{font-size:22px}.sub{font-size:13px}.actions{justify-content:flex-start;margin-top:10px}.month{padding:12px 10px 14px}.month h2{font-size:17px}.stats,.legend{gap:7px}.stat,.legend-card{font-size:12px;padding:7px 10px}}@media (orientation:portrait) and (max-width:820px){.gridwrap{display:none}.agenda{display:block}.aday{scroll-margin-top:18px}.aday.today{background:linear-gradient(90deg,rgba(15,125,125,.10),transparent);border-radius:14px}}@media (orientation:landscape) and (max-height:540px){.sub,.stats,.legend,.filters,.foot{display:none}.month{padding:8px;margin-top:10px}.month h2{font-size:15px;margin:0 0 6px}.gridwrap{overflow:visible}.grid{min-width:0;grid-template-columns:repeat(7,minmax(0,1fr));gap:3px}.dow{font-size:8.5px;letter-spacing:0;padding:0}.cell{min-height:98px;height:auto;padding:2px;border-radius:5px;overflow:visible}.dnum{font-size:8.5px;gap:2px}.dnum .dmon{font-size:6.7px}.dnum .dday{font-size:9px}.chip{padding:2px 3px 3px;border-radius:4px;overflow:visible}.chip.confirmed{border-width:1.8px!important}.chip.unconfirmed{border-width:1.8px!important}.chip.note{border-width:1.3px!important}.chip .top{margin-bottom:1px}.chip .cat,.chip .status{font-size:5.8px;font-weight:550;letter-spacing:0}.chip .ttl,.chip .det{display:none}.chip .fulltxt{display:block;font-size:6.6px;font-weight:400;line-height:1.14;color:#172232;white-space:normal;overflow:visible;word-break:break-word;overflow-wrap:anywhere}}@media print{body{background:#fff}.month,.stat,.legend-card{box-shadow:none}.actions,.filters{display:none}.gridwrap{overflow:visible}.grid{min-width:0}.chip{-webkit-print-color-adjust:exact;print-color-adjust:exact}}
'''

CSS += r'''
@media (min-width:821px){.wrap{width:100%;max-width:none;margin:0;padding:28px clamp(16px,1.6vw,36px) 70px}}
.title,.month h2{letter-spacing:0}
'''

def chip(ev):
    st = ev['status']
    mark = '✓' if st == 'confirmed' else '?' if st == 'unconfirmed' else '•'
    title_html = ev.get("title_html") or ehtml(ev["title"])
    detail_html = ev.get("detail_html") or ehtml(ev["detail"])
    full_html = ev.get("html") or ehtml(ev["text"])
    red_cls = " has-red" if ev.get("red") else ""
    return (f'<div class="chip {st} cat-{ev["category"]} grp-{ev["group"]}{red_cls}" tabindex="0" role="button" '
            f'data-date="{ehtml(ev["date"])}" data-status="{ehtml(st)}" data-cat="{ehtml(ev["category_label"])}" data-group="{ehtml(ev["group"])}" data-group-label="{ehtml(ev["group_label"])}" data-text="{ehtml(ev["text"])}" data-html="{ehtml(full_html)}">'
            f'<div class="top"><span class="cat">{ehtml(ev["category_label"])}</span><span class="status">{mark}</span></div>'
            f'<div class="ttl">{title_html}</div><div class="det">{detail_html}</div><div class="fulltxt">{full_html}</div></div>')

def month_html(year, month):
    cal = calendar.Calendar(firstweekday=6)
    cells = [f'<div class="dow">{d}</div>' for d in ["Sun","Mon","Tue","Wed","Thu","Fri","Sat"]]
    for week in cal.monthdatescalendar(year, month):
        for day in week:
            ds = day.isoformat()
            evs = [] if day.month != month else by_date.get(ds, [])
            cls = "cell" + (" out" if day.month != month else "") + (" wknd" if day.weekday() >= 5 and day.month == month else "") + (" has" if evs else "")
            mon = calendar.month_abbr[day.month]
            cells.append(f'<div class="{cls}" id="d-{ds}"><div class="dnum"><span class="dmon">{mon}</span><span class="dday">{day.day}</span></div>' + ''.join(chip(e) for e in evs) + '</div>')
    grid = '<div class="gridwrap"><div class="grid">' + ''.join(cells) + '</div></div>'
    daykeys = sorted(d for d in (datetime.date.fromisoformat(k) for k in by_date) if d.year == year and d.month == month)
    agenda_bits = []
    for day in daykeys:
        ds = day.isoformat()
        mon = calendar.month_abbr[day.month]
        agenda_bits.append(f'<div class="aday" id="a-d-{ds}" data-date="{ds}"><div class="adate"><span class="adow">{day.strftime("%a")}</span><span class="amon">{mon}</span><span class="anum">{day.day}</span></div><div class="achips">' + ''.join(chip(e) for e in by_date[ds]) + '</div></div>')
    agenda = ''.join(agenda_bits)
    return f'<section class="month" id="m{month}"><h2>{calendar.month_name[month]} {year}</h2>{grid}<div class="agenda">{agenda}</div></section>'

counts = {"confirmed": 0, "unconfirmed": 0, "note": 0}
for e in events:
    counts[e['status']] = counts.get(e['status'], 0) + 1
cat_counts = {}
for e in events:
    cat_counts[e['category_label']] = cat_counts.get(e['category_label'], 0) + 1
months_html = ''.join(month_html(YEAR, m) for m in range(6, 13))
cat_filters = ''.join(f'<button class="filter {ehtml(group_status)}" data-filter="{ehtml(slug)}" data-first-date="{ehtml(first_date)}" data-status-summary="{ehtml(group_status)}" title="{ehtml(label)} · {ehtml(group_status)}">{ehtml(label)} ({sum(1 for e in events if e["group"] == slug)})</button>' for label, slug, group_status, first_date in GROUPS)

HTML = f'''<!doctype html><html lang="en"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1, minimum-scale=1, maximum-scale=6, user-scalable=yes">
<title>ERB Super Timetable — Jun–Dec 2026</title>
<meta name="description" content="ERB / YMCA / school teaching timetable, June to December 2026. Solid frame = confirmed; dotted frame = unconfirmed.">
<link rel="apple-touch-icon" sizes="180x180" href="icon-180.png"><link rel="icon" type="image/png" sizes="32x32" href="favicon-32.png"><link rel="icon" type="image/png" sizes="192x192" href="icon-192.png"><link rel="manifest" href="manifest.webmanifest">
<meta name="apple-mobile-web-app-capable" content="yes"><meta name="mobile-web-app-capable" content="yes"><meta name="apple-mobile-web-app-title" content="ERB Timetable"><meta name="apple-mobile-web-app-status-bar-style" content="default"><meta name="theme-color" content="#0f7d7d">
<meta name="erb-build" content="{BUILD_ID}">
<meta http-equiv="Cache-Control" content="no-cache, no-store, must-revalidate">
<meta http-equiv="Pragma" content="no-cache">
<meta http-equiv="Expires" content="0">
<script>window.ERB_BUILD_ID='{BUILD_ID}';(function(){{if(!/^https?:$/.test(location.protocol))return;var p=new URLSearchParams(location.search);if(p.get('build')!==window.ERB_BUILD_ID){{p.set('build',window.ERB_BUILD_ID);location.replace(location.pathname+'?'+p.toString()+location.hash);}}}})();</script>
<style>{CSS}</style></head><body><main class="wrap">
<div class="hero"><div><h1 class="title"><span class="y">ERB</span> Super Timetable</h1><p class="sub">June–December 2026 · copied from Excel source · solid frame = confirmed, dotted frame = unconfirmed</p></div><div class="actions"><a class="btn" href="#today" id="todayBtn">Today</a><a class="btn" href="#m6">Jun</a><a class="btn" href="#m7">Jul</a><a class="btn" href="#m8">Aug</a><a class="btn" href="#m9">Sep</a><a class="btn" href="#m10">Oct</a><a class="btn" href="#m11">Nov</a><a class="btn" href="#m12">Dec</a></div></div>
<div class="stats"><div class="stat"><b>{len(events)}</b> total entries</div><div class="stat"><b>{counts.get('confirmed',0)}</b> confirmed</div><div class="stat"><b>{counts.get('unconfirmed',0)}</b> unconfirmed</div><div class="stat"><b>{counts.get('note',0)}</b> notes/holidays</div></div>
<div class="legend"><div class="legend-card"><span class="sample confirmed"></span> Confirmed / 已確認</div><div class="legend-card"><span class="sample unconfirmed"></span> Unconfirmed / 未確認</div><div class="legend-card"><span class="sample note"></span> Note / holiday</div></div>
<div class="section-h">Filter by course / class</div><div class="filters"><button class="filter active" data-filter="all">All ({len(events)})</button>{cat_filters}</div>
{months_html}
<div class="foot">Source: <b>{ehtml(SRC.name)}</b>. Generated from Excel border styles: solid/medium = confirmed, dashed = unconfirmed. Filtered and sorted by course code, class, lesson/time. Click any entry to read the full copied text.</div>
</main><div id="modal" class="modal" hidden><div class="modal-card"><button class="modal-x" aria-label="Close">×</button><div class="modal-h"></div><div class="modal-date"></div><div class="modal-body"></div></div></div>
<script>
if('serviceWorker' in navigator&&/^https?:$/.test(location.protocol)){{window.addEventListener('load',()=>navigator.serviceWorker.register('./sw.js?build='+window.ERB_BUILD_ID).then(r=>r.update()).catch(()=>{{}}));}}
const modal=document.getElementById('modal');
function openChip(el){{
  const st=el.dataset.status, cat=el.dataset.cat, txt=el.dataset.text, html=el.dataset.html||'', date=el.dataset.date;
  modal.querySelector('.modal-h').textContent=cat;
  modal.querySelector('.modal-date').innerHTML=date+' · <span class="pill '+st+'">'+(st==='confirmed'?'Confirmed / 已確認':st==='unconfirmed'?'Unconfirmed / 未確認':'Note / 備註')+'</span>';
  modal.querySelector('.modal-body').innerHTML=html||txt;
  modal.hidden=false;
}}
document.querySelectorAll('.chip').forEach(el=>{{el.addEventListener('click',()=>openChip(el));el.addEventListener('keydown',e=>{{if(e.key==='Enter'||e.key===' '){{e.preventDefault();openChip(el)}}}})}});
modal.querySelector('.modal-x').onclick=()=>modal.hidden=true; modal.addEventListener('click',e=>{{if(e.target===modal) modal.hidden=true}}); document.addEventListener('keydown',e=>{{if(e.key==='Escape') modal.hidden=true}});
function isPortraitAgenda(){{return window.matchMedia('(orientation: portrait) and (max-width: 820px)').matches;}}
function jumpToFilter(btn){{
  const ds=btn.dataset.firstDate;
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
document.querySelectorAll('.filter').forEach(btn=>btn.addEventListener('click',()=>{{
  document.querySelectorAll('.filter').forEach(b=>b.classList.remove('active')); btn.classList.add('active');
  const f=btn.dataset.filter;
  window.__filterActive = f !== 'all';
  document.querySelectorAll('.chip').forEach(ch=>{{ ch.style.display=(f==='all'||ch.classList.contains('grp-'+f))?'':'none'; }});
  document.querySelectorAll('.cell').forEach(cell=>{{ const visible=Array.from(cell.querySelectorAll('.chip')).some(ch=>ch.style.display!=='none'); if(cell.querySelector('.chip')) cell.classList.toggle('has', visible); }});
  document.querySelectorAll('.aday').forEach(day=>{{ const chips=Array.from(day.querySelectorAll('.chip')); if(chips.length) day.style.display=(f==='all'||chips.some(ch=>ch.style.display!=='none'))?'':'none'; }});
  if(f!=='all') jumpToFilter(btn);
}}));
(function(){{
 const pad=n=>String(n).padStart(2,'0');
 const localDate=d=>`${{d.getFullYear()}}-${{pad(d.getMonth()+1)}}-${{pad(d.getDate())}}`;
 const params=new URLSearchParams(location.search);
 const override=params.get('today');
 const ds=/^\\d{{4}}-\\d{{2}}-\\d{{2}}$/.test(override||'') ? override : localDate(new Date());
 const gridToday=document.getElementById('d-'+ds);
 const agendaToday=document.getElementById('a-d-'+ds);
 if(gridToday) gridToday.classList.add('today');
 if(agendaToday) agendaToday.classList.add('today');
 const todayBtn=document.getElementById('todayBtn');
 function isPortraitAgenda(){{return window.matchMedia('(orientation: portrait) and (max-width: 820px)').matches;}}
 function focusToday(){{
   if(window.__filterActive) return;
   const portrait=isPortraitAgenda();
   const target=portrait ? agendaToday : gridToday;
   if(!target){{todayBtn.href='#m6'; return;}}
   todayBtn.href='#';
   if(portrait){{
     const y=window.pageYOffset + target.getBoundingClientRect().top - 10;
     window.scrollTo(0, Math.max(0, y));
   }} else {{
     target.scrollIntoView({{block:'center', inline:'center', behavior:'auto'}});
   }}
 }}
 todayBtn.addEventListener('click', e=>{{e.preventDefault(); window.__filterActive=false; focusToday();}});
 focusToday();
 requestAnimationFrame(focusToday);
 window.addEventListener('load', ()=>setTimeout(focusToday,80));
 window.addEventListener('orientationchange', ()=>setTimeout(focusToday,450));
 setTimeout(focusToday,300);
 setTimeout(focusToday,900);
}})();
</script></body></html>'''

(OUTDIR / 'index.html').write_text(HTML, encoding='utf-8')
(OUTDIR / '.nojekyll').write_text('', encoding='utf-8')
(OUTDIR / 'events.json').write_text(json.dumps(events, ensure_ascii=False, indent=2), encoding='utf-8')
(OUTDIR / 'summary.json').write_text(json.dumps({"source": str(SRC), "events": len(events), "counts": counts, "categories": cat_counts, "months": MONTH_SHEETS}, ensure_ascii=False, indent=2), encoding='utf-8')
(OUTDIR / 'manifest.webmanifest').write_text(json.dumps({"name":"ERB Super Timetable","short_name":"ERB Timetable","start_url":"./?v=redtext1&build=" + BUILD_ID,"display":"standalone","background_color":"#eef1f6","theme_color":"#0f7d7d","icons":[{"src":"icon-192.png","sizes":"192x192","type":"image/png"},{"src":"icon-512.png","sizes":"512x512","type":"image/png"}]}, ensure_ascii=False, indent=2), encoding='utf-8')
try:
    from PIL import Image, ImageDraw
    def make_icon(size, filename):
        output_path = OUTDIR / filename
        if output_path.exists():
            return
        img = Image.new('RGB', (size, size), '#0f7d7d')
        d = ImageDraw.Draw(img)
        pad = size // 9
        d.rounded_rectangle([pad, pad, size-pad, size-pad], radius=size//7, fill='#ffffff')
        d.text((size//2, size//2), 'ERB', anchor='mm', fill='#0f7d7d')
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
