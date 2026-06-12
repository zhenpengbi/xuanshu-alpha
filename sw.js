// 玄枢Alpha · Service Worker
// 策略：data/*.json → 网络优先（金融数据要实时）; 其他 → 缓存优先

const CACHE_NAME = 'xuanshu-v2';

const STATIC_ASSETS = [
  '/xuanshu-alpha/',
  '/xuanshu-alpha/index.html',
  '/xuanshu-alpha/logo.svg',
  '/xuanshu-alpha/manifest.json',
  '/xuanshu-alpha/icons/icon-192.png',
  '/xuanshu-alpha/icons/icon-512.png',
  'https://cdn.jsdelivr.net/npm/echarts@5/dist/echarts.min.js',
];

// ── install：预缓存静态资产 ────────────────────────────────────
self.addEventListener('install', event => {
  event.waitUntil(
    caches.open(CACHE_NAME).then(cache =>
      cache.addAll(STATIC_ASSETS).catch(err =>
        console.warn('[SW] pre-cache partial failure', err)
      )
    ).then(() => self.skipWaiting())
  );
});

// ── activate：清除旧缓存 ──────────────────────────────────────
self.addEventListener('activate', event => {
  event.waitUntil(
    caches.keys().then(keys =>
      Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
    ).then(() => self.clients.claim())
  );
});

// ── fetch：双策略路由 ─────────────────────────────────────────
self.addEventListener('fetch', event => {
  const { request } = event;
  const url = new URL(request.url);

  // 非 GET 请求直接透传
  if (request.method !== 'GET') return;

  // data/*.json → 网络优先（失败降级缓存）
  if (url.pathname.match(/\/data\/[^/]+\.json$/) ||
      url.pathname.match(/\/value_compass\/data\/[^/]+\.json$/) ||
      url.pathname.match(/\/backtest\/data\/[^/]+\.json$/)) {
    event.respondWith(networkFirst(request));
    return;
  }

  // 其他资源 → 缓存优先（失败降级网络）
  event.respondWith(cacheFirst(request));
});

async function networkFirst(request) {
  const cache = await caches.open(CACHE_NAME);
  try {
    const response = await fetch(request);
    if (response.ok) {
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    const cached = await cache.match(request);
    return cached || new Response('{"error":"offline"}',
      { headers: { 'Content-Type': 'application/json' } });
  }
}

async function cacheFirst(request) {
  const cached = await caches.match(request);
  if (cached) return cached;
  try {
    const response = await fetch(request);
    if (response.ok) {
      const cache = await caches.open(CACHE_NAME);
      cache.put(request, response.clone());
    }
    return response;
  } catch {
    // 离线时对主页面返回缓存的 index.html
    if (request.mode === 'navigate') {
      const cached = await caches.match('/xuanshu-alpha/index.html');
      if (cached) return cached;
    }
    return new Response('Offline', { status: 503 });
  }
}
