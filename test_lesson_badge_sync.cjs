const fs=require('node:fs'),vm=require('node:vm'),assert=require('node:assert/strict');
const html=fs.readFileSync('index.html','utf8').replace(/\r/g,'');
const start=html.indexOf('(function(){\n  const APP_BASE=');
const code=html.slice(start,html.indexOf('\n})();',start)+6);
const remote=new Map(), events={}, intervals=[];
let inflight=0,maxInflight=0,calls=0,fail=false,incomplete=false,clock=Date.now();
const keys=Array.from({length:12},(_,i)=>`2026-09-${String(i+7).padStart(2,'0')}|HK244EG · CW|Lesson ${i}|19:00-21:30`);
const buttons=keys.flatMap(key=>Array.from({length:2},()=>({
 dataset:{logKey:key},textContent:'記錄',attrs:{},classes:new Set(),
 classList:{toggle(c,b){b?this.owner.classes.add(c):this.owner.classes.delete(c)},contains(c){return this.owner.classes.has(c)}},
 setAttribute(k,v){this.attrs[k]=v},addEventListener(){},
 getBoundingClientRect(){return {width:30,height:20,top:100,bottom:120}}
})));
buttons.forEach(b=>b.classList.owner=b);
const context={document:{hidden:false,documentElement:{classList:{add(){}}},querySelectorAll:()=>buttons,addEventListener:(n,f)=>events[n]=f},
 window:{addEventListener:(n,f)=>events[n]=f},location:{},innerHeight:900,
 localStorage:{getItem:()=>null},TextEncoder,URLSearchParams,AbortController,
 btoa:s=>Buffer.from(s,'binary').toString('base64'),setTimeout,clearTimeout,
 setInterval:f=>intervals.push(f),Date:class extends Date{static now(){return clock}},
 fetch:async url=>{assert.equal(url.endsWith('/api/note-status'),true);calls++;inflight++;maxInflight=Math.max(maxInflight,inflight);await new Promise(r=>setTimeout(r,2));inflight--;
 if(fail)return {ok:false,status:503};
 return {ok:true,json:async()=>({complete:!incomplete,recorded:[...remote.keys()].map(k=>Buffer.from(k).toString('base64url'))})};}
};
const settle=async()=>{for(let i=0;i<100;i++){await new Promise(r=>setTimeout(r,3));if(!inflight)return;}throw Error('queue did not drain')};
(async()=>{
 remote.set(keys[0],'Saved from iPhone');vm.runInNewContext(code,context);await settle();
 assert.equal(maxInflight,1);assert.equal(calls,1);assert.equal(buttons[0].textContent,'已記錄');assert.equal(buttons[1].textContent,'已記錄');
 remote.set(keys[1],'Saved from PC');clock+=5001;intervals[0]();await settle();assert.equal(buttons[2].textContent,'已記錄');
 fail=true;clock+=5001;intervals[0]();await settle();assert.equal(buttons[0].textContent,'已記錄 ↻');assert.equal(buttons[4].textContent,'待同步');
 const previousCalls=calls;intervals[0]();await settle();assert.equal(calls,previousCalls);
 fail=false;events.online();await settle();assert.equal(buttons[0].textContent,'已記錄');assert.equal(buttons[4].textContent,'記錄');
 remote.set(keys[2],'Saved while timetable in back-forward cache');events.pageshow();await settle();assert.equal(buttons[4].textContent,'已記錄');
 incomplete=true;events.online();await settle();assert.equal(buttons[0].textContent,'已記錄 ↻');
 console.log('PASS: one request for all lessons, remote refresh, duplicate badges, retry backoff, online recovery, back navigation, incomplete payload preserves badges');
})().catch(e=>{console.error(e);process.exitCode=1});

