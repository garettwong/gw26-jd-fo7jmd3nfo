"""Add explicitly confirmed invoice work without changing teaching lessons.

Only descriptions, dates, hours and amounts enter encrypted salary payloads.
Source paths, email IDs and bank details stay in the private delivery register.
"""
from datetime import date
from decimal import Decimal


def _number(value):
    if isinstance(value, bool):
        raise ValueError("Invalid extra-work number")
    number = Decimal(str(value))
    if not number.is_finite() or number <= 0:
        raise ValueError("Extra-work numbers must be finite and positive")
    return number


def apply_extra_work(mode, row, delivery):
    items = delivery.get("additional_work", [])
    if not items:
        return
    clean = []
    for item in items:
        if item.get("confirmation_status") != "confirmed_by_user":
            raise ValueError("Unconfirmed additional invoice work")
        when = date.fromisoformat(item["date"]).isoformat()
        if when > delivery["invoice_date"]:
            raise ValueError("Additional work occurs after invoice date")
        description = item["description"].strip()
        if not description:
            raise ValueError("Missing extra-work description")
        hours, rate, amount = (_number(item[k]) for k in
                              ("hours", "rate_hkd_per_hour", "amount_hkd"))
        if hours * rate != amount:
            raise ValueError("Extra-work hours/rate/amount mismatch")
        clean.append({"description": description, "date": when,
                      "hours": float(hours), "rate": float(rate), "amount": float(amount)})
    if len({(r["date"], r["description"]) for r in clean}) != len(clean):
        raise ValueError("Duplicate additional work")
    teaching_hours = _number(delivery["teaching_hours"])
    teaching_amount = _number(delivery["teaching_amount_hkd"])
    extra_hours = sum(Decimal(str(r["hours"])) for r in clean)
    extra_amount = sum(Decimal(str(r["amount"])) for r in clean)
    if teaching_hours + extra_hours != _number(delivery["hours"]) or teaching_amount + extra_amount != _number(delivery["amount_hkd"]):
        raise ValueError("Teaching and additional work do not reconcile to invoice")
    if row.get("additional_work"):
        if (row["additional_work"] != clean or row["amount"] != delivery["amount_hkd"]
                or row["hours"] != delivery["hours"]):
            raise ValueError("Previously applied additional work differs")
        return
    if _number(row["hours"]) != teaching_hours or _number(row["amount"]) != teaching_amount:
        raise ValueError("Original teaching hours/amount differ from invoice")
    def month_name(when):
        value = date.fromisoformat(when)
        return value.strftime("%B") if value.year == 2026 else value.strftime("%B %Y")
    months = {m["month"]: m for m in mode["months"]}
    if any(month_name(r["date"]) not in months for r in clean):
        raise ValueError("Additional work month absent from salary report")
    row.update(teaching_hours=float(teaching_hours), teaching_amount=float(teaching_amount),
               additional_work=clean, hours=float(teaching_hours + extra_hours),
               amount=float(teaching_amount + extra_amount))
    for item in clean:
        month = months[month_name(item["date"])]
        month["additional_work_hours"] = month.get("additional_work_hours", 0) + item["hours"]
        month["additional_work_pay"] = month.get("additional_work_pay", 0) + item["amount"]
        month["total"] += item["amount"]
    mode["grand_total"] += float(extra_amount)
