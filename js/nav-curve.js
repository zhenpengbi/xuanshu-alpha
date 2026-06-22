// ========== 玄枢Alpha - 组合净值曲线 ==========
// ========== 组合净值曲线 ==========
let _phChart = null;
async function loadPortfolioHistory() {
    const meta = document.getElementById('portfolioHistoryMeta');
    const wrap = document.getElementById('portfolioHistoryWrap');
    await loadJSON('data/portfolio_history.json', d => {
        const series = d.series || [];
        if (!series.length) { if (wrap) wrap.style.display = 'none'; return; }

        // 元数据行
        if (meta) {
            const retCls = d.return_pct >= 0 ? 'color:var(--green)' : 'color:var(--red)';
            const retSign = d.return_pct >= 0 ? '+' : '';
            meta.innerHTML =
                `<span style="color:var(--text-secondary);">组合净值曲线（近60日）</span>` +
                `<span style="color:var(--text-muted);">起始 <b style="color:var(--text-primary);">¥${d.start_value.toLocaleString('zh-CN',{maximumFractionDigits:0})}</b></span>` +
                `<span style="color:var(--text-muted);">当前 <b style="color:var(--text-primary);">¥${d.current_value.toLocaleString('zh-CN',{maximumFractionDigits:0})}</b></span>` +
                `<span style="color:var(--text-muted);">区间 <b style="${retCls}">${retSign}${d.return_pct.toFixed(2)}%</b></span>`;
        }

        const el = document.getElementById('portfolioHistoryChart');
        if (!el) return;
        if (!_phChart) {
            _phChart = echarts.init(el);
            window.addEventListener('resize', () => _phChart && _phChart.resize());
        }
        const cc = getChartColors();
        const dates = series.map(p => p.date);
        const vals  = series.map(p => p.value);
        _phChart.setOption({
            backgroundColor: 'transparent',
            grid: { top: 12, right: 20, bottom: 32, left: 60 },
            tooltip: {
                trigger: 'axis',
                backgroundColor: cc.bgTooltip, borderColor: cc.lineColor,
                textStyle: { color: cc.textPrimary, fontSize: 12 },
                formatter: p => p[0].axisValue + '<br>组合市值: ¥' + (+p[0].value).toLocaleString('zh-CN', {maximumFractionDigits: 0})
            },
            xAxis: { type: 'category', data: dates, axisLabel: { color: cc.muted, fontSize: 10 },
                     axisLine: { lineStyle: { color: cc.lineColor } }, splitLine: { show: false } },
            yAxis: { type: 'value', axisLabel: { color: cc.muted, fontSize: 10,
                     formatter: v => '¥' + (v/1e4).toFixed(0) + 'w' },
                     splitLine: { lineStyle: { color: cc.lineColor, type: 'dashed' } } },
            series: [{ type: 'line', data: vals, smooth: true, symbol: 'none',
                lineStyle: { color: cc.accent, width: 2 },
                areaStyle: { color: { type: 'linear', x: 0, y: 0, x2: 0, y2: 1,
                    colorStops: [{ offset: 0, color: 'rgba(0,200,255,.22)' }, { offset: 1, color: 'rgba(0,200,255,.01)' }] } } }]
        });
    }, () => { if (wrap) wrap.style.display = 'none'; });
}

