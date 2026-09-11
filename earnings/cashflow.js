/* Private records are supplied only after the existing AES-GCM unlock. */
window.mountCashflow = function (data) {
  const cash = n => new Intl.NumberFormat('en-HK', {style:'currency', currency:'HKD', maximumFractionDigits:0}).format(n);
  const esc = s => String(s ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
  const hkToday = () => new Intl.DateTimeFormat('en-CA', {timeZone:'Asia/Hong_Kong',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date());
  const add = (day,n) => {const d=new Date(day+'T00:00:00Z'); d.setUTCDate(d.getUTCDate()+n); return d.toISOString().slice(0,10);};
  const sum = rows => rows.reduce((n,r)=>n+r.amount,0);
  const rows = data.confirmed.expected_payments.rows;
  const unpaid = rows.filter(r=>!r.received);
  const style = document.createElement('style');
  style.textContent = `.cashflow{margin:20px 0;padding:20px;background:#fff;border:1px solid #c4dbd8;border-top:5px solid #0f7074;border-radius:12px}.cashflow h2{font-size:24px;margin:0 0 5px}.cashflow h3{font-size:16px;margin:20px 0 8px}.cf-muted{color:#667387;font-size:13px;line-height:1.6}.cf-grid{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:10px;margin:15px 0}.cf-card{background:#edf7f5;border-radius:8px;padding:14px}.cf-card strong{display:block;font-size:27px;color:#0f7074;margin:5px 0}.cf-card small{display:block;color:#52666a;font-size:12px}.cf-warn{padding:12px;border-radius:8px;background:#fff4df;color:#785000;margin:12px 0;line-height:1.6}.cf-list{list-style:none;padding:0;margin:0}.cf-list li{display:flex;justify-content:space-between;gap:15px;padding:13px 0;border-bottom:1px solid #d7dee8}.cf-list span{display:block}.cf-list strong{white-space:nowrap}.cf-planner{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:12px}.cf-planner label{font-size:13px;font-weight:700}.cf-planner input,.cf-planner select{display:block;width:100%;min-width:0;padding:10px;margin-top:5px;border:1px solid #aabdc4;border-radius:6px;font:16px 'Segoe UI',sans-serif;background:white;color:#1d2734}.cf-result{margin-top:12px;padding:14px;background:#edf7f5;border-radius:8px;line-height:1.6}.cf-result strong{font-size:23px}.cf-reset{background:white;border:1px solid #aabdc4;border-radius:6px;padding:9px;margin-top:10px;color:#1d2734}.cf-toolbar{display:flex;justify-content:space-between;gap:10px;align-items:center}.cf-toolbar button{background:#0f7074;color:white;border:0;border-radius:6px;padding:9px;font:inherit;white-space:nowrap}@media(max-width:620px){.cashflow{padding:14px;margin-top:14px}.cashflow h2{font-size:21px}.cf-grid{grid-template-columns:1fr}.cf-card{display:grid;grid-template-columns:1fr auto;align-items:center;gap:0 8px}.cf-card strong{grid-column:2;grid-row:1/3;font-size:25px}.cf-card small{grid-column:1}.cf-planner{grid-template-columns:1fr}.cf-list li{font-size:14px}.cf-toolbar{align-items:flex-start}}`;
  document.head.append(style);
  style.textContent += '.cf-result strong{white-space:nowrap}';
  const section=document.createElement('section'); section.className='cashflow'; section.id='cashflow';
  document.querySelector('main').prepend(section);
  let today='';
  function render(){
    today=hkToday();
    const future=unpaid.filter(r=>r.expected_payment_date && r.expected_payment_date>=today);
    const overdue=unpaid.filter(r=>r.expected_payment_date && r.expected_payment_date<today);
    const pending=unpaid.filter(r=>!r.expected_payment_date);
    const completed=unpaid.filter(r=>r.kind==='ERB' && r.invoice_date<today);
    const eligibleUnissued=unpaid.filter(r=>r.forecast_stage==='future_course' && r.invoice_date<today);
    const reliableFuture=future.filter(r=>!eligibleUnissued.includes(r));
    const inDays=n=>reliableFuture.filter(r=>r.expected_payment_date<=add(today,n));
    const age=Math.floor((Date.parse(today)-Date.parse(data.records_as_of.slice(0,10)))/86400000);
    section.innerHTML=`<div class="cf-toolbar"><div><h2>接下來有多少錢可收？</h2><div class="cf-muted">今天 ${esc(today)} · 香港時間<br>發票核對：${esc(data.records_as_of.slice(0,16).replace('T',' '))}<br>課表：${esc(data.version_id)} · 已確認課程；不包括未確認工作</div></div><button id="cfRefresh" type="button">重新整理</button></div>
    ${age>7?'<div class="cf-warn">記錄已超過 7 日未核對。下列預測使用已存資料，不代表最新銀行入賬。</div>':''}
    <div class="cf-grid">${[30,60,90].map(n=>`<div class="cf-card"><span>未來 ${n} 日預計可收</span><strong data-horizon="${n}">${cash(sum(inDays(n)))}</strong><small>累計至 ${add(today,n)}</small></div>`).join('')}</div>
    <p class="cf-muted">三個數字是累計，不能相加。只計尚未確認收款、具規劃日期的已確認工作；未完班款項仍以完成教學及即時提交發票為前提。這是預測，不是銀行結餘或保證收入。</p>
    <div class="cf-warn"><strong>已完班、未確認收款（Calvin）：${cash(sum(completed))}</strong><br>其中待提交／未有日期：${cash(sum(pending))}；已過規劃日但收款未核實：${cash(sum(overdue))}。這些不會自動當作已收款。${eligibleUnissued.length?'<br>另有 '+eligibleUnissued.length+' 班按課表已完結，但未有發票更新；已暫停計入近期到賬預測。':''}</div>
    <h3>下一批預計入賬</h3><ul class="cf-list">${reliableFuture.slice(0,6).map(r=>`<li><div><span>${esc(r.expected_payment_date)} · ${esc(r.label)}</span><span class="cf-muted">${esc(r.invoice_status)}<br>${esc(r.basis)}</span></div><strong>${cash(r.amount)}</strong></li>`).join('')||'<li>目前沒有可列日期的未來款項。</li>'}</ul>
    ${pending.length?'<h3>要先處理</h3><ul class="cf-list">'+pending.map(r=>`<li><div>${esc(r.label)}<span class="cf-muted">${esc(r.invoice_status)}<br>若今天提交，按 21 日規劃約 ${add(today,21)}；未計入以上預測。</span></div><strong>${cash(r.amount)}</strong></li>`).join('')+'</ul>':''}
    ${overdue.length?'<h3>已過規劃日：待核實</h3><ul class="cf-list">'+overdue.map(r=>`<li><div>${esc(r.label)}<span class="cf-muted">原規劃 ${esc(r.expected_payment_date)}；不是已證實逾期欠款。</span></div><strong>${cash(r.amount)}</strong></li>`).join('')+'</ul>':''}
    <h3>買東西前，試算一下</h3><p class="cf-muted">填入目前銀行可用結餘、這段期間預留生活費及購物預算。資料只留在這個瀏覽器，不上傳，也不會更改正式薪酬紀錄。</p>
    <div class="cf-planner"><label>目前可用結餘（HK$）<input id="cfBalance" type="number" min="0" step="0.01" inputmode="decimal" placeholder="未提供，不會假設為零"></label><label>期間內生活費／預留款（HK$）<input id="cfReserve" type="number" min="0" step="0.01" inputmode="decimal" placeholder="請填寫；沒有則填 0"></label><label>想買的東西預算（HK$）<input id="cfPurchase" type="number" min="0" step="0.01" inputmode="decimal" placeholder="例如新電話的實際售價"></label><label>預計購買日期<input id="cfTarget" type="date" min="${today}" value="${add(today,30)}"></label></div><div id="cfResult" class="cf-result" aria-live="polite"></div><button id="cfReset" class="cf-reset" type="button">清除本機試算資料</button>
    <h3>完整薪酬及每筆收款紀錄</h3><p class="cf-muted">下方保留月度工資、已收款切換及所有未來班別。到賬倒數每天按香港日期重算；實際收款必須有記錄或你的確認，不會因日期到了而自動標成已收。</p>`;
    document.getElementById('cfRefresh').onclick=()=>location.reload();
    const ids=['cfBalance','cfReserve','cfPurchase','cfTarget'];
    const store='garett-private-purchase-planner-v1';
    try{const saved=JSON.parse(localStorage.getItem(store)||'{}');ids.forEach(id=>{if(saved[id]!==undefined)document.getElementById(id).value=saved[id];});}catch{}
    function plan(){
      const values=Object.fromEntries(ids.map(id=>[id,document.getElementById(id).value]));
      localStorage.setItem(store,JSON.stringify(values));
      const result=document.getElementById('cfResult');
      if(!/^\d{4}-\d{2}-\d{2}$/.test(values.cfTarget)||values.cfTarget<today){result.textContent='請選擇今天或以後的購買日期。';return;}
      if(['cfBalance','cfReserve','cfPurchase'].some(id=>values[id]===''||!Number.isFinite(Number(values[id]))||Number(values[id])<0)){result.textContent='填齊結餘、預留款及購物預算後，才可計算預計餘額。';return;}
      const inflow=sum(reliableFuture.filter(r=>r.expected_payment_date<=values.cfTarget));
      const now=Number(values.cfBalance)-Number(values.cfReserve)-Number(values.cfPurchase);
      const later=now+inflow;
      result.innerHTML=`不靠未入賬薪酬，買後餘額：<strong>${cash(now)}</strong><br>若截至 ${esc(values.cfTarget)} 的預計收入 ${cash(inflow)} 全部到賬，買後約剩：<strong>${cash(later)}</strong><br><span class="cf-muted">${now<0?'目前可用款不足以同時保留預留款並購買。':'按你填寫的結餘可覆蓋預留款及購物。'} 未入賬收入不能當作現有現金；本試算不含未知開支及未登記工作。</span>`;
    }
    ids.forEach(id=>document.getElementById(id).addEventListener('input',plan));
    document.getElementById('cfReset').onclick=()=>{localStorage.removeItem(store);ids.slice(0,3).forEach(id=>document.getElementById(id).value='');document.getElementById('cfTarget').value=add(today,30);plan();};
    plan();
  }
  render();
  document.addEventListener('visibilitychange',()=>{if(!document.hidden&&hkToday()!==today)render();});
  setInterval(()=>{if(hkToday()!==today)render();},60000);
};
