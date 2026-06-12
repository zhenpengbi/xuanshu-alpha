# 玄枢Alpha · PWA 移动端改造任务书

## 一、改造目标

把 xuanshu-alpha 从"只能桌面浏览"升级为**可添加到主屏的 PWA 应用**，
同时解决移动端可用性问题（超长单页滚动、硬编码 inline 数据停滞不更新）。

---

## 二、P0（本次必须完成）

### 2.1 数据 Fetch 改造

| 问题 | 状态 |
|------|------|
| `portfolioData` 硬编码 inline（旧代码、旧日期） | ✅ 已修复：`loadPortfolio()` 动态 fetch |
| `mockTimeline` 硬编码假新闻 | ✅ 已修复：替换为空数组 fallback |

### 2.2 PWA 三件套

```
manifest.json   ── 应用元数据、图标、主题色、display=standalone
sw.js           ── Service Worker：data/*.json 网络优先，shell 缓存优先
icons/
  icon-192.png  ── 192×192 应用图标
  icon-512.png  ── 512×512 应用图标
```

**index.html `<head>` 新增**：
```html
<link rel="manifest" href="manifest.json">
<meta name="apple-mobile-web-app-capable" content="yes">
<meta name="apple-mobile-web-app-status-bar-style" content="black-translucent">
<meta name="apple-mobile-web-app-title" content="玄枢">
<meta name="theme-color" content="#c9a227">
<link rel="apple-touch-icon" href="icons/icon-192.png">
```

**SW 注册**（DOMContentLoaded 前）：
```javascript
if ('serviceWorker' in navigator) {
  navigator.serviceWorker.register('/xuanshu-alpha/sw.js')
    .then(r => console.log('[SW] registered', r.scope))
    .catch(e => console.warn('[SW] failed', e));
}
```

### 2.3 移动端底部 5-Tab 导航栏

仅在 `max-width: 768px` 下显示。桌面端忽略。

| Tab | 图标 | 分组 sections |
|-----|------|--------------|
| 总览 | 📊 | 实时行情、资产总览、持仓明细 |
| 信号 | 📡 | 量化信号、技术指标信号、融合决策 |
| 策略 | ⚡ | 策略回测、主动基诊断 |
| 资讯 | 📰 | 早晚报、新闻情绪、基金雷达 |
| 建议 | 🧭 | AI 操作建议 |

**实现方案（最小侵入）**：
- 每个 `<section>` 加 `data-panel="xxx"` 属性
- CSS `@media (max-width:768px) { .section[data-panel]:not(.panel-active) { display:none; } }`
- 底部 nav 按钮点击 → 切换哪些 section 有 `.panel-active`
- 桌面：`data-panel` 不影响，所有 section 正常显示

---

## 三、P1

### 3.1 移动端 Header 精简
- 隐藏 LIVE badge
- 总资产 + 今日收益 两行 inline
- 更新时间缩短为 "06-11 17:30" 格式

### 3.2 持仓明细移动端卡片视图
- `@media (<768px)` 隐藏 `.holdings-table`，显示 `.holdings-cards`
- 每张卡片：名称 + 金额 + 涨跌 + 持有收益率

### 3.3 骨架屏加载状态
- 数据 fetch 前显示灰色脉冲占位块
- fetch 成功后替换为真实内容

---

## 四、验收标准

1. Chrome DevTools → Application → Manifest 正确显示应用信息
2. Service Worker 已注册、状态 active
3. 手机访问 GitHub Pages，"添加到主屏"后以 standalone 模式打开
4. 总资产显示最新 portfolio.json 数据（动态）
5. 底部 Tab 可切换，切换后仅显示对应分组 section
6. 网络断开后，页面仍可从缓存加载

---

## 五、文件清单

| 文件 | 用途 |
|------|------|
| `manifest.json` | PWA 清单 |
| `sw.js` | Service Worker |
| `icons/icon-192.png` | 应用图标 192px |
| `icons/icon-512.png` | 应用图标 512px |
| `index.html` | 主改造对象（head/sections/nav/JS） |
