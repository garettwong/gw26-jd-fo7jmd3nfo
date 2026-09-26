/* Private payment ledger. Records are supplied only after decryption. */
function calvinPaymentTiming(r){
 if(r.kind!=='ERB')return null;
 if(!r.received)return {text:'收款後自動計算',note:'由實際交單日期至實際收款日期'};
 if(!r.submitted_on||!r.received_on)return {text:!r.submitted_on&&!r.received_on?'交單及收款日期未記錄':!r.submitted_on?'交單日期未記錄':'收款日期未記錄',note:'資料不足，未能計算付款所需時間'};
 const day=value=>{
  if(!/^\d{4}-\d{2}-\d{2}$/.test(value))return NaN;
  const date=new Date(value+'T00:00:00Z');
  return Number.isFinite(date.getTime())&&date.toISOString().slice(0,10)===value?date.getTime()/86400000:NaN;
 };
 const days=day(r.received_on)-day(r.submitted_on);
 if(!Number.isFinite(days)||days<0)return {text:'日期需核對',note:'未能計算付款所需時間'};
 return {text:(r.received_date_precision==='approximate'?'約 ':'')+days+' 日',note:'由交單至收款，按曆日計算'};
}
window.mountCashflow=function(data){
 const cash=n=>new Intl.NumberFormat('en-HK',{style:'currency',currency:'HKD',maximumFractionDigits:0}).format(n);
 const esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 const sum=rs=>rs.reduce((n,r)=>n+r.amount,0),s=data.confirmed.expected_payments,all=[...s.rows,...s.undated];
 const paid=all.filter(r=>r.received),waiting=all.filter(r=>!r.received&&r.submission_state==='submitted'),future=all.filter(r=>!r.received&&r.submission_state!=='submitted');
 const main=document.querySelector('main'),archive=document.createElement('details');archive.id='salaryArchive';archive.innerHTML='<summary>薪酬計算規則</summary>';
 while(main.firstChild)archive.append(main.firstChild);main.append(archive);
 const legacy=archive.querySelector('.expected');if(legacy)legacy.style.display='none';const remaining=archive.querySelector('[data-mode="remaining"]');if(remaining)remaining.style.display='none';
 const section=document.createElement('section');section.id='cashflow';main.prepend(section);
 // Keep assignment status visible, independently of invoice/payment status.
 const work=document.createElement('section');work.id='salaryWork';work.className='cf-panel';
 work.innerHTML='<h2>教學薪酬 · Confirmed / Unconfirmed</h2><p class="cf-muted">按任教月份計算；待確認收入並非已落實工作或已收到款項。</p>';
 for(const selector of ['.modes','.summary','#monthlyTable']){const element=archive.querySelector(selector);if(element)work.append(element);}
 const confirmed=work.querySelector('[data-mode="confirmed"]'),combined=work.querySelector('[data-mode="confirmed_and_unconfirmed"]');
 if(confirmed)confirmed.textContent='Confirmed · 已確認';
 if(combined)combined.textContent='Confirmed + unconfirmed · 包括待確認';
 const pending=document.createElement('p');pending.className='cf-muted';pending.id='salaryPendingTotal';
 pending.textContent='待確認收入（未計未定價課程）：'+cash(data.confirmed_and_unconfirmed.grand_total-data.confirmed.grand_total);work.append(pending);
 const proposals=data.pending_courses||[];
 if(proposals.length){
  pending.textContent=proposals.length+' 個待確認課程 · 已可估算 '+cash(proposals.reduce((total,r)=>total+(r.amount||0),0))+(proposals.some(r=>r.amount===null)?'，另有 '+proposals.filter(r=>r.amount===null).length+' 個課程金額待定':'');
  const list=document.createElement('section');list.id='pendingSalaryCourses';list.innerHTML='<h3>Unconfirmed · 待確認課程明細</h3><div class="cf-items">'+proposals.map(r=>'<article class="cf-item"><b>'+esc(r.label)+'</b><p>'+r.lesson_count+' 節 · '+r.hours+' 小時</p><strong class="cf-amount">'+(r.amount===null?'金額待定':cash(r.amount))+'</strong><p>'+ (r.rate===null?'時薪待確認':cash(r.rate)+'/小時（估算）')+'</p><small>'+esc(r.basis)+'</small></article>').join('')+'</div><p class="cf-muted">這是擬任教工作的估算；撞期須先解決，不能視為可同時收取的保證收入。</p>';work.append(list);
 }
 const unpriced=data.unpriced_courses||[];
 if(unpriced.length){const box=document.createElement('div');box.id='salaryUnpriced';box.innerHTML='<h3>Unconfirmed · 金額待定</h3>'+unpriced.map(r=>'<p><b>'+esc(r.label)+'</b><br>'+esc(r.dates.join('、'))+' · '+esc(r.time)+'<br>'+esc(r.reason)+'</p>').join('');work.append(box);}
 main.prepend(work);
 const style=document.createElement('style');style.textContent=`
 #cashflow{font-family:"Segoe UI","Microsoft JhengHei",sans-serif;color:#193337;line-height:1.5;margin:18px 0}#cashflow h2{font-size:24px;margin:0}#cashflow h3{font-size:21px;margin:0}.cf-panel{padding:22px;background:white;border:1px solid #d2dfdf;border-radius:12px;margin-bottom:16px}.cf-muted{font-size:13px;color:#586d73}.cf-totals{display:grid;grid-template-columns:repeat(3,1fr);gap:14px;margin:18px 0}.cf-total{padding:18px;background:#f1f6f6;border-radius:9px}.cf-total strong{display:block;font-size:30px;color:#096a66}.cf-total.waiting{background:#fff3d9}.cf-total small{display:block;color:#586d73}.cf-ledger-head{display:flex;justify-content:space-between;gap:14px;align-items:center}.cf-ledger-head select{padding:10px;border:1px solid #afc5c6;border-radius:6px;font-size:16px;max-width:100%}.cf-items{display:grid;grid-template-columns:1fr 1fr;gap:14px;margin-top:14px}.cf-item{padding:18px;border:1px solid #cadcdb;border-radius:10px;min-width:0;background:white}.cf-item header{display:flex;justify-content:space-between;gap:12px;background:none;border:0}.cf-item header b{font-size:17px;overflow-wrap:anywhere}.cf-amount{font-size:21px;white-space:nowrap;color:#0f7074}.cf-course-name{font-size:15px;margin:10px 0}.cf-badge{display:inline-block;background:#eef4f5;padding:4px 8px;border-radius:4px;font-size:13px;margin-bottom:12px}.cf-paid .cf-badge{background:#d9efe4;color:#165a3b}.cf-dates{min-width:0;width:100%;border-collapse:collapse;table-layout:fixed}.cf-dates th,.cf-dates td{border-top:1px solid #dce7e6;padding:11px 0;text-align:left;vertical-align:top;overflow-wrap:anywhere}.cf-dates th{width:43%;padding-right:12px;font-size:14px;font-weight:500;color:#586d73}.cf-dates td{font-size:15px;font-weight:650}.cf-dates small{display:block;font-weight:400;font-size:12px;color:#586d73;margin-top:3px}#salaryArchive{margin:16px 0}#salaryArchive>summary{padding:16px;background:white;border:1px solid #d2dfdf;border-radius:8px;cursor:pointer;font-weight:700}@media(max-width:620px){.cf-panel{padding:15px}.cf-totals,.cf-items{grid-template-columns:1fr}.cf-total{padding:14px}.cf-total strong{font-size:29px}.cf-ledger-head{display:block}.cf-ledger-head select{width:100%;margin:12px 0}.cf-item{padding:14px}.cf-item header{flex-wrap:wrap}.cf-dates th{width:43%;font-size:13px}.cf-dates td{font-size:14px}}
 `;document.head.append(style);
 section.innerHTML=`<div class="cf-panel" id="cfOverview"><h2>收款紀錄總覽</h2><p class="cf-muted">紀錄更新：${esc(data.records_as_of.slice(0,10))} · 只計已確認工作</p><div class="cf-totals"><div class="cf-total"><span>已實際收到</span><strong id="cfReceived">${cash(sum(paid))}</strong><small>所有已確認收款，包括 Calvin、SEN 及 DGS</small></div><div class="cf-total waiting"><span>已交 Calvin，尚未收到</span><strong id="cfWaiting">${cash(sum(waiting))}</strong><small>${waiting.length} 張已提交發票</small></div><div class="cf-total"><span>未完班／未交單的預計收入</span><strong id="cfFutureIncome">${cash(sum(future))}</strong><small>尚未成為已提交的待收款發票</small></div></div><p class="cf-muted">已登記工作總額 ${cash(sum(all))} ＝ 已收款 ${cash(sum(paid))} ＋ 已交單待收款 ${cash(sum(waiting))} ＋ 未完班／未交單 ${cash(sum(future))}。<br>這是工作收入紀錄，不是銀行現有結餘。</p></div><div class="cf-panel"><div class="cf-ledger-head"><h3>課程及收款進度</h3><select id="cfFilter" aria-label="收款記錄篩選"><option value="all">全部紀錄</option><option value="waiting">已交 Calvin，尚未收到</option><option value="paid">已收到</option><option value="future">未完班／未交單</option></select></div><div id="cfLedgerSummary" class="cf-muted"></div><div id="cfItems" class="cf-items"></div><p class="cf-muted">交單日期按實際提交紀錄填寫；預計日期只是估計。未有紀錄的日期會明示，不會用發票日期或預計日期代替。</p></div>`;
 function card(r){
  if(r.kind==='DGS'&&r.received){
   const when=r.received_on?(r.received_date_precision==='approximate'?'約 ':'')+r.received_on:'已收到；日期未記錄';
   return '<article class="cf-item cf-paid" data-group="DGS"><header><b>DGS</b><strong class="cf-amount">'+cash(r.amount)+'</strong></header><p class="cf-course-name">DGS</p><span class="cf-badge">已收到 · 已完成</span><table class="cf-dates"><tbody><tr><th scope="row">收款日期</th><td>'+esc(when)+'</td></tr></tbody></table></article>';
  }
  const submitted=r.submission_state==='submitted';
  const end=r.class_end||(r.service_period?.match(/(\d{4}-\d{2}-\d{2})$/)||[])[1]||'日期未記錄';
  const sent=r.submitted_on?r.submitted_on+(r.submitted_at?' '+r.submitted_at.slice(11,16):''):r.received?'交單日期未記錄':submitted?'已交單；日期未記錄':r.kind==='ERB'?'尚未提交':'提交日期未記錄';
  let expected=r.expected_payment_date||'未有足夠資料估計',estimate='';
  if(r.expected_payment_date)estimate=submitted?'按交單日加 21 日估計':r.kind==='ERB'?(r.received?'當時按完班即交單估計':'假設完班即交單，再加 21 日'): '按月結週期估計';
  const actual=r.received?(r.received_on||'已收到；日期未記錄'):'尚未收到';
  const row=(a,b,n='')=>'<tr><th scope="row">'+esc(a)+'</th><td>'+esc(b)+(n?'<small>'+esc(n)+'</small>':'')+'</td></tr>';
  const timing=calvinPaymentTiming(r);
  const badge=r.received?'已收到':submitted?'已交單，等收款':'未完班／未交單';
  return '<article class="cf-item '+(r.received?'cf-paid':'')+'" data-group="'+esc(r.group||r.label)+'"><header><b>'+esc(r.label)+'</b><strong class="cf-amount">'+cash(r.amount)+'</strong></header><p class="cf-course-name">'+esc(r.course_name||r.label)+'</p><span class="cf-badge">'+badge+'</span><table class="cf-dates"><tbody>'+row('1. 課程完結日期',end)+row('2. 發票提交日期',sent)+row('3. 預計收款日期',expected,estimate)+row('4. 實際收款日期',actual)+(timing?row('5. Calvin 付款所需時間',timing.text,timing.note):'')+'</tbody></table></article>';
 }
 function render(){const filter=document.getElementById('cfFilter').value,rows=filter==='paid'?paid:filter==='waiting'?waiting:filter==='future'?future:all;document.getElementById('cfLedgerSummary').textContent=rows.length+' 筆 · 合共 '+cash(sum(rows));document.getElementById('cfItems').innerHTML=rows.map(card).join('')||'<p>這個分類沒有款項。</p>';}
 document.getElementById('cfFilter').onchange=render;render();
};
