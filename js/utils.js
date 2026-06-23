// ========== 玄枢Alpha - 工具函数 ==========
// ========== Utility Functions ==========
function fmt(val, decimals=2) {
    return val.toLocaleString('zh-CN', {minimumFractionDigits:decimals, maximumFractionDigits:decimals});
}
function fmtMoney(val) { return '¥' + fmt(val); }
function fmtReturn(val) { return (val>=0?'+':'') + fmt(val); }
function fmtPct(val) { return (val>=0?'+':'') + val.toFixed(2) + '%'; }
function retClass(val) { return val>0?'positive':val<0?'negative':''; }

function getCategoryTagClass(cat) {
    const m = {'黄金':'tag-gold','AI/科技':'tag-tech','光伏/新能源':'tag-green','有色金属':'tag-metal','高端制造':'tag-mfg','货币基金':'tag-cash'};
    return m[cat]||'tag-cash';
}


// ========== 通用 JSON 加载工具 ==========
/**
 * 加载 JSON 文件并回调渲染函数。
 * 统一处理 cache-busting、NaN 清洗、错误兜底。
 * @param {string} path - 文件路径（不含 ?t= 参数）
 * @param {Function} onSuccess - 数据加载成功时的回调 (data) => void
 * @param {Function} [onFallback] - 加载失败时的兜底回调 () => void
 */
async function loadJSON(path, onSuccess, onFallback) {
    try {
        const r = await fetch(path + '?t=' + Date.now());
        if (!r.ok) { if (onFallback) onFallback(); return null; }
        const txt = await r.text();
        // 兼容含 NaN 的非标准 JSON（如 gold_signal.json）
        const data = JSON.parse(txt.replace(/:\s*NaN\b/g, ': null'));
        onSuccess(data);
        return data;
    } catch(e) {
        console.warn('[loadJSON] 加载失败:', path, e);
        if (onFallback) onFallback();
        return null;
    }
}
