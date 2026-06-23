// ========== 玄枢Alpha - 融合决策/回测/情绪/基金/AI建议/主动基 ==========
// ========== 融合决策卡：从 value_compass/data/fusion.json 加载 ==========

// 安全转义 HTML，防止 reason 里的 < > 破坏 DOM（如 "MA5<MA20"）
function escHtml(s) {
    return String(s)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;');
}

const TECH_BADGE_CLS  = { '买入': 'fc-badge-buy', '卖出': 'fc-badge-sell', '持有': 'fc-badge-hold' };
const VALUE_BADGE_CLS = { '优质': 'fc-badge-quality', '合格': 'fc-badge-ok', '瑕疵': 'fc-badge-flaw' };

async function loadAndRenderFusion() {
    await loadJSON('value_compass/data/fusion.json',
        data => renderFusion(data.items || []),
        renderFusionFallback
    );
}

function renderFusion(items) {
    const grid = document.getElementById('fusionGrid');
    if (!grid || !items.length) { renderFusionFallback(); return; }
    // 每张卡独立平铺为 grid 的直接子元素
    grid.innerHTML = items.map(item => {
        const isTrend = item.asset_type === 'trend';
        let badge1, badge2;
        if (isTrend) {
            // 趋势型资产：显示"趋势型"标识 + 技术信号仅供参考
            badge1 = `<span class="fc-badge fc-badge-trend">📈 趋势型</span>`;
            badge2 = `<span class="fc-badge fc-badge-techref">技术参考&nbsp;${escHtml(item.tech_signal)}</span>`;
        } else {
            // 震荡型 / 可穿透资产：技术信号 + 价值评级双确认
            const techCls  = TECH_BADGE_CLS[item.tech_signal]  || 'fc-badge-hold';
            const valueCls = item.applicable
                ? (VALUE_BADGE_CLS[item.value_rating] || 'fc-badge-na')
                : 'fc-badge-na';
            const valueTxt = escHtml(item.applicable ? item.value_rating : '价值框架不适用');
            badge1 = `<span class="fc-badge ${techCls}">技术&nbsp;${escHtml(item.tech_signal)}</span>`;
            badge2 = `<span class="fc-badge ${valueCls}">${valueTxt}</span>`;
        }
        const actionCls = `fc-action-${item.level}`;
        const cardCls   = `fusion-card level-${item.level}`;
        return `<div class="${cardCls}">
            <div class="fc-name">${escHtml(item.name)}</div>
            <div class="fc-code num">${escHtml(item.code)}</div>
            <div class="fc-badges">${badge1}${badge2}</div>
            <div class="fc-action ${actionCls}">${escHtml(item.action)}</div>
            <div class="fc-reason">${escHtml(item.reason)}</div>
        </div>`;
    }).join('');
}

function renderFusionFallback() {
    const grid = document.getElementById('fusionGrid');
    if (grid) grid.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:16px 0;">暂无融合决策数据，请先运行 python3 value_compass/build_fusion.py</div>';
}

// ========== 策略回测：从 backtest/data/backtest.json 加载 ==========
let _btData = null;
let _btChart = null;
let _btSelected = null;

async function loadAndRenderBacktest() {
    await loadJSON('backtest/data/backtest.json', data => {
        _btData = data;
        const results = _btData.results || [];
        renderBacktestCards(results);
        if (results.length) selectBtFund(results[0].code);
    }, renderBacktestFallback);
}

function renderBacktestCards(results) {
    const grid = document.getElementById('backtestCards');
    if (!grid || !results.length) { renderBacktestFallback(); return; }
    // 当前持仓代码集合，用于标注"未持仓"
    const heldCodes = new Set((portfolioData.holdings || []).map(h => h.code));
    // portfolioData 未就绪时（holdings 为空），不显示未持仓标注，避免误标
    const noHoldingData = heldCodes.size === 0;
    grid.innerHTML = results.map(r => {
        const s = r.metrics.strategy;
        const b = r.metrics.benchmark;
        const alpha    = s.annual_return_pct - b.annual_return_pct;
        const aCls     = alpha >= 0 ? 'positive' : 'negative';
        const aSign    = alpha >= 0 ? '+' : '';
        const retCls   = s.annual_return_pct >= 0 ? 'positive' : 'negative';
        const retSign  = s.annual_return_pct >= 0 ? '+' : '';
        const ddCls    = s.max_drawdown_pct <= -20 ? 'negative' : '';
        const shpCls   = s.sharpe >= 1 ? 'positive' : s.sharpe < 0 ? 'negative' : '';
        const isHeld   = noHoldingData || heldCodes.has(r.code);
        const notHeldBadge = isHeld ? '' : '<span class="bt-not-held-badge">未持仓</span>';
        const notHeldCls   = isHeld ? '' : ' not-held';
        return `<div class="backtest-card${notHeldCls}" data-code="${escHtml(r.code)}"
                     onclick="selectBtFund('${escHtml(r.code)}')">
            ${notHeldBadge}
            <div class="bt-name">${escHtml(r.name)}</div>
            <div class="bt-code num">${escHtml(r.code)}</div>
            <div class="bt-metrics">
                <div class="bt-metric">
                    <span class="bt-label">策略年化</span>
                    <span class="bt-val num ${retCls}">${retSign}${s.annual_return_pct.toFixed(1)}%</span>
                    <span class="bt-sub ${aCls}">α ${aSign}${alpha.toFixed(1)}pt</span>
                </div>
                <div class="bt-metric">
                    <span class="bt-label">最大回撤</span>
                    <span class="bt-val num ${ddCls}">${s.max_drawdown_pct.toFixed(1)}%</span>
                    <span class="bt-sub">基准 ${b.max_drawdown_pct.toFixed(1)}%</span>
                </div>
                <div class="bt-metric">
                    <span class="bt-label">夏普比率</span>
                    <span class="bt-val num ${shpCls}">${s.sharpe.toFixed(2)}</span>
                    <span class="bt-sub">基准 ${b.sharpe.toFixed(2)}</span>
                </div>
                <div class="bt-metric">
                    <span class="bt-label">胜率 / 笔数</span>
                    <span class="bt-val num">${s.win_rate_pct.toFixed(0)}%</span>
                    <span class="bt-sub">${s.trade_count} 笔交易</span>
                </div>
            </div>
            <div class="bt-period">${escHtml(r.period_start)} ~ ${escHtml(r.period_end)}</div>
        </div>`;
    }).join('');
}

function selectBtFund(code) {
    _btSelected = code;
    document.querySelectorAll('.backtest-card').forEach(el =>
        el.classList.toggle('selected', el.dataset.code === code));
    if (!_btData) return;
    const result = _btData.results.find(r => r.code === code);
    if (result) renderBtChart(result);
}

function renderBtChart(result) {
    const el = document.getElementById('backtestChart');
    if (!el) return;
    if (!_btChart) {
        _btChart = echarts.init(el);
        window.addEventListener('resize', () => _btChart.resize());
    }
    const c = result.nav_curve;
    const s = result.metrics.strategy;
    const b = result.metrics.benchmark;
    const sSign = s.annual_return_pct >= 0 ? '+' : '';
    const bSign = b.annual_return_pct >= 0 ? '+' : '';
    const alpha = s.annual_return_pct - b.annual_return_pct;
    const cc = getChartColors();
    _btChart.setOption({
        backgroundColor: 'transparent',
        title: {
            text: escHtml(result.name) + ' · 净值曲线对比',
            subtext: '策略 ' + sSign + s.annual_return_pct.toFixed(1) + '%  ·  '
                   + '基准 ' + bSign + b.annual_return_pct.toFixed(1) + '%  ·  '
                   + 'α ' + (alpha >= 0 ? '+' : '') + alpha.toFixed(1) + 'pt  ·  '
                   + '回撤 ' + s.max_drawdown_pct.toFixed(1) + '%  ·  '
                   + '夏普 ' + s.sharpe.toFixed(2),
            left: 'center', top: 14,
            textStyle:    { color: cc.textPrimary, fontSize: 14, fontWeight: 600 },
            subtextStyle: { color: cc.muted, fontSize: 11.5 },
        },
        tooltip: {
            trigger: 'axis',
            backgroundColor: cc.bgTooltip,
            borderColor: cc.lineColor,
            textStyle: { color: cc.textPrimary, fontSize: 12 },
            formatter: params =>
                params[0].axisValue + '<br>' +
                params.map(p => p.marker + p.seriesName + ': ' + (+p.value).toFixed(3)).join('<br>')
        },
        legend: {
            top: 60, left: 'center',
            textStyle: { color: cc.dim, fontSize: 11 },
            data: ['信号策略', '买入持有(基准)']
        },
        grid: { left: 56, right: 22, top: 90, bottom: 80 },
        xAxis: {
            type: 'category', data: c.dates,
            axisLabel: { color: cc.muted, fontSize: 10, rotate: 30, interval: 'auto' },
            axisLine:  { lineStyle: { color: cc.border } },
            splitLine: { show: false },
        },
        yAxis: {
            type: 'value',
            axisLabel: { color: cc.muted, formatter: v => v.toFixed(2) },
            splitLine: { lineStyle: { color: cc.border } },
        },
        series: [
            {
                name: '信号策略', type: 'line', data: c.strategy,
                smooth: true, symbol: 'none',
                lineStyle: { color: cc.green, width: 2.2 },
                areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [{ offset: 0, color: cc.green + '38' },
                                 { offset: 1, color: cc.green + '05' }] }},
            },
            {
                name: '买入持有(基准)', type: 'line', data: c.benchmark,
                smooth: true, symbol: 'none',
                lineStyle: { color: cc.accent + 'b0', width: 1.6, type: 'dashed' },
            }
        ]
    });
}

function renderBacktestFallback() {
    const grid = document.getElementById('backtestCards');
    if (grid) grid.innerHTML =
        '<div style="color:var(--text-muted);font-size:13px;padding:16px 0;">' +
        '暂无回测数据，请先运行 python3 backtest/backtest_engine.py</div>';
}

// ========== 新闻情绪：从 data/news_impact.json 加载 ==========
async function loadAndRenderSentiment() {
    await loadJSON('data/news_impact.json',
        data => renderSentiment(data.items || [], data),
        renderSentimentFallback
    );
}

function renderSentiment(items, meta) {
    const grid = document.getElementById('sentimentGrid');
    if (!grid || !items.length) { renderSentimentFallback(); return; }
    const total = (meta.total_news || 1);
    grid.innerHTML = items.map(item => {
        const score = item.sentiment_score;
        const label = item.sentiment_label;
        const bull  = item.bullish_count;
        const bear  = item.bearish_count;
        const neut  = item.neutral_count;
        const cardCls  = score > 0 ? 'sent-bull' : score < 0 ? 'sent-bear' : 'sent-neut';
        const labelCls = score > 0 ? 'sc-label-bull' : score < 0 ? 'sc-label-bear' : 'sc-label-neut';
        const sign     = score > 0 ? '+' : '';
        // Progress bar widths (bull + bear share 100%, neutral excluded)
        const tot = bull + bear || 1;
        const bw = Math.round(bull / tot * 100);
        const rw = 100 - bw;
        // Top news (max 3)
        const newsHtml = (item.top_impact_news || []).slice(0, 3).map(n => {
            const dc = n.sentiment === '利多' ? 'dot-bull' : n.sentiment === '利空' ? 'dot-bear' : 'dot-neut';
return `<div class="sc-news-item">
<span class="sc-news-dot ${dc}"></span>
<span class="sc-news-title" title="${escHtml(n.title)}">${escHtml(n.title)}</span>
</div>`;
        }).join('');
        return `<div class="sentiment-card ${cardCls}">
            <div class="sc-name">${escHtml(item.name)}</div>
            <div class="sc-code num">${escHtml(item.code)}</div>
            <span class="sc-label ${labelCls}">${escHtml(label)}&nbsp;${sign}${score}</span>
            <div class="sc-bar-wrap">
                <div class="sc-bar-bull" style="width:${bw}%"></div>
                <div class="sc-bar-bear" style="width:${rw}%"></div>
            </div>
            <div class="sc-counts">
                <span class="bull">利多 ${bull} 条</span>&nbsp;/&nbsp;
                <span class="bear">利空 ${bear} 条</span>&nbsp;/&nbsp;中性 ${neut} 条
            </div>
            <div class="sc-news">${newsHtml || '<span style="color:var(--text-muted)">暂无相关新闻</span>'}</div>
        </div>`;
    }).join('');
}

function renderSentimentFallback() {
    const grid = document.getElementById('sentimentGrid');
    if (grid) grid.innerHTML = '<div style="color:var(--text-muted);font-size:13px;padding:16px 0;">暂无情绪数据，请先运行 python3 scripts/build_news_impact.py</div>';
}

// ========== 基金雷达：从 data/fund_recommendations.json 加载 ==========
async function loadAndRenderRadar() {
    await loadJSON('data/fund_recommendations.json',
        data => renderRadar(data),
        renderRadarFallback
    );
}

function renderRadar(data) {
    const wrap = document.getElementById('fundRadarSection');
    if (!wrap) return;

    const recs       = data.recommendations || [];   // 恐慌触发扫描
    const undervalued = data.undervalued   || [];    // 低位常态扫描

    // 两个列表都空 → 显示空状态
    if (!recs.length && !undervalued.length) {
        const msg = data.message || '当前市场情绪平稳，暂无扫描结果';
        wrap.innerHTML = `<div class="radar-empty">
            <div style="font-size:28px;margin-bottom:12px;">📡</div>
            <div style="font-size:14px;color:var(--text-secondary);margin-bottom:6px;">${escHtml(msg)}</div>
            <div style="font-size:11px;color:var(--text-muted);">avg_sell_score = ${data.avg_sell_score || 0} · 触发门槛 ≥ ${data.panic_threshold || 2.0}</div>
        </div>`;
        return;
    }

    // ---- 卡片渲染函数（超跌恐慌 & 低位观察共用）----
    function buildCard(r, isPanic) {
        const isBounce = r.signal === '超跌反弹';
        const cardCls  = isBounce ? 'signal-rebound' : 'signal-watch';
        const badgeCls = isBounce ? 'badge-rebound'  : 'badge-watch';

        if (isPanic) {
            // 超跌恐慌：展示 20日跌幅 + RSI + 规模
            return `<div class="radar-card ${cardCls}">
                <div class="rc-header">
                    <div>
                        <div class="rc-name">${escHtml(r.name)}</div>
                        <div class="rc-code num">${escHtml(r.code)}</div>
                    </div>
                    <span class="rc-signal-badge ${badgeCls}">${escHtml(r.signal)}</span>
                </div>
                <div class="rc-metrics">
                    <div class="rc-metric">
                        <span class="rc-metric-label">20日跌幅</span>
                        <span class="rc-metric-val negative">-${r.drop_20d_pct != null ? r.drop_20d_pct.toFixed(1) : '--'}%</span>
                    </div>
                    <div class="rc-metric">
                        <span class="rc-metric-label">RSI(14)</span>
                        <span class="rc-metric-val" style="color:var(--accent);">${r.rsi14 != null ? r.rsi14.toFixed(1) : '--'}</span>
                    </div>
                    <div class="rc-metric">
                        <span class="rc-metric-label">规模(亿)</span>
                        <span class="rc-metric-val">${r.scale_bn > 0 ? r.scale_bn.toFixed(1) : '--'}</span>
                    </div>
                </div>
                <div class="rc-reason">${escHtml(r.reason)}</div>
                ${r.risk_warning ? `<div class="rc-warning">${escHtml(r.risk_warning)}</div>` : ''}
            </div>`;
        } else {
            // 低位观察：展示 60日跌幅 + RSI + 今日涨跌
            const drop60   = r.drop_60d_pct  != null ? r.drop_60d_pct.toFixed(1)  : '--';
            const rsi      = r.rsi14         != null ? r.rsi14.toFixed(1)          : '--';
            const todayChg = r.today_chg_pct != null ? r.today_chg_pct.toFixed(2) : '--';
            const todayCls = r.today_chg_pct >= 0 ? 'positive' : 'negative';
            const todayStr = r.today_chg_pct >= 0 ? `+${todayChg}%` : `${todayChg}%`;
            return `<div class="radar-card signal-watch">
                <div class="rc-header">
                    <div>
                        <div class="rc-name">${escHtml(r.name)}</div>
                        <div class="rc-code num">${escHtml(r.code)}</div>
                    </div>
                    <span class="rc-signal-badge badge-watch">${escHtml(r.signal || '低位观察')}</span>
                </div>
                <div class="rc-metrics">
                    <div class="rc-metric">
                        <span class="rc-metric-label">60日跌幅</span>
                        <span class="rc-metric-val negative">-${drop60}%</span>
                    </div>
                    <div class="rc-metric">
                        <span class="rc-metric-label">RSI(14)</span>
                        <span class="rc-metric-val" style="color:var(--accent);">${rsi}</span>
                    </div>
                    <div class="rc-metric">
                        <span class="rc-metric-label">今日涨跌</span>
                        <span class="rc-metric-val ${todayCls}">${todayStr}</span>
                    </div>
                </div>
                <div class="rc-reason">${escHtml(r.reason || '')}</div>
            </div>`;
        }
    }

    let html = '';

    // ---- 超跌恐慌扫描（仅 triggered 时展示）----
    if (data.triggered && recs.length) {
        html += `<div class="radar-section-label" style="grid-column:1/-1;display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <span style="font-size:11px;font-weight:700;color:var(--red);letter-spacing:.5px;text-transform:uppercase;">🚨 超跌恐慌扫描</span>
            <span style="font-size:10px;color:var(--text-muted);">avg_sell_score=${data.avg_sell_score || 0} ≥ ${data.panic_threshold || 2.0}</span>
        </div>`;
        html += recs.map(r => buildCard(r, true)).join('');
    }

    // ---- 低位常态扫描（始终展示）----
    if (undervalued.length) {
        const separator = (data.triggered && recs.length)
            ? `<div style="grid-column:1/-1;border-top:1px solid var(--line);margin:8px 0;"></div>` : '';
        html += `${separator}<div class="radar-section-label" style="grid-column:1/-1;display:flex;align-items:center;gap:8px;margin-bottom:4px;">
            <span style="font-size:11px;font-weight:700;color:var(--accent);letter-spacing:.5px;text-transform:uppercase;">📉 低位观察</span>
            <span style="font-size:10px;color:var(--text-muted);">近60日回调 · RSI偏低</span>
        </div>`;
        html += undervalued.map(r => buildCard(r, false)).join('');
    }

    // ---- 情绪状态条（无超跌时也显示市场温度）----
    if (!data.triggered) {
        html += `<div style="grid-column:1/-1;margin-top:6px;padding:8px 12px;background:var(--bg-hover);border-radius:8px;border:1px solid var(--line);display:flex;align-items:center;gap:8px;">
            <span style="font-size:11px;color:var(--text-muted);">📡 市场情绪平稳</span>
            <span style="font-size:11px;color:var(--text-muted);">avg_sell_score = ${data.avg_sell_score || 0} · 未达超跌阈值（≥${data.panic_threshold || 2.0}）</span>
        </div>`;
    }

    const disc = escHtml(data.disclaimer || '以上仅为量化扫描结果，不构成投资建议');
    wrap.innerHTML = `<div class="radar-grid">${html}</div>
        <div class="radar-disclaimer">⚠️ ${disc}</div>`;
}

function renderRadarFallback() {
    const wrap = document.getElementById('fundRadarSection');
    if (wrap) wrap.innerHTML = '<div class="radar-empty">暂无基金雷达数据，请先运行 python3 scripts/fund_scanner.py</div>';
}

// ========== AI 操作建议（真实数据版，读 portfolio.json + rebalance.json）==========

async function loadAndRenderAdviceModule() {
    // 并发加载 portfolio + rebalance + fusion（signals 已在 loadSignals() 加载）
    let portfolio = null, rebalance = null, fusion = null;
    try {
        [portfolio, rebalance, fusion] = await Promise.all([
            fetch('data/portfolio.json?t='                 + Date.now()).then(r => r.ok ? r.json() : null),
            fetch('data/rebalance.json?t='                 + Date.now()).then(r => r.ok ? r.json() : null),
            fetch('value_compass/data/fusion.json?t='      + Date.now()).then(r => r.ok ? r.json() : null),
        ]);
    } catch(e) { console.warn('advice module load failed', e); }

    _renderAdviceDataBar(portfolio, rebalance);
    _renderAdviceSignalCard(portfolio, rebalance, fusion);
    _renderAdviceRebalanceCard(rebalance);
window._cachedRebalance = rebalance;
_renderBulletZone(rebalance, portfolio);
_renderUSMarketPanel(rebalance);
}

function _renderAdviceDataBar(portfolio, rebalance) {
    const bar = document.getElementById('adviceDataBar');
    if (!bar) return;
    const pt = (portfolio && portfolio.updateTime) || '--';
    const rb = (rebalance && rebalance.portfolio_updateTime) || pt;
    const tot = (rebalance && rebalance.total_value) ? `¥${rebalance.total_value.toLocaleString('zh-CN',{minimumFractionDigits:2})}` : '--';
    bar.innerHTML = `
        <span class="adb-item"><span class="adb-dot"></span>持仓快照: ${escHtml(rb)}</span>
        <span class="adb-item"><span class="adb-dot" style="background:var(--accent)"></span>投资性资产: ${escHtml(tot)}</span>
        <span class="adb-item"><span class="adb-dot" style="background:var(--text-muted)"></span>数据: portfolio.json + rebalance.json + signals.json</span>
    `;
}

function _renderAdviceSignalCard(portfolio, rebalance, fusion) {
    // 综合信号摘要：从 fusion.json 提取 oscillation 资产信号 + 再平衡高优先级动作
    const actEl  = document.getElementById('adviceAction');
    const reaEl  = document.getElementById('adviceReason');
    const metaEl = document.getElementById('adviceMeta');
    if (!actEl) return;

    const items = (fusion && fusion.items) || [];
    const oscItems = items.filter(i => i.asset_type === 'oscillation');
    const actions  = (rebalance && rebalance.actions) || [];
    const highActs = actions.filter(a => a.priority === 'high');
    const toEstab  = actions.filter(a => a.action === '待建仓');

    // 确定主行动
    let mainAction = '持有观察';
    if (highActs.length > 0)        mainAction = '需要操作 · 见清单';
    else if (toEstab.length > 0)    mainAction = '待建仓类别 · 可分批入场';
    actEl.textContent = mainAction;

    // 理由列表
    const reasons = [];
    oscItems.forEach(i => {
        const s = i.tech_signal === '买入' ? '↑ 买入' : i.tech_signal === '卖出' ? '↓ 卖出' : '→ 观望';
        reasons.push(`${i.name}：技术${s}，建议「${i.action}」`);
    });
    toEstab.forEach(a => reasons.push(`${a.category} 待建仓，缺口 ≈ ¥${Math.abs(a.deviation_amount||0).toLocaleString('zh-CN',{maximumFractionDigits:0})}`));
    highActs.slice(0, 2).forEach(a => reasons.push(`${a.category} [${a.action}]：${(a.reason||'').slice(0,55)}…`));

    reaEl.innerHTML = reasons.length
        ? reasons.map(r => `<div style="margin-bottom:6px;">• ${escHtml(r)}</div>`).join('')
        : '<div style="color:var(--text-muted);">当前无高优先级操作建议</div>';

    // 元信息（从 signalData.us 读 QQQ 评分，从 signalData.gold 读日期）
    const u = signalData && signalData.us;
    const g = signalData && signalData.gold;
    const qqq = u ? `QQQ评分 ${Math.round(u.qqq_score||0)}` : '';
    const dt  = (rebalance && rebalance.portfolio_updateTime) || (g && g.date) || '--';
    metaEl.textContent = `持仓: ${dt} · ${qqq} · signals + fusion 双确认`;
}

function _renderAdviceRebalanceCard(rebalance) {
    const listEl = document.getElementById('rebalanceList');
    const metaEl = document.getElementById('rebalanceMeta');
    if (!listEl) return;

    if (!rebalance || !rebalance.actions || !rebalance.actions.length) {
        listEl.innerHTML = '<div style="color:var(--text-muted);">再平衡数据加载失败，请运行 python3 data/rebalance.py</div>';
        return;
    }

    // 按优先级排序，只展示 needs_action=true 的
    const acts = rebalance.actions.filter(a => a.needs_action);
    if (!acts.length) {
        listEl.innerHTML = '<div style="color:var(--text-muted);">当前配置接近目标，无需调整</div>';
        if (metaEl) metaEl.textContent = '所有类别偏差在容忍区间内';
        return;
    }

    const PRIORITY_CLS = { high: 'rb-action-high', medium: 'rb-action-medium', low: 'rb-action-low' };
    const PENDING_ACTS = new Set(['待建仓', '待主动基诊断']);

    listEl.innerHTML = acts.map(a => {
        const pCls = PENDING_ACTS.has(a.action) ? 'rb-action-pending' : (PRIORITY_CLS[a.priority] || 'rb-action-low');
        const amtHtml = a.recommend_amount
            ? `<span class="rb-amount"> ≈ ¥${Math.abs(a.recommend_amount).toLocaleString('zh-CN',{maximumFractionDigits:0})}</span>`
            : '';
        const sign = a.deviation >= 0 ? '+' : '';
        return `<div class="rb-item">
            <span class="rb-cat">${escHtml(a.category)}</span>
            <span class="rb-action ${pCls}">${escHtml(a.action)}</span>${amtHtml}
            <span style="color:var(--text-muted);font-size:11px;"> (${sign}${a.deviation.toFixed(1)}pt)</span>
            <div class="rb-reason">${escHtml((a.reason||'').slice(0, 90))}${(a.reason||'').length > 90 ? '…' : ''}</div>
        </div>`;
    }).join('');

    if (metaEl) {
        const pt = rebalance.portfolio_updateTime || '--';
        const tv = rebalance.total_value ? `¥${rebalance.total_value.toLocaleString('zh-CN',{minimumFractionDigits:2})}` : '--';
        metaEl.textContent = `持仓快照: ${pt} · 投资性资产: ${tv} · 阈值 ±${rebalance.rebalance_threshold_pct||5}pt`;
    }
}

function _renderBulletZone(rebalance, portfolio) {
    const el = document.getElementById('bulletZoneContent');
    if (!el) return;

    const bullet   = rebalance && rebalance.bullet;
    const bAmount  = bullet ? bullet.amount : 0;
    const bPlan    = (bullet && bullet.plan) || [];
    const holdings = portfolio && portfolio.holdings;
    const cashH    = holdings && holdings.find(h => h.assetType === 'cash');
    const cashAmt  = cashH ? cashH.amount : bAmount;

    const amtStr = `<div class="cash-edit-wrap" id="cashAmtWrap"><span class="bullet-amount" id="cashAmtDisplay">¥${cashAmt > 0 ? cashAmt.toLocaleString('zh-CN',{minimumFractionDigits:2}) : '--'}</span><button class="cash-edit-btn" title="编辑余额宝可用" onclick="_bulletCashEditStart(${cashAmt})">${_SVG_PENCIL}</button></div>`;

    const planHtml = bPlan.length
        ? bPlan.map(p => `<div class="bullet-plan-item">
            <span>${escHtml(p.category)} <span style="color:var(--accent);font-size:12px;">${escHtml(p.action)}</span></span>
            <span class="rb-amount">¥${(p.alloc||0).toLocaleString('zh-CN',{maximumFractionDigits:0})}</span>
          </div>`).join('')
        : `<div style="color:var(--text-muted);font-size:13px;margin-top:8px;">
            ${cashAmt > 500 ? '子弹可用，优先补待建仓类别（纳指100/标普500）定投入场' : '子弹不足 ¥500，建议先积累子弹再操作'}
           </div>`;

    el.innerHTML = `
        <div class="bullet-header">
            <div>
                <div style="font-size:11px;color:var(--text-muted);letter-spacing:1px;text-transform:uppercase;margin-bottom:4px;">余额宝可用</div>
                ${amtStr}
            </div>
            <div style="font-size:12px;color:var(--text-muted);text-align:right;line-height:1.8;">
                优先级：待建仓 → 低配加仓<br>货币基金不计入再平衡盘
            </div>
        </div>
        ${planHtml}
    `;
}

function _renderUSMarketPanel(rebalance) {
    const el = document.getElementById('usMarketContent');
    if (!el) return;

    // 从 rebalance.json 取纳指/标普动作
    const acts = (rebalance && rebalance.actions) || [];
    const qqq  = acts.find(a => a.category === '纳指100');
    const spy  = acts.find(a => a.category === '标普500');

    // VIX / QQQ 评分 from signalData
    const usData = signalData && signalData.us;
    const qqqScore = usData ? Math.round(usData.qqq_score || 0) : null;
    const spyScore = usData ? Math.round(usData.spy_score || 0) : null;

    // VIX
    let vix = null;
    const gData = signalData && signalData.gold;
    if (gData && gData.score_detail) {
        for (const k in gData.score_detail) {
            if (k.includes('VIX')) {
                const m = String(gData.score_detail[k]).match(/VIX=([\d.]+)/);
                if (m) { vix = parseFloat(m[1]); break; }
            }
        }
    }

    // 入场倾向
    function entryTend(score, vixVal, action) {
        if (action === '待建仓') {
            if (vixVal != null && vixVal > 25) return { cls: 'tend-enter', txt: '恐慌加深 → 分批建仓机会' };
            if (score != null && score >= 60) return { cls: 'tend-watch', txt: '信号偏强，等回调再入' };
            return { cls: 'tend-wait', txt: '定投等待，勿追高' };
        }
        return { cls: 'tend-watch', txt: '保持观察' };
    }
    const qqqTend = entryTend(qqqScore, vix, qqq && qqq.action);
    const spyTend = entryTend(spyScore, vix, spy && spy.action);

    // 从 backtest.json 计算距高点回撤（_btData 是全局变量）
    function calcDrawdown(code) {
        if (!_btData) return null;
        const r = _btData.results && _btData.results.find(x => x.code === code);
        if (!r || !r.nav_curve || !r.nav_curve.benchmark) return null;
        const bench = r.nav_curve.benchmark;
        const cur = bench[bench.length - 1];
        const peak = Math.max(...bench);
        if (!peak) return null;
        return round2((peak - cur) / peak * 100);
    }
    function round2(v) { return Math.round(v * 100) / 100; }

    const qqqDd = calcDrawdown('513100');
    const spyDd = calcDrawdown('513500');
    const ddStr = v => v != null ? `-${v.toFixed(1)}%` : '--';
    const scoreStr = v => v != null ? `${v}分` : '--';
    const vixStr = vix != null ? vix.toFixed(1) : '--';
    const vixCls = vix == null ? '' : vix > 30 ? 'negative' : vix > 20 ? '' : 'positive';

    el.innerHTML = `<div class="us-panel-grid">
        <div class="us-panel-item">
            <div class="us-label">纳指100 (QQQ)</div>
            <div class="us-val">${scoreStr(qqqScore)}</div>
            <div class="us-sub">信号评分 | 距高点 ${ddStr(qqqDd)}</div>
            <div class="us-sub" style="margin-top:6px;">建议: ${qqq ? escHtml(qqq.action) : '待建仓'}</div>
            <div class="us-sub ${qqqTend.cls}" style="margin-top:4px;">→ ${qqqTend.txt}</div>
        </div>
        <div class="us-panel-item">
            <div class="us-label">标普500 (SPY)</div>
            <div class="us-val">${scoreStr(spyScore)}</div>
            <div class="us-sub">信号评分 | 距高点 ${ddStr(spyDd)}</div>
            <div class="us-sub" style="margin-top:6px;">建议: ${spy ? escHtml(spy.action) : '待建仓'}</div>
            <div class="us-sub ${spyTend.cls}" style="margin-top:4px;">→ ${spyTend.txt}</div>
        </div>
        <div class="us-panel-item">
            <div class="us-label">VIX 恐慌指数</div>
            <div class="us-val ${vixCls}">${vixStr}</div>
            <div class="us-sub">${vix == null ? '--' : vix > 30 ? '高恐慌 · 逢恐贪婪入场窗口' : vix > 20 ? '中等波动 · 谨慎' : '低恐慌 · 市场平稳'}</div>
            <div class="us-sub" style="margin-top:8px;color:var(--text-muted);font-size:10px;">
                估值分位 -- (P2 任务5 填入)
            </div>
        </div>
    </div>`;
}

// ========== 主动基诊断：从 data/active_funds.json 加载 ==========
async function loadAndRenderActiveFunds() {
    await loadJSON('data/active_funds.json',
        data => renderActiveFunds(data.funds || []),
        renderActiveFundsFallback
    );
}

function renderActiveFunds(funds) {
    const grid = document.getElementById('activeFundGrid');
    if (!grid || !funds.length) { renderActiveFundsFallback(); return; }

    const ACTION_CLS = {
        '建议评估替换': { card: 'afd-replace', badge: 'afd-badge-replace' },
        '持有但关注':   { card: 'afd-watch',   badge: 'afd-badge-watch'   },
        '可持有':       { card: 'afd-hold',     badge: 'afd-badge-hold'    },
    };

    grid.innerHTML = funds.map(f => {
        const diag   = f.diagnosis || {};
        const action = diag.action || '待诊断';
        const cls    = ACTION_CLS[action] || { card: 'afd-watch', badge: 'afd-badge-watch' };
        const pctYtd = f.rank_percentile_ytd;
        const alpha  = f.alpha_pct;
        const tenure = f.manager_tenure_days ? Math.round(f.manager_tenure_days / 365 * 10) / 10 : null;

        // 名称不符警告
        const mismatchHtml = f.name_mismatch
            ? `<div class="afd-mismatch">
                ⚠️ 代码 ${escHtml(f.code)} 官方名称与持仓标注不符<br>
                官方：${escHtml(f.official_name || '--')}<br>
                持仓标注：${escHtml(f.portfolio_name || '--')}
               </div>`
            : '';

        // 理由 + 警告
        const reasons = [...(diag.reasons || []), ...(diag.warnings || [])].slice(0, 3);
        const reasonHtml = reasons.length
            ? reasons.map(r => `<div>• ${escHtml(r)}</div>`).join('')
            : '<div>详见 data/active_funds.json</div>';

        // 质地摘要
        const qs = f.quality_summary;
        const qualityHtml = qs
            ? `<div class="afd-m-label" style="margin-top:8px;">持仓质地</div>
               <div style="font-size:11.5px;color:var(--text-muted);">${escHtml(qs.verdict || '--')}</div>`
            : '';

        return `<div class="afd-card ${cls.card}">
            ${mismatchHtml}
            <div class="afd-name">${escHtml(f.official_name || f.portfolio_name)}</div>
            <div class="afd-subname">${escHtml(f.code)} · ${escHtml(f.fund_type || '--')} · ${escHtml(f.company || '--')}</div>
            <div class="afd-metrics">
                <div>
                    <div class="afd-m-label">同类排名</div>
                    <div class="afd-m-val">${pctYtd != null ? `前${pctYtd.toFixed(0)}%` : '--'}</div>
                </div>
                <div>
                    <div class="afd-m-label">经理年限</div>
                    <div class="afd-m-val">${tenure != null ? tenure + 'y' : '--'}</div>
                </div>
                <div>
                    <div class="afd-m-label">规模</div>
                    <div class="afd-m-val" style="font-size:13px;">${escHtml(f.scale_str || '--')}</div>
                </div>
            </div>
            <span class="afd-action-badge ${cls.badge}">${escHtml(action)}</span>
            <div class="afd-reasons">${reasonHtml}</div>
            ${qualityHtml}
        </div>`;
    }).join('');
}

function renderActiveFundsFallback() {
    const grid = document.getElementById('activeFundGrid');
    if (grid) grid.innerHTML =
        '<div style="color:var(--text-muted);font-size:13px;padding:16px 0;">' +
        '暂无主动基诊断数据，请先运行 python3 scripts/active_fund_diagnose.py</div>';
}

