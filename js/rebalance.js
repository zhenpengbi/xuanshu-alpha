// ========== 玄枢Alpha - 再平衡引擎 ==========
// ========== 再平衡引擎 (基于真实持仓偏离 + 信号) ==========
// 类别 → 信号映射：用真实量化评分决定"减仓/加仓"倾向
function getCategorySignalScore(cat){
    if((cat==='黄金') && signalData.gold) return Math.round(signalData.gold.combined_score ?? signalData.gold.score);
    if((cat==='有色金属') && signalData.metals) return signalData.metals.score;
    if((cat==='纳指100'||cat==='标普500'||cat==='AI/科技') && signalData.us) return signalData.us.qqq_score;
    return null;
}

function computeRebalance(){
    const total = portfolioData.totalAsset;
    // 实际各类别占比
    const catRatio = {};
    portfolioData.holdings.forEach(h=>{ catRatio[h.category]=(catRatio[h.category]||0)+h.ratio; });
    const target = portfolioData.targetAllocation;
    const allCats = [...new Set([...Object.keys(target),...Object.keys(catRatio)])];
    const actions = [];
    allCats.forEach(cat=>{
        const tgt = target[cat]||0;
        const act = +(catRatio[cat]||0).toFixed(1);
        const dev = +(act-tgt).toFixed(1);            // 偏离百分点
        const amtDev = Math.round(dev/100*total);     // 偏离金额
        if(Math.abs(dev) < 2) return;                  // 偏离<2pt忽略
        const sig = getCategorySignalScore(cat);
        actions.push({cat, tgt, act, dev, amtDev, sig});
    });
    // 按偏离绝对值排序
    actions.sort((a,b)=>Math.abs(b.dev)-Math.abs(a.dev));
    return actions;
}

function renderRebalance(){
    const actions = computeRebalance();
    const listEl = document.getElementById('rebalanceList');
    if(!actions.length){ listEl.innerHTML='当前配置接近目标，无需调整。'; document.getElementById('rebalanceMeta').textContent='偏离均<2个百分点'; return; }
    listEl.innerHTML = actions.map((a,i)=>{
        const over = a.dev>0;
        const verb = over?'减仓':'加仓';
        const arrow = over?'🔻':'🔺';
        const color = over?'var(--red)':'var(--green)';
        let sigNote='';
        if(a.sig!=null){
            // 减仓时信号高=暂缓减仓；加仓时信号低=谨慎
            if(over && a.sig>=65) sigNote=`（⚠️信号${a.sig}偏强，可暂缓减仓）`;
            else if(over && a.sig<45) sigNote=`（信号${a.sig}偏弱，减仓时机佳）`;
            else if(!over && a.sig>=65) sigNote=`（✅信号${a.sig}偏强，加仓时机佳）`;
            else if(!over && a.sig<45) sigNote=`（信号${a.sig}偏弱，分批为宜）`;
            else sigNote=`（信号${a.sig}中性）`;
        }
        return `<div style="margin-bottom:10px;line-height:1.6;">
            <span style="color:${color};font-weight:600;">${arrow} ${a.cat}</span> ${verb}
            <span class="num">≈¥${Math.abs(a.amtDev).toLocaleString('zh-CN')}</span>
            <span style="color:var(--text-muted);">（实际${a.act}% vs 目标${a.tgt}%，偏${a.dev>0?'+':''}${a.dev}pt）</span>
            <span style="color:var(--text-secondary);font-size:12px;">${sigNote}</span>
        </div>`;
    }).join('');
    const maxAbs = Math.max(...actions.map(a=>Math.abs(a.dev)));
    const risk = maxAbs>20?'高':maxAbs>10?'中等':'低';
    document.getElementById('rebalanceMeta').textContent = `基于真实持仓偏离度 + 量化信号联合判定 · 配置风险等级: ${risk}`;
}

// ========== AI 操作建议引擎 ==========
function renderAdvice(){
    const g=signalData.gold, u=signalData.us;
    const goldScore = g?Math.round(g.combined_score??g.score):null;
    const usScore = u?Math.round(u.qqq_score):null;
    const actions = computeRebalance();
    const maxDev = actions.length?actions[0]:null;

    // 决策逻辑
    let action='持有观望', reasons=[];
    if(maxDev && Math.abs(maxDev.dev)>20){
        action = maxDev.dev>0 ? '建议再平衡（减超配）' : '建议再平衡（补低配）';
    }
    // 黄金信号解读
    if(goldScore!=null){
        if(goldScore>=65) reasons.push(`黄金量化评分${goldScore}偏强，超配部分可暂缓减仓`);
        else if(goldScore<45) reasons.push(`黄金量化评分${goldScore}偏弱（${g.signal}），超配的黄金是减仓良机`);
        else reasons.push(`黄金量化评分${goldScore}中性（${g.signal}），维持观望`);
    }
    // 美股信号解读
    if(usScore!=null){
        if(usScore>=65) reasons.push(`美股QQQ评分${usScore}（${u.qqq_signal}），纳指/标普缺口可逢回调分批建仓`);
        else reasons.push(`美股QQQ评分${usScore}（${u.qqq_signal}），美股建仓需谨慎`);
    }
    // 配置偏离
    if(maxDev) reasons.push(`最大偏离：${maxDev.cat} ${maxDev.dev>0?'超配':'低配'}${Math.abs(maxDev.dev)}pt，建议优先处理`);

    document.getElementById('adviceAction').textContent = action;
    document.getElementById('adviceReason').innerHTML = reasons.map(r=>`<div style="margin-bottom:6px;">• ${r}</div>`).join('');
    const conf = (g&&g.risk_flags&&g.risk_flags.signal_confidence)||'medium';
    const confMap={high:'高',medium:'中',low:'低'};
    const dt = g?g.date:'';
    document.getElementById('adviceMeta').textContent = `信号置信度: ${confMap[conf]||conf} · 数据: ${(g&&g.data_source)||'--'} · 更新: ${dt}`;
}

