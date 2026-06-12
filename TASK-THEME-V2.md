# 玄枢 Alpha — 主题重构：深蓝科技风 + 日/夜/跟随系统三模式

> 执行者：Claude Code（CatPaw）  
> 设计：小老大  
> 日期：2026-06-12  
> 优先级：P0

---

## 一、总体目标

将当前「暖黑×新中式金」主题替换为 **深蓝科技风**（类 Bloomberg/富途），同时支持 **三种模式切换**：

| 模式 | 说明 |
|------|------|
| 日间模式（Light） | 浅色版深蓝科技风：白/浅灰底 + 深蓝文字 + 亮蓝绿强调 |
| 夜间模式（Dark） | 深蓝科技风主色调：深海蓝底 + 白字 + 亮蓝绿强调 |
| 跟随系统（Auto） | 自动读取 `prefers-color-scheme`，跟随 OS 设置 |

用户可在页面内手动切换，选择存入 `localStorage`，下次打开自动应用。

---

## 二、色板定义

### 夜间模式（Dark）— 主色调

```css
:root[data-theme="dark"] {
  --bg-0: #080d19;          /* 最深底色 */
  --bg-1: #0a1628;          /* 主背景 */
  --bg-2: #0f1d35;          /* 卡片背景 */
  --bg-3: #142744;          /* 悬停/激活 */
  --text-primary: #f0f4f8;  /* 主文字：近白 */
  --text-secondary: #a8b8cc; /* 次要文字 */
  --text-muted: #5a7494;    /* 辅助/标签 */
  --accent: #00d4ff;        /* 主强调：亮青蓝 */
  --accent-soft: #0099cc;   /* 柔和强调 */
  --green: #00e09a;         /* 涨 */
  --green-bg: rgba(0,224,154,.1);
  --red: #ff5252;           /* 跌 */
  --red-bg: rgba(255,82,82,.1);
  --border: rgba(0,212,255,.1);  /* 边框 */
  --border-hover: rgba(0,212,255,.25);
  --card-shadow: 0 4px 24px rgba(0,0,0,.4);
  --glow: 0 0 12px rgba(0,212,255,.15);
}
```

### 日间模式（Light）

```css
:root[data-theme="light"] {
  --bg-0: #f4f7fa;          /* 页面底色 */
  --bg-1: #ffffff;          /* 主背景/卡片 */
  --bg-2: #f8fafc;          /* 次级区域 */
  --bg-3: #eef2f7;          /* 悬停 */
  --text-primary: #0a1628;  /* 主文字：深蓝 */
  --text-secondary: #3d5a80; /* 次要文字 */
  --text-muted: #8ba4be;    /* 辅助 */
  --accent: #0077cc;        /* 主强调：深蓝 */
  --accent-soft: #00a3e0;
  --green: #00b87a;         /* 涨 */
  --green-bg: rgba(0,184,122,.08);
  --red: #e53935;           /* 跌 */
  --red-bg: rgba(229,57,53,.08);
  --border: rgba(10,22,40,.08);
  --border-hover: rgba(10,22,40,.15);
  --card-shadow: 0 2px 12px rgba(10,22,40,.06);
  --glow: none;
}
```

---

## 三、CSS 变量映射（改造重点）

所有现有组件统一使用新变量名，**不再使用旧变量**（`--ink-0`、`--gold`、`--paper` 等）。

### 3.1 全局替换映射

| 旧变量 | → 新变量 |
|--------|----------|
| `--ink-0` / `--ink-1` / `--ink-2` | `--bg-0` / `--bg-1` / `--bg-2` |
| `--paper` | `--text-primary` |
| `--paper-dim` | `--text-secondary` |
| `--paper-faint` | `--text-muted` |
| `--gold` / `--gold-bright` | `--accent` / `--accent-soft` |
| `--jade` / `--jade-soft` | `--green` |
| `--red` | `--red` |
| `--line` | `--border` |

### 3.2 组件级改造

**Header：**
- 背景：`var(--bg-1)`
- 品牌名颜色：`var(--accent)`
- 总资产文字：`var(--text-primary)` + `font-weight: 700`
- 收益颜色：涨 `var(--green)` / 跌 `var(--red)`

**卡片：**
- 背景：`var(--bg-2)`
- 边框：`1px solid var(--border)`
- 悬停：`border-color: var(--border-hover); box-shadow: var(--glow)`
- 圆角：`12px`

**底部 Tab Bar：**
- 背景：`var(--bg-1)` + `backdrop-filter: blur(20px)`
- 非激活图标/文字：`var(--text-muted)`
- 激活态：`var(--accent)` + `filter: drop-shadow(0 0 6px var(--accent))`

**行情卡片：**
- 左侧 border 色条：涨 `var(--green)` / 跌 `var(--red)`
- 基金名称：`var(--text-primary)`
- 净值：`var(--text-primary)` + `font-weight: 700`
- 涨跌幅：对应 `var(--green)` 或 `var(--red)`

**持仓卡片（移动端）：**
- 同上卡片规范
- 金额：`var(--text-primary)`
- 日收益：涨 `var(--green)` / 跌 `var(--red)`

**量化信号仪表盘：**
- 仪表盘主色：`var(--accent)`
- 分数文字：`var(--text-primary)`

---

## 四、主题切换 UI

### 4.1 切换按钮位置

**移动端：** Header 右上角，一个小图标按钮，点击弹出 3 选 1 浮层

```html
<!-- 主题切换按钮（Header 内） -->
<button class="theme-toggle" id="themeToggle" aria-label="切换主题">
  <svg class="theme-icon" viewBox="0 0 24 24">
    <!-- 日间：太阳 / 夜间：月亮 / 跟随：自动 -->
  </svg>
</button>

<!-- 浮层 -->
<div class="theme-menu" id="themeMenu">
  <button class="theme-opt" data-theme="light">
    <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="5"/><path d="M12 1v2M12 21v2M4.22 4.22l1.42 1.42M18.36 18.36l1.42 1.42M1 12h2M21 12h2M4.22 19.78l1.42-1.42M18.36 5.64l1.42-1.42"/></svg>
    日间
  </button>
  <button class="theme-opt" data-theme="dark">
    <svg viewBox="0 0 24 24"><path d="M21 12.79A9 9 0 1111.21 3 7 7 0 0021 12.79z"/></svg>
    夜间
  </button>
  <button class="theme-opt active" data-theme="auto">
    <svg viewBox="0 0 24 24"><circle cx="12" cy="12" r="9"/><path d="M12 3v18"/><path d="M12 3a9 9 0 010 18"/></svg>
    跟随系统
  </button>
</div>
```

**PC 端：** 同样位于 Header 右侧，样式略大

### 4.2 JS 逻辑

```javascript
(function initTheme() {
  const STORAGE_KEY = 'xuanshu-theme';
  const root = document.documentElement;
  
  function getSystemTheme() {
    return window.matchMedia('(prefers-color-scheme: dark)').matches ? 'dark' : 'light';
  }
  
  function applyTheme(mode) {
    // mode: 'light' | 'dark' | 'auto'
    const actual = mode === 'auto' ? getSystemTheme() : mode;
    root.setAttribute('data-theme', actual);
    root.setAttribute('data-mode', mode); // 记录用户选择
    
    // 更新 meta theme-color（影响浏览器地址栏颜色）
    const meta = document.querySelector('meta[name="theme-color"]');
    if (meta) meta.content = actual === 'dark' ? '#080d19' : '#ffffff';
  }
  
  function saveTheme(mode) {
    localStorage.setItem(STORAGE_KEY, mode);
  }
  
  // 初始化
  const saved = localStorage.getItem(STORAGE_KEY) || 'auto';
  applyTheme(saved);
  
  // 监听系统变化（auto 模式下实时响应）
  window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', () => {
    if ((localStorage.getItem(STORAGE_KEY) || 'auto') === 'auto') {
      applyTheme('auto');
    }
  });
  
  // 切换菜单交互
  document.addEventListener('DOMContentLoaded', () => {
    const toggle = document.getElementById('themeToggle');
    const menu = document.getElementById('themeMenu');
    
    toggle?.addEventListener('click', (e) => {
      e.stopPropagation();
      menu.classList.toggle('show');
    });
    
    menu?.addEventListener('click', (e) => {
      const opt = e.target.closest('[data-theme]');
      if (!opt) return;
      const mode = opt.dataset.theme;
      applyTheme(mode);
      saveTheme(mode);
      // 更新 active 状态
      menu.querySelectorAll('.theme-opt').forEach(b => b.classList.remove('active'));
      opt.classList.add('active');
      menu.classList.remove('show');
    });
    
    // 点击外部关闭
    document.addEventListener('click', () => menu?.classList.remove('show'));
    
    // 恢复 active 状态
    const current = localStorage.getItem(STORAGE_KEY) || 'auto';
    menu?.querySelector(`[data-theme="${current}"]`)?.classList.add('active');
  });
})();
```

---

## 五、浮层样式

```css
.theme-toggle {
  background: none; border: none; cursor: pointer;
  padding: 6px; border-radius: 8px;
  color: var(--text-secondary);
  transition: color .2s, background .2s;
}
.theme-toggle:hover { color: var(--accent); background: var(--bg-3); }
.theme-toggle svg {
  width: 20px; height: 20px;
  stroke: currentColor; fill: none; stroke-width: 2;
  stroke-linecap: round; stroke-linejoin: round;
}

.theme-menu {
  position: absolute; top: calc(100% + 8px); right: 0;
  background: var(--bg-2);
  border: 1px solid var(--border-hover);
  border-radius: 12px;
  padding: 6px;
  min-width: 140px;
  box-shadow: var(--card-shadow);
  opacity: 0; visibility: hidden;
  transform: translateY(-8px);
  transition: opacity .2s, transform .2s, visibility .2s;
  z-index: 500;
}
.theme-menu.show { opacity: 1; visibility: visible; transform: translateY(0); }

.theme-opt {
  display: flex; align-items: center; gap: 10px;
  width: 100%; padding: 10px 14px;
  background: none; border: none; border-radius: 8px;
  font-size: 13px; color: var(--text-secondary);
  cursor: pointer; transition: background .15s, color .15s;
}
.theme-opt:hover { background: var(--bg-3); color: var(--text-primary); }
.theme-opt.active { color: var(--accent); font-weight: 600; }
.theme-opt svg {
  width: 18px; height: 18px;
  stroke: currentColor; fill: none; stroke-width: 2;
  stroke-linecap: round; stroke-linejoin: round;
}
```

---

## 六、字体与排版调整

```css
:root {
  --mono: 'SF Mono', 'JetBrains Mono', 'Cascadia Code', ui-monospace, monospace;
  --sans: -apple-system, BlinkMacSystemFont, 'PingFang SC', 'Noto Sans SC', sans-serif;
}

body {
  font-family: var(--sans);
  font-size: 14px;
  line-height: 1.5;
  -webkit-font-smoothing: antialiased;
  -moz-osx-font-smoothing: grayscale;
}

/* 数字统一等宽 */
.num { font-family: var(--mono); font-variant-numeric: tabular-nums; }
```

---

## 七、需要保留/不动的

- `data/*.json`、`scripts/*.py`、`run_all.sh` — 不动
- `sw.js` — 只改 CACHE_NAME 版本号
- `manifest.json` — 改 `theme_color` 和 `background_color`
- ECharts 图表 — 配色跟随 CSS 变量（通过 JS 读取 getComputedStyle）
- 底部 Tab 的 SVG 图标 — 保留 SVG 结构，只改颜色变量
- PWA 安装引导 Banner — 保留功能，样式跟随新主题
- 北斗七星 SVG 装饰 — **删除**（不符合新风格）

---

## 八、改造范围

| 文件 | 改动 |
|------|------|
| `index.html` | CSS 变量全部替换 + HTML 加主题切换按钮/浮层 + JS 加主题逻辑 |
| `manifest.json` | `theme_color` → `#080d19`，`background_color` → `#080d19` |
| `sw.js` | `CACHE_NAME` 版本号 +1 |

---

## 九、执行顺序

1. 定义新 CSS 变量（`:root[data-theme="dark"]` + `[data-theme="light"]`）
2. 全局替换旧变量引用（搜索替换 `--ink-*`、`--gold*`、`--paper*`、`--jade*`）
3. 删除北斗七星 SVG 装饰
4. 添加主题切换 HTML + CSS + JS
5. ECharts 配色改为读取 CSS 变量
6. 更新 manifest.json
7. Bump sw.js CACHE_NAME
8. 测试日间/夜间/跟随系统三模式

---

## 十、验收标准

1. ✅ 默认「跟随系统」，手机白天自动浅色、晚上自动深色
2. ✅ 手动切换后 localStorage 记住选择，刷新不丢失
3. ✅ 夜间模式：深蓝底 + 白字 + 亮青蓝强调，文字清晰可读
4. ✅ 日间模式：白/浅灰底 + 深蓝字，户外阳光下可读
5. ✅ 底部 Tab、卡片、Header 在两个模式下均协调美观
6. ✅ ECharts 图表配色跟随主题
7. ✅ PC 端与移动端均可切换
8. ✅ 切换动画平滑（transition 300ms）
