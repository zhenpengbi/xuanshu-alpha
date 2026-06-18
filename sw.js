/**
 * 玄枢Alpha · Service Worker
 * ==========================
 * 策略：Network First + Cache Fallback
 * - 优先走网络拿最新数据
 * - 网络不通时从缓存返回上次成功的响应
 * - 缓存范围：index.html + data/*.json + manifest.json
 */

const CACHE_NAME = 'xuanshu-alpha-v1';

const PRECACHE_URLS = [
    './',
    './index.html',
    './manifest.json',
    './data/signals.json',
    './data/risk.json',
    './data/valuation.json',
    './data/rebalance.json',
    './data/portfolio.json',
    './data/nav.json',
    './data/indicators.json',
    './data/news_impact.json',
    './data/active_funds.json',
    './data/fund_recommendations.json',
    './data/positions.json',
    './data/portfolio_history.json',
];

// 安装：预缓存核心资源
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME).then(cache => {
            return cache.addAll(PRECACHE_URLS);
        }).then(() => self.skipWaiting())
    );
});

// 激活：清理旧缓存
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys => {
            return Promise.all(
                keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k))
            );
        }).then(() => self.clients.claim())
    );
});

// 请求拦截：Network First + Cache Fallback
self.addEventListener('fetch', event => {
    // 只处理同源 GET 请求
    if (event.request.method !== 'GET') return;

    event.respondWith(
        fetch(event.request).then(response => {
            // 网络成功：缓存后返回
            if (response.ok) {
                const cloned = response.clone();
                caches.open(CACHE_NAME).then(cache => {
                    cache.put(event.request, cloned);
                });
            }
            return response;
        }).catch(() => {
            // 网络失败：从缓存返回
            return caches.match(event.request).then(cached => {
                return cached || new Response('Offline', { status: 503, statusText: 'Service Unavailable' });
            });
        })
    );
});
