// ========== 玄枢Alpha - 持仓编辑器 + 余额宝编辑 ==========
// ========== 持仓编辑器 ==========

const PE_CATEGORIES = ['黄金','AI/科技','有色金属','光伏/新能源','高端制造','货币基金','纳指100','标普500','其他'];
const PE_ASSET_BY_CAT = {
    '黄金':'trend','有色金属':'trend','纳指100':'trend','标普500':'trend',
    'AI/科技':'oscillation','光伏/新能源':'oscillation',
    '高端制造':'active','货币基金':'cash','其他':'active',
};
const GH_REPO = 'zhenpengbi/xuanshu-alpha';
let _patResolve = null;

// ── open / close ────────────────────────────────────────────────
function openPortfolioEditor() {
    document.getElementById('pe-date').value =
        portfolioData.updateTime || new Date().toISOString().slice(0, 10);
    _peRenderRows();
    _peUpdateTotal();
    document.getElementById('pe-status').textContent = '';
    document.getElementById('portfolioEditorModal').style.display = 'flex';
}
function closePortfolioEditor() {
    document.getElementById('portfolioEditorModal').style.display = 'none';
}
function peOverlayClick(e) {
    if (e.target === e.currentTarget) closePortfolioEditor();
}

// ── row rendering ───────────────────────────────────────────────
function _peEsc(s) {
    return String(s ?? '').replace(/[&<>"']/g,
        c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
}
function _peRenderRows() {
    const wrap = document.getElementById('pe-rows');
    wrap.innerHTML = '';
    (portfolioData.holdings || []).forEach((h, i) => wrap.appendChild(_peBuildRow(h, i)));
}
function _peBuildRow(h, idx) {
    const div = document.createElement('div');
    div.className = 'pe-row';
    const catOpts = PE_CATEGORIES.map(c =>
        `<option value="${_peEsc(c)}"${c === (h.category||'其他') ? ' selected':''}>${_peEsc(c)}</option>`
    ).join('');
    div.innerHTML = `
        <div class="pe-row-top">
            <span class="pe-row-tag pe-tag-${idx}">
                <b style="color:var(--text-primary,#e6edf3);">${_peEsc(h.name||'新基金')}</b>
                <span style="font-size:10px;opacity:.6;margin-left:4px;">${_peEsc(h.code||'')}</span>
            </span>
            <button class="pe-row-del" title="删除" onclick="deletePeRow(this)">×</button>
        </div>
        <div class="pe-fields">
            <div class="pe-field"><label>代码</label>
                <input class="pe-input pe-code" value="${_peEsc(h.code||'')}" placeholder="6位代码"
                       oninput="_peTagSync(this)">
            </div>
            <div class="pe-field"><label>基金名称</label>
                <input class="pe-input pe-name" value="${_peEsc(h.name||'')}" placeholder="简称"
                       oninput="_peTagSync(this)">
            </div>
            <div class="pe-field"><label>类别</label>
                <select class="pe-input pe-cat">${catOpts}</select>
            </div>
            <div class="pe-field"><label>金额 ¥</label>
                <input class="pe-input pe-amount" type="number" step="0.01"
                       value="${h.amount ?? 0}" oninput="_peUpdateTotal()">
            </div>
            <div class="pe-field"><label>今日盈亏 ¥</label>
                <input class="pe-input pe-daily" type="number" step="0.01" value="${h.dailyReturn ?? 0}">
            </div>
            <div class="pe-field"><label>持有收益 ¥</label>
                <input class="pe-input pe-hold" type="number" step="0.01" value="${h.holdingReturn ?? 0}">
            </div>
            <div class="pe-field"><label>持有收益率 %</label>
                <input class="pe-input pe-holdr" type="number" step="0.01" value="${h.holdingReturnRate ?? 0}">
            </div>
            <div class="pe-field"><label>累计收益 ¥</label>
                <input class="pe-input pe-total" type="number" step="0.01" value="${h.totalReturn ?? 0}">
            </div>
        </div>`;
    return div;
}
function _peTagSync(input) {
    const row = input.closest('.pe-row');
    const name = row.querySelector('.pe-name').value;
    const code = row.querySelector('.pe-code').value;
    const tag  = row.querySelector('.pe-row-tag');
    tag.innerHTML = `<b style="color:var(--text-primary,#e6edf3);">${_peEsc(name||'新基金')}</b>`
        + `<span style="font-size:10px;opacity:.6;margin-left:4px;">${_peEsc(code)}</span>`;
}
function _peUpdateTotal() {
    const total = [...document.querySelectorAll('#pe-rows .pe-amount')]
        .reduce((s, el) => s + (parseFloat(el.value) || 0), 0);
    const el = document.getElementById('pe-total-display');
    if (el) el.innerHTML = `总资产: <strong>¥${total.toLocaleString('zh-CN',{minimumFractionDigits:2})}</strong>`;
}
function deletePeRow(btn) {
    btn.closest('.pe-row').remove();
    _peUpdateTotal();
}
function addPortfolioRow() {
    const wrap = document.getElementById('pe-rows');
    const row  = _peBuildRow({code:'',name:'',amount:0,dailyReturn:0,holdingReturn:0,holdingReturnRate:0,totalReturn:0,category:'其他'}, wrap.children.length);
    wrap.appendChild(row);
    row.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
}
function _peCollect() {
    const date = document.getElementById('pe-date').value || new Date().toISOString().slice(0, 10);
    const rows = [...document.querySelectorAll('#pe-rows .pe-row')];
    const holdings = rows.map(r => {
        const code  = r.querySelector('.pe-code').value.trim();
        const name  = r.querySelector('.pe-name').value.trim();
        const cat   = r.querySelector('.pe-cat').value;
        const amount          = Math.round((parseFloat(r.querySelector('.pe-amount').value)  || 0) * 100) / 100;
        const dailyReturn     = Math.round((parseFloat(r.querySelector('.pe-daily').value)   || 0) * 100) / 100;
        const holdingReturn   = Math.round((parseFloat(r.querySelector('.pe-hold').value)    || 0) * 100) / 100;
        const holdingReturnRate= Math.round((parseFloat(r.querySelector('.pe-holdr').value)  || 0) * 100) / 100;
        const totalReturn     = Math.round((parseFloat(r.querySelector('.pe-total').value)   || 0) * 100) / 100;
        return { name, code, amount, dailyReturn, holdingReturn, holdingReturnRate, totalReturn,
                 category: cat, assetType: PE_ASSET_BY_CAT[cat] || 'active' };
    });
    const totalAsset = Math.round(holdings.reduce((s, h) => s + h.amount, 0) * 100) / 100;
    // ratio：占比重算
    holdings.forEach(h => {
        h.ratio = totalAsset > 0 ? Math.round(h.amount / totalAsset * 10000) / 100 : 0;
    });
    // 修正四舍五入误差
    if (holdings.length && totalAsset > 0) {
        const ratioSum = Math.round(holdings.reduce((s, h) => s + h.ratio, 0) * 100) / 100;
        const diff     = Math.round((100 - ratioSum) * 100) / 100;
        const big      = holdings.reduce((a, b) => a.amount > b.amount ? a : b);
        big.ratio      = Math.round((big.ratio + diff) * 100) / 100;
    }
    return { updateTime: date, totalAsset, holdings, targetAllocation: portfolioData.targetAllocation };
}

// ── PAT ─────────────────────────────────────────────────────────
function _getPAT() { return localStorage.getItem('gh_pat') || null; }
function _setPAT(p) { if (p) localStorage.setItem('gh_pat', p.trim()); }
function openPatModal() {
    const cur = _getPAT();
    document.getElementById('pat-input').value = cur || '';
    document.getElementById('pat-error').textContent = '';
    document.getElementById('patInputModal').style.display = 'flex';
    return new Promise(r => { _patResolve = r; });
}
function confirmPat() {
    const pat = document.getElementById('pat-input').value.trim();
    if (!pat) { document.getElementById('pat-error').textContent = '请输入 Token'; return; }
    _setPAT(pat);
    document.getElementById('patInputModal').style.display = 'none';
    if (_patResolve) { _patResolve(pat); _patResolve = null; }
}
function closePatModal() {
    document.getElementById('patInputModal').style.display = 'none';
    if (_patResolve) { _patResolve(null); _patResolve = null; }
}

// ── GitHub Contents API ──────────────────────────────────────────
async function _ghGet(path, pat) {
    const r = await fetch(`https://api.github.com/repos/${GH_REPO}/contents/${path}`, {
        headers: { 'Authorization': `token ${pat}`, 'Accept': 'application/vnd.github.v3+json' }
    });
    if (!r.ok) throw new Error(`GET ${path}: HTTP ${r.status}`);
    return r.json();
}
async function _ghPut(path, content, message, pat) {
    const meta = await _ghGet(path, pat);
    const b64  = btoa(unescape(encodeURIComponent(content)));  // UTF-8 safe base64
    const r    = await fetch(`https://api.github.com/repos/${GH_REPO}/contents/${path}`, {
        method: 'PUT',
        headers: {
            'Authorization': `token ${pat}`,
            'Accept': 'application/vnd.github.v3+json',
            'Content-Type': 'application/json',
        },
        body: JSON.stringify({ message, content: b64, sha: meta.sha }),
    });
    if (!r.ok) {
        const err = await r.json().catch(() => ({}));
        throw new Error(err.message || `PUT ${path}: HTTP ${r.status}`);
    }
    return true;
}
function _buildInlineBlock(data) {
    return `const portfolioData = ${JSON.stringify(data, null, 4)};`;
}

// ── save ──────────────────────────────────────────────────────────
async function savePortfolio() {
    const btn    = document.getElementById('pe-save-btn');
    const status = document.getElementById('pe-status');
    btn.disabled = true;
    status.className = 'pe-status';
    status.textContent = '⏳ 保存中...';
    try {
        const newData = _peCollect();

        // ensure PAT
        let pat = _getPAT();
        if (!pat) pat = await openPatModal();
        if (!pat) { status.textContent = '已取消'; btn.disabled = false; return; }

        // 1. update data/portfolio.json
        status.textContent = '📤 更新 portfolio.json...';
        await _ghPut(
            'data/portfolio.json',
            JSON.stringify(newData, null, 2) + '\n',
            `chore: 更新持仓快照 ${newData.updateTime}（总额 ¥${newData.totalAsset}）`,
            pat
        );

        // 2. update index.html inline portfolioData block
        status.textContent = '📤 更新 index.html 内联块...';
        const htmlMeta = await _ghGet('index.html', pat);
        // decode base64 (strip line breaks inserted by GitHub API)
        const rawB64   = (htmlMeta.content || '').replace(/\n/g, '');
        const htmlText = decodeURIComponent(escape(atob(rawB64)));
        const newBlock = _buildInlineBlock(newData);
        // Replace: const portfolioData = { ... }; (top-level, ends at \n};)
        const htmlNew  = htmlText.replace(
            /const portfolioData = \{[\s\S]*?\n\};/,
            newBlock
        );
        if (htmlNew === htmlText) {
            console.warn('[PE] portfolioData 块替换未命中，跳过 index.html 更新');
        } else {
            await _ghPut(
                'index.html',
                htmlNew,
                `chore: 同步 portfolioData 内联快照 ${newData.updateTime}`,
                pat
            );
        }

        // 3. update local state and re-render
        Object.assign(portfolioData, newData);
        renderHeader();
        renderMetrics();
        renderPieChart();
        renderBarChart();
        renderHoldings();

        status.className = 'pe-status ok';
        status.textContent = '✅ 已提交到 GitHub，数据已刷新';
        setTimeout(() => {
            if (document.getElementById('portfolioEditorModal').style.display !== 'none')
                closePortfolioEditor();
        }, 2200);
    } catch(e) {
        console.error('[Portfolio Editor]', e);
        // If token invalid, ask again
        if (String(e.message).includes('401') || String(e.message).includes('Bad credentials')) {
            localStorage.removeItem('gh_pat');
        }
        status.className = 'pe-status err';
        status.textContent = '❌ ' + (e.message || '提交失败，请检查网络或 Token 权限');
    } finally {
        btn.disabled = false;
    }
}

// ========== 子弹区余额宝快捷编辑 ==========
const _SVG_PENCIL = `<svg width="16" height="16" viewBox="0 0 16 16" fill="none"><path d="M11.5 2.5l2 2L5 13H3v-2L11.5 2.5z" stroke="currentColor" stroke-width="1.4" stroke-linejoin="round"/><path d="M10 4l2 2" stroke="currentColor" stroke-width="1.4" stroke-linecap="round"/></svg>`;
function _bulletCashEditStart(curAmt) {
    const wrap = document.getElementById('cashAmtWrap');
    if (!wrap) return;
    wrap.innerHTML = `
      <input class="cash-edit-input" id="cashEditInput" type="number" step="0.01" value="${curAmt > 0 ? curAmt : ''}" placeholder="输入金额">
      <div class="cash-edit-action">
        <button class="cash-edit-confirm" onclick="_bulletCashEditConfirm()" style="background:#f0b90b;color:#1a1f2e;border:none;border-radius:6px;padding:4px 12px;font-size:12px;font-weight:600;cursor:pointer;">确认</button>
        <button class="cash-edit-cancel" onclick="_bulletCashEditCancel(${curAmt})" style="background:none;border:1px solid rgba(0,0,0,0.15);color:rgba(0,0,0,0.6);border-radius:6px;padding:4px 10px;font-size:12px;cursor:pointer;">取消</button>
      </div>`;
    const inp = document.getElementById('cashEditInput');
    if (inp) { inp.focus(); inp.select(); }
    inp && inp.addEventListener('keydown', e => {
        if (e.key === 'Enter') _bulletCashEditConfirm();
        if (e.key === 'Escape') _bulletCashEditCancel(curAmt);
    });
}

async function _bulletCashEditConfirm() {
    const inp = document.getElementById('cashEditInput');
    if (!inp) return;
    const newAmt = parseFloat(inp.value);
    if (isNaN(newAmt) || newAmt < 0) { inp.focus(); return; }

    const wrap = document.getElementById('cashAmtWrap');
    wrap.innerHTML = `<span style="color:var(--text-muted);font-size:13px;">提交中…</span>`;

    try {
        // 更新内存中的 portfolioData
        const cashH = portfolioData.holdings && portfolioData.holdings.find(h => h.assetType === 'cash');
        if (cashH) {
            cashH.amount = newAmt;
            // 重算 totalAsset 和 ratio
            const total = portfolioData.holdings.reduce((s, h) => s + (h.amount || 0), 0);
            portfolioData.totalAsset = Math.round(total * 100) / 100;
            portfolioData.holdings.forEach(h => {
                h.ratio = total > 0 ? Math.round(h.amount / total * 10000) / 100 : 0;
            });
        }

        // 持久化到 GitHub
        let pat = _getPAT();
        if (!pat) pat = await openPatModal();
        if (!pat) { _bulletCashEditCancel(newAmt); return; }

        await _ghPut(
            'data/portfolio.json',
            JSON.stringify(portfolioData, null, 2) + '\n',
            `chore: 更新余额宝可用 ¥${newAmt}`,
            pat
        );
        const htmlMeta = await _ghGet('index.html', pat);
        const rawB64   = (htmlMeta.content || '').replace(/\n/g, '');
        const htmlText = decodeURIComponent(escape(atob(rawB64)));
        const newBlock = _buildInlineBlock(portfolioData);
        const htmlNew  = htmlText.replace(/const portfolioData = \{[\s\S]*?\n\};/, newBlock);
        if (htmlNew !== htmlText) {
            await _ghPut('index.html', htmlNew, `chore: 同步 portfolioData 内联 余额宝¥${newAmt}`, pat);
        }

        // 重渲
        renderHeader();
        renderMetrics();
        renderPieChart();
        renderBarChart();
        renderHoldings();

        // 刷新子弹区（会重建 cashAmtWrap）
        const rebalData = window._cachedRebalance;
        if (rebalData) _renderBulletZone(rebalData, portfolioData);

    } catch(e) {
        console.error('[CashEdit]', e);
        if (wrap) wrap.innerHTML = `<span class="bullet-amount" id="cashAmtDisplay">¥${newAmt.toLocaleString('zh-CN',{minimumFractionDigits:2})}</span><button class="cash-edit-btn" title="编辑余额宝可用" onclick="_bulletCashEditStart(${newAmt})">${_SVG_PENCIL}</button>`;
    }
}

function _bulletCashEditCancel(curAmt) {
    const wrap = document.getElementById('cashAmtWrap');
    if (!wrap) return;
    wrap.innerHTML = `<span class="bullet-amount" id="cashAmtDisplay">¥${curAmt > 0 ? curAmt.toLocaleString('zh-CN',{minimumFractionDigits:2}) : '--'}</span><button class="cash-edit-btn" title="编辑余额宝可用" onclick="_bulletCashEditStart(${curAmt})">${_SVG_PENCIL}</button>`;
}

