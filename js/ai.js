// ========== 玄枢Alpha - AI 智能分析（DeepSeek 直连，流式输出）==========
// 模型配置从 data/ai_config.json 动态加载，更换模型只需修改 JSON，无需改代码。

const AI_CFG = {
    KEY_STORE:   'xuanshu_ai_key',
    MODEL_STORE: 'xuanshu_ai_model',
    HIST_STORE:  'xuanshu_ai_history',
    HIST_MAX:    30,   // 最多保留条数
    // 以下由 loadAIConfig() 动态填充，这里保留兜底默认值
    BASE_URLS:   { deepseek: 'https://api.deepseek.com' },
    DEFAULT_MODEL:    'deepseek-v4-flash',
    DEFAULT_PROVIDER: 'deepseek',
    MODELS: [],   // 从 ai_config.json 加载后填充
};

// ── 历史记录存取 ──
function aiHistLoad() {
    try { return JSON.parse(localStorage.getItem(AI_CFG.HIST_STORE) || '[]'); }
    catch { return []; }
}
function aiHistSave(list) {
    localStorage.setItem(AI_CFG.HIST_STORE, JSON.stringify(list));
}
function aiHistAdd(modelId, text) {
    const list = aiHistLoad();
    const now  = new Date();
    const pad  = n => String(n).padStart(2, '0');
    list.unshift({
        id:    now.getTime(),
        ts:    `${now.getFullYear()}-${pad(now.getMonth()+1)}-${pad(now.getDate())} ${pad(now.getHours())}:${pad(now.getMinutes())}`,
        model: modelDisplayName(modelId),
        model_id: modelId,
        text,
    });
    // 超出上限时丢弃最旧的
    if (list.length > AI_CFG.HIST_MAX) list.splice(AI_CFG.HIST_MAX);
    aiHistSave(list);
    return list.length;
}
function aiHistClear() {
    localStorage.removeItem(AI_CFG.HIST_STORE);
}

// ── 历史抽屉渲染 ──
function aiHistRenderList() {
    const listEl = document.getElementById('aiHistList');
    if (!listEl) return;
    const list = aiHistLoad();
    if (!list.length) {
        listEl.innerHTML = '<div class="ai-hist-empty">📭 暂无历史记录<br>分析完成后自动保存</div>';
        return;
    }
    listEl.innerHTML = list.map((item, idx) => `
        <div class="ai-hist-item" data-idx="${idx}">
            <div class="ai-hist-item-meta">
                <span class="ai-hist-item-time">${escHtml(item.ts)}</span>
                <span class="ai-hist-item-model">${escHtml(item.model)}</span>
            </div>
            <div class="ai-hist-item-preview">${escHtml(item.text.slice(0, 120))}</div>
        </div>
    `).join('');
}

function aiHistRenderDetail(idx) {
    const list = aiHistLoad();
    const item = list[idx];
    if (!item) return;
    const detailMeta = document.getElementById('aiHistDetailMeta');
    const detailText = document.getElementById('aiHistDetailText');
    if (detailMeta) detailMeta.textContent = `${item.ts}　${item.model}`;
    if (detailText) detailText.innerHTML = renderAIMarkdown(item.text);
    // 切换视图
    const listEl   = document.getElementById('aiHistList');
    const detailEl = document.getElementById('aiHistDetail');
    if (listEl)   listEl.style.display   = 'none';
    if (detailEl) detailEl.style.display = '';
}

// ── 历史抽屉开关（全局函数，供 HTML onclick 调用）──
function aiHistOpen() {
    const overlay = document.getElementById('aiHistOverlay');
    const drawer  = document.getElementById('aiHistDrawer');
    const listEl  = document.getElementById('aiHistList');
    const detailEl= document.getElementById('aiHistDetail');
    // 每次打开都回到列表视图
    if (listEl)   listEl.style.display   = '';
    if (detailEl) detailEl.style.display = 'none';
    aiHistRenderList();
    if (overlay) overlay.style.display = '';
    if (drawer)  drawer.style.display  = '';
}
function aiHistClose() {
    document.getElementById('aiHistOverlay').style.display = 'none';
    document.getElementById('aiHistDrawer').style.display  = 'none';
}

// 更新「历史」按钮上的计数徽章
function aiHistSyncBadge() {
    const count = aiHistLoad().length;
    const badge = document.getElementById('aiHistCount');
    if (!badge) return;
    if (count > 0) { badge.textContent = count; badge.style.display = ''; }
    else            { badge.style.display = 'none'; }
}

// ── 从 data/ai_config.json 动态加载模型配置 ──
async function loadAIConfig() {
    const cfg = await loadJSON('data/ai_config.json', d => d);
    if (!cfg) return;

    // 更新 base URL
    if (cfg.providers) {
        Object.entries(cfg.providers).forEach(([name, p]) => {
            if (p.base_url) AI_CFG.BASE_URLS[name] = p.base_url;
        });
    }

    // 更新默认提供商
    if (cfg.default_provider) AI_CFG.DEFAULT_PROVIDER = cfg.default_provider;

    // 更新模型列表
    if (cfg.models && cfg.models.length) {
        AI_CFG.MODELS = cfg.models;
        const def = cfg.models.find(m => m.default);
        if (def) AI_CFG.DEFAULT_MODEL = def.id;
    }
}

// ── API Key / 模型 存取 ──
function aiGetKey()     { return localStorage.getItem(AI_CFG.KEY_STORE) || ''; }
function aiSaveKey(k)   { localStorage.setItem(AI_CFG.KEY_STORE, k.trim()); }
function aiClearKey()   { localStorage.removeItem(AI_CFG.KEY_STORE); }
function aiGetModel()   {
    try { return JSON.parse(localStorage.getItem(AI_CFG.MODEL_STORE)); } catch { return null; }
}
function aiSaveModel(m) { localStorage.setItem(AI_CFG.MODEL_STORE, JSON.stringify(m)); }
function aiCurrentModel() {
    const saved = aiGetModel();
    // 如果已保存的模型 ID 在当前配置里存在，直接使用；否则回退到默认
    if (saved && saved.id) {
        const inList = AI_CFG.MODELS.find(m => m.id === saved.id);
        if (inList) return { id: inList.id, provider: inList.provider };
    }
    const def = AI_CFG.MODELS.find(m => m.default) || AI_CFG.MODELS[0];
    return def
        ? { id: def.id, provider: def.provider }
        : { id: AI_CFG.DEFAULT_MODEL, provider: AI_CFG.DEFAULT_PROVIDER };
}

// ── 模型名称显示（从配置读取，不再硬编码）──
function modelDisplayName(id) {
    const m = AI_CFG.MODELS.find(m => m.id === id);
    return m ? m.name : id;
}

// ── 动态渲染模型 Tab ──
function renderModelTabs(container) {
    if (!container || !AI_CFG.MODELS.length) return;
    const current = aiCurrentModel();
    container.innerHTML = AI_CFG.MODELS.map(m => `
        <button class="ai-model-tab${m.id === current.id ? ' active' : ''}"
                data-model="${escHtml(m.id)}"
                data-provider="${escHtml(m.provider)}">
            ${escHtml(m.name)}<span class="ai-model-desc">${escHtml(m.desc || '')}</span>
        </button>
    `).join('');
}

// ── Prompt 构建 ──
function buildAIPrompt() {
    const p    = portfolioData || {};
    const sigs = window.techSignalsData || [];

    // 余额宝（货币基金）= 可用资金
    const cashH = (p.holdings || []).find(h => h.category === '货币基金');
    const cash  = cashH ? cashH.amount : 0;

    // 持仓文字
    const holdingsText = (p.holdings || []).map(h => {
        const ret = h.holdingReturnRate;
        const retStr = ret != null ? `持仓收益${ret >= 0 ? '+' : ''}${ret.toFixed(1)}%` : '';
        return `  - ${h.name}（${h.category}·${h.assetType === 'trend' ? '趋势型' : '震荡型'}）：` +
               `¥${h.amount.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}（${h.ratio}%）${retStr ? '，' + retStr : ''}`;
    }).join('\n');

    // 信号文字（仅有明确操作方向的）
    const BUY_SIG  = new Set(['买入', '定投', '定投补仓', '可加仓', '待建仓']);
    const SELL_SIG = new Set(['减仓', '卖出', '高估警惕']);
    const actionSigs = sigs.filter(s => BUY_SIG.has(s.signal) || SELL_SIG.has(s.signal));
    const sigsText   = actionSigs.length
        ? actionSigs.map(s => `  - ${s.name}：${s.signal}，${(s.action_detail || s.reason || '').slice(0, 80)}`).join('\n')
        : '  暂无明确操作信号，整体观望';

    // 年化推算
    let annualNote = '';
    const hist = window._portfolioHistCache;
    if (hist && hist.return_pct != null && hist.series && hist.series.length >= 7) {
        const d0   = new Date(hist.series[0].date);
        const d1   = new Date(hist.series[hist.series.length - 1].date);
        const days = Math.max(1, Math.round((d1 - d0) / 86400000));
        const ann  = (Math.pow(1 + hist.return_pct / 100, 365 / days) - 1) * 100;
        annualNote = `近${days}天收益${hist.return_pct.toFixed(2)}%，推算年化约${ann.toFixed(1)}%（目标10%）。`;
    }

    return `你是玄枢Alpha的AI投资顾问，专注中国基金理财。

【用户目标】年化收益率≥10%。${annualNote}

【当前持仓 · 总资产¥${(p.totalAsset || 0).toLocaleString('zh-CN', { maximumFractionDigits: 0 })}，可用资金（余额宝）¥${cash.toLocaleString('zh-CN', { maximumFractionDigits: 0 })}】
${holdingsText || '  暂无持仓数据'}

【今日量化信号（有操作方向的）】
${sigsText}

请给出今日投资建议，格式如下，不要超过300字：

**今日操作**：有机会则说清楚操作哪个基金、从余额宝转多少钱；没有机会就直接说"今日无需操作"。
**最大风险**：当前最需要注意的风险（一句话）。
**一句话总结**：今日核心策略（15字以内）。

语言简洁，面向普通投资者，避免堆砌专业术语。`;
}

// ── 流式调用 AI API（兼容 OpenAI 格式）──
async function callAIStream(prompt, model, apiKey, onToken, onDone, onError) {
    const provider = model.provider || AI_CFG.DEFAULT_PROVIDER;
    const baseUrl  = AI_CFG.BASE_URLS[provider] || AI_CFG.BASE_URLS.deepseek;

    let res;
    try {
        res = await fetch(`${baseUrl}/chat/completions`, {
            method:  'POST',
            headers: {
                'Content-Type':  'application/json',
                'Authorization': `Bearer ${apiKey}`,
            },
            body: JSON.stringify({
                model:      model.id,
                messages:   [{ role: 'user', content: prompt }],
                stream:     true,
                max_tokens: 600,
            }),
        });
    } catch (e) {
        onError('网络错误：' + e.message); return;
    }

    if (!res.ok) {
        let msg = `API 错误 ${res.status}`;
        try { const j = await res.json(); msg = j.error?.message || msg; } catch {}
        onError(msg); return;
    }

    const reader  = res.body.getReader();
    const decoder = new TextDecoder();
    let   buf     = '';

    while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        buf += decoder.decode(value, { stream: true });
        const lines = buf.split('\n');
        buf = lines.pop();
        for (const line of lines) {
            if (!line.startsWith('data: ')) continue;
            const data = line.slice(6).trim();
            if (data === '[DONE]') { onDone(); return; }
            try {
                const j     = JSON.parse(data);
                const token = j.choices?.[0]?.delta?.content;
                if (token) onToken(token);
            } catch {}
        }
    }
    onDone();
}

// ── 简单 Markdown 渲染（粗体 + 换行）──
function renderAIMarkdown(text) {
    return escHtml(text)
        .replace(/\*\*(.+?)\*\*/g, '<strong>$1</strong>')
        .replace(/\n/g, '<br>');
}

// ── UI 初始化 ──
async function initAIModule() {
    // 先加载模型配置，再初始化 UI
    await loadAIConfig();

    const keyBtn     = document.getElementById('aiKeyBtn');
    const keyPanel   = document.getElementById('aiKeyPanel');
    const keyInput   = document.getElementById('aiKeyInput');
    const keySave    = document.getElementById('aiKeySave');
    const keyClear   = document.getElementById('aiKeyClear');
    const runBtn     = document.getElementById('aiRunBtn');
    const modelTabs  = document.getElementById('aiModelTabs');
    const outputWrap = document.getElementById('aiOutputWrap');
    const outputEl   = document.getElementById('aiOutput');
    const outputMeta = document.getElementById('aiOutputMeta');
    const emptyEl    = document.getElementById('aiEmpty');
    const keyStatus  = document.getElementById('aiKeyStatus');

    if (!keyBtn) return;

    // 动态渲染模型 Tab
    renderModelTabs(modelTabs);

    // 历史徽章初始化
    aiHistSyncBadge();

    // 历史按钮
    const histBtn = document.getElementById('aiHistBtn');
    if (histBtn) histBtn.addEventListener('click', aiHistOpen);

    // 历史详情返回按钮
    const histBack = document.getElementById('aiHistBack');
    if (histBack) histBack.addEventListener('click', () => {
        document.getElementById('aiHistDetail').style.display = 'none';
        document.getElementById('aiHistList').style.display   = '';
    });

    // 历史列表点击（事件委托）
    const histList = document.getElementById('aiHistList');
    if (histList) histList.addEventListener('click', e => {
        const item = e.target.closest('.ai-hist-item');
        if (!item) return;
        aiHistRenderDetail(Number(item.dataset.idx));
    });

    // 清空历史
    const histClear = document.getElementById('aiHistClear');
    if (histClear) histClear.addEventListener('click', () => {
        if (!confirm('确认清空所有历史记录？')) return;
        aiHistClear();
        aiHistRenderList();
        aiHistSyncBadge();
    });

    // 同步 Key 状态显示
    function syncKeyStatus() {
        const k = aiGetKey();
        if (keyStatus) {
            keyStatus.textContent = k ? '已配置 ✓' : '未配置';
            keyStatus.style.color = k ? 'var(--green)' : '';
        }
    }
    syncKeyStatus();

    // 同步 Tab 高亮
    function syncModelTabs() {
        const m = aiCurrentModel();
        if (!modelTabs) return;
        modelTabs.querySelectorAll('.ai-model-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.model === m.id);
        });
    }

    // Key 面板开关
    keyBtn.addEventListener('click', () => {
        const open = keyPanel.style.display !== 'none';
        keyPanel.style.display = open ? 'none' : '';
        if (!open) { keyInput.value = aiGetKey(); keyInput.focus(); }
    });

    // 保存 Key
    keySave.addEventListener('click', () => {
        const v = keyInput.value.trim();
        if (!v) { keyInput.focus(); return; }
        aiSaveKey(v);
        syncKeyStatus();
        keyPanel.style.display = 'none';
    });
    keyInput.addEventListener('keydown', e => { if (e.key === 'Enter') keySave.click(); });

    // 清除 Key
    keyClear.addEventListener('click', () => {
        aiClearKey();
        keyInput.value = '';
        syncKeyStatus();
    });

    // 模型切换
    if (modelTabs) {
        modelTabs.addEventListener('click', e => {
            const btn = e.target.closest('.ai-model-tab');
            if (!btn) return;
            aiSaveModel({ id: btn.dataset.model, provider: btn.dataset.provider });
            syncModelTabs();
        });
    }

    // 立即分析
    runBtn.addEventListener('click', async () => {
        const key = aiGetKey();
        if (!key) {
            keyPanel.style.display = '';
            keyInput.focus();
            return;
        }

        const model = aiCurrentModel();
        runBtn.disabled          = true;
        runBtn.textContent       = '分析中…';
        outputWrap.style.display = '';
        emptyEl.style.display    = 'none';
        outputEl.innerHTML       = '<span class="ai-cursor">▌</span>';
        outputMeta.textContent   = `${modelDisplayName(model.id)} · 生成中…`;

        const prompt = buildAIPrompt();
        let   full   = '';

        await callAIStream(
            prompt, model, key,
            token => {
                full += token;
                outputEl.innerHTML = renderAIMarkdown(full) + '<span class="ai-cursor">▌</span>';
                outputEl.parentElement.scrollTop = outputEl.parentElement.scrollHeight;
            },
            () => {
                outputEl.innerHTML = renderAIMarkdown(full);
                const now = new Date();
                const hh  = now.getHours().toString().padStart(2, '0');
                const mm  = now.getMinutes().toString().padStart(2, '0');
                outputMeta.textContent = `${modelDisplayName(model.id)} · ${hh}:${mm} · 基于实时持仓数据`;
                runBtn.disabled      = false;
                runBtn.textContent   = '▶ 再次分析';
                // 自动保存到历史，更新徽章
                if (full.trim()) {
                    aiHistAdd(model.id, full.trim());
                    aiHistSyncBadge();
                }
            },
            err => {
                outputEl.innerHTML = `<span style="color:var(--red);">❌ ${escHtml(err)}</span>
<div style="font-size:12px;color:var(--text-muted);margin-top:8px;">
请检查 API Key 是否正确，或网络是否能访问 ${AI_CFG.BASE_URLS[AI_CFG.DEFAULT_PROVIDER]}
</div>`;
                outputMeta.textContent = '分析失败';
                runBtn.disabled      = false;
                runBtn.textContent   = '▶ 重试';
            }
        );
    });
}

document.addEventListener('DOMContentLoaded', initAIModule);
