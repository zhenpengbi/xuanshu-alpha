// ========== 玄枢Alpha - AI 智能分析（DeepSeek 直连，流式输出）==========

const AI_CFG = {
    KEY_STORE:        'xuanshu_ai_key',
    MODEL_STORE:      'xuanshu_ai_model',
    BASE_URLS:        { deepseek: 'https://api.deepseek.com' },
    DEFAULT_MODEL:    'deepseek-chat',
    DEFAULT_PROVIDER: 'deepseek',
};

// ── API Key / 模型 存取 ──
function aiGetKey()     { return localStorage.getItem(AI_CFG.KEY_STORE) || ''; }
function aiSaveKey(k)   { localStorage.setItem(AI_CFG.KEY_STORE, k.trim()); }
function aiClearKey()   { localStorage.removeItem(AI_CFG.KEY_STORE); }
function aiGetModel()   {
    try { return JSON.parse(localStorage.getItem(AI_CFG.MODEL_STORE)); } catch { return null; }
}
function aiSaveModel(m) { localStorage.setItem(AI_CFG.MODEL_STORE, JSON.stringify(m)); }
function aiCurrentModel() {
    return aiGetModel() || { id: AI_CFG.DEFAULT_MODEL, provider: AI_CFG.DEFAULT_PROVIDER };
}

// ── Prompt 构建 ──
// 把持仓、信号、风险、历史数据组装成自然语言，让 AI 有足够上下文
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

    // 信号文字（仅有明确操作方向的，减少噪音）
    const BUY_SIG  = new Set(['买入', '定投', '定投补仓', '可加仓', '待建仓']);
    const SELL_SIG = new Set(['减仓', '卖出', '高估警惕']);
    const actionSigs = sigs.filter(s => BUY_SIG.has(s.signal) || SELL_SIG.has(s.signal));
    const sigsText   = actionSigs.length
        ? actionSigs.map(s => `  - ${s.name}：${s.signal}，${(s.action_detail || s.reason || '').slice(0, 80)}`).join('\n')
        : '  暂无明确操作信号，整体观望';

    // 年化推算（使用 _portfolioHistCache）
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

// ── 流式调用 DeepSeek ──
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
        buf = lines.pop(); // 保留不完整的行
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

// ── 模型名称显示 ──
function modelDisplayName(id) {
    return id === 'deepseek-chat' ? 'DeepSeek-V3' :
           id === 'deepseek-reasoner' ? 'DeepSeek-R1' : id;
}

// ── UI 初始化 ──
function initAIModule() {
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

    if (!keyBtn) return; // 元素未渲染时跳过

    // 同步 Key 状态
    function syncKeyStatus() {
        const k = aiGetKey();
        if (keyStatus) {
            keyStatus.textContent = k ? '已配置 ✓' : '未配置';
            keyStatus.style.color = k ? 'var(--green)' : '';
        }
    }
    syncKeyStatus();

    // 同步模型 Tab 选中状态
    function syncModelTabs() {
        const m = aiCurrentModel();
        if (!modelTabs) return;
        modelTabs.querySelectorAll('.ai-model-tab').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.model === m.id);
        });
    }
    syncModelTabs();

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
            // 未配置 Key，展开配置面板
            keyPanel.style.display = '';
            keyInput.focus();
            return;
        }

        const model = aiCurrentModel();
        runBtn.disabled      = true;
        runBtn.textContent   = '分析中…';
        outputWrap.style.display = '';
        emptyEl.style.display    = 'none';
        outputEl.innerHTML   = '<span class="ai-cursor">▌</span>';
        outputMeta.textContent = `${modelDisplayName(model.id)} · 生成中…`;

        const prompt = buildAIPrompt();
        let   full   = '';

        await callAIStream(
            prompt, model, key,
            // onToken
            token => {
                full += token;
                outputEl.innerHTML = renderAIMarkdown(full) + '<span class="ai-cursor">▌</span>';
                outputEl.parentElement.scrollTop = outputEl.parentElement.scrollHeight;
            },
            // onDone
            () => {
                outputEl.innerHTML = renderAIMarkdown(full);
                const now = new Date();
                const hh  = now.getHours().toString().padStart(2, '0');
                const mm  = now.getMinutes().toString().padStart(2, '0');
                outputMeta.textContent = `${modelDisplayName(model.id)} · ${hh}:${mm} · 基于实时持仓数据`;
                runBtn.disabled      = false;
                runBtn.textContent   = '▶ 再次分析';
            },
            // onError
            err => {
                outputEl.innerHTML = `<span style="color:var(--red);">❌ ${escHtml(err)}</span>
<div style="font-size:12px;color:var(--text-muted);margin-top:8px;">
请检查 API Key 是否正确，或网络是否能访问 api.deepseek.com
</div>`;
                outputMeta.textContent = '分析失败';
                runBtn.disabled      = false;
                runBtn.textContent   = '▶ 重试';
            }
        );
    });
}

document.addEventListener('DOMContentLoaded', initAIModule);
