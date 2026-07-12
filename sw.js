const BUILD_ID = 'checking06-hk281dscw7-mc0106ds-20260712-r02';

self.addEventListener('install', event => {
  self.skipWaiting();
});

self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys()
      .then(keys => Promise.all(keys.map(key => caches.delete(key))))
      .then(() => self.clients.claim())
  );
});

self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  if (url.origin !== self.location.origin) return;
  if (event.request.method !== 'GET') return;
  const req = new Request(event.request, { cache: 'no-store' });
  event.respondWith(fetch(req).catch(() => fetch(event.request)));
});
