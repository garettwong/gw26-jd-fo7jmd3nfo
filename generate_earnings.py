from __future__ import annotations

import base64
import json
import os
import re
from collections import defaultdict
from datetime import date
from pathlib import Path

from cryptography.hazmat.primitives.ciphers.aead import AESGCM


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "earnings"
KEY_FILE = ROOT / "private_earnings_key.txt"
EVENTS = json.loads((ROOT / "events.json").read_text(encoding="utf-8"))
TIME_RE = re.compile(r"(?<!\d)(\d{1,2})(?::?(\d{2}))?\s*(?:[AaPp][Mm])?\s*[-–]\s*(\d{1,2})(?::?(\d{2}))?\s*(?:[AaPp][Mm])?(?!\d)")
CANCELLED_RE = re.compile(r"cancel(?:led|ed)", re.I)
GARETT_RE = re.compile(r"\bGar(?:e|r)tt\b", re.I)
MONTHS = ("June", "July", "August", "September", "October", "November", "December")


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
        return bool(GARETT_RE.search(event["text"] + " " + str(event.get("teacher", ""))))
    return False


def merge_minutes(intervals: list[tuple[int, int]]) -> int:
    merged: list[list[int]] = []
    for start, end in sorted(intervals):
        if merged and start <= merged[-1][1]:
            merged[-1][1] = max(merged[-1][1], end)
        else:
            merged.append([start, end])
    return sum(end - start for start, end in merged)


def calculate(statuses: set[str]) -> dict:
    regular_by_date: dict[str, list[tuple[int, int]]] = defaultdict(list)
    dgs_dates: set[str] = set()
    counted_events = 0
    for event in EVENTS:
        event_date = event["date"]
        if not ("2026-06-01" <= event_date <= "2026-12-31"):
            continue
        if event["status"] not in statuses or event_date == "2026-06-03":
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

    rows = []
    grand_total = 0
    for month_number, month_name in enumerate(MONTHS, 6):
        regular_minutes = sum(
            merge_minutes(intervals)
            for event_date, intervals in regular_by_date.items()
            if int(event_date[5:7]) == month_number
        )
        regular_hours = regular_minutes / 60
        dgs_days = sum(int(event_date[5:7]) == month_number for event_date in dgs_dates)
        dgs_hours = dgs_days * 4
        regular_pay = regular_hours * 300
        dgs_pay = dgs_hours * 900
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


if KEY_FILE.exists():
    key = base64.urlsafe_b64decode(KEY_FILE.read_text(encoding="ascii").strip() + "==")
else:
    key = AESGCM.generate_key(bit_length=256)
    KEY_FILE.write_text(encode(key), encoding="ascii")

report = {
    "name": "Garett Wong",
    "period": "June to December 2026",
    "generated": date.today().isoformat(),
    "version": "2026-07-14 - V05b",
    "rates": {"ERB and SEN": "HKD 300/hour", "DGS": "HKD 900/hour, 4 hours/day"},
    "confirmed": calculate({"confirmed"}),
    "confirmed_and_unconfirmed": calculate({"confirmed", "unconfirmed"}),
    "notes": [
        "Only Garett's lessons are counted; YMCA SEN and DGS are treated as Garett's lessons.",
        "June 3, Mike Sir, cancelled lessons, holidays, and other teachers are excluded.",
        "Overlapping time ranges on the same date are merged to prevent double payment.",
        "The June 18 afternoon SEN entry is included because the source says black rain but does not say cancelled.",
    ],
}
plaintext = json.dumps(report, ensure_ascii=False, separators=(",", ":")).encode("utf-8")
nonce = os.urandom(12)
ciphertext = AESGCM(key).encrypt(nonce, plaintext, b"erb-earnings-v1")
OUT.mkdir(exist_ok=True)
(OUT / "earnings.enc.json").write_text(json.dumps({
    "version": 1,
    "nonce": encode(nonce),
    "ciphertext": encode(ciphertext),
}), encoding="utf-8")

page = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="robots" content="noindex,nofollow,noarchive"><meta name="referrer" content="no-referrer"><meta name="theme-color" content="#0f7074"><title>Private earnings</title>
<style>
:root{--ink:#1d2734;--muted:#667387;--line:#d7dee8;--paper:#fff;--bg:#eef1f6;--teal:#0f7074;--orange:#f2a33a;--red:#b42318}*{box-sizing:border-box}html{background:var(--bg);color:var(--ink);font:15px/1.4 "Segoe UI",Arial,sans-serif;letter-spacing:0}body{margin:0}header{background:#fff;border-bottom:1px solid var(--line);border-top:6px solid var(--teal)}.bar,main{max-width:1040px;margin:auto;padding-left:20px;padding-right:20px}.bar{padding-top:18px;padding-bottom:18px}h1{font-size:24px;margin:0}.sub{color:var(--muted);margin:4px 0 0}.modes{display:flex;gap:6px;margin:22px 0 14px}.modes button{border:1px solid var(--line);background:#fff;color:var(--ink);padding:9px 12px;border-radius:6px;font:inherit;font-weight:700}.modes button.active{background:var(--teal);border-color:var(--teal);color:#fff}.summary{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));border:1px solid var(--line);background:#fff;border-radius:8px;margin-bottom:16px}.metric{padding:15px;border-right:1px solid var(--line)}.metric:last-child{border-right:0}.metric small{display:block;color:var(--muted);font-weight:700}.metric strong{display:block;font-size:24px;margin-top:4px}.table-wrap{overflow:auto;border:1px solid var(--line);border-radius:8px;background:#fff}table{width:100%;border-collapse:collapse;min-width:720px}th,td{text-align:right;padding:11px 12px;border-bottom:1px solid var(--line)}th{font-size:12px;color:var(--muted);background:#f7f9fb}th:first-child,td:first-child{text-align:left}tbody tr:last-child td{border-bottom:0}td.total{font-weight:850;color:var(--teal)}.notes{margin:18px 0 40px;color:var(--muted)}.notes h2{font-size:14px;color:var(--ink)}.notes li{margin:5px 0}.locked{max-width:520px;margin:15vh auto;background:#fff;border:1px solid var(--line);border-top:6px solid var(--red);padding:24px;border-radius:8px}.hidden{display:none}@media(max-width:620px){.bar,main{padding-left:12px;padding-right:12px}.summary{grid-template-columns:1fr}.metric{border-right:0;border-bottom:1px solid var(--line)}.metric:last-child{border-bottom:0}.metric strong{font-size:21px}.modes{display:grid;grid-template-columns:1fr 1fr}.modes button{padding:10px 6px;font-size:13px}}
</style></head><body><div id="locked" class="locked"><h1>Private link required</h1><p>This earnings page needs the complete private URL, including the key after <strong>#</strong>.</p></div><div id="app" class="hidden"><header><div class="bar"><h1 id="title"></h1><p class="sub" id="subtitle"></p></div></header><main><div class="modes"><button type="button" data-mode="confirmed" class="active">Confirmed</button><button type="button" data-mode="confirmed_and_unconfirmed">Confirmed + unconfirmed</button></div><section class="summary"><div class="metric"><small>Total earnings</small><strong id="grand"></strong></div><div class="metric"><small>Counted source entries</small><strong id="events"></strong></div><div class="metric"><small>Rates</small><strong style="font-size:15px" id="rates"></strong></div></section><div class="table-wrap"><table><thead><tr><th>Month</th><th>ERB/SEN hours</th><th>ERB/SEN pay</th><th>DGS hours</th><th>DGS pay</th><th>Total</th></tr></thead><tbody id="rows"></tbody></table></div><section class="notes"><h2>Calculation rules</h2><ul id="notes"></ul></section></main></div>
<script>
const dec=s=>{s=s.replace(/-/g,'+').replace(/_/g,'/');while(s.length%4)s+='=';return Uint8Array.from(atob(s),c=>c.charCodeAt(0))};
const money=n=>new Intl.NumberFormat('en-HK',{style:'currency',currency:'HKD',maximumFractionDigits:0}).format(n);
const hours=n=>Number.isInteger(n)?String(n):n.toFixed(2).replace(/0+$/,'').replace(/\.$/,'');
async function start(){try{const raw=location.hash.slice(1).replace(/^key=/,'');if(!raw)return;const key=await crypto.subtle.importKey('raw',dec(raw),'AES-GCM',false,['decrypt']);const enc=await fetch('earnings.enc.json',{cache:'no-store'}).then(r=>r.json());const plain=await crypto.subtle.decrypt({name:'AES-GCM',iv:dec(enc.nonce),additionalData:new TextEncoder().encode('erb-earnings-v1')},key,dec(enc.ciphertext));const data=JSON.parse(new TextDecoder().decode(plain));document.getElementById('locked').remove();document.getElementById('app').classList.remove('hidden');document.getElementById('title').textContent=data.name+' — Earnings';document.getElementById('subtitle').textContent=data.period+' · '+data.version+' · Updated '+data.generated;document.getElementById('rates').textContent=Object.values(data.rates).join(' · ');document.getElementById('notes').innerHTML=data.notes.map(x=>'<li>'+x.replace(/[&<>]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;'}[c]))+'</li>').join('');function render(mode){const d=data[mode];document.getElementById('grand').textContent=money(d.grand_total);document.getElementById('events').textContent=d.counted_events;document.getElementById('rows').innerHTML=d.months.map(r=>`<tr><td>${r.month}</td><td>${hours(r.regular_hours)}</td><td>${money(r.regular_pay)}</td><td>${hours(r.dgs_hours)}</td><td>${money(r.dgs_pay)}</td><td class="total">${money(r.total)}</td></tr>`).join('');document.querySelectorAll('[data-mode]').forEach(b=>b.classList.toggle('active',b.dataset.mode===mode))}document.querySelectorAll('[data-mode]').forEach(b=>b.onclick=()=>render(b.dataset.mode));render('confirmed')}catch(e){document.querySelector('#locked p').textContent='This private link is invalid or the encrypted data could not be opened.'}}start();
</script></body></html>'''
(OUT / "index.html").write_text(page, encoding="utf-8")
print(OUT)
print("PRIVATE_URL_FRAGMENT=" + encode(key))
print(json.dumps({k: v["grand_total"] for k, v in report.items() if isinstance(v, dict) and "grand_total" in v}, indent=2))
