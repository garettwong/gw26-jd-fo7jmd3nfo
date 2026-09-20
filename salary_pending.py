"""Explicit pending-work scenarios; never treated as confirmed cash receipts."""
import copy
import json
from pathlib import Path


def add_pending_estimates(report, events, version_id, event_interval):
    configurations = sorted(p for p in Path(__file__).with_name("salary_estimates").glob("*.json") if p.stem <= version_id)
    if not configurations:
        return
    source = configurations[-1]
    courses = json.loads(source.read_text(encoding="utf-8"))["courses"]
    pending = []
    combined = copy.deepcopy(report["confirmed"])
    allocations = []
    for course in courses:
        lessons = [e for e in events if e.get("status") == "unconfirmed"
                   and course["match"] in e.get("text", "")
                   and e.get("teacher") in {"Garett", "Garrett"}]
        if not lessons:
            continue
        hours = 0
        for event in lessons:
            interval = event_interval(event["text"])
            duration = (interval[1] - interval[0]) / 60 if interval else course.get("hours_per_lesson")
            if duration is None:
                raise ValueError(f"Missing provisional hours: {course['id']}")
            hours += duration
            if course["hourly_rate"] is not None:
                allocations.append((event["date"], duration, duration * course["hourly_rate"]))
        rate = course["hourly_rate"]
        pending.append({"id": course["id"], "label": course["label"], "lesson_count": len(lessons),
                        "dates": sorted(e["date"] for e in lessons), "hours": hours, "rate": rate,
                        "amount": hours * rate if rate is not None else None, "basis": course["basis"]})
    for day, hours, amount in allocations:
        row = combined["months"][int(day[5:7]) - 6]
        row["regular_hours"] += hours
        row["regular_pay"] += amount
        row["total"] += amount
    combined["grand_total"] += sum(amount for _, _, amount in allocations)
    combined["counted_events"] += len(allocations)
    report["confirmed_and_unconfirmed"] = combined
    report["pending_courses"] = pending
    report["unpriced_courses"] = []
    report["notes"].append("待確認收入是各擬任教課程的獨立估算；有撞期的工作不能同時履行，不代表保證收入、已交單或已收款。未定價課程不當作零元。")
