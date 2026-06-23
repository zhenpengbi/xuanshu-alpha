// ========== 玄枢Alpha - 新闻/时间线渲染 ==========
// ========== Render Timeline ==========
// 影响判断 → 标签样式映射
const IMPACT_META = {
    gold:   {label:'🥇黄金'},
    ashare: {label:'📈A股'},
    nasdaq: {label:'🇺🇸纳指'},
    retail: {label:'🛒零售'}
};
function impactType(view){
    if(/利多/.test(view)) return 'up';
    if(/利空/.test(view)) return 'down';
    return 'neutral';
}
function impactArrow(view){
    if(/利多/.test(view)) return '↑';
    if(/利空/.test(view)) return '↓';
    return '→';
}
/**
 * renderDateTabs — 通用日期/分类切换胶囊组件（可复用）
 * @param {HTMLElement} container  — 将 tab-bar 前置插入此容器
 * @param {Array<{label:string, value:string}>} dates — tab 数据
 * @param {Function} onSelect — 选中回调，参数为 value
 */
function renderDateTabs(container, dates, onSelect) {
    // 清除已有 tab-bar，避免重复渲染
    const existing = container.querySelector('.date-tab-bar');
    if (existing) existing.remove();

    const tabBar = document.createElement('div');
    tabBar.className = 'date-tab-bar';
    dates.forEach((d, i) => {
        const tab = document.createElement('button');
        tab.className = 'date-tab' + (i === 0 ? ' active' : '');
        tab.textContent = d.label;
        tab.dataset.dateValue = d.value;
        tab.addEventListener('click', () => {
            tabBar.querySelectorAll('.date-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            onSelect(d.value);
        });
        tabBar.appendChild(tab);
    });
    container.prepend(tabBar);
}

/**
 * renderTimelineItems — 将一组 news items 渲染到 #timeline 容器内（保留 tab-bar）
 */
function renderTimelineItems(el, items, meta) {
    // 保留 date-tab-bar（若存在），只替换后面的内容
    const tabBar = el.querySelector('.date-tab-bar');
    // 清除非 tab-bar 的子节点
    Array.from(el.childNodes).forEach(n => {
        if (n !== tabBar) n.remove ? n.remove() : el.removeChild(n);
    });

    if (!items || !items.length) {
        const empty = document.createElement('div');
        empty.style.cssText = 'color:var(--text-muted);font-size:13px;padding:20px 0;text-align:center;';
        empty.textContent = '该期暂无资讯数据';
        el.appendChild(empty);
        return;
    }

    const header = document.createElement('div');
    header.style.cssText = 'font-size:11px;color:var(--text-muted);margin-bottom:14px;';
    header.textContent = `数据更新：${meta.date||meta.updated||''} ${meta.period||''} · 每条附 AI 持仓影响判断`;
    el.appendChild(header);

    items.forEach(item => {
        const imp = item.impact || {};
        const tags = Object.keys(IMPACT_META)
            .filter(k => imp[k])
            .map(k => {
                const view = imp[k];
                return `<span class="impact-tag impact-${impactType(view)}">${IMPACT_META[k].label}${impactArrow(view)} ${view}</span>`;
            }).join('');
        const div = document.createElement('div');
        div.className = 'timeline-item';
        div.innerHTML = `
            <div class="timeline-time">${item.time||''}${item.source?` · 来源 ${item.source}`:''}</div>
            <div class="timeline-title">${item.title||''}</div>
            ${item.summary?`<div class="timeline-summary">${item.summary}</div>`:''}
            ${tags?`<div class="timeline-tags">${tags}</div>`:''}
            ${item.reason?`<div class="timeline-reason">💡 ${item.reason}</div>`:''}`;
        el.appendChild(div);
    });
}

/**
 * _renderPeriodTab — 早报☀️/晚报🌙 内容切换渲染器
 * 兼容新格式（morning/evening 双分区）、history 数组格式及旧 items 格式。
 */
function _renderTimelinePeriodTabs(el, news) {
    // 定义两个时段配置
    const PERIODS = [
        { key: 'morning', label: '早报 ☀️' },
        { key: 'evening', label: '晚报 🌙' },
    ];

    // 提取各时段数据
    const sections = PERIODS.map(p => {
        const sec = news[p.key];
        const items = sec && Array.isArray(sec.items) ? sec.items : [];
        return {
            key:    p.key,
            label:  p.label,
            period: sec && sec.period ? sec.period : p.label.replace(/ [☀🌙️].*/, '').trim(),
            date:   news.updated || '',
            items,
        };
    });

    // 默认选最新有数据的时段：
    //   上午（<13:00）且早报有数据 → 早报；否则晚报有数据 → 晚报；都无数据 → 晚报
    const hour = new Date().getHours();
    let defaultKey = 'evening';
    if (hour < 13 && sections[0].items.length) {
        defaultKey = 'morning';
    } else if (sections[1].items.length) {
        defaultKey = 'evening';
    } else if (sections[0].items.length) {
        defaultKey = 'morning';
    }

    // 构建 Tab 容器
    const tabWrap = document.createElement('div');
    tabWrap.className = 'period-tab-bar';

    const contentEl = document.createElement('div');
    contentEl.className = 'period-tab-content';

    function _showSection(key) {
        const sec = sections.find(s => s.key === key);
        // 切换 active 样式
        tabWrap.querySelectorAll('.period-tab').forEach(t => {
            t.classList.toggle('active', t.dataset.key === key);
        });
        // 清空内容区（保留 tab-bar 外的内容）
        contentEl.innerHTML = '';
        if (!sec || !sec.items.length) {
            const tip = document.createElement('div');
            tip.style.cssText = 'color:var(--text-muted);font-size:13px;padding:24px 0;text-align:center;';
            tip.textContent = sec && sec.key === 'morning'
                ? '☀️ 今日早报暂未生成，稍后更新'
                : '🌙 今日晚报暂未生成，稍后更新';
            contentEl.appendChild(tip);
            return;
        }
        // 渲染信息栏
        const header = document.createElement('div');
        header.style.cssText = 'font-size:11px;color:var(--text-muted);margin-bottom:14px;';
        header.textContent = `数据更新：${sec.date} ${sec.period} · 每条附 AI 持仓影响判断`;
        contentEl.appendChild(header);
        // 渲染条目
        sec.items.forEach(item => {
            const imp  = item.impact || {};
            const tags = Object.keys(IMPACT_META)
                .filter(k => imp[k])
                .map(k => {
                    const view = imp[k];
                    return `<span class="impact-tag impact-${impactType(view)}">${IMPACT_META[k].label}${impactArrow(view)} ${view}</span>`;
                }).join('');
            const div = document.createElement('div');
            div.className = 'timeline-item';
            div.innerHTML = `
                <div class="timeline-time">${item.time||''}${item.source?` · 来源 ${item.source}`:''}</div>
                <div class="timeline-title">${item.title||''}</div>
                ${item.summary?`<div class="timeline-summary">${item.summary}</div>`:''}
                ${tags?`<div class="timeline-tags">${tags}</div>`:''}
                ${item.reason?`<div class="timeline-reason">💡 ${item.reason}</div>`:''}`;
            contentEl.appendChild(div);
        });
    }

    // 渲染 Tabs
    sections.forEach(sec => {
        const btn = document.createElement('button');
        btn.className = 'period-tab' + (sec.key === defaultKey ? ' active' : '');
        btn.dataset.key = sec.key;
        // 无数据时 Tab 显示淡化样式
        if (!sec.items.length) btn.classList.add('empty');
        btn.textContent = sec.label;
        btn.addEventListener('click', () => _showSection(sec.key));
        tabWrap.appendChild(btn);
    });

    el.innerHTML = '';
    el.appendChild(tabWrap);
    el.appendChild(contentEl);
    _showSection(defaultKey);
}

// ── 把单条 history record 包装成 _renderTimelinePeriodTabs 所需结构 ──
function _recordToNewsObj(rec) {
    const isMorning = (rec.period || '').includes('早');
    const key = isMorning ? 'morning' : 'evening';
    return {
        updated: rec.date || '',
        [key]: { period: rec.period || '', items: rec.items || [] },
    };
}

async function renderTimeline() {
    const el  = document.getElementById('timeline');
    const sel = document.getElementById('newsDateSelect');

    // ── 优先尝试加载 news_history.json（有历史记录时启用下拉选择器）──
    let historyData = null;
    await loadJSON('data/news_history.json', d => { historyData = d; });

    if (historyData && Array.isArray(historyData.records) && historyData.records.length) {
        const records = historyData.records; // 最新在前

        // 填充下拉选项
        if (sel) {
            sel.innerHTML = records.map((rec, i) => {
                const periodShort = (rec.period || '').replace('报', '');
                return `<option value="${i}">${rec.date} ${periodShort}</option>`;
            }).join('');
            sel.style.display = '';
            sel.value = '0';

            const showRecord = idx => {
                const rec = records[idx];
                if (!rec) return;
                _renderTimelinePeriodTabs(el, _recordToNewsObj(rec));
            };
            sel.onchange = () => showRecord(parseInt(sel.value));
            showRecord(0);
        }
        return;
    }

    // ── 回退：用 window.newsData（保持原有逻辑不变）──
    const news = window.newsData;
    if (!news) {
        el.innerHTML = `<div style="color:var(--text-muted);font-size:13px;padding:20px 0;text-align:center;">
            暂无资讯数据 · 请运行 <code style="background:rgba(255,255,255,.06);padding:2px 6px;border-radius:4px;">python3 scripts/build_news_impact.py</code>
        </div>`;
        return;
    }
    if (news.morning !== undefined || news.evening !== undefined) {
        _renderTimelinePeriodTabs(el, news); return;
    }
    if (Array.isArray(news.items) && news.items.length && news.period) {
        const key = news.period.includes('早') ? 'morning' : 'evening';
        _renderTimelinePeriodTabs(el, { updated: news.updated || '', [key]: { period: news.period, items: news.items } });
        return;
    }
    if (Array.isArray(news.items) && news.items.length) {
        renderTimelineItems(el, news.items, news); return;
    }
    el.innerHTML = `<div style="color:var(--text-muted);font-size:13px;padding:20px 0;text-align:center;">
        暂无资讯数据 · 请运行 <code style="background:rgba(255,255,255,.06);padding:2px 6px;border-radius:4px;">python3 scripts/build_news_impact.py</code>
    </div>`;
}

