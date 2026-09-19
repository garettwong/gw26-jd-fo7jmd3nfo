  // One read per lesson (calendar and class views share the same record).
  const buttons=Array.from(document.querySelectorAll('.lesson-log-open'));
  const groups=new Map();
  const checked=new Map();
  const pending=new Set();
  const queue=[];
  let running=0;
  buttons.forEach(button=>{
    const key=button.dataset.logKey||'';
    if(!groups.has(key))groups.set(key,[]);
    groups.get(key).push(button);
    button.textContent='讀取中';
    button.setAttribute('aria-label','正在核對網上教學記錄');
    button.setAttribute('aria-hidden','false');
    button.setAttribute('role','button');
    button.tabIndex=0;
    const open=event=>{event.preventDefault();event.stopPropagation();openEditor(button);};
    button.addEventListener('click',open);
    button.addEventListener('keydown',event=>{if(event.key==='Enter'||event.key===' '){open(event);}});
  });
  window.openLessonLogForButton=openEditor;
  const visible=key=>groups.get(key).some(button=>{
    const r=button.getBoundingClientRect();
    return r.width>0&&r.height>0&&r.bottom>=-200&&r.top<=innerHeight+200;
  });
  const refreshBadge=async key=>{
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),10000);
    try{
      const response=await fetch(APP_BASE+'/api/notes/'+encodeURIComponent(lessonIdFor(key)),{
        cache:'no-store',signal:controller.signal
      });
      if(!response.ok)throw new Error('HTTP '+response.status);
      const payload=await response.json();
      if(typeof payload.content!=='string')throw new Error('Invalid record');
      const exists=Boolean(payload.content.trim());
      groups.get(key).forEach(button=>{
        button.classList.toggle('logged',exists);
        button.textContent=exists?'已記錄':'記錄';
        button.setAttribute('aria-label',exists?'已同步教學記錄；按此查看或修改':'尚未有教學記錄；按此填寫');
        button.title=exists?'已核對網上記錄':'已核對：尚未有記錄';
      });
      checked.set(key,Date.now());
    }catch(_error){
      groups.get(key).forEach(button=>{
        button.textContent=button.classList.contains('logged')?'已記錄 ↻':'待同步';
        button.title='未能核對最新記錄，會自動重試；按此直接開啟網上記錄';
        button.setAttribute('aria-label',button.title);
      });
      checked.delete(key);
    }finally{clearTimeout(timer);}
  };
  const pump=()=>{
    while(running<3&&queue.length){
      const key=queue.shift();running++;
      refreshBadge(key).finally(()=>{running--;pending.delete(key);pump();});
    }
  };
  const refresh=()=>{
    if(document.hidden)return;
    const now=Date.now();
    // Visible lessons refresh every five seconds, all others every five minutes.
    for(const key of groups.keys()){
      const age=now-(checked.get(key)||0);
      if(!pending.has(key)&&age>=(visible(key)?4000:300000)){
        pending.add(key);queue.push(key);
      }
    }
    queue.sort((a,b)=>Number(visible(b))-Number(visible(a))||
      Math.abs(Date.parse(a.split('|')[0])-now)-Math.abs(Date.parse(b.split('|')[0])-now));
    pump();
  };
  refresh();
  migrateLegacyNotes().finally(()=>{checked.clear();refresh();});
  window.addEventListener('focus',refresh);
  window.addEventListener('pageshow',()=>{checked.clear();refresh();});
  window.addEventListener('online',()=>{checked.clear();refresh();});
  document.addEventListener('visibilitychange',refresh);
  let scrollTimer;
  window.addEventListener('scroll',()=>{clearTimeout(scrollTimer);scrollTimer=setTimeout(refresh,150);},{passive:true});
  setInterval(refresh,5000);
