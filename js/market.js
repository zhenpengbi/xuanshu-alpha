// ========== 玄枢Alpha - 行情加载 ==========
// ========== 实时行情：从 prices.json 加载 ==========
async function loadAndRenderPrices() {
    await loadJSON('data/prices.json', prices => {
        window.pricesData = prices;
        renderPricesSection(prices);
        const latest = prices.reduce((a, b) => a.updated_at > b.updated_at ? a : b);
        document.getElementById('headerUpdateTime').textContent =
            window.innerWidth <= 768 ? latest.updated_at : ('行情更新: ' + latest.updated_at);
    });
}

function renderPricesSection(prices) {
    const grid = document.getElementById('pricesGrid');
    if (!grid) return;
    grid.innerHTML = prices.map(p => {
        const isUp = p.change_pct >= 0;
        const sign = isUp ? '+' : '';
        const cls = isUp ? 'positive' : 'negative';
        const cardCls = isUp ? 'price-up' : 'price-down';
        return `<div class="price-card ${cardCls}">
            <div class="pc-name">${p.name}</div>
            <div class="pc-code num">${p.code}</div>
            <div class="pc-price-wrap">
                <div class="pc-price num">${p.price.toFixed(4)}</div>
                <div class="pc-change ${cls}">${sign}${p.change_pct.toFixed(2)}%</div>
            </div>
            <div class="pc-time">更新: ${p.updated_at}</div>
        </div>`;
    }).join('');
}

// ========== 技术指标信号：从 signals.json 加载 ==========
async function loadAndRenderTechSignals() {
    await loadJSON('data/signals.json', data => {
        window.techSignalsData = data.signals || [];   // 缓存供健康体检复用
        renderTechSignals(window.techSignalsData);
    }, renderTechSignalsFallback);
}

// ── 信号翻译辅助函数 ──
function _rsiInfo(rsi) {
    if (rsi == null) return null;
    if (rsi < 20) return { label:'严重超卖', cls:'positive', tip:'跌幅很大，历史上强烈反弹信号，但需结合趋势判断' };
    if (rsi < 30) return { label:'超卖',     cls:'positive', tip:'近期跌幅明显，历史上此区间反弹概率偏高' };
    if (rsi < 40) return { label:'弱超卖',   cls:'warn',     tip:'有一定跌幅，可考虑少量介入，不宜重仓' };
    if (rsi < 60) return { label:'中性',     cls:'neutral',  tip:'涨跌均衡，无明显超买或超卖信号，观望为主' };
    if (rsi < 70) return { label:'弱超买',   cls:'warn',     tip:'近期涨幅较大，注意追高风险，可等回调' };
    if (rsi < 80) return { label:'超买',     cls:'negative', tip:'近期涨幅明显，建议等待回调后再介入' };
    return             { label:'严重超买',   cls:'negative', tip:'涨幅过大，回调风险高，不建议此时买入' };
}

function _maInfo(ma5, ma20) {
    if (ma5 == null || ma20 == null) return null;
    return ma5 > ma20
        ? { label:'金叉', cls:'positive', tip:'短期均线在长期均线上方，短期走势偏强，动能向好' }
        : { label:'死叉', cls:'negative', tip:'短期均线在长期均线下方，短期走势偏弱，动能不足' };
}

function _macdInfo(trend) {
    if (!trend) return null;
    return trend === 'bullish'
        ? { label:'多头', cls:'positive', tip:'趋势动能向上，有助于持续上涨' }
        : { label:'空头', cls:'negative', tip:'趋势动能向下，建议分批介入而非一次重仓' };
}

function _sigConclusion(s) {
    const TYPE = { trend:'趋势型', oscillation:'震荡型', active:'主动型', pending:'待建仓' };
    const ACTION = {
        '买入':'信号较强，可以买入',        '定投':'适合定期定额投入',
        '定投补仓':'逢低分批补仓',           '可加仓':'有加仓机会，量力而行',
        '持有':'维持现有仓位，不追涨不杀跌', '持有观察':'观望为主，等待更清晰信号',
        '减仓':'建议分批降低仓位',            '卖出':'信号偏空，考虑减仓',
        '高估警惕':'估值偏高，避免追高',      '待建仓':'尚未建仓，可考虑分批定投建仓'
    };
    return `${TYPE[s.asset_type] || ''}　${ACTION[s.signal] || s.signal}`;
}

function _amountHint(s) {
    const BUY  = new Set(['买入','定投','定投补仓','可加仓','待建仓']);
    const SELL = new Set(['减仓','卖出']);
    if (!BUY.has(s.signal) && !SELL.has(s.signal)) return '';
    if (!portfolioData || !portfolioData.totalAsset) return '';
    // 余额宝 = 货币基金持仓
    const cashH  = (portfolioData.holdings||[]).find(h => h.category==='货币基金');
    const cash   = cashH ? cashH.amount : 0;
    const devAmt = Math.abs((s.deviation_pt||0)/100 * portfolioData.totalAsset);
    if (devAmt < 200) return '';
    if (BUY.has(s.signal) && (s.deviation_pt||0) <= 0) {
        const suggest = Math.min(devAmt * 0.5, cash * 0.5);
        if (suggest < 200) return '';
        return `💰 参考：从余额宝转入约 ¥${(Math.round(suggest/100)*100).toLocaleString('zh-CN')}`;
    }
    if (SELL.has(s.signal) && (s.deviation_pt||0) > 0) {
        const suggest = devAmt * 0.3;
        if (suggest < 200) return '';
        return `💰 参考：可减仓约 ¥${(Math.round(suggest/100)*100).toLocaleString('zh-CN')}（超配 ${s.deviation_pt.toFixed(1)}pt）`;
    }
    return '';
}

function renderTechSignals(signals) {
    // 改用卡片容器，id 从 techSignalsBody 改为 techSignalsCards
    const wrap = document.getElementById('techSignalsCards');
    if (!wrap || !signals.length) { renderTechSignalsFallback(); return; }

    const BUY_SIG  = new Set(['买入','定投','定投补仓','可加仓','待建仓']);
    const SELL_SIG = new Set(['减仓','卖出','高估警惕']);

    wrap.innerHTML = signals.map(s => {
        const rsi  = _rsiInfo(s.rsi14);
        const ma   = _maInfo(s.ma5, s.ma20);
        const macd = _macdInfo(s.macd_trend);
        const amtH = _amountHint(s);
        const isBuy  = BUY_SIG.has(s.signal);
        const isSell = SELL_SIG.has(s.signal);
        const badgeCls = isBuy ? 'sig-badge-buy' : isSell ? 'sig-badge-sell' : 'sig-badge-hold';
        const cardGlow = isBuy ? 'sig-card-buy' : isSell ? 'sig-card-sell' : '';

        // 每个指标：第一行 label+badge，第二行解释文字
        const rowHtml = (icon, label, val, info) => info ? `
        <div class="sig-exp-row">
            <div class="sig-exp-row-top">
                <span class="sig-exp-label">${icon} ${label} <b class="num">${val}</b></span>
                <span class="sig-exp-tag sig-exp-${info.cls}">${info.label}</span>
            </div>
            <span class="sig-exp-tip">${info.tip}</span>
        </div>` : '';

        return `<div class="sig-card ${cardGlow}"><span class="sweep"></span>
            <div class="sig-card-head">
                <div>
                    <div class="sig-card-name">${escHtml(s.name)}</div>
                    <div class="sig-card-code num">${escHtml(s.code)}</div>
                </div>
                <span class="sig-badge ${badgeCls}">${escHtml(s.signal)}</span>
            </div>
            <div class="sig-exp-body">
                ${rowHtml('📊','RSI', s.rsi14!=null?s.rsi14.toFixed(1):'--', rsi)}
                ${rowHtml('📈','均线', ma?(s.ma5>s.ma20?'金叉':'死叉'):'--', ma)}
                ${rowHtml('📉','MACD', s.macd_trend==='bullish'?'多头':'空头', macd)}
            </div>
            <div class="sig-card-foot">
                <span class="sig-conclusion">${_sigConclusion(s)}</span>
                ${amtH ? `<span class="sig-amount">${amtH}</span>` : ''}
            </div>
        </div>`;
    }).join('');
}

function renderTechSignalsFallback() {
    const wrap = document.getElementById('techSignalsCards');
    if (wrap) wrap.innerHTML = '<div style="text-align:center;color:var(--text-muted);padding:32px;">暂无技术指标数据，请先运行 run_all.sh</div>';
}

// ========== 再平衡：优先从 rebalance.json 加载 ==========
async function loadAndRenderRebalanceJson() {
    await loadJSON('data/rebalance.json',
        data => { if (data && Array.isArray(data.actions)) renderRebalanceFromFile(data); }
    );
}

function renderRebalanceFromFile(data) {
    const listEl = document.getElementById('rebalanceList');
    const metaEl = document.getElementById('rebalanceMeta');
    if (!listEl) return;

    const needsRebalance = data.actions.filter(a => a.needs_rebalance);
    if (!needsRebalance.length) {
        listEl.innerHTML = '当前配置接近目标，所有标的偏差均在5%以内，无需调整。';
        if (metaEl) metaEl.textContent = `更新: ${data.updated_at} · 总市值: ¥${data.total_value.toLocaleString('zh-CN', {minimumFractionDigits:2})}`;
        return;
    }

    // Sort by abs deviation descending
    needsRebalance.sort((a, b) => Math.abs(b.deviation) - Math.abs(a.deviation));

    listEl.innerHTML = needsRebalance.map(a => {
        const over = a.deviation > 0;
        const arrow = over ? '🔻' : '🔺';
        const color = over ? 'var(--red)' : 'var(--green)';
        const verb = over ? '减仓' : '加仓';
        const sign = over ? '+' : '';
        const amt = Math.abs(Math.round(a.deviation_amount));
        return `<div style="margin-bottom:10px;line-height:1.7;">
            <span style="color:${color};font-weight:600;">${arrow} ${a.name}</span>
            &nbsp;${verb} <span class="num">≈¥${amt.toLocaleString('zh-CN')}</span>
            <span style="color:var(--text-muted);font-size:12px;">（实际${a.actual_pct.toFixed(1)}% vs 目标${a.target_pct}%，偏${sign}${a.deviation.toFixed(1)}pt）</span>
        </div>`;
    }).join('');

    if (metaEl) {
        const maxAbsDev = Math.max(...data.actions.map(a => Math.abs(a.deviation)));
        const risk = maxAbsDev > 20 ? '高' : maxAbsDev > 10 ? '中等' : '低';
        metaEl.textContent = `更新: ${data.updated_at} · 总市值: ¥${data.total_value.toLocaleString('zh-CN', {minimumFractionDigits:2})} · 配置风险: ${risk}`;
    }
}

