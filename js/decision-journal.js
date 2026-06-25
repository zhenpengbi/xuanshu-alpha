// ========== 玄枢Alpha - 决策日志 ==========
// 记录每次操作依据和结果，形成可复盘的学习闭环

const DJ = {
    STORE:      'xuanshu_decisions',
    MAX:        200,
    REVIEW_DAYS: 30,
};

// ── 存取 ──
function djLoad() {
    try { return JSON.parse(localStorage.getItem(DJ.STORE) || '[]'); }
    catch { return []; }
}
function djSave(list) {
    localStorage.setItem(DJ.STORE, JSON.stringify(list));
}
function djAdd(entry) {
    const list = djLoad();
    const now  = new Date();
    const review = new Date(now.getTime() + DJ.REVIEW_DAYS * 86400000);
    const fmt  = d => `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`;
    const full = {
        id:          now.getTime(),
        date:        fmt(now),
        review_date: fmt(review),
        reviewed:    false,
        outcome:     { pct: null, amount: null, assessment: null, note: '' },
        ...entry,
    };
    list.unshift(full);
    if (list.length > DJ.MAX) list.splice(DJ.MAX);
    djSave(list);
    return full;
}
function djUpdate(id, changes) {
    const list = djLoad();
    const idx  = list.findIndex(e => e.id === id);
    if (idx < 0) return;
    Object.assign(list[idx], changes);
    djSave(list);
}
function djDelete(id) {
    const list = djLoad().filter(e => e.id !== id);
    djSave(list);
}

// ── 辅助 ──
function djIsOverdue(entry) {
    return !entry.reviewed && entry.review_date <= new Date().toISOString().slice(0,10);
}

const DJ_ACTION_COLOR = {
    '买入':   'green',  '定投':  'green',  '定投补仓': 'green',
    '减仓':   'red',    '卖出':  'red',
    '观望':   'muted',  '持有':  'muted',
};
function djActionCls(action) {
    const c = DJ_ACTION_COLOR[action] || 'muted';
    return c === 'green' ? 'dj-badge-buy'
         : c === 'red'   ? 'dj-badge-sell'
         : 'dj-badge-hold';
}

const DJ_ASSESSMENT_LABEL = { correct:'✅ 判断正确', partial:'⚠️ 有偏差', wrong:'❌ 判断失误' };

// ── 渲染日志列表 ──
function djRenderList() {
    const container = document.getElementById('djList');
    if (!container) return;
    const list = djLoad();

    if (!list.length) {
        container.innerHTML = `
            <div class="dj-empty">
                <div>📒 暂无记录</div>
                <div style="font-size:12px;margin-top:6px;color:var(--text-muted);">
                    在 AI 分析或今日决策面板中点击「📝 记录操作」开始记录
                </div>
            </div>`;
        return;
    }

    // 待复盘提醒条
    const overdue = list.filter(djIsOverdue);
    const overdueBar = overdue.length
        ? `<div class="dj-overdue-bar">🔔 有 <b>${overdue.length}</b> 条记录已到复盘时间，请及时填写结果</div>`
        : '';

    container.innerHTML = overdueBar + list.map(e => {
        const badgeCls  = djActionCls(e.action);
        const isOverdue = djIsOverdue(e);
        const statusHtml = e.reviewed
            ? `<span class="dj-status dj-status-done">${DJ_ASSESSMENT_LABEL[e.outcome?.assessment] || '✅ 已复盘'}</span>`
            : isOverdue
            ? `<span class="dj-status dj-status-due">🔴 待复盘</span>`
            : `<span class="dj-status dj-status-wait">⏳ ${e.review_date} 复盘</span>`;

        const outcomeHtml = e.reviewed && e.outcome?.pct != null
            ? `<div class="dj-outcome">
                实际收益：<b class="${e.outcome.pct >= 0 ? 'positive' : 'negative'}">${e.outcome.pct >= 0 ? '+' : ''}${e.outcome.pct}%</b>
                ${e.outcome.note ? `· ${escHtml(e.outcome.note)}` : ''}
               </div>`
            : '';

        return `<div class="dj-item${isOverdue ? ' dj-item-due' : ''}${e.reviewed ? ' dj-item-done' : ''}" data-id="${e.id}">
            <div class="dj-item-head">
                <div class="dj-item-left">
                    <span class="dj-badge ${badgeCls}">${escHtml(e.action)}</span>
                    <span class="dj-fund">${escHtml(e.fund || '--')}</span>
                    ${e.amount ? `<span class="dj-amount num">¥${Number(e.amount).toLocaleString('zh-CN')}</span>` : ''}
                </div>
                <div class="dj-item-right">
                    ${statusHtml}
                    <span class="dj-date">${e.date}</span>
                </div>
            </div>
            ${e.reason ? `<div class="dj-reason">${escHtml(e.reason.slice(0,120))}${e.reason.length>120?'…':''}</div>` : ''}
            ${outcomeHtml}
            <div class="dj-item-actions">
                ${!e.reviewed ? `<button class="dj-btn-review" data-id="${e.id}">填写复盘</button>` : ''}
                <button class="dj-btn-del" data-id="${e.id}">删除</button>
            </div>
        </div>`;
    }).join('');

    // 绑定按钮事件（事件委托）
    container.onclick = e => {
        const btn = e.target.closest('[data-id]');
        if (!btn) return;
        const id = Number(btn.dataset.id);
        if (btn.classList.contains('dj-btn-review')) djOpenReview(id);
        if (btn.classList.contains('dj-btn-del'))    djConfirmDelete(id);
    };

    // 同步徽章和统计
    djSyncBadge();
    djRenderStats();
}

// ── 新建记录 Modal ──
function djOpenAdd(prefill = {}) {
    const holdings = (portfolioData?.holdings || []).map(h => h.name);
    const options  = holdings.map(n => `<option value="${escHtml(n)}">${escHtml(n)}</option>`).join('');

    djShowModal(`
        <h3 class="dj-modal-title">📝 记录操作</h3>
        <div class="dj-form">
            <label>操作类型</label>
            <select id="djF-action">
                ${['买入','定投','定投补仓','减仓','卖出','观望'].map(a =>
                    `<option${(prefill.action||'买入')===a?' selected':''}>${a}</option>`
                ).join('')}
            </select>
            <label>基金名称</label>
            <input id="djF-fund" list="djFundList" placeholder="输入或选择基金"
                   value="${escHtml(prefill.fund||'')}">
            <datalist id="djFundList">${options}</datalist>
            <label>操作金额（元）</label>
            <input id="djF-amount" type="number" min="0" placeholder="例：1450"
                   value="${prefill.amount||''}">
            <label>操作依据 / 原因</label>
            <textarea id="djF-reason" rows="3" placeholder="来自AI建议、信号判断等…">${escHtml(prefill.reason||'')}</textarea>
            <label>来源</label>
            <select id="djF-source">
                ${['AI分析','量化信号','自主判断','其他'].map(s =>
                    `<option${(prefill.source||'AI分析')===s?' selected':''}>${s}</option>`
                ).join('')}
            </select>
        </div>
        <div class="dj-modal-btns">
            <button class="dj-btn-cancel" onclick="djCloseModal()">取消</button>
            <button class="dj-btn-confirm" onclick="djSubmitAdd()">保存记录</button>
        </div>
    `);
}

function djSubmitAdd() {
    const action = document.getElementById('djF-action')?.value?.trim();
    const fund   = document.getElementById('djF-fund')?.value?.trim();
    const amount = document.getElementById('djF-amount')?.value;
    const reason = document.getElementById('djF-reason')?.value?.trim();
    const source = document.getElementById('djF-source')?.value;

    if (!action || !fund) { alert('请填写操作类型和基金名称'); return; }

    djAdd({ action, fund, amount: amount ? Number(amount) : null, reason, source });
    djCloseModal();
    djRenderList();
}

// ── 复盘 Modal ──
function djOpenReview(id) {
    djShowModal(`
        <h3 class="dj-modal-title">📋 复盘记录</h3>
        <div class="dj-form">
            <label>实际收益（%）</label>
            <input id="djR-pct" type="number" step="0.01" placeholder="例：3.5 或 -1.2">
            <label>评价</label>
            <select id="djR-assessment">
                <option value="correct">✅ 判断正确</option>
                <option value="partial">⚠️ 有偏差</option>
                <option value="wrong">❌ 判断失误</option>
            </select>
            <label>复盘总结（可选）</label>
            <textarea id="djR-note" rows="3" placeholder="这次决策的收获或教训…"></textarea>
        </div>
        <div class="dj-modal-btns">
            <button class="dj-btn-cancel" onclick="djCloseModal()">取消</button>
            <button class="dj-btn-confirm" onclick="djSubmitReview(${id})">完成复盘</button>
        </div>
    `);
}

function djSubmitReview(id) {
    const pct        = document.getElementById('djR-pct')?.value;
    const assessment = document.getElementById('djR-assessment')?.value;
    const note       = document.getElementById('djR-note')?.value?.trim();

    djUpdate(id, {
        reviewed: true,
        outcome: { pct: pct !== '' ? Number(pct) : null, assessment, note }
    });
    djCloseModal();
    djRenderList();
}

// ── 删除确认 ──
function djConfirmDelete(id) {
    if (!confirm('确认删除这条记录？')) return;
    djDelete(id);
    djRenderList();
}

// ── Modal 通用容器 ──
function djShowModal(html) {
    let overlay = document.getElementById('djModalOverlay');
    if (!overlay) {
        overlay = document.createElement('div');
        overlay.id = 'djModalOverlay';
        overlay.className = 'dj-modal-overlay';
        overlay.onclick = e => { if (e.target === overlay) djCloseModal(); };
        document.body.appendChild(overlay);
    }
    overlay.innerHTML = `<div class="dj-modal">${html}</div>`;
    overlay.style.display = 'flex';
}
function djCloseModal() {
    const o = document.getElementById('djModalOverlay');
    if (o) o.style.display = 'none';
}

// ── 徽章（待复盘数）──
function djSyncBadge() {
    const list    = djLoad();
    const overdue = list.filter(djIsOverdue).length;
    const badge   = document.getElementById('djNavBadge');
    if (!badge) return;
    if (overdue > 0) { badge.textContent = overdue; badge.style.display = ''; }
    else              { badge.style.display = 'none'; }
}

// ── 复盘统计看板 ──
function djRenderStats() {
    const statsCard  = document.getElementById('djStatsCard');
    if (!statsCard) return;

    const list     = djLoad();
    const reviewed = list.filter(e => e.reviewed);

    // 无数据时隐藏
    if (!list.length) { statsCard.style.display = 'none'; return; }
    statsCard.style.display = '';

    // 基础统计
    const total    = list.length;
    const revCount = reviewed.length;
    const correct  = reviewed.filter(e => e.outcome?.assessment === 'correct').length;
    const winRate  = revCount > 0 ? Math.round(correct / revCount * 100) : null;

    // 平均收益（只统计填了数字的）
    const withPct  = reviewed.filter(e => e.outcome?.pct != null);
    const avgPct   = withPct.length > 0
        ? (withPct.reduce((s, e) => s + e.outcome.pct, 0) / withPct.length).toFixed(1)
        : null;

    // 渲染四格数字
    const set = (id, val, cls) => {
        const el = document.getElementById(id);
        if (!el) return;
        el.textContent = val;
        if (cls) el.className = 'dj-stat-value ' + cls;
    };
    set('djStatTotal',    total);
    set('djStatReviewed', revCount);
    set('djStatWinRate',  winRate !== null ? winRate + '%' : '--',
        winRate === null ? '' : winRate >= 60 ? 'positive' : winRate >= 40 ? 'warn' : 'negative');
    set('djStatAvgPct',   avgPct !== null ? (avgPct >= 0 ? '+' : '') + avgPct + '%' : '--',
        avgPct === null ? '' : Number(avgPct) >= 0 ? 'positive' : 'negative');

    // 来源胜率对比（≥2条已复盘才显示）
    const sourceWrap = document.getElementById('djSourceWrap');
    const sourceList = document.getElementById('djSourceList');
    if (!sourceWrap || !sourceList) return;

    const sources = {};
    reviewed.forEach(e => {
        const src = e.source || '其他';
        if (!sources[src]) sources[src] = { total: 0, correct: 0, pcts: [] };
        sources[src].total++;
        if (e.outcome?.assessment === 'correct') sources[src].correct++;
        if (e.outcome?.pct != null) sources[src].pcts.push(e.outcome.pct);
    });

    const srcEntries = Object.entries(sources).filter(([, v]) => v.total >= 1);
    if (srcEntries.length < 2) { sourceWrap.style.display = 'none'; return; }

    sourceWrap.style.display = '';
    sourceList.innerHTML = srcEntries
        .sort((a, b) => (b[1].correct / b[1].total) - (a[1].correct / a[1].total))
        .map(([src, v]) => {
            const wr  = Math.round(v.correct / v.total * 100);
            const avg = v.pcts.length
                ? (v.pcts.reduce((s,x) => s+x, 0) / v.pcts.length).toFixed(1)
                : null;
            const cls = wr >= 60 ? 'positive' : wr >= 40 ? 'warn' : 'negative';
            return `<div class="dj-source-row">
                <span class="dj-source-name">${escHtml(src)}</span>
                <span class="dj-source-detail">
                    <span class="${cls}">${wr}% 正确率</span>
                    <span class="dj-source-n">（${v.total}笔）</span>
                    ${avg !== null ? `<span class="${Number(avg)>=0?'positive':'negative'}">${Number(avg)>=0?'+':''}${avg}%</span>` : ''}
                </span>
            </div>`;
        }).join('');
}

// ── 初始化 ──
function initDecisionJournal() {
    djRenderList();
    djRenderStats();

    // 「记录操作」按钮
    const addBtn = document.getElementById('djAddBtn');
    if (addBtn) addBtn.addEventListener('click', () => djOpenAdd());
}

// 供外部调用（AI分析完成后预填）
function djRecordFromAI(aiText) {
    djOpenAdd({
        action: '买入',
        reason: aiText.slice(0, 200),
        source: 'AI分析',
    });
}

document.addEventListener('DOMContentLoaded', initDecisionJournal);
