/**
 * 玄枢Alpha · Service Worker  v3
 * ================================
 * 策略：Network First + Cache Fallback
 * - 优先走网络拿最新数据
 * - 网络不通时从缓存返回上次成功的响应
 * - 缓存范围：HTML + CSS + JS + 数据 JSON
 */

const CACHE_NAME = 'xuanshu-alpha-v3';

const PRECACHE_URLS = [
    './',
    './index.html',
    './manifest.json',
    // CSS & JS（Phase 1 拆分后全部纳入缓存）
    './css/style.css',
    './js/data.js',
    './js/utils.js',
    './js/portfolio.js',
    './js/signals.js',
    './js/news.js',
    './js/rebalance.js',
    './js/market.js',
    './js/analysis.js',
    './js/nav.js',
    './js/theme.js',
    './js/editors.js',
    './js/nav-curve.js',
    './js/app.js',
    './js/ai.js',
    './js/decision-journal.js',
    './js/auth.js',
    // 核心数据（离线时展示上次快照）
    './data/portfolio.json',
    './data/signals.json',
    './data/risk.json',
    './data/rebalance.json',
    './data/portfolio_history.json',
    './data/nav.json',
    './data/news.json',
    './data/news_impact.json',
    './data/fund_recommendations.json',
    './data/active_funds.json',
    './data/positions.json',
    './data/valuation.json',
    './data/indicators.json',
    './data/ai_config.json',
];

// ── 安装：预缓存核心资源 ──
self.addEventListener('install', event => {
    event.waitUntil(
        caches.open(CACHE_NAME)
            .then(cache => cache.addAll(PRECACHE_URLS))
            .then(() => self.skipWaiting())
    );
});

// ── 激活：清理旧版本缓存 ──
self.addEventListener('activate', event => {
    event.waitUntil(
        caches.keys().then(keys =>
            Promise.all(keys.filter(k => k !== CACHE_NAME).map(k => caches.delete(k)))
        ).then(() => self.clients.claim())
    );
});

// ── 请求拦截：Network First + Cache Fallback ──
self.addEventListener('fetch', event => {
    if (event.request.method !== 'GET') return;
    const url = new URL(event.request.url);
    if (url.origin !== self.location.origin) return;

    event.respondWith(
        fetch(event.request).then(response => {
            if (response.ok) {
                const cloned = response.clone();
                caches.open(CACHE_NAME).then(cache => cache.put(event.request, cloned));
            }
            return response;
        }).catch(() =>
            caches.match(event.request).then(cached =>
                cached || new Response('离线模式 · 请检查网络连接', {
                    status: 503,
                    headers: { 'Content-Type': 'text/plain; charset=utf-8' },
                })
            )
        )
    );
});

// ── 推送通知处理 ──
self.addEventListener('push', event => {
    if (!event.data) return;
    const data = event.data.json();
    event.waitUntil(
        self.registration.showNotification(data.title || '玄枢Alpha', {
            body:      data.body  || '',
            icon:      data.icon  || './icons/icon-192.png',
            badge:                   './icons/icon-192.png',
            tag:       'xuanshu-signal',
            renotify:  true,
        })
    );
});

self.addEventListener('notificationclick', event => {
    event.notification.close();
    event.waitUntil(
        clients.matchAll({ type: 'window' }).then(list => {
            if (list.length) return list[0].focus();
            return clients.openWindow('./');
        })
    );
});
