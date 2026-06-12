# 玄枢 Alpha — 移动端 UI 重构（V2 行业最高标准）

> 对标产品：支付宝基金详情页 / 且慢 / 有知有行 / Robinhood / Coinbase  
> 设计：小老大  
> 执行：Claude Code  
> 日期：2026-06-12  
> 目标：移动端体验达到专业理财 App 水准

---

## 当前问题（从真机截图分析）

| 问题 | 严重度 |
|------|--------|
| Header 太臃肿（Logo+副标题+LIVE badge 全堆一起） | 🔴 |
| 行情卡片过大，一屏只能看 1-2 张 | 🔴 |
| 底部 Tab 用 emoji 做图标，廉价感强 | 🔴 |
| 没有 iOS PWA 安装引导 | 🟡 |
| 卡片间距过大，信息密度低 | 🟡 |
| 净值数字字号过大（视觉像对账单不像投顾） | 🟡 |

---

## 一、移动端 Header 重构

### 目标效果（紧凑两行式）

```
┌─────────────────────────────────────┐
│  🏛 玄枢                   06-11 ●  │
│  ¥55,522.55        今日 +699.83 ↑  │
└─────────────────────────────────────┘
```

### 设计规范

- **高度**：56px（含 padding），不超过屏幕 8%
- **第一行**：品牌名「玄枢」14px 半透明金 + 右侧更新时间 11px + 绿色小圆点(4px)替代 LIVE 文字
- **第二行**：总资产 24px 白色粗体 + 今日收益 16px 带颜色（涨绿跌红）
- **去掉**：Logo SVG 图形、副标题「北斗定枢·守正出奇」、LIVE 方框 badge
- **背景**：纯色 `rgba(19,16,12,.97)` + 底边 1px 金色分割线
- **sticky**：滚动时 header 始终置顶

### CSS（覆盖现有 @media max-width:768px）

```css
@media (max-width: 768px) {
  .header { padding: 0; }
  .header-inner {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 10px 16px;
    border-radius: 0;
    border: none;
    box-shadow: none;
    background: rgba(19,16,12,.97);
    border-bottom: 1px solid rgba(201,162,39,.15);
  }
  .header-inner::after,
  .header-inner::before { display: none; }
  .logo-area { display: none; } /* 移动端隐藏Logo区 */
  
  /* 用新的移动端 header 结构替代 */
  .mobile-header-brand {
    display: flex;
    align-items: center;
    gap: 6px;
  }
  .mobile-header-brand .brand-name {
    font-size: 14px;
    color: var(--gold);
    font-weight: 600;
    letter-spacing: 1px;
  }
  .mobile-header-right {
    display: flex;
    align-items: center;
    gap: 8px;
  }
  .mobile-header-right .update-dot {
    width: 5px; height: 5px;
    border-radius: 50%;
    background: var(--jade-soft);
    box-shadow: 0 0 6px rgba(31,184,116,.6);
  }
  
  /* 资产行 */
  .mobile-asset-row {
    display: flex;
    justify-content: space-between;
    align-items: baseline;
    padding: 6px 16px 12px;
    background: rgba(19,16,12,.97);
  }
  .mobile-asset-total {
    font-size: 24px;
    font-weight: 700;
    font-family: var(--mono);
    color: var(--paper);
  }
  .mobile-asset-daily {
    font-size: 15px;
    font-weight: 600;
    font-family: var(--mono);
  }
  
  /* 隐藏 PC header 元素 */
  .header-stats { display: none; }
}
```

### HTML（在 header 内部添加移动端专属结构）

```html
<!-- 移动端 Header（PC 端 display:none） -->
<div class="mobile-header" id="mobileHeader">
  <div class="mobile-header-top">
    <span class="brand-name">玄枢</span>
    <span class="header-update">
      <span class="update-text num" id="mUpdateTime">06-11</span>
      <span class="update-dot"></span>
    </span>
  </div>
  <div class="mobile-asset-row">
    <span class="mobile-asset-total num" id="mTotal">¥55,522.55</span>
    <span class="mobile-asset-daily num positive" id="mDaily">+699.83</span>
  </div>
</div>
```

---

## 二、底部 Tab Bar 重构（对标支付宝/且慢级别）

### 设计规范

- **高度**：52px + safe-area
- **图标**：使用 SVG 线性图标（非 emoji），激活态描边变金色+填充
- **字号**：10px，激活态金色，非激活 `var(--paper-faint)`
- **Tab 数量**：5 个
- **动效**：切换时图标有微弹 `transform: scale(1.1)` + 150ms ease
- **指示器**：激活 Tab 顶部有 2px 金色横线

### Tab 图标定义（SVG inline，24x24 viewBox）

| Tab | 名称 | SVG 描述 |
|-----|------|---------|
| 1 | 总览 | 四格方块（Dashboard grid） |
| 2 | 持仓 | 饼图/钱包 |
| 3 | 信号 | 折线图+脉冲点 |
| 4 | 资讯 | 报纸/文档 |
| 5 | 建议 | 指南针/靶心 |

### CSS

```css
.mobile-tab-bar {
  display: none;
  position: fixed;
  bottom: 0; left: 0; right: 0;
  height: calc(52px + env(safe-area-inset-bottom, 0px));
  padding-bottom: env(safe-area-inset-bottom, 0px);
  background: rgba(19,16,12,.98);
  backdrop-filter: blur(16px) saturate(1.2);
  border-top: 1px solid rgba(201,162,39,.12);
  z-index: 200;
  justify-content: space-around;
  align-items: center;
}

@media (max-width: 768px) {
  .mobile-tab-bar { display: flex; }
  body { padding-bottom: calc(52px + env(safe-area-inset-bottom, 0px)); }
}

.tab-btn {
  display: flex;
  flex-direction: column;
  align-items: center;
  gap: 3px;
  background: none;
  border: none;
  cursor: pointer;
  padding: 6px 16px;
  position: relative;
  -webkit-tap-highlight-color: transparent;
}

.tab-btn svg {
  width: 22px; height: 22px;
  stroke: var(--paper-faint);
  fill: none;
  stroke-width: 1.6;
  transition: stroke .2s, transform .15s;
}

.tab-btn .tab-label {
  font-size: 10px;
  color: var(--paper-faint);
  letter-spacing: 0.3px;
  transition: color .2s;
}

/* 激活态 */
.tab-btn.active svg {
  stroke: var(--gold-bright);
  transform: scale(1.08);
}
.tab-btn.active .tab-label {
  color: var(--gold-bright);
  font-weight: 600;
}
.tab-btn.active::before {
  content: '';
  position: absolute;
  top: 0; left: 25%; right: 25%;
  height: 2px;
  background: linear-gradient(90deg, transparent, var(--gold-bright), transparent);
  border-radius: 0 0 2px 2px;
}
```

### HTML

```html
<nav class="mobile-tab-bar" id="mobileTabBar">
  <button class="tab-btn active" data-panel="overview">
    <svg viewBox="0 0 24 24"><rect x="3" y="3" width="7" height="7" rx="1.5"/><rect x="14" y="3" width="7" height="7" rx="1.5"/><rect x="3" y="14" width="7" height="7" rx="1.5"/><rect x="14" y="14" width="7" height="7" rx="1.5"/></svg>
    <span class="tab-label">总览</span>
  </button>
  <button class="tab-btn" data-panel="holdings">
    <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 3v9l6.36 3.64"/></svg>
    <span class="tab-label">持仓</span>
  </button>
  <button class="tab-btn" data-panel="signals">
    <svg viewBox="0 0 24 24"><polyline points="3,17 8,11 13,14 21,6"/><circle cx="21" cy="6" r="2"/></svg>
    <span class="tab-label">信号</span>
  </button>
  <button class="tab-btn" data-panel="news">
    <svg viewBox="0 0 24 24"><rect x="4" y="4" width="16" height="16" rx="2"/><line x1="8" y1="9" x2="16" y2="9"/><line x1="8" y1="13" x2="13" y2="13"/></svg>
    <span class="tab-label">资讯</span>
  </button>
  <button class="tab-btn" data-panel="advice">
    <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><circle cx="12" cy="12" r="5"/><circle cx="12" cy="12" r="1.5" fill="currentColor"/></svg>
    <span class="tab-label">建议</span>
  </button>
</nav>
```

---

## 三、行情卡片压缩（信息密度提升 3x）

### 当前问题
- 每张卡高度约 200px，一屏只看到 1.5 张
- 净值数字 26px 太大，「更新: 2026-06-11」太占空间

### 目标效果（每张卡高度 ≤ 72px，一屏看 5-6 张）

```
┌─────────────────────────────────────┐
│  易方达黄金ETF联接C    2.8518       │
│  002963               -2.17% ↓     │
└─────────────────────────────────────┘
```

### 设计规范

- **卡片高度**：68-72px（含 padding）
- **布局**：左侧基金名+代码（纵向），右侧净值+涨跌（纵向）
- **净值字号**：18px（非26px）
- **涨跌字号**：14px 带颜色
- **间距**：卡片间 8px（非现在的 20px）
- **去掉**：「更新: 2026-06-11」文字（统一在 header 显示更新时间）
- **边框**：涨跌色左侧 3px 色条保留

### CSS

```css
@media (max-width: 768px) {
  .price-card {
    padding: 12px 14px;
    display: flex;
    justify-content: space-between;
    align-items: center;
  }
  .price-card .pc-name { font-size: 13px; margin-bottom: 2px; }
  .price-card .pc-code { font-size: 10px; margin-bottom: 0; }
  .price-card .pc-price { font-size: 18px; text-align: right; }
  .price-card .pc-change { font-size: 13px; text-align: right; margin-top: 2px; }
  .price-card .pc-time { display: none; } /* 移动端隐藏 */
  
  /* 行情网格改为紧凑间距 */
  #pricesGrid.grid-3 {
    grid-template-columns: 1fr;
    gap: 8px;
  }
}
```

---

## 四、iOS PWA 安装引导 Banner

iOS Safari 没有自动安装提示，需要手动引导：

### 设计

在页面底部（Tab 上方）显示一次性引导条：

```
┌─────────────────────────────────────┐
│ 📲 添加到主屏幕，获得 App 级体验     │
│    点击 ⬆️ 分享 → 「添加到主屏幕」    [✕] │
└─────────────────────────────────────┘
```

### 逻辑

```javascript
function showIOSInstallBanner() {
  const isIOS = /iPad|iPhone|iPod/.test(navigator.userAgent);
  const isStandalone = window.navigator.standalone;
  const dismissed = localStorage.getItem('pwa-install-dismissed');
  
  if (isIOS && !isStandalone && !dismissed) {
    const banner = document.createElement('div');
    banner.className = 'ios-install-banner';
    banner.innerHTML = `
      <div class="install-text">
        <strong>添加到主屏幕</strong>
        <span>点击 <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 12v8a2 2 0 002 2h12a2 2 0 002-2v-8M16 6l-4-4-4 4M12 2v13"/></svg> → 「添加到主屏幕」获得 App 体验</span>
      </div>
      <button class="install-close" onclick="this.parentElement.remove();localStorage.setItem('pwa-install-dismissed','1')">✕</button>
    `;
    document.body.appendChild(banner);
  }
}
```

### CSS

```css
.ios-install-banner {
  position: fixed;
  bottom: calc(56px + env(safe-area-inset-bottom, 0px));
  left: 12px; right: 12px;
  background: rgba(44,35,24,.95);
  border: 1px solid rgba(201,162,39,.25);
  border-radius: 12px;
  padding: 12px 14px;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 12px;
  z-index: 199;
  backdrop-filter: blur(8px);
  animation: slideUp .3s ease;
}
@keyframes slideUp { from { transform: translateY(20px); opacity: 0; } }
.install-text { font-size: 12px; color: var(--paper-dim); line-height: 1.6; }
.install-text strong { color: var(--paper); display: block; font-size: 13px; margin-bottom: 2px; }
.install-close {
  background: none; border: none; color: var(--paper-faint);
  font-size: 18px; cursor: pointer; padding: 4px 8px;
}
```

---

## 五、整体移动端布局调优

### 5.1 容器 padding

```css
@media (max-width: 768px) {
  .container { padding: 0 12px; }
  .section { padding: 16px 0; } /* 从 30px 缩到 16px */
  .section-title { font-size: 12px; letter-spacing: 1.5px; margin-bottom: 12px; }
}
```

### 5.2 卡片统一圆角和间距

```css
@media (max-width: 768px) {
  .card, .metric-card, .signal-card, .advice-card {
    border-radius: 12px;
    padding: 14px;
  }
  .grid-2, .grid-3, .grid-4 {
    grid-template-columns: 1fr;
    gap: 10px;
  }
}
```

### 5.3 指标卡片（4格）改为 2x2

```css
@media (max-width: 768px) {
  .grid-4 {
    grid-template-columns: 1fr 1fr;
    gap: 8px;
  }
  .metric-card .value { font-size: 20px; }
  .metric-card .label { font-size: 9px; }
  .metric-card { padding: 12px 14px; }
}
```

### 5.4 仪表盘（量化信号 3 列 → 滑动 carousel 或 1 列）

```css
@media (max-width: 768px) {
  /* 量化信号区：横向滚动 */
  .section[data-panel="signals"] .grid-3 {
    display: flex;
    overflow-x: auto;
    scroll-snap-type: x mandatory;
    gap: 10px;
    padding-bottom: 8px;
    -webkit-overflow-scrolling: touch;
  }
  .section[data-panel="signals"] .grid-3 > .signal-card {
    flex: none;
    width: 85vw;
    scroll-snap-align: start;
  }
}
```

---

## 六、执行顺序

| 步骤 | 内容 | 预估 |
|------|------|------|
| 1 | 替换底部 Tab Bar（SVG 图标 + 新样式） | 15min |
| 2 | 移动端 Header 重构（隐藏旧结构，新增紧凑结构） | 15min |
| 3 | 行情卡片压缩 | 10min |
| 4 | 整体间距/字号/圆角调优 | 10min |
| 5 | iOS 安装引导 Banner | 5min |
| 6 | 量化信号横滑 carousel | 10min |

---

## 七、验收标准

1. **首屏信息密度**：一屏（iPhone 14）能同时看到：Header + 至少 4 张行情卡
2. **底部 Tab**：SVG 图标，激活态金色+顶部指示线，切换有微弹动效
3. **Header**：高度 ≤ 56px，只显示品牌名+总资产+今日收益
4. **iOS 引导**：首次打开显示安装引导条，关闭后不再显示
5. **专业感**：截图发给设计师看，不会觉得是"网页"而是"App"

---

## 八、参考竞品截图描述

**支付宝基金详情页**：
- Header 极简（基金名+代码+关注按钮）
- 净值大字 + 涨跌小字右对齐
- 底部 Tab 用细线图标，不用 emoji

**且慢 App**：
- 暗色主题
- 总资产区域 = 1 行大字 + 1 行小字收益
- 持仓列表每行高度约 64px
- Tab 图标是圆角线性 SVG

**有知有行 App**：
- 极简黑白
- 信息密度高但不拥挤
- 数字用等宽字体对齐
- Tab 5 个，每个图标有独特辨识度

---

## 约束

- 仅改移动端样式（@media max-width: 768px），PC 端保持不变
- 不动后端 Python / JSON 文件
- 保持现有色板（暖黑+金+翡翠绿）
- ECharts 图表在移动端可适当缩小但不隐藏
