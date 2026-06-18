# TASK-fix-v2.md — 二次修复：主题弹窗遮挡 + 资讯Tab内容截断

## 背景

commit 9590866 的修复验收后，用户反馈：
1. **主题弹窗仍被遮挡** — 点击右上角主题切换按钮，弹窗打开后被下方内容遮住
2. **资讯Tab仍有信息看不全** — 移动端某些内容被截断

## 问题1：主题弹窗遮挡

### 根因分析

`.theme-popover` 当前是 `position: absolute` 定位在按钮的父容器 `div[style="position:relative;flex:none;"]` 内。

虽然 `.header-inner` 已删除 `overflow:hidden`，但 `.header` 有 `backdrop-filter: blur(12px)`，在 iOS Safari/移动端浏览器中会创建独立合成层（compositing layer），导致内部绝对定位子元素的绘制被限制在该层内，视觉上表现为「被遮挡」。

此外，移动端 `.header-inner` 高度固定 56px + `border-radius: 0`，弹窗向下展开时会超出 header 可视区域。

### 修复方案

**将 `.theme-popover` 改为 `position: fixed` 定位**，脱离 header 层叠上下文：

```css
.theme-popover {
    position: fixed;
    top: 64px;        /* header高度(56px) + 间距(8px) */
    right: 16px;
    z-index: 9999;    /* 确保在所有内容之上 */
    /* 其余样式保持不变 */
}
```

同时需要修改 JS：点击按钮时动态计算弹窗位置（获取按钮的 getBoundingClientRect），或者用固定位置也行（因为按钮始终在右上角）。

**桌面端**（无 `@media` 限制）也同样改为 fixed，因为桌面端可能也有此问题。

**补充**：添加点击弹窗外区域关闭的逻辑（如果还没有的话）。

## 问题2：资讯Tab信息截断

### 根因分析

资讯Tab（data-panel="news"）包含3个 section：
1. 市场早晚报（timeline）
2. 新闻情绪 · 持仓影响速览（sentiment-grid）
3. 基金雷达（fundRadarSection + radar-grid）

移动端媒体查询中对这些区域加了 `overflow-x: hidden`，但问题是：
- sentiment 卡片或 radar 卡片内部内容（如标签、指标数字）在窄屏下可能需要换行而非截断
- `overflow-x: hidden` 会直接截掉超出部分

### 修复方案

1. **sentiment-grid 内的卡片**：确保卡片内文字 `word-break: break-word; overflow-wrap: break-word;`，不要让文本被截断
2. **radar-card 内的指标区（.rc-metrics）**：`grid-template-columns: repeat(3, 1fr)` 在极窄屏下 3 列太挤 → 移动端改为 `repeat(2, 1fr)` 或自动换行 `auto-fill, minmax(90px, 1fr)`
3. **radar-card 内表格**：已有 `overflow-x: auto`（横向滚动），但确认实际生效（需要外层有明确宽度限制 `max-width: 100%`）
4. **timeline-item 内容**：检查是否有固定宽度或 `text-overflow: ellipsis` 导致标题被截断 → 如有，移动端去掉省略号限制，允许完整展示
5. **整体**：将资讯Tab区域的 `overflow-x: hidden` 改为 `overflow-x: auto`（允许在必要时横向滚动而非硬截断）

### 关键原则

**移动端内容优先完整展示，允许换行/折叠，不要硬截断。** 如果实在放不下，用 `overflow-x: auto`（可滚动）而非 `overflow-x: hidden`（硬截）。

## 验收标准

- [ ] iPhone SE / 375px 宽度下，点击主题切换按钮，弹窗完整可见且不被遮挡
- [ ] iPhone SE / 375px 宽度下，切换到资讯Tab，所有卡片内容（情绪分、雷达指标、早晚报标题）完整可读，无截断
- [ ] iPad / 768px 宽度下同样验证上述两点
- [ ] 桌面端功能不退化

## 文件

只需修改 `index.html`（单文件项目）

## 提交

修复完成后 `git add . && git commit -m "fix: 二次修复主题弹窗遮挡+资讯Tab内容截断" && git push origin main`
