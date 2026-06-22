// ========== 玄枢Alpha - 信号渲染 ==========
// ========== Signal Data (loaded from JSON) ==========
let signalData = { gold: null, us: null, metals: null };

async function loadSignals() {
    const tryFetch = async (path) => {
        try { const r = await fetch(path + '?t=' + Date.now()); if(!r.ok) return null;
            let txt = await r.text();
            // gold_signal.json 可能含 NaN（非法JSON），替换为 null
            txt = txt.replace(/:\s*NaN/g, ': null');
            return JSON.parse(txt);
        } catch(e){ console.warn('load fail', path, e); return null; }
    };
    [signalData.gold, signalData.us, signalData.metals, window.navData, window.newsData] = await Promise.all([
        tryFetch('data/gold_signal.json'),
        tryFetch('data/us_signal.json'),
        tryFetch('data/metals_signal.json'),
        tryFetch('data/nav.json'),
        tryFetch('data/news.json')
    ]);
}

// ========== Render Gauge Charts (真实数据) ==========
function renderGauges() {
    const g = signalData.gold, u = signalData.us;
    const goldChart = echarts.init(document.getElementById('goldGauge'));
    const goldScore = g ? Math.round(g.combined_score ?? g.score) : 0;
    goldChart.setOption(gaugeOption(goldScore, '黄金'));
    document.getElementById('goldSignalDesc').innerHTML = g
        ? `综合评分 <b>${goldScore}</b>/100 · ${g.emoji||''} ${g.signal||''}` + (g.price?` · 金价 $${g.price}`:'')
        : '数据加载失败';

    const usChart = echarts.init(document.getElementById('usGauge'));
    const usScore = u ? Math.round(u.qqq_score) : 0;
    usChart.setOption(gaugeOption(usScore, '美股'));
    document.getElementById('usSignalDesc').innerHTML = u
        ? `综合评分 <b>${usScore}</b>/100 · ${u.qqq_emoji||''} ${u.qqq_signal||''} · SPY ${u.spy_score}`
        : '数据加载失败';

    window.addEventListener('resize',()=>{goldChart.resize();usChart.resize();});
}

// ========== Render VIX (从信号中提取) ==========
function renderVix() {
    // VIX 出现在 macro_VIX 维度描述里，从 gold 信号提取
    let vix = null, pctile = null;
    const src = (signalData.gold && signalData.gold.score_detail) || (signalData.us && signalData.us.qqq_score_detail);
    if(src){
        for(const k in src){
            if(k.includes('VIX')){
                const m = String(src[k]).match(/VIX=([\d.]+)/);
                const p = String(src[k]).match(/分位=(\d+)%/);
                if(m) vix = parseFloat(m[1]);
                if(p) pctile = parseInt(p[1]);
                if(vix) break;
            }
        }
    }
    const valEl = document.getElementById('vixValue');
    const dotEl = document.getElementById('vixDot');
    const descEl = document.getElementById('vixDesc');
    const pctEl = document.getElementById('vixPctile');
    if(vix == null){ valEl.textContent='N/A'; descEl.textContent='数据不可用'; return; }
    valEl.textContent = vix.toFixed(1);
    let color, desc;
    if(vix < 20){ color='var(--green)'; desc='低波动 · 市场情绪稳定'; }
    else if(vix < 30){ color='var(--gold-dark)'; desc='中等波动 · 谨慎观察'; }
    else { color='var(--red)'; desc='高恐慌 · 系统性风险定价中'; }
    dotEl.style.background = color;
    dotEl.style.boxShadow = '0 0 12px ' + color;
    descEl.textContent = desc;
    if(pctile != null) pctEl.textContent = `2年历史分位: ${pctile}%`;
}

// ========== Render Signal Detail Grid ==========
function renderSignalDetail() {
    const grid = document.getElementById('signalDetailGrid');
    const blocks = [];
    const buildBlock = (title, data) => {
        if(!data) return '';
        const rows = Object.entries(data).map(([k,v])=>{
            const label = k.replace(/^(tech|macro|senti|val)_/,'');
            const scoreM = String(v).match(/得分\s*(\d+)\/(\d+)/);
            let badge = '';
            if(scoreM){
                const ratio = +scoreM[1]/+scoreM[2];
                const c = ratio>=0.7?'var(--green)':ratio>=0.4?'var(--gold-dark)':'var(--red)';
                badge = `<span style="color:${c};font-weight:600;">${scoreM[1]}/${scoreM[2]}</span>`;
            }
            return `<div style="display:flex;justify-content:space-between;gap:8px;padding:4px 0;border-bottom:1px solid var(--border-color);font-size:11px;">
                <span style="color:var(--text-secondary);flex:1;">${label}</span>${badge}</div>`;
        }).join('');
        return `<div><div style="font-size:12px;color:var(--text-secondary);margin-bottom:8px;font-weight:600;">${title}</div>${rows}</div>`;
    };
    blocks.push(buildBlock('🥇 黄金维度', signalData.gold && signalData.gold.score_detail));
    blocks.push(buildBlock('🇺🇸 美股QQQ维度', signalData.us && signalData.us.qqq_score_detail));
    blocks.push(buildBlock('🟣 有色金属维度', signalData.metals && signalData.metals.score_detail));
    grid.innerHTML = blocks.filter(Boolean).join('');
}

function gaugeOption(value, name) {
    const cc = getChartColors();
    // 进度弧：高分亮青→中分蓝→低分暗蓝
    const arcColor = value >= 70
        ? new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:'#7de8ff'},{offset:1,color:cc.accent}])
        : value >= 40
        ? new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:cc.accent},{offset:1,color:cc.blue}])
        : new echarts.graphic.LinearGradient(0,0,0,1,[{offset:0,color:cc.blue},{offset:1,color:'#1a3a6a'}]);
    return {
        backgroundColor: 'transparent',
        series:[{
            type:'gauge',
            startAngle:200,endAngle:-20,
            min:0,max:100,
            splitNumber:10,
            itemStyle:{color:arcColor},
            progress:{show:true,width:12},
            pointer:{show:true,length:'60%',width:4,itemStyle:{color:cc.accent}},
            axisLine:{lineStyle:{width:12,color:[
                [0.4,'rgba(10,30,70,.6)'],
                [0.7,'rgba(0,100,180,.6)'],
                [1,'rgba(0,180,255,.7)']
            ]}},
            axisTick:{show:false},
            splitLine:{length:8,lineStyle:{width:2,color:cc.lineColor}},
            axisLabel:{distance:16,color:cc.muted,fontSize:10},
            title:{show:false},
            detail:{valueAnimation:true,fontSize:28,fontWeight:700,color:cc.textPrimary,offsetCenter:[0,'40%'],formatter:'{value}'},
            data:[{value:value}]
        }]
    };
}

