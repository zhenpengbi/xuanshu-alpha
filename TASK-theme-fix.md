# 任务书：主题切换 Bug 修复 + PWA 图标替换

## 背景

commit `86dfc35` 的主题重构有两个 Bug 需要修复，另外 PWA 图标需要替换为品牌 Logo。

---

## Bug 1：切换模式只有夜间模式生效

### 现象
用户点击 Header 右上角主题切换浮层，选择「日间」或「自动」，页面视觉效果始终是夜间（深蓝底）。

### 根因分析

1. **IIFE 防白闪脚本缺失**：`<head>` 中没有在 `<style>` 之前执行的内联脚本来读取 localStorage 并设置 `data-theme` 属性。当前的 SW 注册脚本不是防白闪用途。

2. **CSS 结构问题**：`:root` 直接定义为 dark 变量（第29-30行 `:root, [data-theme="dark"]`），导致 `auto` 模式下 `removeAttribute('data-theme')` 后 `:root` 仍然是 dark 样式。只有 `@media (prefers-color-scheme: light)` 下的 `:root:not([data-theme])` 才会覆盖为 light——如果用户系统是暗色模式，则 auto 永远等于 dark。

3. **`savedTheme()` 默认值**是 `'dark'`（第2916行），首次访问就是 dark，用户可能从未成功切到 light。

### 修复方案

1. 在 `<head>` 中、`<style>` 标签之前，添加 IIFE 防白闪脚本：
```html
<script>
(function(){
  var t = localStorage.getItem('xuanshu-theme') || 'auto';
  if (t === 'dark' || t === 'light') {
    document.documentElement.setAttribute('data-theme', t);
  }
  // auto 模式不设 data-theme，让 CSS @media 接管
})();
</script>
```

2. 确保 `savedTheme()` 默认返回 `'auto'`（而不是 `'dark'`），让首次访问跟随系统：
```js
return localStorage.getItem(STORAGE_KEY) || 'auto';
```

3. 验证 `[data-theme="light"]` 的 CSS 变量是否完整覆盖了所有组件（特别是 `.card`、`.metric-card`、图表容器的背景色、文字色）。当前看 CSS 中 light 模式变量定义在第94-140行，确认无遗漏。

---

## Bug 2：资讯 Tab 移动端交互不适配

### 现象
点击底部「资讯」tab 后，内容区交互有问题。

### 可能原因

1. 资讯 tab 内有3个 `data-panel="news"` 的 section（市场早晚报、新闻情绪、基金雷达），`switchTab` 函数用 `classList.toggle('panel-active', sec.dataset.panel === panel)` 切换时应该能正确显示它们。

2. 排查方向：
   - 资讯模块内的组件（timeline、sentimentGrid、fundRadarSection）是否在移动端有溢出、高度塌陷或层叠遮挡
   - 底部 tab-nav（`position: fixed; bottom: 0; height: 56px`）是否遮挡了内容区底部——需要给 body/main 添加 `padding-bottom: 64px`
   - 基金雷达表格是否超宽需要横向滚动

3. 修复方向：
   - 确保 `<main>` 或最外层容器有 `padding-bottom: calc(56px + env(safe-area-inset-bottom, 0px))` 防止内容被底部 tab 遮挡
   - 资讯 tab 内的 timeline、sentimentGrid 等子组件添加移动端适配样式（max-width: 100%, overflow-x: auto）
   - 如果 fundRadar section 有横向表格，加 `overflow-x: auto` wrapper

---

## 任务 3：PWA 图标替换

### 需求
当前 `icons/icon-192.png` 和 `icons/icon-512.png` 是通用占位符，需要替换为玄枢品牌 Logo。

### 方案
从 `logo.svg` 生成对应尺寸的 PNG：
- `icons/icon-192.png`（192x192）
- `icons/icon-512.png`（512x512）

可以用 Inkscape CLI 或者 `rsvg-convert`（librsvg）：
```bash
rsvg-convert -w 192 -h 192 logo.svg > icons/icon-192.png
rsvg-convert -w 512 -h 512 logo.svg > icons/icon-512.png
```

如果工具不可用，也可以用 Python + cairosvg：
```bash
pip install cairosvg
python3 -c "
import cairosvg
cairosvg.svg2png(url='logo.svg', write_to='icons/icon-192.png', output_width=192, output_height=192)
cairosvg.svg2png(url='logo.svg', write_to='icons/icon-512.png', output_width=512, output_height=512)
"
```

---

## 验收标准

1. ✅ 切换到「日间」模式：页面变为白/浅蓝底 + 深色文字
2. ✅ 切换到「自动」模式：跟随系统偏好（macOS 暗色→dark，亮色→light）
3. ✅ 刷新页面后主题选择保持（localStorage 持久化）
4. ✅ 无白闪（IIFE 在 CSS 前执行）
5. ✅ 移动端点击「资讯」tab，内容正常展示，不被底部 tab 遮挡，无溢出
6. ✅ PWA 安装后图标为玄枢品牌 Logo（金色北斗星盘）
7. ✅ Git commit & push

## 优先级
Bug 1 > Bug 2 > PWA 图标
