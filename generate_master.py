from __future__ import annotations

import html
import json
import shutil
from pathlib import Path


ROOT = Path(__file__).resolve().parent
OUT = ROOT / "master"
VERSIONS = json.loads((ROOT / "versions.json").read_text(encoding="utf-8"))
OUT.mkdir(exist_ok=True)


def version_row(item: dict) -> str:
    badge = '<span class="latest">Latest</span>' if item.get("latest") else ""
    label = html.escape(item["label"])
    summary = html.escape(item["summary"])
    version_id = html.escape(item["id"], quote=True)
    return f'''<a class="version" href="../versions/{version_id}/?v=redtext1">
      <span class="version-main"><strong>{label}</strong>{badge}<small>{summary}</small></span>
      <span class="open" aria-hidden="true">›</span>
    </a>'''


rows = "\n".join(version_row(item) for item in VERSIONS)
latest = next(item for item in VERSIONS if item.get("latest"))
build = latest["id"]

page = f'''<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1,viewport-fit=cover">
<meta name="theme-color" content="#0f7074">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="default">
<meta name="apple-mobile-web-app-title" content="Garett's ERB">
<link rel="apple-touch-icon" href="icon-180.png">
<link rel="icon" href="favicon-32.png">
<link rel="manifest" href="manifest.webmanifest">
<title>Garett's ERB Timetable</title>
<style>
:root{{--ink:#1d2734;--muted:#667387;--line:#d7dee8;--paper:#fff;--bg:#eef1f6;--teal:#0f7074;--orange:#f2a33a}}
*{{box-sizing:border-box}}html{{background:var(--bg);color:var(--ink);font:16px/1.4 "Segoe UI",Arial,sans-serif;letter-spacing:0}}body{{margin:0;min-height:100vh}}
header{{background:var(--paper);border-bottom:1px solid var(--line)}}.bar{{max-width:980px;margin:auto;padding:18px 20px;display:flex;align-items:center;gap:14px}}.mark{{width:48px;height:48px;border-radius:8px;background:var(--teal);display:grid;place-items:center;color:#fff;font-size:22px;font-weight:900;box-shadow:inset 0 9px 0 var(--orange)}}h1{{font-size:22px;line-height:1.15;margin:0}}header p{{color:var(--muted);margin:3px 0 0;font-size:13px}}
main{{max-width:980px;margin:auto;padding:24px 20px 48px}}h2{{font-size:14px;text-transform:uppercase;color:var(--muted);margin:0 0 10px}}.versions{{border:1px solid var(--line);background:var(--paper);border-radius:8px;overflow:hidden}}.version{{min-height:78px;padding:14px 16px;display:flex;align-items:center;gap:14px;color:inherit;text-decoration:none;border-bottom:1px solid var(--line)}}.version:last-child{{border-bottom:0}}.version:hover,.version:focus-visible{{background:#f5faf9;outline:0}}.version-main{{display:flex;align-items:center;gap:9px;flex:1;min-width:0;flex-wrap:wrap}}.version strong{{font-size:17px}}.version small{{flex-basis:100%;color:var(--muted);font-size:13px}}.latest{{background:var(--teal);color:#fff;border-radius:999px;padding:2px 8px;font-size:11px;font-weight:800}}.open{{font-size:30px;color:var(--teal)}}
@media(max-width:560px){{.bar{{padding:14px 16px}}main{{padding:18px 12px 36px}}.mark{{width:42px;height:42px}}h1{{font-size:19px}}.version{{padding:13px 12px}}.version strong{{font-size:16px}}}}
</style>
</head>
<body>
<header><div class="bar"><div class="mark" aria-hidden="true">G</div><div><h1>Garett's ERB Timetable</h1><p>Select a saved version. The newest version is always first.</p></div></div></header>
<main><h2>Timetable Versions</h2><div class="versions">{rows}</div></main>
<script>
if('serviceWorker' in navigator) window.addEventListener('load',()=>navigator.serviceWorker.register('./sw.js').then(r=>r.update()).catch(()=>{{}}));
</script>
</body>
</html>'''

(OUT / "index.html").write_text(page, encoding="utf-8")
(OUT / "manifest.webmanifest").write_text(json.dumps({
    "id": "./",
    "name": "Garett's ERB Timetable",
    "short_name": "Garett's ERB",
    "description": "Version selector for Garett's ERB timetable",
    "start_url": "./",
    "scope": "./",
    "display": "standalone",
    "background_color": "#eef1f6",
    "theme_color": "#0f7074",
    "icons": [
        {"src": "icon-192.png", "sizes": "192x192", "type": "image/png", "purpose": "any maskable"},
        {"src": "icon-512.png", "sizes": "512x512", "type": "image/png", "purpose": "any maskable"},
    ],
}, indent=2), encoding="utf-8")
(OUT / "sw.js").write_text(f'''const CACHE='erb-master-{build}';
self.addEventListener('install',event=>{{self.skipWaiting();}});
self.addEventListener('activate',event=>{{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.map(key=>caches.delete(key)))).then(()=>self.clients.claim()));}});
self.addEventListener('fetch',event=>{{if(event.request.method==='GET')event.respondWith(fetch(new Request(event.request,{{cache:'no-store'}})).catch(()=>fetch(event.request)));}});
''', encoding="utf-8")
for filename in ("favicon-32.png", "icon-180.png", "icon-192.png", "icon-512.png"):
    shutil.copy2(ROOT / filename, OUT / filename)
print(OUT)
