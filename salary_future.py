"""User-selected provisional courses included in the private future-income view."""
import json
from pathlib import Path

INCLUSIONS = Path(r"D:\Garett Super Jobs 2026\Calvin\REAL ERB\Invoice\salary_future_inclusions.json")


def add_future_income_estimates(report):
    if not INCLUSIONS.exists():
        return
    settings = json.loads(INCLUSIONS.read_text(encoding="utf-8"))
    estimates = []
    seen = set()
    for selected in settings["courses"]:
        identifier = selected["id"]
        if identifier in seen:
            raise ValueError(f"Duplicate future-income selection: {identifier}")
        seen.add(identifier)
        if report["version_id"] < selected["start_version"]:
            continue
        matches = [r for r in report.get("pending_courses", []) if r["id"] == identifier]
        if not matches:
            continue  # A confirmed course is already represented by confirmed income.
        if len(matches) != 1 or matches[0]["amount"] is None:
            raise ValueError(f"Ambiguous future-income estimate: {identifier}")
        course = matches[0]
        deduction = sum(r["amount_hkd"] for r in report["confirmed_and_unconfirmed"].get("overlap_adjustments", [])
                        if identifier in r.get("courses", []))
        amount = course["amount"] - deduction
        if not 0 <= amount <= course["amount"]:
            raise ValueError(f"Invalid future-income deduction: {identifier}")
        estimates.append({"id": identifier, "label": course["label"], "amount": amount,
                          "gross_amount": course["amount"], "overlap_deduction": deduction,
                          "dates": course["dates"], "hours": course["hours"], "rate": course["rate"],
                          "basis": course["basis"], "status": "provisional"})
    report["future_income_estimates"] = estimates
