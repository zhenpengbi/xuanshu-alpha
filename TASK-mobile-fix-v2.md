# 任务书：移动端适配修复 V2 + PWA 图标

## 项目路径
`/Users/noah/Documents/AI /xuanshu-alpha/`
文件：`index.html`

---

## Bug 1：主题切换浮层被下方内容遮挡

### 现象
点击 Header 右上角主题切换按钮，弹出的浮层被下方模块盖住看不到。

### 根因
`.header-inner`（约第257行）设置了 `overflow: hidden`，导致内部绝对定位的 `.theme-popover` 被裁剪。

### 修复
移除 `.header-inner` 的 `overflow: hidden`。如果 sweep 装饰线需要 overflow 限制，改为用 `clip-path` 或在装饰伪元素上单独设 overflow。

```css
/* 改前 */
.header-inner {
    ...
    position: relative; overflow: hidden;
    ...
}

/* 改后 */
.header-inner {
    ...
    position: relative; /* 去掉 overflow: hidden */
    ...
}
```

如果去掉后顶部装饰线（`::after`）溢出，给 `::after` 加 `overflow: hidden` 或改用 `clip-path: inset(0)`。

---

## Bug 2：移动端「资讯」Tab 内容展示不全

### 现象
- 浏览器中打开看不全资讯内容
- 安装为 PWA 后同样不适配

### 排查方向
1. 资讯 tab 下有3个 section（`data-panel="news"`）：市场早晚报、新闻情绪、基金雷达——确认移动端全部 section 都能正确显示
2. `.timeline` 内容可能因为长文本溢出或绝对定位导致高度塌陷
3. `.sentiment-grid` 卡片布局在小屏下是否正确折叠为单列
4. `#fundRadarSection` 内表格或卡片是否超宽

### 修复思路
- `.timeline`、`.sentiment-grid` 在移动端确认 `width: 100%; box-sizing: border-box;`
- timeline-item 如果有固定宽度或 `white-space: nowrap`，改为自适应
- sentiment-grid 如果用了 `grid-template-columns: repeat(3, 1fr)`，移动端改为 `1fr`
- 确保资讯 tab 切换后 scrollTop 重置到 0（已有逻辑），内容区不被任何 fixed 元素遮挡

---

## Bug 3：移动端 Header 首行「更新时间」换行过多

### 现象
更新时间文字（如"行情更新: 2026-06-14 09:30"）在手机窄屏上换了好几行，占用太多空间。

### 修复方案
移动端（`@media max-width: 768px`）下，更新时间做以下优化之一：
- **方案A（推荐）**：只显示时间不显示"更新"两字，JS 中改为只输出 `HH:MM` 格式
- **方案B**：CSS 设置 `white-space: nowrap; overflow: hidden; text-overflow: ellipsis; max-width: 80px;`
- **方案C**：移动端直接隐藏更新时间 `.update-time { display: none !important; }` 

推荐方案A：在 JS 渲染 headerUpdateTime 时，判断屏幕宽度，窄屏只输出简短格式。或者更简单——CSS 上限制容器不换行 + 缩小字号到 8px。

---

## Bug 4：移动端策略回测趋势图显示不出来

### 现象
手机端点击「策略」tab，回测趋势图（ECharts）完全不显示。

### 排查
1. `#backtestChart` 容器在移动端 CSS 中设为 `height: 240px !important`（第1030行），检查是否被 `display:none` 或父容器高度 0 遮盖
2. ECharts `init` 时如果容器宽度为 0（panel 未激活时 display:none），图表不会渲染
3. **关键**：移动端初始只激活 `overview` panel，其他 panel 设为 `display: none`。当切换到 `strategy` 时，容器从 `none` 变为 `block`，但 ECharts 可能已经在页面加载时尝试渲染——此时容器宽高为 0，导致图表无法绑定。

### 修复
在 `switchTab` 函数中，切换到 `strategy` panel 时，延迟调用 `_btChart.resize()`：

```js
function switchTab(panel) {
    // ... 现有逻辑 ...
    
    // 切换后重新调整图表尺寸
    requestAnimationFrame(() => {
        if (panel === 'strategy' && _btChart) _btChart.resize();
        if (panel === 'overview') {
            // 如果 overview 里也有 echarts 图表，也 resize
            // 例如持仓饼图等
        }
    });
}
```

或者更保险的方案：首次切换到 strategy 时才初始化图表（延迟渲染），或在 `selectBtFund` 中加 `setTimeout(() => _btChart.resize(), 50)`。

---

## Bug 5：策略回测中包含未持仓基金（纳指100ETF、标普500ETF）

### 现象
回测模块展示了 6 只基金，其中「纳指100ETF」（513100）和「标普500ETF」（513500）不在当前持仓中。

### 背景
回测数据来自 `backtest/data/backtest.json`，包含 6 只基金。持仓数据来自 `data/portfolio.json`，有 9 只基金。两者 code 不完全一致（回测用的是 ETF 代码，持仓用的是联接基金代码）。

回测基金列表：
- 000216 易方达黄金ETF联接C ← 持仓有 002963/000307
- 008585 天弘AI主题指数C ← 持仓有 011840（天弘中证人工智能C）
- 017766 南方有色金属ETF联接E ← 持仓有 010990
- 515790 华夏光伏ETF ← 持仓有 012885（华夏中证光伏产业ETF发起式联接A）
- 513100 纳指100ETF ← ❌ 不在持仓
- 513500 标普500ETF ← ❌ 不在持仓

### 修复方案
在 `renderBacktestCards` 中，对每只基金做持仓匹配判断。未持仓的基金卡片上加一个标注角标：

```js
// 在 renderBacktestCards 中：
const portfolioCodes = new Set(portfolioData?.holdings?.map(h => h.code) || []);
// 也需要做模糊匹配（ETF vs 联接基金同资产类别）
const isHeld = portfolioCodes.has(r.code) || /* 关联匹配逻辑 */;

// 卡片 HTML 中加标注：
${!isHeld ? '<span class="bt-tag-not-held">未持仓</span>' : ''}
```

**但更简单的方案**：在回测卡片中，用不同视觉样式区分已持仓 vs 未持仓（比如未持仓的卡片边框虚线 + 右上角灰色「未持仓」标签），让用户一眼区分。

建议 CSS：
```css
.bt-tag-not-held {
    position: absolute; top: 8px; right: 8px;
    font-size: 10px; padding: 2px 6px; border-radius: 4px;
    background: rgba(255,255,255,.08); color: var(--text-muted);
    border: 1px dashed var(--text-muted);
}
.backtest-card.not-held { border-style: dashed; opacity: .75; }
```

---

## 验收标准

1. ✅ 主题切换浮层完全可见，不被任何下方内容遮挡
2. ✅ 移动端资讯 tab 所有内容（早晚报 + 情绪 + 雷达）完整展示
3. ✅ 移动端 Header 更新时间单行展示，不再换行
4. ✅ 移动端策略 tab 趋势图正常渲染
5. ✅ 回测卡片中，未持仓的基金有明确标注
6. ✅ git commit & push

## 优先级
Bug 1 > Bug 4 > Bug 2 > Bug 3 > Bug 5
