// ========== 玄枢Alpha - 持仓渲染 ==========
// ========== Render Header ==========
function renderHeader() {
    const totalDaily = portfolioData.holdings.reduce((s,h)=>s+h.dailyReturn,0);
    document.getElementById('headerTotal').textContent = fmtMoney(portfolioData.totalAsset);
    const el = document.getElementById('headerDailyReturn');
    el.textContent = fmtReturn(totalDaily);
    el.className = 'header-stat-value num ' + retClass(totalDaily);
    document.getElementById('headerUpdateTime').textContent =
        window.innerWidth <= 768 ? portfolioData.updateTime : ('更新: ' + portfolioData.updateTime);
}

// ========== Render Metrics ==========
function renderMetrics() {
    const totalDaily = portfolioData.holdings.reduce((s,h)=>s+h.dailyReturn,0);
    const totalHolding = portfolioData.holdings.reduce((s,h)=>s+h.holdingReturn,0);
    const maxH = portfolioData.holdings.reduce((a,b)=>a.amount>b.amount?a:b);
    document.getElementById('metricTotal').textContent = fmtMoney(portfolioData.totalAsset);
    const dEl = document.getElementById('metricDaily');
    dEl.textContent = fmtReturn(totalDaily);
    dEl.style.color = totalDaily>=0?'var(--green)':'var(--red)';
    const hEl = document.getElementById('metricHolding');
    hEl.textContent = fmtReturn(totalHolding);
    hEl.style.color = totalHolding>=0?'var(--green)':'var(--red)';
    document.getElementById('metricMax').textContent = maxH.name;
    document.getElementById('metricMaxRatio').textContent = maxH.ratio + '%';
}

// ========== Render Pie Chart ==========
let _pieChart = null;
function renderPieChart() {
    if (!_pieChart) {
        _pieChart = echarts.init(document.getElementById('pieChart'));
        window.addEventListener('resize', () => _pieChart.resize());
    }
    const cc = getChartColors();
    const catMap = {};
    portfolioData.holdings.forEach(h => { catMap[h.category] = (catMap[h.category]||0) + h.amount; });
    // 深蓝科技风色盘：亮青蓝 → 蓝 → 紫 → 绿 → 亮蓝紫，逐级递变
    const palette = [cc.accent, cc.blue, cc.purple, cc.green,
        '#22d3ee', '#60a5fa', '#a78bfa', '#34d399', '#f472b6', '#fb923c'];
    const data = Object.entries(catMap).map(([n,v])=>({name:n,value:+v.toFixed(2)}));
    data.sort((a,b)=>b.value-a.value);
    // 最大扇区构造径向渐变发光质感
    const topGlow = new echarts.graphic.RadialGradient(0.5,0.5,0.85,[
        {offset:0,color:'#7de8ff'},
        {offset:0.55,color:cc.accent},
        {offset:1,color:cc.blue}
    ]);
    _pieChart.setOption({
        backgroundColor: 'transparent',
        title:{text:'持仓分布',left:'center',top:10,textStyle:{color:cc.textPrimary,fontSize:14,fontWeight:600}},
        tooltip:{trigger:'item',formatter:'{b}: ¥{c} ({d}%)',
            backgroundColor:cc.bgTooltip,borderColor:cc.lineColor,textStyle:{color:cc.textPrimary}},
        series:[{
            type:'pie',radius:['45%','72%'],center:['50%','55%'],
            avoidLabelOverlap:true,
            itemStyle:{borderRadius:4,borderColor:'rgba(0,0,0,.3)',borderWidth:2},
            label:{show:true,color:cc.dim,fontSize:12,formatter:'{b}\n{d}%'},
            labelLine:{lineStyle:{color:cc.lineColor}},
            data: data.map((d,idx)=>{
                const color = idx===0 ? topGlow : palette[Math.min(idx, palette.length-1)];
                return {...d,itemStyle:{color}};
            })
        }]
    });
}

// ========== Render Bar Chart (Target vs Actual) ==========
let _barChart = null;
function renderBarChart() {
    if (!_barChart) {
        _barChart = echarts.init(document.getElementById('barChart'));
        window.addEventListener('resize', () => _barChart.resize());
    }
    const cc = getChartColors();
    const catMap = {};
    portfolioData.holdings.forEach(h => { catMap[h.category] = (catMap[h.category]||0) + h.ratio; });
    // Merge all categories from target + actual
    const allCats = [...new Set([...Object.keys(portfolioData.targetAllocation),...Object.keys(catMap)])];
    const targetData = allCats.map(c => portfolioData.targetAllocation[c]||0);
    const actualData = allCats.map(c => +(catMap[c]||0).toFixed(1));

    _barChart.setOption({
        backgroundColor: 'transparent',
        title:{text:'目标 vs 实际配置',left:'center',top:10,textStyle:{color:cc.textPrimary,fontSize:14,fontWeight:600}},
        tooltip:{trigger:'axis',backgroundColor:cc.bgTooltip,borderColor:cc.lineColor,textStyle:{color:cc.textPrimary},
            formatter:function(p){return p[0].name+'<br/>'+p.map(i=>i.marker+i.seriesName+': '+i.value+'%').join('<br/>');}
        },
        legend:{bottom:0,textStyle:{color:cc.dim},data:['目标','实际']},
        grid:{left:50,right:20,top:50,bottom:40},
        xAxis:{type:'category',data:allCats,
            axisLabel:{color:cc.muted,fontSize:11,rotate:15},
            axisLine:{lineStyle:{color:cc.border}}},
        yAxis:{type:'value',
            axisLabel:{color:cc.muted,formatter:'{value}%'},
            splitLine:{lineStyle:{color:cc.border}},
            axisLine:{lineStyle:{color:cc.border}}},
        series:[
            // 目标柱：半透明描边强调色，作为"基准"，轻盈
            {name:'目标',type:'bar',barWidth:'30%',
                itemStyle:{
                    color: (function(){ const a=cc.accent; return a.replace(')',',0.12)').replace('rgb','rgba'); })(),
                    borderColor:cc.accent+'88',borderWidth:1,borderRadius:[5,5,0,0]},
                data:targetData},
            // 实际柱：青蓝纵向渐变（顶部亮青蓝→底部深蓝），科技感
            {name:'实际',type:'bar',barWidth:'30%',
                itemStyle:{borderRadius:[5,5,0,0],color:new echarts.graphic.LinearGradient(0,0,0,1,[
                    {offset:0,color:'#7de8ff'},
                    {offset:0.5,color:cc.accent},
                    {offset:1,color:cc.blue}
                ])},
                data:actualData}
        ]
    });
}

// ========== Render Holdings Table ==========
function switchTabFromCap(panel) {
    const nav = document.getElementById('tabNav');
    if (!nav) return;
    const btn = nav.querySelector(`[data-panel="${panel}"]`);
    if (btn) btn.click();
}

function renderHoldings() {
    // ── 调试：验证渲染时持仓数据完整性 ──
    const _codes = (portfolioData.holdings||[]).map(h=>h.code);
    console.error('[renderHoldings] holdings codes:', _codes.join(','), '| count:', _codes.length);
    // --- 移动端卡片 ---
    const cardsEl = document.getElementById('holdingsCards');
    if (cardsEl) {
        cardsEl.innerHTML = portfolioData.holdings.map(h => {
            const cls = h.dailyReturn >= 0 ? 'positive' : 'negative';
            return `<div class="holding-card ${cls}">
                <div class="hc-left">
                    <div class="hc-name">${h.name}</div>
                    <div class="hc-meta"><span class="hc-tag">${h.category}</span><span>${h.code}</span></div>
                </div>
                <div class="hc-right">
                    <div class="hc-amount">¥${(h.amount).toLocaleString('zh-CN', {minimumFractionDigits:2, maximumFractionDigits:2})}</div>
                    <div class="hc-return ${cls}">${h.dailyReturn>=0?'+':''}${h.dailyReturn.toFixed(2)}</div>
                    <div class="hc-ratio">占比 ${h.ratio}%</div>
                </div>
            </div>`;
        }).join('');
    }
    // --- PC端表格 ---
    const tbody = document.getElementById('holdingsBody');
    tbody.innerHTML = portfolioData.holdings.map((h,i) => {
        const dailyCls = retClass(h.dailyReturn);
        const holdCls  = retClass(h.holdingReturnRate);
        const totalCls = retClass(h.totalReturn);
        const tagCls   = getCategoryTagClass(h.category);
        return `<tr>
            <td><div class="fund-name">${h.name}</div></td>
            <td><span class="fund-code num">${h.code}</span></td>
            <td><span class="tag ${tagCls}">${h.category}</span></td>
            <td style="text-align:right;" class="num">${fmtMoney(h.amount)}</td>
            <td style="text-align:right;" class="num">${h.ratio}%</td>
            <td style="text-align:right;" class="num ${dailyCls}">${fmtReturn(h.dailyReturn)}</td>
            <td style="text-align:right;">
                <div class="num hold-return-amt ${holdCls}">${fmtReturn(h.holdingReturn)}</div>
                <div class="num hold-return-rate ${holdCls}">${fmtPct(h.holdingReturnRate)}</div>
            </td>
            <td style="text-align:right;" class="num ${totalCls}">${fmtReturn(h.totalReturn)}</td>
            <td><div style="display:flex;align-items:center;gap:8px;">
                <canvas class="sparkline-canvas" id="spark${i}"></canvas>
                <span class="num" id="navchg${i}" style="font-size:11px;min-width:48px;text-align:right;"></span>
            </div></td>
        </tr>`;
    }).join('');
    // ── 调试：验证 DOM 行数是否与预期匹配 ──
    const _domRows = tbody.querySelectorAll('tr').length;
    if (_domRows !== portfolioData.holdings.length) {
        console.error('[renderHoldings] DOM行数异常! 预期', portfolioData.holdings.length, '实际', _domRows, '| tbody.innerHTML长度:', tbody.innerHTML.length);
    }
    // Draw sparklines（真实净值，60日；无净值数据回退随机趋势）
    const nav = (window.navData && window.navData.funds) || {};
    portfolioData.holdings.forEach((h,i) => {
        const fd = nav[h.code];
        const canvas = document.getElementById('spark'+i);
        const chgEl = document.getElementById('navchg'+i);
        if (fd && fd.navs && fd.navs.length > 1) {
            const up = fd.change >= 0;
            drawSparkline(canvas, up, fd.navs);
            if (chgEl) { chgEl.textContent = (up?'+':'') + fd.change + '%'; chgEl.className = 'num ' + retClass(fd.change); }
        } else {
            // 货币基金/无数据：画平直线，区间显示 —
            drawSparkline(canvas, h.holdingReturnRate >= 0, null);
            if (chgEl) { chgEl.textContent = '—'; chgEl.style.color = 'var(--text-muted)'; }
        }
    });
}

function drawSparkline(canvas, isPositive, navs) {
    if(!canvas) return;
    const ctx = canvas.getContext('2d');
    const w = canvas.width = 80;
    const h = canvas.height = 28;
    const pad = 3;
    const points = [];
    if (navs && navs.length > 1) {
        // 真实净值：归一化到画布高度
        const min = Math.min(...navs), max = Math.max(...navs);
        const range = (max - min) || 1;
        const n = navs.length;
        for (let i=0; i<n; i++) {
            const x = pad + (w-2*pad) * i/(n-1);
            const y = h - pad - (h-2*pad) * (navs[i]-min)/range;
            points.push([x, y]);
        }
    } else {
        // 无净值数据：画一条接近水平的平直线
        points.push([pad, h/2], [w-pad, h/2]);
    }
    // 涨用亮青蓝（深蓝科技风强调色），跌用语义红
    const color = isPositive
        ? (getCssVar('--accent') || '#00c8ff')
        : (getCssVar('--red') || '#ff4f6a');
    // 渐变填充
    const grad = ctx.createLinearGradient(0,0,0,h);
    grad.addColorStop(0, color + '40');
    grad.addColorStop(1, color + '00');
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for(let i=1;i<points.length;i++) ctx.lineTo(points[i][0], points[i][1]);
    ctx.lineTo(points[points.length-1][0], h);
    ctx.lineTo(points[0][0], h);
    ctx.closePath();
    ctx.fillStyle = grad;
    ctx.fill();
    // 折线
    ctx.beginPath();
    ctx.moveTo(points[0][0], points[0][1]);
    for(let i=1;i<points.length;i++) ctx.lineTo(points[i][0], points[i][1]);
    ctx.strokeStyle = color;
    ctx.lineWidth = 1.3;
    ctx.stroke();
}

// ========== 目标进度条渲染 ==========
// GOAL: 10% 年化、夏普 ≥ 1、最大回撤 ≤ 20%
const GOAL_ANNUAL_PCT  = 10;   // 年化目标 %
const WARN_DRAWDOWN    = 20;   // 回撤警戒线 %
const DANGER_DRAWDOWN  = 30;   // 回撤危险线 %
const GOOD_SHARPE      = 1.0;  // 夏普良好阈值

/**
 * renderPerfBar — 渲染目标进度条
 * @param {object} history - portfolio_history.json 数据
 * @param {object} risk    - risk.json 数据
 */
function renderPerfBar(history, risk) {
    const bar = document.getElementById('perfBar');
    if (!bar) return;

    // ── 年化收益推算 ──
    const series = (history && history.series) || [];
    let annualPct = null;
    if (series.length >= 7 && history.return_pct != null) {
        const d0  = new Date(series[0].date);
        const d1  = new Date(series[series.length - 1].date);
        const days = Math.max(1, Math.round((d1 - d0) / 86400000));
        const ret  = history.return_pct / 100;           // e.g. 0.0305
        annualPct  = (Math.pow(1 + ret, 365 / days) - 1) * 100;
    }

    // ── 最大回撤 / 夏普 ──
    const drawdown = risk?.portfolio_risk?.drawdown ?? null;
    const sharpe   = risk?.portfolio_risk?.sharpe   ?? null;
    const days     = series.length;

    // ── 渲染：年化 ──
    const annualEl  = document.getElementById('perfAnnualVal');
    const annualSub = document.getElementById('perfAnnualSub');
    if (annualEl) {
        if (annualPct === null) {
            annualEl.textContent = '积累中';
            annualEl.className = 'perf-value';
            if (annualSub) annualSub.textContent = `已记录 ${days} 天`;
        } else {
            const sign = annualPct >= 0 ? '+' : '';
            annualEl.textContent = `${sign}${annualPct.toFixed(1)}%`;
            annualEl.className   = 'perf-value ' + (annualPct >= GOAL_ANNUAL_PCT ? 'positive' : annualPct >= 0 ? 'warn' : 'negative');
            if (annualSub) annualSub.textContent = `目标 ${GOAL_ANNUAL_PCT}% | ${days}天基准`;
        }
    }

    // ── 渲染：最大回撤 ──
    const ddEl    = document.getElementById('perfDrawdownVal');
    const ddBadge = document.getElementById('perfDrawdownBadge');
    if (ddEl) {
        if (drawdown === null) {
            ddEl.textContent = '--';
            ddEl.className = 'perf-value';
        } else {
            ddEl.textContent = `-${drawdown.toFixed(1)}%`;
            if (drawdown > DANGER_DRAWDOWN) {
                ddEl.className = 'perf-value negative';
                if (ddBadge) { ddBadge.textContent = '危险'; ddBadge.className = 'perf-badge bad'; }
            } else if (drawdown > WARN_DRAWDOWN) {
                ddEl.className = 'perf-value warn';
                if (ddBadge) { ddBadge.textContent = '偏高'; ddBadge.className = 'perf-badge warn'; }
            } else {
                ddEl.className = 'perf-value positive';
                if (ddBadge) { ddBadge.textContent = '安全'; ddBadge.className = 'perf-badge ok'; }
            }
        }
    }

    // ── 渲染：夏普 ──
    const shpEl  = document.getElementById('perfSharpe');
    const shpSub = document.getElementById('perfSharpeSub');
    if (shpEl) {
        if (sharpe === null) {
            shpEl.textContent = '--';
            shpEl.className = 'perf-value';
        } else {
            shpEl.textContent = sharpe.toFixed(2);
            shpEl.className   = 'perf-value ' + (sharpe >= GOOD_SHARPE ? 'positive' : sharpe >= 0.5 ? 'warn' : 'negative');
            if (shpSub) shpSub.textContent = `目标 ≥ ${GOOD_SHARPE}`;
        }
    }

    // ── 渲染：综合状态 ──
    const statusEl = document.getElementById('perfStatus');
    if (statusEl) {
        const drawdownOk  = drawdown === null || drawdown <= WARN_DRAWDOWN;
        const annualOk    = annualPct === null || annualPct >= GOAL_ANNUAL_PCT;
        const sharpeOk    = sharpe === null || sharpe >= 0.5;
        const isAtRisk    = drawdown !== null && drawdown > DANGER_DRAWDOWN;

        if (isAtRisk) {
            statusEl.textContent = '⚠️ 回撤超警戒，控制仓位';
            statusEl.className   = 'perf-status at-risk';
        } else if (annualOk && drawdownOk && sharpeOk) {
            statusEl.textContent = '✅ 策略在轨';
            statusEl.className   = 'perf-status on-track';
        } else {
            statusEl.textContent = '📊 关注回撤 / 年化偏低';
            statusEl.className   = 'perf-status behind';
        }
    }

    bar.style.display = '';
}

// ========== 持仓健康体检 ==========
// 在 renderHoldings() + loadSignals() 均完成后调用，为问题持仓打标签
const HEALTH_LOSS_WARN   = -15;  // 持仓亏损警戒线 %
const HEALTH_LOSS_DANGER = -30;  // 持仓亏损危险线 %

function renderHoldingsHealth(signals) {
    if (!signals || !signals.length) return;

    // code → signal 映射
    const sigMap = {};
    signals.forEach(s => { if (s.code) sigMap[s.code] = s; });

    const SELL_SET = new Set(['减仓', '卖出', '高估警惕']);
    const BUY_SET  = new Set(['买入', '定投', '定投补仓', '可加仓']);

    portfolioData.holdings.forEach((h, i) => {
        const sig     = sigMap[h.code];
        const rate    = h.holdingReturnRate;
        const badges  = [];

        // 亏损程度
        if (rate <= HEALTH_LOSS_DANGER) {
            badges.push(`<span class="health-badge health-danger">亏损${rate.toFixed(0)}%</span>`);
        } else if (rate <= HEALTH_LOSS_WARN) {
            badges.push(`<span class="health-badge health-warn">亏损${rate.toFixed(0)}%</span>`);
        }

        // 信号方向
        if (sig) {
            if (SELL_SET.has(sig.signal)) {
                badges.push(`<span class="health-badge health-sell">${sig.signal}</span>`);
            } else if (BUY_SET.has(sig.signal)) {
                badges.push(`<span class="health-badge health-buy">${sig.signal}</span>`);
            }
        }

        if (!badges.length) return;

        // PC 表格：在基金名称旁注入
        const nameEl = document.querySelector(`#holdingsBody tr:nth-child(${i+1}) .fund-name`);
        if (nameEl && !nameEl.querySelector('.health-badge')) {
            nameEl.insertAdjacentHTML('beforeend', ' ' + badges.join(''));
        }

        // 移动端卡片：在名称旁注入
        const cards = document.querySelectorAll('#holdingsCards .holding-card');
        const card  = cards[i];
        if (card) {
            const nameDiv = card.querySelector('.hc-name');
            if (nameDiv && !nameDiv.querySelector('.health-badge')) {
                nameDiv.insertAdjacentHTML('beforeend', ' ' + badges.join(''));
            }
        }
    });
}

