// ========== 玄枢Alpha - 信号推送通知 ==========
// 当有明确买入/卖出信号时，通过浏览器本地通知提醒用户
// 不依赖后端服务器，每天最多提醒一次同类信号

const NOTIFY_CFG = {
    STORE_KEY: 'xuanshu_notify_sent',   // 记录当天已发送的通知类型
    ACTIONS:   new Set(['买入', '定投', '定投补仓', '可加仓', '减仓', '卖出']),
};

// 获取今天的日期字符串，用于去重
function notifyTodayKey() {
    return new Date().toISOString().slice(0, 10);
}

// 检查某个 key 今天是否已推送过
function notifyAlreadySent(key) {
    try {
        const record = JSON.parse(localStorage.getItem(NOTIFY_CFG.STORE_KEY) || '{}');
        return record[notifyTodayKey()]?.includes(key);
    } catch { return false; }
}

// 标记今天某个 key 已推送
function notifyMarkSent(key) {
    try {
        const record = JSON.parse(localStorage.getItem(NOTIFY_CFG.STORE_KEY) || '{}');
        const today  = notifyTodayKey();
        if (!record[today]) record[today] = [];
        if (!record[today].includes(key)) record[today].push(key);
        // 只保留最近 7 天
        Object.keys(record).filter(d => d < new Date(Date.now() - 7*86400000).toISOString().slice(0,10))
              .forEach(d => delete record[d]);
        localStorage.setItem(NOTIFY_CFG.STORE_KEY, JSON.stringify(record));
    } catch {}
}

// 发送一条浏览器通知
function notifySend(title, body, tag = 'xuanshu') {
    if (Notification.permission !== 'granted') return;
    try {
        new Notification(title, {
            body,
            icon:  './icons/icon-192.png',
            badge: './icons/icon-192.png',
            tag,
            renotify: true,
        });
    } catch {}
}

// ── 主函数：扫描信号，有操作机会时推送 ──
function checkAndNotifySignals() {
    if (!('Notification' in window)) return;
    if (Notification.permission !== 'granted')  return;

    const sigs = window.techSignalsData || [];
    if (!sigs.length) return;

    // 筛选有操作方向的信号
    const actionSigs = sigs.filter(s => NOTIFY_CFG.ACTIONS.has(s.signal));
    if (!actionSigs.length) return;

    // 买入类
    const buySigs  = actionSigs.filter(s => ['买入','定投','定投补仓','可加仓'].includes(s.signal));
    const sellSigs = actionSigs.filter(s => ['减仓','卖出'].includes(s.signal));

    if (buySigs.length && !notifyAlreadySent('buy')) {
        const names = buySigs.slice(0, 2).map(s => s.name.slice(0, 8)).join('、');
        notifySend(
            '📈 玄枢Alpha · 买入信号',
            `${names} 等 ${buySigs.length} 个标的出现买入信号，点击查看详情`,
            'xuanshu-buy'
        );
        notifyMarkSent('buy');
    }

    if (sellSigs.length && !notifyAlreadySent('sell')) {
        const names = sellSigs.slice(0, 2).map(s => s.name.slice(0, 8)).join('、');
        notifySend(
            '📉 玄枢Alpha · 减仓提醒',
            `${names} 等 ${sellSigs.length} 个标的出现卖出/减仓信号`,
            'xuanshu-sell'
        );
        notifyMarkSent('sell');
    }
}

// ── 请求通知权限（首次访问提示，不强制）──
async function requestNotifyPermission() {
    if (!('Notification' in window)) return;
    if (Notification.permission !== 'default') return;

    // 延迟 5 秒后再请求，避免页面刚加载就弹权限框
    await new Promise(r => setTimeout(r, 5000));
    try {
        await Notification.requestPermission();
    } catch {}
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    requestNotifyPermission();
});
