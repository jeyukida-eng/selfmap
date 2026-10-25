const CACHE = 'jeyuk-app-v1';
const BASE = new URL('./', self.location.href);
const SHELL = ['', 'index.html', 'install.js', 'manifest.json', 'logo.png',
  'icon-192.png', 'icon-512.png', 'apple-touch-icon.png', 'favicon-32.png'];
const ASSETS = new Set(SHELL.map(path => new URL(path, BASE).href));
self.addEventListener('install', event => {
  event.waitUntil(caches.open(CACHE).then(cache => cache.addAll([...ASSETS]))
    .then(() => self.skipWaiting()));
});
self.addEventListener('activate', event => {
  event.waitUntil(caches.keys().then(keys => Promise.all(
    keys.filter(key => key.startsWith('jeyuk-app-') && key !== CACHE)
      .map(key => caches.delete(key))
  )).then(() => self.clients.claim()));
});
self.addEventListener('fetch', event => {
  const url = new URL(event.request.url);
  // Never intercept external order forms or store customer/order data.
  if (event.request.method !== 'GET' || url.origin !== BASE.origin ||
      !url.pathname.startsWith(BASE.pathname)) return;
  const canonical = new URL(url.pathname, BASE.origin).href;
  if (!ASSETS.has(canonical)) return;
  event.respondWith(fetch(event.request).then(response => {
    if (response.ok && response.type === 'basic') {
      const copy = response.clone();
      event.waitUntil(caches.open(CACHE).then(cache => cache.put(canonical, copy)));
    }
    return response;
  }).catch(async () => {
    const cache = await caches.open(CACHE);
    return await cache.match(canonical) ||
      (event.request.mode === 'navigate' && await cache.match(new URL('./', BASE).href)) ||
      Response.error();
  }));
});
