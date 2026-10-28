"""Keep separately priced DGS engagements separate from the historic flat-fee course."""
from datetime import date
import json

def add_priced_dgs(report, events, event_interval):
    lessons = [e for e in events if e.get('category') == 'dgs' and e.get('salary_engagement')]
    if not lessons:
        return
    receipts = {}
    # Only the latest report has reconciled cashflow; retain historical snapshots.
    if 'cashflow' in report:
        from salary_cashflow import REGISTER
        ledger = json.loads(REGISTER.read_text(encoding='utf-8-sig'))
        receipts = ledger['payment_reconciliation'].get('other_engagement_receipts', {})
    seen = set()
    for event in lessons:
        identity = (event['salary_engagement'], event['date'], event['text'])
        if identity in seen:
            raise ValueError('Duplicate priced DGS engagement')
        seen.add(identity)
        if event.get('teacher') not in {'Garett', 'Garrett'}:
            continue
        interval = event_interval(event['text'])
        hours = event.get('official_teaching_hours', (interval[1] - interval[0]) / 60)
        amount = hours * event['salary_hourly_rate']
        if amount != event['salary_amount']:
            raise ValueError('Priced DGS amount does not match hours and rate')
        for mode, statuses in [('confirmed', {'confirmed'}), ('confirmed_and_unconfirmed', {'confirmed', 'unconfirmed'})]:
            if event['status'] not in statuses:
                continue
            target = report[mode]
            day = date.fromisoformat(event['date'])
            month = day.strftime('%B') + (f' {day.year}' if day.year != 2026 else '')
            row = next(r for r in target['months'] if r['month'] == month)
            row['dgs_hours'] += hours
            row['dgs_days'] += 1
            row['dgs_pay'] += amount
            row['total'] += amount
            target['grand_total'] += amount
            target['counted_events'] += 1
            payment = {
                'kind':'DGS', 'label':f"DGS · Blender · {event['date']}",
                'course_name':'Blender 入門（Peach Princess）', 'hours':hours, 'amount':amount,
                'received':False, 'class_start':event['date'], 'class_end':event['date'],
                'basis':f"{hours}小時 × HK${event['salary_hourly_rate']}/小時；付款日期待確認。",
                'invoice_status':'已確認單堂；付款日期及交單安排待確認'}
            receipt = receipts.get(event['salary_engagement'])
            if receipt:
                if receipt['amount_hkd'] != amount or receipt['service_date'] != event['date']:
                    raise ValueError('DGS engagement receipt does not match lesson')
                if receipt['status'] != 'received':
                    raise ValueError('Unexpected DGS engagement receipt status')
                payment.update(received=True, salary_engagement=event['salary_engagement'],
                    receipt_confirmed_on=receipt['confirmed_by_user_date'],
                    received_date_precision=receipt.get('date_precision', 'unknown'),
                    invoice_status='已確認收款',
                    basis=f"{hours}小時 × HK${event['salary_hourly_rate']}/小時；用戶已確認收款。")
                if receipt.get('received_date'):
                    payment['received_on'] = receipt['received_date']
            target['expected_payments']['undated'].append(payment)
    report['rates']['DGS'] = '7月 Unreal：HK$7,000 最終總額；另外議定的 DGS 單堂按各堂獨立時薪計算。'
    report['notes'].append('DGS Blender 與7月 Unreal 是不同工作；沒有把之前 HK$7,000 總額或收款狀態套用到新課堂。')
