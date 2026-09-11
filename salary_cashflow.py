"""Reconcile the latest encrypted salary snapshot with the local invoice ledger.

Only sanitized status fields enter the encrypted payload. Never publish the
register, email identifiers, bank information, or local evidence paths.
"""
import json
from datetime import date, timedelta
from pathlib import Path

REGISTER = Path(r"D:\Garett Super Jobs 2026\Calvin\REAL ERB\Invoice\invoice_delivery_register.json")


def reconcile_current(report, contexts):
    ledger = json.loads(REGISTER.read_text(encoding="utf-8-sig"))
    reconciliation = ledger["payment_reconciliation"]
    as_of = reconciliation["as_of"]
    by_group = {r["group"]: r for r in ledger["deliveries"]}
    paid = {r["course_instance"]: r for r in reconciliation["confirmed_received"]}
    contexts = {r["group"]: r for r in contexts}
    for mode in ("confirmed", "confirmed_and_unconfirmed"):
        schedule = report[mode]["expected_payments"]
        for row in schedule["rows"]:
            if row["kind"] != "ERB":
                row["invoice_status"] = "已收款（既有確認記錄）" if row.get("received") else "按月結週期估算；未連接銀行"
                continue
            context = contexts[row["group"]]
            row["class_start"] = context["full_course_start"]
            row["class_end"] = context["full_course_end"]
            row["invoice_submit_from"] = context["full_course_end"]
            delivery = by_group.get(row["group"])
            submission = (delivery or {}).get("client_submission", {})
            row["submitted_on"] = submission.get("submitted_date") or submission.get("submitted_timestamp", "")[:10] or None
            row["submission_confirmed_on"] = submission.get("confirmed_by_user_date")
            row["submission_state"] = ("submitted" if row["submitted_on"] or submission.get("status") == "confirmed_by_user" else "unknown" if delivery else "not_issued")
            row["invoice_prepared_on"] = (delivery or {}).get("completion_date")
            row["invoice_issued_on"] = (delivery or {}).get("invoice_date") or (delivery or {}).get("completion_date")
            row["submitted_at"] = submission.get("submitted_timestamp")
            legacy = [r for key, r in paid.items() if key.split("|")[0] == context["course_code"] and key.split("|")[-1] == context["full_course_start"]]
            if len(legacy) > 1:
                raise ValueError("Ambiguous paid cohort")
            received = paid.get(delivery["course_instance"]) if delivery else (legacy[0] if legacy else None)
            if delivery and delivery.get("payment_status", {}).get("status") == "received":
                received = delivery["payment_status"]
            if delivery and row["amount"] != delivery["amount_hkd"]:
                raise ValueError(f"Invoice/salary mismatch: {row['group']}")
            row["received"] = received is not None
            if received:
                if received.get("invoice_date"):
                    row["invoice_issued_on"] = received["invoice_date"]
                if row["amount"] != received["amount_hkd"]:
                    raise ValueError("Paid amount differs from salary")
                row["invoice_status"] = "已確認收款"
                if received.get("received_date"):
                    row["received_on"] = received["received_date"]
                continue
            row["forecast_stage"] = "future_course"
            row["invoice_status"] = "全班未完結；完成及提交後才可收款"
            row["basis"] = "假設全班完結即提交發票，再按 21 日規劃；非保證到賬日"
            if not delivery:
                continue
            row["label"] = delivery["course_code"] + " · " + delivery["class"] + (" · " + delivery["cohort"] if delivery.get("cohort") else "")
            submission = delivery.get("client_submission", {})
            submitted = submission.get("submitted_date") or submission.get("submitted_timestamp", "")[:10]
            if submitted:
                row["forecast_stage"] = "submitted"
                row["invoice_status"] = "已交 Calvin " + submitted + "；收款待確認"
                row["expected_payment_date"] = (date.fromisoformat(submitted) + timedelta(days=21)).isoformat()
                row["basis"] = "以實際提交日加 21 日作保守規劃，非承諾付款期限"
            elif submission.get("status") == "confirmed_by_user":
                anchor = submission["confirmed_by_user_date"]
                row["forecast_stage"] = "submitted_date_unknown"
                row["invoice_status"] = "已交 Calvin（用戶確認）；提交日期未提供"
                row["expected_payment_date"] = (date.fromisoformat(anchor) + timedelta(days=21)).isoformat()
                row["basis"] = "暫以用戶確認日 " + anchor + " 加 21 日；不是實際提交日或保證日期"
            else:
                row["forecast_stage"] = "awaiting_submission"
                row["invoice_status"] = "發票已備妥並寄給你；尚未確認交 Calvin"
                row["expected_payment_date"] = None
                row["basis"] = "提交 Calvin 後才開始估算；不計入未來 30／60／90 日到賬預測"
        schedule["rows"].sort(key=lambda r: (r.get("expected_payment_date") or "9999", r["label"]))
        schedule["dated_total"] = sum(r["amount"] for r in schedule["rows"] if r.get("expected_payment_date"))
    rows = report["confirmed"]["expected_payments"]["rows"]
    completed_unpaid = sum(r["amount"] for r in rows if r["kind"] == "ERB" and not r["received"] and r["invoice_date"] <= as_of[:10])
    if completed_unpaid != reconciliation["not_confirmed_received_hkd"]:
        raise ValueError("Completed unpaid salary differs from reconciliation")
    report["records_as_of"] = as_of
    report["submission_records_as_of"] = reconciliation.get("submission_records_updated_at", as_of)
    report["cashflow"] = {"schema": 1, "calvin_completed_unpaid": completed_unpaid, "calvin_received": reconciliation["confirmed_received_hkd"], "bank_connected": False}
    report["notes"] = [n for n in report["notes"] if not n.startswith("ERB 預計到賬日")]
    report["notes"].append("最新發票／Calvin 收款狀態已與發票登記冊核對；SEN 及 DGS 沿用先前已確認收款記錄。沒有銀行即時連線，未確認收款不等於銀行一定未入賬。")
