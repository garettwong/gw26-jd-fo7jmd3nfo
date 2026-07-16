const CACHE='erb-master-2026-07-16-V12';
self.addEventListener('install',event=>{self.skipWaiting();});
self.addEventListener('activate',event=>{event.waitUntil(caches.keys().then(keys=>Promise.all(keys.map(key=>caches.delete(key)))).then(()=>self.clients.claim()));});
self.addEventListener('fetch',event=>{if(event.request.method==='GET')event.respondWith(fetch(new Request(event.request,{cache:'no-store'})).catch(()=>fetch(event.request)));});
