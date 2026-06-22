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
    await loadJSON('data/signals.json',
        data => renderTechSignals(data.signals || []),
        renderTechSignalsFallback
    );
}

function renderTechSignals(signals) {
    const tbody = document.getElementById('techSignalsBody');
    if (!tbody || !signals.length) { renderTechSignalsFallback(); return; }
    tbody.innerHTML = signals.map(s => {
        const rsiVal = s.rsi14 != null ? s.rsi14.toFixed(1) : '--';
        const rsiCls = s.rsi14 < 30 ? 'positive' : s.rsi14 > 70 ? 'negative' : '';
        const maCls = (s.ma5 != null && s.ma20 != null)
            ? (s.ma5 > s.ma20 ? 'positive' : 'negative') : '';
        const macdLabel = s.macd_trend === 'bullish' ? '▲ 多头' : '▼ 空头';
        const macdCls = s.macd_trend === 'bullish' ? 'positive' : 'negative';
        let badgeCls = 'signal-hold', badgeText = '— 观望';
        if (s.signal === '买入') { badgeCls = 'signal-buy'; badgeText = '▲ 买入'; }
        else if (s.signal === '卖出') { badgeCls = 'signal-sell'; badgeText = '▼ 卖出'; }
        const rowCls = s.signal === '买入' ? 'has-signal-buy' : s.signal === '卖出' ? 'has-signal-sell' : '';
        return `<tr class="${rowCls}">
            <td><div class="fund-name">${s.name}</div><div class="fund-code num">${s.code}</div></td>
            <td style="text-align:right;" class="num ${rsiCls}">${rsiVal}</td>
            <td style="text-align:right;" class="num">${s.ma5 != null ? s.ma5.toFixed(4) : '--'}</td>
            <td style="text-align:right;" class="num ${maCls}">${s.ma20 != null ? s.ma20.toFixed(4) : '--'}</td>
            <td style="text-align:center;" class="${macdCls}">${s.macd_hist != null ? macdLabel : '--'}</td>
            <td style="text-align:center;"><span class="signal-badge ${badgeCls}">${badgeText}</span></td>
            <td style="font-size:12px;color:var(--text-secondary);line-height:1.6;">${s.reason || '--'}</td>
        </tr>`;
    }).join('');
}

function renderTechSignalsFallback() {
    const tbody = document.getElementById('techSignalsBody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="7" style="text-align:center;color:var(--text-muted);padding:24px;">暂无技术指标数据，请先运行 run_all.sh</td></tr>';
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

