from __future__ import annotations

import base64
import calendar
import html
import json
import os
import re
from collections import defaultdict
from datetime import date, timedelta
from pathlib import Path
from string import Template

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "earnings"
KEY_FILE = ROOT / "private_earnings_key.txt"
VERSIONS = json.loads((ROOT / "versions.json").read_text(encoding="utf-8"))
TIME_RE = re.compile(
    r"(?<!\d)(\d{1,2})(?::?(\d{2}))?\s*(?:[AaPp][Mm])?\s*[-\u2013]\s*"
    r"(\d{1,2})(?::?(\d{2}))?\s*(?:[AaPp][Mm])?(?!\d)"
)
CANCELLED_RE = re.compile(r"cancel(?:led|ed)", re.I)
PROPOSED_AVAILABILITY_RE = re.compile(r"PROPOSED availability only", re.I)
HK280HS_SS_RE = re.compile(r"HK280HS\s*,?\s*Class\s+SS", re.I)
GARETT_RE = re.compile(r"\bGar(?:e|r)tt\b", re.I)
MONTHS = ("June", "July", "August", "September", "October", "November", "December")
AAD = b"erb-earnings-v1"
DGS_FINAL_TOTAL = 7000
HK280HS_SS_PENDING_HOURS = 18
REVISED_SALARY_RULES_FROM = "2026-07-19-V18h"


def event_interval(text: str) -> tuple[int, int] | None:
    match = TIME_RE.search(text)
    if not match:
        return None
    start_hour, start_minute = int(match.group(1)), int(match.group(2) or 0)
    end_hour, end_minute = int(match.group(3)), int(match.group(4) or 0)
    if start_hour < 8:
        start_hour += 12
    if end_hour < 8:
        end_hour += 12
    start, end = start_hour * 60 + start_minute, end_hour * 60 + end_minute
    if end <= start:
        end += 12 * 60
    return start, end


def is_garetts(event: dict) -> bool:
    category = event["category"]
    if category in {"ymca", "dgs"}:
        return True
    if category in {"erb", "methodist"}:
        explicit_teacher = str(event.get("teacher", "")).strip()
        if explicit_teacher:
            return bool(GARETT_RE.search(explicit_teacher))
        return bool(GARETT_RE.search(event["text"]))
    return False


def merge_minutes(intervals: list[tuple[int, int]]) -> int:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum(end - start for start, end in merged)


def calculate(events: list[dict], statuses: set[str], revised_rules: bool = False) -> dict:
    regular_by_date: dict[str, list[tuple[int, int]]] = defaultdict(list)
    dgs_dates: set[str] = set()
    hk280hs_pending_placeholders: set[str] = set()
    counted_events = 0
    for event in events:
        event_date = event["date"]
        if not ("2026-06-01" <= event_date <= "2026-12-31"):
            continue
        if event["status"] not in statuses or event_date == "2026-06-03":
            continue
        if PROPOSED_AVAILABILITY_RE.search(event["text"]):
            if (
                revised_rules
                and event["status"] == "unconfirmed"
                and "unconfirmed" in statuses
                and HK280HS_SS_RE.search(event["text"])
            ):
                hk280hs_pending_placeholders.add(event_date)
            continue
        if not is_garetts(event) or CANCELLED_RE.search(event["text"]):
            continue
        if event["category"] == "dgs":
            dgs_dates.add(event_date)
            counted_events += 1
            continue
        interval = event_interval(event["text"])
        if interval is None:
            raise ValueError(f"No time range for counted event: {event_date} {event['text']}")
        regular_by_date[event_date].append(interval)
        counted_events += 1

    counted_events += len(hk280hs_pending_placeholders)
    hk280hs_pending_active = bool(hk280hs_pending_placeholders)
    dgs_payment_month = min(
        (int(event_date[5:7]) for event_date in dgs_dates),
        default=None,
    )
    rows = []
    grand_total = 0
    for month_number, month_name in enumerate(MONTHS, 6):
        regular_minutes = sum(
            merge_minutes(intervals)
            for event_date, intervals in regular_by_date.items()
            if int(event_date[5:7]) == month_number
        )
        pending_hours = (
            HK280HS_SS_PENDING_HOURS
            if hk280hs_pending_active and month_number == 9
            else 0
        )
        regular_hours = regular_minutes / 60 + pending_hours
        dgs_days = sum(int(event_date[5:7]) == month_number for event_date in dgs_dates)
        dgs_hours = dgs_days * 4
        regular_pay = regular_hours * 300
        dgs_pay = (
            DGS_FINAL_TOTAL if month_number == dgs_payment_month else 0
        ) if revised_rules else dgs_hours * 900
        total = regular_pay + dgs_pay
        grand_total += total
        rows.append({
            "month": month_name,
            "regular_hours": regular_hours,
            "regular_pay": regular_pay,
            "dgs_days": dgs_days,
            "dgs_hours": dgs_hours,
            "dgs_pay": dgs_pay,
            "total": total,
        })
    return {"months": rows, "grand_total": grand_total, "counted_events": counted_events}


def encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).decode("ascii").rstrip("=")


def decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def encrypt_report(report: dict, key: bytes) -> dict:
    plaintext = json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    nonce = os.urandom(12)
    ciphertext = AESGCM(key).encrypt(nonce, plaintext, AAD)
    return {"version": 1, "nonce": encode(nonce), "ciphertext": encode(ciphertext)}


def decrypt_report(payload: dict, key: bytes) -> dict:
    plaintext = AESGCM(key).decrypt(
        decode(payload["nonce"]), decode(payload["ciphertext"]), AAD
    )
    return json.loads(plaintext.decode("utf-8"))


def calculate_expected_payments(
    events: list[dict],
    statuses: set[str],
    payment_context: list[dict],
) -> dict:
    context_by_group = {item["group"]: item for item in payment_context}
    erb_by_group: dict[str, dict[str, list[tuple[int, int]]]] = defaultdict(
        lambda: defaultdict(list)
    )
    sen_by_month: dict[str, dict[str, list[tuple[int, int]]]] = defaultdict(
        lambda: defaultdict(list)
    )

    def payment_group(event: dict) -> str:
        existing = str(event.get("group", ""))
        if existing in context_by_group:
            return existing
        text = str(event.get("text", ""))
        event_date = str(event.get("date", ""))
        candidates = []
        for group, context in context_by_group.items():
            code = str(context.get("course_code", ""))
            if not code or code not in text:
                continue
            label_parts = str(context.get("label", "")).split(" · ")
            class_name = label_parts[1] if len(label_parts) > 1 else ""
            class_matches = bool(
                class_name
                and (
                    re.search(rf"\bClass\s+{re.escape(class_name)}\b", text, re.I)
                    or re.search(rf"\({re.escape(class_name)}\)", text, re.I)
                )
            )
            if not class_matches:
                continue
            if len(label_parts) > 2:
                if not (
                    context["full_course_start"]
                    <= event_date
                    <= context["full_course_end"]
                ):
                    continue
            candidates.append(group)
        if len(candidates) != 1:
            raise ValueError(
                f"Expected one payment group, found {candidates}: "
                f"{event_date} {text}"
            )
        return candidates[0]

    for event in events:
        event_date = str(event.get("date", ""))
        if not ("2026-06-01" <= event_date <= "2026-12-31"):
            continue
        if event.get("status") not in statuses or event_date == "2026-06-03":
            continue
        text = str(event.get("text", ""))
        if (
            PROPOSED_AVAILABILITY_RE.search(text)
            or CANCELLED_RE.search(text)
            or not is_garetts(event)
        ):
            continue
        interval = event_interval(text)
        if interval is None:
            raise ValueError(f"No time range for expected payment: {event_date} {text}")
        category = event.get("category")
        if category in {"erb", "methodist"}:
            group = payment_group(event)
            erb_by_group[group][event_date].append(interval)
        elif category == "ymca":
            sen_by_month[event_date[:7]][event_date].append(interval)

    rows = []
    for group, dates in erb_by_group.items():
        context = context_by_group[group]
        minutes = sum(merge_minutes(intervals) for intervals in dates.values())
        full_end = date.fromisoformat(context["full_course_end"])
        rows.append({
            "kind": "ERB",
            "label": context["label"],
            "course_name": context["course_name"],
            "provider": context["provider"],
            "service_period": f'{min(dates)} to {max(dates)}',
            "invoice_date": full_end.isoformat(),
            "expected_payment_date": (full_end + timedelta(days=21)).isoformat(),
            "basis": "全班最後一課後開單；按 Calvin 所述以 3 星期規劃",
            "hours": minutes / 60,
            "amount": minutes / 60 * 300,
        })

    for month_key, dates in sen_by_month.items():
        year, month = (int(value) for value in month_key.split("-"))
        month_end = date(year, month, calendar.monthrange(year, month)[1])
        minutes = sum(merge_minutes(intervals) for intervals in dates.values())
        rows.append({
            "kind": "SEN",
            "label": f"YMCA SEN · {month_end.strftime('%B %Y')}",
            "course_name": "特殊教育需要支援課程",
            "provider": "YMCA",
            "service_period": f'{min(dates)} to {max(dates)}',
            "invoice_date": month_end.isoformat(),
            "expected_payment_date": (month_end + timedelta(days=7)).isoformat(),
            "basis": "月結後開單；約 1 星期",
            "hours": minutes / 60,
            "amount": minutes / 60 * 300,
        })

    rows.sort(key=lambda row: (row["expected_payment_date"], row["kind"], row["label"]))
    return {
        "rows": rows,
        "dated_total": sum(row["amount"] for row in rows),
        "undated": [{
            "kind": "DGS",
            "label": "DGS",
            "amount": DGS_FINAL_TOTAL,
            "reason": "尚未提供可開單日／到賬週期，暫不推算日期。",
        }],
    }


def build_report(
    item: dict,
    events: list[dict],
    payment_context: list[dict] | None = None,
) -> dict:
    revised_rules = item["id"] >= REVISED_SALARY_RULES_FROM
    notes = [
        "Only Garett's lessons are counted; YMCA SEN and DGS are treated as Garett's lessons.",
        "June 3, Mike Sir, cancelled lessons, holidays, and other teachers are excluded.",
        "Overlapping time ranges on the same date are merged to prevent double payment.",
    ]
    if revised_rules:
        notes.append("DGS is counted as the final agreed flat total of HKD 7,000.")
        if item["id"] < "2026-07-21-V18n":
            notes.append(
                "Confirmed + unconfirmed includes HK280HS SS once as an 18-hour pending course (HKD 5,400); its five availability placeholders are not five separate 18-hour courses."
            )
        elif any(
            event.get("status") == "unconfirmed"
            and PROPOSED_AVAILABILITY_RE.search(str(event.get("text", "")))
            and HK280HS_SS_RE.search(str(event.get("text", "")))
            for event in events
        ):
            notes.append(
                "Confirmed + unconfirmed includes HK280HS SS once as an 18-hour pending course; its five availability placeholders are not five separate courses."
            )
    notes.append(
        "The June 18 afternoon SEN entry is included because the source says black rain but does not say cancelled."
    )
    report = {
        "name": "Garett Wong",
        "period": "June to December 2026",
        "generated": item["id"][:10],
        "version": item["label"],
        "version_id": item["id"],
        "rates": {
            "ERB and SEN": "HKD 300/hour",
            "DGS": "HKD 7,000 final flat total" if revised_rules else "HKD 900/hour, 4 hours/day",
        },
        "confirmed": calculate(events, {"confirmed"}, revised_rules),
        "confirmed_and_unconfirmed": calculate(events, {"confirmed", "unconfirmed"}, revised_rules),
        "notes": notes,
    }
    if payment_context:
        report["confirmed"]["expected_payments"] = calculate_expected_payments(
            events, {"confirmed"}, payment_context
        )
        report["confirmed_and_unconfirmed"]["expected_payments"] = (
            calculate_expected_payments(
                events, {"confirmed", "unconfirmed"}, payment_context
            )
        )
        report["notes"].extend([
            "ERB 預計到賬日以全班最後一課後 21 個曆日規劃；Calvin 說的是 3 星期內，因此實際可能較早或受會計處理影響。",
            "SEN 預計到賬日以每月最後一日後 7 個曆日規劃。",
            "DGS 只有 HKD 7,000 最終總額，未有到賬週期，因此不列入有日期的預計到賬合計。",
        ])
    return report


SELECTOR_PAGE = Template(r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" content="noindex,nofollow,noarchive"><meta name="referrer" content="no-referrer"><meta http-equiv="Cache-Control" content="no-cache,no-store,must-revalidate"><meta name="theme-color" content="#0f7074"><link rel="icon" href="../favicon-32.png"><title>Private salary versions</title>
<style>
:root{--ink:#1d2734;--muted:#667387;--line:#d7dee8;--paper:#fff;--bg:#eef1f6;--teal:#0f7074;--orange:#f2a33a;--red:#b42318}*{box-sizing:border-box}html{background:var(--bg);color:var(--ink);font:15px/1.4 "Segoe UI",Arial,sans-serif;letter-spacing:0}body{margin:0;min-height:100vh}header{background:#fff;border-top:6px solid var(--teal);border-bottom:1px solid var(--line)}.bar,main{max-width:980px;margin:auto;padding-left:20px;padding-right:20px}.bar{padding-top:18px;padding-bottom:18px;display:flex;align-items:center;gap:14px}.mark{width:48px;height:48px;border-radius:8px;background:var(--teal);display:grid;place-items:center;color:#fff;font-size:22px;font-weight:900;box-shadow:inset 0 9px 0 var(--orange)}.copy{flex:1;min-width:0}h1{font-size:23px;line-height:1.15;margin:0}.sub{color:var(--muted);margin:4px 0 0}.nav{display:flex;gap:7px}.nav a{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:8px 12px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--ink);font:inherit;font-weight:800;text-decoration:none;white-space:nowrap}.nav a:hover,.nav a:focus-visible{background:#e9f5f4;outline:0}main{padding-top:24px;padding-bottom:48px}h2{font-size:13px;text-transform:uppercase;color:var(--muted);margin:0 0 10px}.versions{border:1px solid var(--line);background:var(--paper);border-radius:8px;overflow:hidden}.version{width:100%;min-height:78px;padding:14px 16px;display:flex;align-items:center;gap:14px;border:0;border-bottom:1px solid var(--line);background:#fff;color:inherit;text-align:left;font:inherit;cursor:pointer}.version:last-child{border-bottom:0}.version:hover,.version:focus-visible{background:#f5faf9;outline:0}.version-main{display:flex;align-items:center;gap:9px;flex:1;min-width:0;flex-wrap:wrap}.version strong{font-size:17px}.version small{flex-basis:100%;color:var(--muted);font-size:13px}.latest{background:var(--teal);color:#fff;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:800}.open{font-size:28px;color:var(--teal)}.hidden{display:none}@media(max-width:620px){.bar{padding:14px 12px;align-items:flex-start;flex-wrap:wrap}.mark{width:42px;height:42px}.copy{width:calc(100% - 58px)}h1{font-size:20px}.nav{width:100%}.nav a{width:100%}main{padding:18px 12px 36px}.version{padding:13px 12px}.version strong{font-size:16px}}
</style></head><body><div id="app" class="hidden"><header><div class="bar"><div class="mark" aria-hidden="true">&#36;</div><div class="copy"><h1>Garett's Salary</h1><p class="sub">Select a saved timetable version.</p></div></div></header><main><h2>Salary Versions</h2><div class="versions">$version_rows</div></main></div>
<script>
const STORAGE_KEY='garetts-erb-earnings-key-v1';
const dec=s=>{s=s.replace(/-/g,'+').replace(/_/g,'/');while(s.length%4)s+='=';return Uint8Array.from(atob(s),c=>c.charCodeAt(0))};
function candidate(){const hash=location.hash.slice(1);const fromHash=hash.replace(/^key=/,'');return fromHash||localStorage.getItem(STORAGE_KEY)||''}
async function decrypt(path,raw){const key=await crypto.subtle.importKey('raw',dec(raw),'AES-GCM',false,['decrypt']);const enc=await fetch(path,{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('Missing encrypted report');return r.json()});const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:dec(enc.nonce),additionalData:new TextEncoder().encode('erb-earnings-v1')},key,dec(enc.ciphertext));return JSON.parse(new TextDecoder().decode(plain))}
async function start(){const raw=candidate();if(!raw){location.replace('../master/?v=redtext1');return}try{await decrypt('versions/$latest_id/earnings.enc.json',raw);localStorage.setItem(STORAGE_KEY,raw);document.getElementById('app').classList.remove('hidden');document.querySelectorAll('[data-version]').forEach(button=>button.addEventListener('click',()=>location.assign('versions/'+button.dataset.version+'/#key='+raw)))}catch(error){location.replace('../master/?v=redtext1')}}
start();window.addEventListener('hashchange',start);
</script></body></html>''')


REPORT_PAGE = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover"><meta name="robots" content="noindex,nofollow,noarchive"><meta name="referrer" content="no-referrer"><meta http-equiv="Cache-Control" content="no-cache,no-store,must-revalidate"><meta name="theme-color" content="#0f7074"><link rel="icon" href="../../../favicon-32.png"><title>Private salary report</title>
<style>
:root{--ink:#1d2734;--muted:#667387;--line:#d7dee8;--paper:#fff;--bg:#eef1f6;--teal:#0f7074;--orange:#f2a33a;--red:#b42318}*{box-sizing:border-box}html{background:var(--bg);color:var(--ink);font:15px/1.4 "Segoe UI",Arial,sans-serif;letter-spacing:0}body{margin:0}header{background:#fff;border-bottom:1px solid var(--line);border-top:6px solid var(--teal)}.bar,main{max-width:1040px;margin:auto;padding-left:20px;padding-right:20px}.bar{padding-top:18px;padding-bottom:18px;display:flex;align-items:center;gap:14px}.copy{flex:1;min-width:0}h1{font-size:24px;margin:0}.sub{color:var(--muted);margin:4px 0 0}.nav{display:flex;gap:7px}.nav a{display:inline-flex;align-items:center;justify-content:center;min-height:40px;padding:8px 12px;border:1px solid var(--line);border-radius:6px;background:#fff;color:var(--ink);font:inherit;font-weight:800;text-decoration:none;white-space:nowrap}.nav a:hover,.nav a:focus-visible{background:#e9f5f4;outline:0}.modes{display:flex;gap:6px;margin:22px 0 14px}.modes button{border:1px solid var(--line);background:#fff;color:var(--ink);padding:9px 12px;border-radius:6px;font:inherit;font-weight:700}.modes button.active{background:var(--teal);border-color:var(--teal);color:#fff}.summary{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));border:1px solid var(--line);background:#fff;border-radius:8px;margin-bottom:16px}.metric{padding:15px;border-right:1px solid var(--line)}.metric:last-child{border-right:0}.metric small{display:block;color:var(--muted);font-weight:700}.metric strong{display:block;font-size:24px;margin-top:4px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff}table{width:100%;border-collapse:collapse;min-width:720px}th,td{text-align:right;padding:11px 12px;border-bottom:1px solid var(--line)}th{font-size:12px;color:var(--muted);background:#f7f9fb}th:first-child,td:first-child{text-align:left}tbody tr:last-child td{border-bottom:0}td.total{font-weight:850;color:var(--teal)}.notes{margin:18px 0 40px;color:var(--muted)}.notes h2{font-size:14px;color:var(--ink)}.notes li{margin:5px 0}.hidden{display:none}@media(max-width:620px){.bar,main{padding-left:12px;padding-right:12px}.bar{align-items:flex-start;flex-wrap:wrap}.copy{width:100%}.nav{width:100%}.nav a{width:100%}.summary{grid-template-columns:1fr}.metric{border-right:0;border-bottom:1px solid var(--line)}.metric:last-child{border-bottom:0}.metric strong{font-size:21px}.modes{display:grid;grid-template-columns:1fr 1fr}.modes button{padding:10px 6px;font-size:13px}}
</style>
<style>
.bar,main{max-width:1120px}.expected{margin-top:22px}.expected-head{display:flex;align-items:end;justify-content:space-between;gap:14px;margin-bottom:9px}.expected h2{font-size:18px;margin:0}.expected-head p{margin:0;color:var(--muted);font-size:12px}.expected-table{min-width:900px}.expected-table th,.expected-table td{text-align:left;vertical-align:top}.expected-table th:last-child,.expected-table td:last-child{text-align:right}.pay-kind{display:inline-block;min-width:38px;margin-right:7px;padding:2px 5px;border-radius:4px;background:var(--teal);color:#fff;font-size:10px;font-weight:900;text-align:center}.pay-kind.sen{background:#247e9b}.pay-label{font-weight:850}.pay-course{display:block;color:var(--muted);font-size:11px}.pay-date{font-weight:850;color:var(--teal);white-space:nowrap}.pay-basis{color:var(--muted);font-size:11px}.undated{margin-top:9px;padding:10px 12px;border:1px solid #e8c78f;border-radius:7px;background:#fff7e8;color:#7d4d00;font-size:12px}@media(max-width:620px){.expected-head{display:block}.expected-head p{margin-top:4px}.expected .table-wrap{overflow:visible;border:0;background:transparent}.expected-table{display:block;min-width:0}.expected-table thead{display:none}.expected-table tbody{display:grid;gap:8px}.expected-table tr{display:grid;grid-template-columns:1fr 1fr;gap:8px 12px;padding:10px;border:1px solid var(--line);border-radius:7px;background:#fff}.expected-table td{display:block;padding:0!important;border:0!important;text-align:left!important}.expected-table td:first-child{grid-column:1/-1}.expected-table td::before{display:block;margin-bottom:2px;color:var(--muted);font-size:9px;font-weight:850;text-transform:uppercase}.expected-table td:nth-child(2)::before{content:"可開單日"}.expected-table td:nth-child(3)::before{content:"預計到賬日"}.expected-table td:nth-child(4)::before{content:"計算依據"}.expected-table td:nth-child(5)::before{content:"金額"}.expected-table td:nth-child(5){font-size:15px}.pay-course{margin-top:2px}}
</style></head><body><div id="app" class="hidden"><header><div class="bar"><div class="copy"><h1 id="title"></h1><p class="sub" id="subtitle"></p></div><div class="nav"><a href="../../">Versions</a></div></div></header><main><div class="modes"><button type="button" data-mode="confirmed" class="active">Confirmed</button><button type="button" data-mode="confirmed_and_unconfirmed">Confirmed + unconfirmed</button></div><section class="summary"><div class="metric"><small>Total earnings</small><strong id="grand"></strong></div><div class="metric"><small>Counted source entries</small><strong id="events"></strong></div></section><div class="table-wrap"><table><thead><tr><th>Month</th><th>ERB/SEN hours</th><th>ERB/SEN pay</th><th>DGS hours</th><th>DGS pay</th><th>Total</th></tr></thead><tbody id="rows"></tbody></table></div><section class="expected"><div class="expected-head"><h2>預計薪酬到賬日</h2><p>ERB：全班完結後 21 日；SEN：月結後 7 日。這是規劃日期，並非會計保證日期。</p></div><div class="table-wrap"><table class="expected-table"><thead><tr><th>課程／月份</th><th>可開單日</th><th>預計到賬日</th><th>計算依據</th><th>金額</th></tr></thead><tbody id="expectedRows"></tbody></table></div><div id="undated" class="undated" hidden></div></section><section class="notes"><h2>Calculation rules</h2><ul id="notes"></ul></section></main></div>
<script>
const STORAGE_KEY='garetts-erb-earnings-key-v1';
const dec=s=>{s=s.replace(/-/g,'+').replace(/_/g,'/');while(s.length%4)s+='=';return Uint8Array.from(atob(s),c=>c.charCodeAt(0))};
const money=n=>new Intl.NumberFormat('en-HK',{style:'currency',currency:'HKD',maximumFractionDigits:0}).format(n);
const hours=n=>Number.isInteger(n)?String(n):n.toFixed(2).replace(/0+$/,'').replace(/\.$/,'');
function candidate(){const hash=location.hash.slice(1);const fromHash=hash.replace(/^key=/,'');return fromHash||localStorage.getItem(STORAGE_KEY)||''}
async function start(){
  try{
    const raw=candidate();
    if(!raw){location.replace('../../');return}
    const key=await crypto.subtle.importKey('raw',dec(raw),'AES-GCM',false,['decrypt']);
    const enc=await fetch('earnings.enc.json',{cache:'no-store'}).then(r=>{if(!r.ok)throw new Error('Missing encrypted report');return r.json()});
    const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:dec(enc.nonce),additionalData:new TextEncoder().encode('erb-earnings-v1')},key,dec(enc.ciphertext));
    const data=JSON.parse(new TextDecoder().decode(plain));
    const esc=x=>String(x||'').replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]));
    localStorage.setItem(STORAGE_KEY,raw);
    document.getElementById('app').classList.remove('hidden');
    document.getElementById('title').textContent=data.name+' - Salary';
    document.getElementById('subtitle').textContent=data.period+' · '+data.version+' · Updated '+data.generated;
    document.getElementById('notes').innerHTML=data.notes.map(x=>'<li>'+esc(x)+'</li>').join('');
    function render(mode){
      const d=data[mode];
      document.getElementById('grand').textContent=money(d.grand_total);
      document.getElementById('events').textContent=d.counted_events;
      document.getElementById('rows').innerHTML=d.months.map(r=>'<tr><td>'+r.month+'</td><td>'+hours(r.regular_hours)+'</td><td>'+money(r.regular_pay)+'</td><td>'+hours(r.dgs_hours)+'</td><td>'+money(r.dgs_pay)+'</td><td class="total">'+money(r.total)+'</td></tr>').join('');
      const schedule=d.expected_payments||{rows:[],undated:[]};
      document.getElementById('expectedRows').innerHTML=schedule.rows.map(r=>'<tr><td><span class="pay-kind '+(r.kind==='SEN'?'sen':'')+'">'+esc(r.kind)+'</span><span class="pay-label">'+esc(r.label)+'</span><span class="pay-course">'+esc(r.course_name)+'</span></td><td>'+esc(r.invoice_date)+'</td><td class="pay-date">'+esc(r.expected_payment_date)+'</td><td><span class="pay-basis">'+esc(r.basis)+'</span><br>'+hours(r.hours)+' hours</td><td class="total">'+money(r.amount)+'</td></tr>').join('')||'<tr><td colspan="5">This saved version has no payment-date projection.</td></tr>';
      const undated=document.getElementById('undated');
      undated.hidden=!schedule.undated.length;
      undated.innerHTML=schedule.undated.map(r=>'<strong>'+esc(r.label)+': '+money(r.amount)+'</strong> · '+esc(r.reason)).join('<br>');
      document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode));
    }
    document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>render(b.dataset.mode));
    render('confirmed');
  }catch(error){location.replace('../../')}
}
start();
</script></body></html>'''


def version_row(item: dict) -> str:
    latest = '<span class="latest">Latest</span>' if item.get("latest") else ""
    return (
        f'<button class="version" type="button" data-version="{html.escape(item["id"], quote=True)}">'
        f'<span class="version-main"><strong>{html.escape(item["label"])}</strong>{latest}'
        f'<small>{html.escape(item["summary"])}</small></span>'
        f'<span class="open" aria-hidden="true">&rsaquo;</span></button>'
    )


def load_or_create_key() -> bytes:
    if KEY_FILE.exists():
        stored = KEY_FILE.read_text(encoding="ascii").strip()
        return base64.urlsafe_b64decode(stored + "=" * (-len(stored) % 4))
    key = AESGCM.generate_key(bit_length=256)
    KEY_FILE.write_text(encode(key), encoding="ascii")
    return key


def main() -> None:
    key = load_or_create_key()
    OUT.mkdir(exist_ok=True)
    versions_out = OUT / "versions"
    versions_out.mkdir(exist_ok=True)
    totals: dict[str, dict[str, float]] = {}
    latest_payload = None

    for item in VERSIONS:
        source = ROOT / "versions" / item["id"] / "events.json"
        if not source.exists():
            raise FileNotFoundError(f"Missing version event ledger: {source}")
        events = json.loads(source.read_text(encoding="utf-8"))
        context_source = ROOT / "versions" / item["id"] / "class_context.json"
        if context_source.exists():
            context_events = json.loads(context_source.read_text(encoding="utf-8"))
            for event in context_events:
                if "category" not in event:
                    text = str(event.get("text", ""))
                    event["category"] = "methodist" if "循道" in text or "MC0106" in text else "erb"
            events.extend(context_events)
        payment_context_source = (
            ROOT / "versions" / item["id"] / "payment_context.json"
        )
        payment_context = (
            json.loads(payment_context_source.read_text(encoding="utf-8"))
            if payment_context_source.exists()
            else None
        )
        report = build_report(item, events, payment_context)
        destination = versions_out / item["id"]
        destination.mkdir(exist_ok=True)
        encrypted_report = destination / "earnings.enc.json"
        if encrypted_report.exists():
            payload = json.loads(encrypted_report.read_text(encoding="utf-8"))
            try:
                saved_report = decrypt_report(payload, key)
            except (KeyError, ValueError):
                saved_report = None
            if saved_report != report:
                payload = encrypt_report(report, key)
                encrypted_report.write_text(
                    json.dumps(payload, separators=(",", ":")), encoding="utf-8"
                )
        else:
            payload = encrypt_report(report, key)
            encrypted_report.write_text(
                json.dumps(payload, separators=(",", ":")), encoding="utf-8"
            )
        report_page = destination / "index.html"
        if payment_context or not report_page.exists():
            report_page.write_text(REPORT_PAGE, encoding="utf-8")
        totals[item["id"]] = {
            "confirmed": report["confirmed"]["grand_total"],
            "confirmed_and_unconfirmed": report["confirmed_and_unconfirmed"]["grand_total"],
        }
        if item.get("latest"):
            latest_payload = payload

    latest = next(item for item in VERSIONS if item.get("latest"))
    rows = "".join(version_row(item) for item in VERSIONS)
    selector = SELECTOR_PAGE.substitute(version_rows=rows, latest_id=latest["id"])
    (OUT / "index.html").write_text(selector, encoding="utf-8")
    (OUT / "versions.json").write_text(
        json.dumps(VERSIONS, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    if latest_payload is None:
        raise ValueError("versions.json has no latest earnings version")
    (OUT / "earnings.enc.json").write_text(
        json.dumps(latest_payload, separators=(",", ":")), encoding="utf-8"
    )

    print(OUT)
    print("PRIVATE_URL_FRAGMENT=" + encode(key))
    print(json.dumps(totals, indent=2))


if __name__ == "__main__":
    main()
