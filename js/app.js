// ========== 玄枢Alpha - 初始化 + 今日决策 Panel + portfolio.json 加载 ==========
// ========== 动态加载 portfolio.json（覆盖 inline fallback）==========
// 加载后 portfolioData 持有最新快照；失败则静默使用 inline 兜底。
async function loadPortfolio() {
    // 深度覆盖：用 JSON 文件数据替换 inline 快照的所有字段；失败则静默使用 data.js 兜底
    await loadJSON('data/portfolio.json', data => Object.assign(portfolioData, data));
}

// ========== Initialize ==========
// ========== 今日决策 Panel ==========
async function loadAndRenderDecision() {
    const errHtml = '<div style="color:var(--red);padding:8px;font-size:13px;">数据加载失败，请重新运行 run_all.sh</div>';
    try {
        const t = Date.now();
        const [sR, rR, vR, bR, frR, ptR] = await Promise.all([
            fetch('data/signals.json?t=' + t),
            fetch('data/risk.json?t=' + t),
            fetch('data/valuation.json?t=' + t),
            fetch('data/rebalance.json?t=' + t),
            fetch('data/fund_recommendations.json?t=' + t),
            fetch('data/positions.json?t=' + t)
        ]);
        const [sD, rD, vD, bD, frD, ptD] = await Promise.all([
            sR.ok?sR.json():null, rR.ok?rR.json():null,
            vR.ok?vR.json():null, bR.ok?bR.json():null,
            frR.ok?frR.json():null, ptR.ok?ptR.json():null
        ]);
        const tsEl = document.getElementById('decisionUpdated');
        if (tsEl) tsEl.textContent = sD?.updated_at || rD?.updated_at || '';
        _renderDeciSignals(sD, errHtml);
        _renderDeciOps(bD, errHtml);
        _renderDeciPositions(ptD, errHtml);
        _renderDeciRisk(rD, errHtml);
        _renderDeciValuation(vD, errHtml);
        _renderDeciUndervalued(frD, errHtml);
    } catch(e) {
        ['decisionSignals','decisionOps','decisionPositions','decisionRiskAlerts','decisionValuation','decisionUndervalued'].forEach(id => {
            const el = document.getElementById(id); if (el) el.innerHTML = errHtml;
        });
        const w = document.getElementById('decisionRiskWrap'); if (w) w.style.display = '';
    }
}
function _renderDeciSignals(data, errHtml) {
    const el = document.getElementById('decisionSignals');
    const moreWrap = document.getElementById('decisionSignalsMore');
    const moreBody = document.getElementById('decisionSignalsAll');
    if (!el) return;
    if (!data) { el.innerHTML = errHtml; return; }
    const HOLD_SET = new Set(['持有', '持有观察']);
    const BUY_SET  = new Set(['买入', '定投', '定投补仓', '可加仓']);
    const SELL_SET = new Set(['减仓', '卖出', '高估警惕']);
    const typeLbl  = t => t === 'trend' ? '趋势' : t === 'oscillation' ? '震荡' : t === 'active' ? '主动' : t === 'pending' ? '待建仓' : (t || '');
    const badgeCls = s => BUY_SET.has(s) ? 'sig-badge-buy' : SELL_SET.has(s) ? 'sig-badge-sell' : 'sig-badge-hold';
    const rowHtml  = s => `<tr>
        <td><span class="sig-name" title="${s.name}">${s.name}</span></td>
        <td><span class="sig-type-tag">${typeLbl(s.asset_type)}</span></td>
        <td><span class="sig-badge ${badgeCls(s.signal)}">${s.signal}</span></td>
        <td class="sig-detail">${s.action_detail || s.reason || '--'}</td>
    </tr>`;
    const active  = (data.signals || []).filter(s => !HOLD_SET.has(s.signal));
    const passive = (data.signals || []).filter(s =>  HOLD_SET.has(s.signal));
    if (!active.length) {
        el.innerHTML = '<div style="color:var(--green);padding:6px 0;font-size:13px;font-weight:500;">今日无需操作，继续持有即可</div>';
    } else {
        el.innerHTML = `<table class="sig-tbl"><tbody>${active.map(rowHtml).join('')}</tbody></table>`;
    }
    if (passive.length && moreWrap && moreBody) {
        moreBody.innerHTML = `<table class="sig-tbl" style="margin-top:6px;"><tbody>${passive.map(rowHtml).join('')}</tbody></table>`;
        moreWrap.style.display = '';
    }
}
function _renderDeciOps(data, errHtml) {
    const el = document.getElementById('decisionOps');
    if (!el) return;
    if (!data) { el.innerHTML = errHtml; return; }
    const ops = data.operations || [];
    if (!ops.length) {
        el.innerHTML = '<div style="color:var(--text-muted);font-size:13px;">当前无操作建议</div>';
        return;
    }
    const fmtAmt = n => '¥' + Number(n).toLocaleString('zh-CN');
    const rowHtml = o => {
        const isSell = o.action === 'sell';
        const dirCls = isSell ? 'ops-dir-sell' : 'ops-dir-buy';
        const dirLbl = isSell ? '卖出' : '买入';
        const amtCls = isSell ? 'ops-amount ops-amount-sell' : 'ops-amount ops-amount-buy';
        const amtPfx = isSell ? '-' : '+';
        return `<tr>
            <td><span class="${dirCls}">${dirLbl}</span></td>
            <td><span class="ops-fname" title="${o.fund_name}">${o.fund_name}</span><span class="ops-code">${o.fund_code}</span></td>
            <td><span class="${amtCls}">${amtPfx}${fmtAmt(o.amount)}</span></td>
            <td class="ops-reason">${o.reason}</td>
        </tr>`;
    };
    const sells = ops.filter(o => o.action === 'sell');
    const buys  = ops.filter(o => o.action === 'buy');
    const rows  = [...sells, ...buys].map(rowHtml).join('');
    el.innerHTML = `<table class="ops-tbl"><tbody>${rows}</tbody></table>
        <div class="ops-disclaimer">基于持仓偏离度计算，建议分批执行，非实时交易指令</div>`;
}
function _renderDeciPositions(data, errHtml) {
    const el = document.getElementById('decisionPositions');
    if (!el) return;
    if (!data) {
        el.innerHTML = '<div style="color:var(--text-muted);font-size:13px;">暂无跟踪中的持仓，请先运行 position_tracker.py</div>';
        return;
    }
    const cfg  = data.config || {};
    const defSL  = cfg.stop_loss_pct     ?? -8;
    const defTP  = cfg.take_profit_pct   ?? 15;
    const defTSL = cfg.trailing_stop_pct ?? -5;
    const positions = (data.positions || []).filter(p => p.status !== 'closed');
    if (!positions.length) {
        el.innerHTML = '<div style="color:var(--text-muted);font-size:13px;">暂无跟踪中的持仓</div>';
        return;
    }
    const rowHtml = pos => {
        const ret     = pos.current_return_pct ?? 0;
        const isAlert = pos.status === 'alert';
        const sl  = pos.stop_loss_pct     ?? defSL;
        const tp  = pos.take_profit_pct   ?? defTP;
        const tsl = pos.trailing_stop_pct ?? defTSL;
        const retCls  = ret > 0 ? 'pt-return-pos' : ret < 0 ? 'pt-return-neg' : 'pt-return-zero';
        const retSign = ret > 0 ? '+' : '';
        // 收益率进度条：[-sl, 0, tp] 区间映射到 [0,100]
        const range   = tp - sl;                              // e.g. 15-(-8)=23
        const barPct  = Math.min(100, Math.max(0, Math.round((ret - sl) / range * 100)));
        const barCls  = ret >= 0 ? 'pt-bar-pos' : 'pt-bar-neg';
        const distSL  = (ret - sl).toFixed(1);               // 距止损还有多少 pt
        const distTP  = (tp - ret).toFixed(1);               // 距止盈还有多少 pt
        const trigLabel = {
            stop_loss:      '触发止损 ' + sl + '%',
            take_profit:    '触发止盈 +' + tp + '%',
            trailing_stop:  '移动止损触发'
        }[pos.triggered] || '';
        return `<div class="pt-row${isAlert ? ' pt-alert' : ''}">
            <div class="pt-row-head">
                <div>
                    <span class="pt-name">${escHtml(pos.fund_name)}</span>
                    <span class="pt-code" style="margin-left:6px;">${escHtml(pos.fund_code)}</span>
                </div>
                <div style="display:flex;align-items:center;gap:8px;">
                    ${isAlert ? `<span class="pt-alert-badge">${escHtml(trigLabel)}</span>` : ''}
                    <span class="${retCls}">${retSign}${ret.toFixed(2)}%</span>
                </div>
            </div>
            <div class="pt-meta">
                <span>建仓日: ${escHtml(pos.entry_date || '--')}</span>
                <span>止损: ${sl}%</span>
                <span>止盈: +${tp}%</span>
                ${pos.current_nav ? `<span>现净值: ${pos.current_nav}</span>` : ''}
            </div>
            <div class="pt-bar-wrap"><div class="pt-bar-inner ${barCls}" style="width:${barPct}%;"></div></div>
            <div class="pt-dist"><span>距止损 +${distSL}pt</span><span>距止盈 -${distTP}pt</span></div>
        </div>`;
    };
    // alert 持仓排在前面
    const sorted = [...positions].sort((a,b) => (b.status==='alert'?1:0) - (a.status==='alert'?1:0));
    const updAt  = data.updated_at ? ` · 更新: ${data.updated_at}` : '';
    el.innerHTML = `<div class="pt-list">${sorted.map(rowHtml).join('')}</div>
        <div class="pt-disclaimer">止损 ${defSL}% / 止盈 +${defTP}% / 移动止损 ${defTSL}%（全局默认）${updAt}</div>`;
}
function _renderDeciUndervalued(data, errHtml) {
    const el = document.getElementById('decisionUndervalued');
    if (!el) return;
    if (!data) { el.innerHTML = '<div style="color:var(--text-muted);font-size:13px;">数据未就绪，请先运行 fund_scanner.py</div>'; return; }
    const uvList = data.undervalued || [];
    const recs   = data.recommendations || [];
    if (!uvList.length && !recs.length) {
        el.innerHTML = '<div style="color:var(--text-muted);font-size:13px;">当前市场情绪平稳，暂无低估或超跌机会</div>';
        return;
    }
    let html = '';
    // 超跌恐慌摘要（如有）
    if (data.triggered && recs.length) {
        html += `<div style="margin-bottom:8px;">
            <div style="font-size:11px;font-weight:700;color:var(--red);margin-bottom:4px;">🚨 超跌恐慌触发（${recs.length}只）</div>`;
        recs.forEach(r => {
            const drop = r.drop_20d_pct != null ? r.drop_20d_pct.toFixed(1) : '--';
            html += `<div style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:12px;">
                <span style="color:var(--text-primary);font-weight:600;">${escHtml(r.name)}</span>
                <span class="num" style="color:var(--text-muted);font-size:10px;">${escHtml(r.code)}</span>
                <span class="negative num" style="margin-left:auto;">-${drop}%</span>
            </div>`;
        });
        html += '</div>';
    }
    // 低估常态摘要（如有）
    if (uvList.length) {
        html += `<div>
            <div style="font-size:11px;font-weight:700;color:var(--accent);margin-bottom:4px;">📉 低位观察（${uvList.length}只）</div>`;
        uvList.forEach(uv => {
            const drop60 = uv.drop_60d_pct != null ? uv.drop_60d_pct.toFixed(1) : '--';
            const rsi    = uv.rsi14 != null ? uv.rsi14.toFixed(1) : '--';
            html += `<div style="display:flex;align-items:center;gap:6px;padding:3px 0;font-size:12px;">
                <span style="color:var(--text-primary);font-weight:600;">${escHtml(uv.name)}</span>
                <span class="num" style="color:var(--text-muted);font-size:10px;">${escHtml(uv.code)}</span>
                <span class="negative num" style="margin-left:auto;">-${drop60}%</span>
                <span class="num" style="color:var(--accent);font-size:11px;">RSI ${rsi}</span>
            </div>`;
        });
        html += '</div>';
    }
    // 跳转提示
    html += `<div style="margin-top:8px;padding-top:6px;border-top:1px solid var(--line);font-size:11px;color:var(--text-muted);cursor:pointer;" onclick="document.querySelector('[data-panel=\\'news\\']')&&document.querySelector('[data-panel=\\'news\\']').click();setTimeout(()=>document.getElementById('sec-radar')&&document.getElementById('sec-radar').scrollIntoView({behavior:'smooth',block:'start'}),300);">
        → 查看完整扫描结果：资讯 · 基金雷达
    </div>`;
    el.innerHTML = html;
}
function _renderDeciRisk(data, errHtml) {
    const wrap     = document.getElementById('decisionRiskWrap');
    const alertsEl = document.getElementById('decisionRiskAlerts');
    const metaEl   = document.getElementById('decisionRiskMeta');
    if (!wrap) return;
    if (!data) { wrap.style.display = ''; if (alertsEl) alertsEl.innerHTML = errHtml; return; }
    const highs = (data.concentration?.alerts || []).filter(a => a.severity === 'high');
    if (!highs.length) { wrap.style.display = 'none'; return; }
    wrap.style.display = '';
    if (alertsEl) alertsEl.innerHTML = highs.map(a =>
        `<div class="deci-alert-item"><div class="deci-alert-dot"></div><div class="deci-alert-msg">${a.message}</div></div>`
    ).join('');
    const pr = data.portfolio_risk || {};
    if (metaEl) {
        const parts = [];
        if (pr.volatility != null) parts.push(`波动率 ${pr.volatility}%`);
        if (pr.drawdown  != null) parts.push(`最大回撤 ${pr.drawdown}%`);
        if (pr.sharpe    != null) parts.push(`夏普 ${pr.sharpe}`);
        metaEl.className   = 'deci-risk-meta';
        metaEl.textContent = parts.join('  ·  ');
    }
}
function _renderDeciValuation(data, errHtml) {
    const el = document.getElementById('decisionValuation');
    if (!el) return;
    if (!data) { el.innerHTML = errHtml; return; }
    const NA_VERDICTS = new Set(['数据缺失', '不适用']);
    const chipCls = v => NA_VERDICTS.has(v.verdict) ? 'na'
        : v.verdict_score <= 40 ? 'green'
        : v.verdict_score <= 60 ? 'yellow'
        : v.verdict_score <= 80 ? 'orange' : 'red';
    el.className = 'val-grid';
    el.innerHTML = (data.valuations || []).map(v => {
        const ck     = chipCls(v);
        const isNA   = ck === 'na';
        const scoreDisplay = isNA ? '—' : (v.pe_pct_5y != null ? v.pe_pct_5y : v.verdict_score);
        const verdictText  = isNA ? '不适用' : v.verdict;
        return `<div class="val-chip val-chip-${ck}" title="${v.index_name || ''}">
            <div class="val-chip-cat">${v.category}</div>
            <div class="val-chip-score">${scoreDisplay}</div>
            <div class="val-chip-verdict">${verdictText}</div>
        </div>`;
    }).join('');
    // PE校准值过期警告
    if (data.warnings && data.warnings.length) {
        const warnDiv = document.createElement('div');
        warnDiv.style.cssText = 'margin-top:10px;padding:8px 12px;border-radius:8px;background:rgba(255,152,0,0.12);border:1px solid rgba(255,152,0,0.3);color:#ff9800;font-size:12px;line-height:1.5;';
        warnDiv.textContent = data.warnings.join(' | ');
        el.appendChild(warnDiv);
    }
}

document.addEventListener('DOMContentLoaded', async function() {
    // ① 先拉最新持仓数据（覆盖 inline 快照），确保所有后续渲染用真实数据
    await loadPortfolio();

    // ② 基于真实 portfolioData 渲染主界面
    renderHeader();
    renderMetrics();
    renderPieChart();
    renderBarChart();
    renderHoldings();

    // ③ 并发/顺序加载各数据模块
    // 今日决策（signals/risk/valuation 并行）
    loadAndRenderDecision();
    // 新闻情绪（data/news_impact.json）
    await loadAndRenderSentiment();
    // 实时行情（prices.json）
    await loadAndRenderPrices();
    // 量化信号（gold/us/metals signal JSON + news.json）
    await loadSignals();
    renderGauges();
    renderVix();
    renderSignalDetail();
    // 早晚报（依赖 window.newsData，必须在 loadSignals 之后）
    renderTimeline();
    // 技术指标信号（signals.json）
    await loadAndRenderTechSignals();
    // 策略回测（backtest/data/backtest.json）
    await loadAndRenderBacktest();
    // 组合净值曲线（data/portfolio_history.json）
    loadPortfolioHistory();
    // 融合决策卡（value_compass/data/fusion.json）
    await loadAndRenderFusion();
    // 主动基诊断（data/active_funds.json）
    await loadAndRenderActiveFunds();
    // 主动基诊断折叠图标联动
    (function() {
        const det = document.getElementById('activeFundDetails');
        const ico = document.getElementById('afdToggleIcon');
        if (!det || !ico) return;
        const update = () => { ico.textContent = det.open ? '▼ 点击收起' : '▶ 点击展开'; };
        det.addEventListener('toggle', update);
        update();
    })();
    // 再平衡（loadAndRenderRebalanceJson 保留兼容，AI建议模块由下方接管）
    await loadAndRenderRebalanceJson();
    // 基金雷达（data/fund_recommendations.json）
    await loadAndRenderRadar();
    // AI 操作建议：读真实 portfolio.json + rebalance.json（替代旧 renderAdvice/renderRebalance）
    await loadAndRenderAdviceModule();

    // 注册 Service Worker（PWA 离线访问）
    if ('serviceWorker' in navigator) {
        try {
            const swReg = await navigator.serviceWorker.register('./sw.js');
            console.log('[SW] registered, scope:', swReg.scope);
        } catch(e) {
            console.warn('[SW] registration failed:', e);
        }
    }
});
