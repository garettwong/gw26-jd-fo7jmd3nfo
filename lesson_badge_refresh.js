  // One read for the whole timetable; mobile must not queue hundreds of requests.
  const buttons=Array.from(document.querySelectorAll('.lesson-log-open'));
  const groups=new Map();
  let running=false, nextCheck=0, failures=0, refreshAgain=false;
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
  const refresh=async(force=false)=>{
    if(document.hidden)return;
    if(running){if(force)refreshAgain=true;return;}
    if(!force&&Date.now()<nextCheck)return;
    running=true;
    const controller=new AbortController();
    const timer=setTimeout(()=>controller.abort(),15000);
    try{
      const response=await fetch(APP_BASE+'/api/note-status',{
        cache:'no-store',signal:controller.signal
      });
      if(!response.ok)throw new Error('HTTP '+response.status);
      const payload=await response.json();
      if(payload.complete!==true||!Array.isArray(payload.recorded)||
        payload.recorded.some(id=>typeof id!=='string'))throw new Error('Incomplete status');
      const recorded=new Set(payload.recorded);
      for(const [key,items] of groups){
        const exists=recorded.has(lessonIdFor(key));
        items.forEach(button=>{
          button.classList.toggle('logged',exists);
          button.textContent=exists?'已記錄':'記錄';
          button.setAttribute('aria-label',exists?'已同步教學記錄；按此查看或修改':'尚未有教學記錄；按此填寫');
          button.title=exists?'已核對網上記錄':'已核對：尚未有記錄';
        });
      }
      failures=0;
      nextCheck=Date.now()+5000;
    }catch(_error){
      failures++;
      nextCheck=Date.now()+Math.min(60000,5000*2**Math.min(failures-1,4));
      buttons.forEach(button=>{
        button.textContent=button.classList.contains('logged')?'已記錄 ↻':'待同步';
        button.title='連線暫時失敗，會自動重試；按此仍可直接開啟網上記錄及同班過往記錄';
        button.setAttribute('aria-label',button.title);
      });
    }finally{
      clearTimeout(timer);running=false;
      if(refreshAgain){refreshAgain=false;void refresh(true);}
    }
  };
  void refresh();
  migrateLegacyNotes().then(count=>{if(count)void refresh(true);}).catch(()=>{});
  window.addEventListener('focus',()=>void refresh(true));
  window.addEventListener('pageshow',()=>void refresh(true));
  window.addEventListener('online',()=>void refresh(true));
  document.addEventListener('visibilitychange',()=>void refresh(true));
  setInterval(()=>void refresh(),5000);
