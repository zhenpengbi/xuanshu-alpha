# 玄枢Alpha Bug修复任务书 v3

> **项目**: https://github.com/zhenpengbi/xuanshu-alpha
> **文件**: `index.html`（单文件应用，约3100行）
> **部署**: GitHub Pages → https://zhenpengbi.github.io/xuanshu-alpha/
> **适配范围**: iPhone SE(375px) / iPhone 14(390px) / iPhone 14 Pro Max(430px) / Android(360~412px) / iPad(768~1024px) / Desktop(1200px+)

---

## ⚠️ 代码质量要求（核心约束）

1. **可复用优先**：每个修复都要考虑是否可以被其他模块复用，不搞一次性 hack
2. **语义化 CSS**：用有意义的 class 名（如 `.mobile-compact-header`），禁止内联 style 堆砌
3. **响应式用标准断点**：统一用 `@media (max-width: 768px)` 作为移动端断点（已有），不新增碎片断点
4. **渐进增强**：移动端简化展示，PC 端保持原有丰富度，不做功能删减
5. **变量复用**：颜色、间距等必须引用已定义的 CSS 变量（如 `var(--bg-card)`, `var(--accent)` 等）
6. **不改数据结构**：前端修复不动 `data/*.json` 的 schema

---

## Bug 1：移动端 Header 一行放不下

### 现状
移动端 header 强制一行 56px，包含「玄枢」品牌名 + 总资产 + 今日收益 + 日期 + 主题按钮，内容溢出。

### 修复方案
移动端 header 去掉品牌名「玄枢」，只保留功能性内容。

**具体改动**（CSS `@media (max-width: 768px)` 区域，约 line 978~1010）：

```css
/* 移动端完全隐藏品牌区域（logo+文字+副标题） */
.logo-area { display: none !important; }

/* header-inner 保持一行，只展示 stats + 主题按钮 */
.header-inner {
    justify-content: space-between;
    padding: 0 12px !important;
    height: 48px;  /* 比之前56px更紧凑 */
}

/* header-stats 自适应分配空间 */
.header-stats {
    flex: 1;
    gap: 12px !important;
    justify-content: flex-start !important;
}
```

**删除**现有的：
```css
.logo-area::before { content: '玄枢'; }
```
以及相关的渐变文字样式（因为整个 `.logo-area` 已经 `display: none`，伪元素也不需要了）。

### 验收标准
- 移动端 header 一行展示：总资产 | 今日收益 | 日期 | 🌙按钮，不溢出
- PC 端 header 保持原样（品牌名 + stats 全部展示）

---

## Bug 2：量化信号 Gauge 图表移动端不协调

### 现状
移动端信号卡片用 `85vw` 宽的 carousel 横滑，Gauge 图表高度固定 200px，加上卡片 padding，一屏只能看一个 gauge 且大量留白。PC 端三列 grid 没问题。

### 修复方案
移动端将 Gauge 图表高度压缩 + 信号描述紧凑排列，卡片宽度缩窄，让用户一屏能看到 1.2 个卡片（暗示可滑动）。

**CSS 修改**（`@media (max-width: 768px)` 区域，约 line 1060~1080）：

```css
/* 信号 carousel 卡片 */
.signals-carousel-wrap .signal-card {
    flex: 0 0 75vw !important;   /* 从85vw缩到75vw，露出下一张边缘 */
    min-width: 75vw !important;
    padding: 14px 16px !important;
}

/* Gauge 图表移动端压缩高度 */
.signals-carousel-wrap .signal-card [id$="Gauge"] {
    height: 160px !important;    /* 从200px压到160px */
}

/* VIX 卡片内数字区域上间距缩小 */
.signals-carousel-wrap .signal-card .vix-indicator {
    margin-top: 20px;
}
```

**HTML 不动**，仅靠 CSS 控制高度。`gaugeOption` 函数里 ECharts 会自动适配容器尺寸。

### 验收标准
- 移动端 carousel 一屏可见约 1.2 张卡片（暗示横滑）
- Gauge 图表完整显示，指针/刻度不截断
- PC 端三列 grid 展示不变

---

## Bug 3：日间模式持仓卡片底色不协调

### 现状
日间模式下，持仓卡片使用暗色渐变背景（`rgba(40,32,23,.7)` → `rgba(26,21,16,.55)`），在白色页面上非常突兀。

### 修复方案
为日间模式专门定义持仓卡片样式，保持卡片的信息层次但融入浅色主题。

**新增 CSS**（在 `[data-theme="light"]` 区域追加，约 line 1147 附近）：

```css
/* 日间模式：持仓卡片 */
[data-theme="light"] .holding-card {
    background: rgba(255,255,255,.92) !important;
    border: 1px solid rgba(0,80,180,.08);
    border-left: 3px solid rgba(0,102,204,.2);
    box-shadow: 0 2px 8px rgba(0,50,120,.05);
}
[data-theme="light"] .holding-card.positive {
    border-left-color: var(--green);
}
[data-theme="light"] .holding-card.negative {
    border-left-color: var(--red);
}
[data-theme="light"] .hc-name {
    color: var(--text-primary);
}
[data-theme="light"] .hc-meta {
    color: var(--text-muted);
}
[data-theme="light"] .hc-amount {
    color: var(--text-primary);
}
[data-theme="light"] .hc-tag {
    background: rgba(0,102,204,.06);
    color: var(--accent);
    border-color: rgba(0,102,204,.12);
}
[data-theme="light"] .hc-ratio {
    color: var(--text-muted);
}
```

同步在 `@media (prefers-color-scheme: light) { :root:not([data-theme])` 区域添加相同规则（用 `:root:not([data-theme])` 选择器替代 `[data-theme="light"]`）。

### 验收标准
- 日间模式：持仓卡片白底 + 微阴影 + 蓝色调边框，文字清晰可读
- 夜间模式：保持原有暗金风格不变
- 正/负收益左边框颜色正确（绿/红）

---

## Bug 4：新闻情绪卡片内容过长被截断

### 现状
新闻条目用 `white-space: nowrap; overflow: hidden; text-overflow: ellipsis;` 强制单行，手机端标题只能看到一半。

### 修复方案
移动端新闻条目改为可换行 + 最多2行截断（用 `-webkit-line-clamp`）；PC 端保持单行省略（信息密度优先）。

**CSS 修改**：

在移动端 `@media (max-width: 768px)` 里新增：

```css
/* 新闻情绪卡片 - 新闻条目移动端允许两行 */
.sc-news-item span[style*="overflow"] {
    white-space: normal !important;
    display: -webkit-box !important;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden !important;
    text-overflow: ellipsis !important;
    line-height: 1.4;
}
```

⚠️ **注意**：上面用了属性选择器匹配内联 style，这是因为原始 HTML 是 JS 动态生成的（`renderSentiment` 函数）。**更好的做法**是同时修改 JS 中的模板，给那个 span 加一个语义化 class：

**JS 修改**（`renderSentiment` 函数，约 line 2468）：

把：
```js
<span style="flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;" title="${escHtml(n.title)}">${escHtml(n.title)}</span>
```

改为：
```js
<span class="sc-news-title" title="${escHtml(n.title)}">${escHtml(n.title)}</span>
```

**新增 CSS class**（在通用样式区域）：
```css
.sc-news-title {
    flex: 1;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
    min-width: 0;
}
```

**移动端覆盖**（`@media (max-width: 768px)`）：
```css
.sc-news-title {
    white-space: normal;
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    line-height: 1.4;
}
```

### 验收标准
- PC 端：新闻标题单行省略，悬浮 title 可看全文
- 移动端：新闻标题最多两行，超出省略
- 不破坏卡片整体高度一致性（每张卡片内最多3条新闻 × 2行 = 可控）

---

## Bug 5：GitHub Actions `daily.yml` 数据更新停止（6/13起）

### 现状
GitHub Actions 的 scheduled workflow 从 6/13 起未被调度执行。无失败记录，直接没触发。可能是 GitHub 静默禁用了 schedule（常见于不活跃仓库或 free 账户）。

### 修复方案
双保险策略：
1. 在 `daily.yml` 中增加 `workflow_dispatch` 手动触发（**已有**，确认保留）
2. 新增 `repository_dispatch` 事件触发，便于外部 cron 调用 GitHub API 兜底
3. 新增 `portfolio.json` 每日净值更新步骤（当前工作流缺失）

**修改 `.github/workflows/daily.yml`**：

```yaml
name: 玄枢Alpha 每日数据更新

on:
  schedule:
    - cron: '30 8 * * 1-5'    # UTC 08:30 = 北京 16:30
  workflow_dispatch:
  repository_dispatch:
    types: [daily-update]

permissions:
  contents: write

jobs:
  update-data:
    runs-on: ubuntu-latest
    steps:
      - name: 检出仓库
        uses: actions/checkout@v4
      - name: 安装 Python 3.11
        uses: actions/setup-python@v5
        with:
          python-version: '3.11'
      - name: 安装依赖
        run: |
          python -m pip install --upgrade pip
          pip install akshare==1.18.64 pandas numpy requests ta tabulate yfinance multitasking
      - name: 拉取行情
        run: python3 fetch_prices.py
      - name: 更新持仓净值
        run: python3 scripts/update_nav.py
      - name: 计算技术指标
        run: python3 data/indicators.py
      - name: 生成买卖信号
        run: python3 data/signals.py
      - name: 新闻情绪分析
        run: python3 scripts/build_news_impact.py
      - name: 基金雷达扫描
        run: python3 scripts/fund_scanner.py
      - name: 计算再平衡建议
        run: python3 data/rebalance.py
      - name: 提交并推送更新
        run: |
          git config user.name "github-actions[bot]"
          git config user.email "github-actions[bot]@users.noreply.github.com"
          git add data/*.json
          if git diff --staged --quiet; then
            echo "数据无变化，跳过提交"
          else
            git commit -m "chore: 每日数据自动更新 $(date +%Y-%m-%d)"
            git push
          fi
```

**新建 `scripts/update_nav.py`**：

```python
#!/usr/bin/env python3
"""
每日净值更新脚本
从 akshare 拉取最新净值，更新 data/portfolio.json 中的每日收益
可复用：任何基于 akshare 的基金净值查询场景均可调用 get_fund_nav()
"""
import json
import akshare as ak
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
PORTFOLIO_PATH = DATA_DIR / 'portfolio.json'


def get_fund_nav(code: str, days: int = 5) -> dict:
    """
    获取基金最近N天净值数据
    Args:
        code: 基金代码（6位）
        days: 获取最近几天的数据
    Returns:
        {'nav': float, 'date': str, 'nav_chg': float} 或 None
    """
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            return None
        df = df.tail(days)
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
        return {
            'nav': float(latest['单位净值']),
            'date': str(latest['净值日期']),
            'nav_chg': float(latest['单位净值']) - float(prev['单位净值']),
            'nav_chg_pct': round((float(latest['单位净值']) - float(prev['单位净值'])) / float(prev['单位净值']) * 100, 4)
        }
    except Exception as e:
        print(f"[WARN] 基金 {code} 净值获取失败: {e}")
        return None


def update_portfolio():
    """读取 portfolio.json，逐只基金更新最新净值和日收益"""
    portfolio = json.loads(PORTFOLIO_PATH.read_text(encoding='utf-8'))
    holdings = portfolio.get('holdings', [])

    today_str = datetime.now().strftime('%Y-%m-%d')
    total_daily_return = 0.0

    for h in holdings:
        code = h.get('code', '')
        if not code or h.get('category') == '货币':
            # 货币基金日收益极小，跳过
            continue

        nav_info = get_fund_nav(code)
        if not nav_info:
            continue

        # 用份额（amount / 上次净值）× 新净值差 计算日收益
        # 简化：用 nav_chg_pct 乘以持仓金额估算
        daily_return = round(h.get('amount', 0) * nav_info['nav_chg_pct'] / 100, 2)
        h['dailyReturn'] = daily_return
        total_daily_return += daily_return
        print(f"  {h['name']}({code}): 净值{nav_info['nav']}({nav_info['date']}), 日收益≈{daily_return}")

    portfolio['updateTime'] = today_str
    portfolio['dailyReturn'] = round(total_daily_return, 2)

    PORTFOLIO_PATH.write_text(json.dumps(portfolio, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n✅ portfolio.json 已更新，日期={today_str}，总日收益={total_daily_return:.2f}")


if __name__ == '__main__':
    update_portfolio()
```

### 验收标准
- `python3 scripts/update_nav.py` 可独立运行，更新 `data/portfolio.json` 的 `updateTime` 和每只基金的 `dailyReturn`
- GitHub Actions `daily.yml` 包含该步骤
- `repository_dispatch` 事件可通过 API 触发（备用兜底）
- `get_fund_nav()` 函数可被其他脚本复用

---

## Bug 6：市场早晚报只能看当天数据

### 现状
`data/news.json` 只保存最近一期早/晚报数据，前端无历史切换能力。

### 修复方案（分两步）

#### Step 1：数据层 — `news.json` 改为滚动7天窗口

**修改 `scripts/build_news_impact.py`**（或对应的新闻生成脚本）：

不改变当前 schema 的根结构，而是把 `items` 升级为按日期分组：

```json
{
  "updated": "2026-06-15",
  "history": [
    {
      "date": "2026-06-15",
      "period": "早报",
      "items": [...]
    },
    {
      "date": "2026-06-14",
      "period": "晚报",
      "items": [...]
    }
  ]
}
```

保留最近 7 天数据，FIFO 淘汰。

#### Step 2：前端 — 日期切换 Tab

**在 `renderTimeline` 函数区域修改**，加入日期选择器：

```js
// 日期切换组件（可复用的 DateTabBar 模式）
function renderDateTabs(container, dates, onSelect) {
    const tabBar = document.createElement('div');
    tabBar.className = 'date-tab-bar';
    dates.forEach((d, i) => {
        const tab = document.createElement('button');
        tab.className = 'date-tab' + (i === 0 ? ' active' : '');
        tab.textContent = d.label;
        tab.dataset.date = d.value;
        tab.onclick = () => {
            tabBar.querySelectorAll('.date-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');
            onSelect(d.value);
        };
        tabBar.appendChild(tab);
    });
    container.prepend(tabBar);
}
```

**新增 CSS**：
```css
.date-tab-bar {
    display: flex; gap: 6px; margin-bottom: 12px;
    overflow-x: auto; scrollbar-width: none;
    padding: 2px 0;
}
.date-tab-bar::-webkit-scrollbar { display: none; }
.date-tab {
    flex: none; padding: 6px 14px;
    font-size: 12px; font-weight: 500;
    border-radius: 20px; border: 1px solid var(--border-color);
    background: var(--bg-card); color: var(--text-secondary);
    cursor: pointer; transition: all .2s;
    white-space: nowrap;
}
.date-tab.active {
    background: var(--accent); color: #fff;
    border-color: var(--accent);
}
```

### 验收标准
- 早晚报区域顶部有日期胶囊 Tab（最近7天），点击切换内容
- 默认展示最新一期
- `renderDateTabs` 是通用组件，后续其他模块（如回测历史）可直接复用
- PC/移动端均正常显示

---

## 执行顺序建议

1. **Bug 1**（header）→ 最简单，纯 CSS 删减
2. **Bug 3**（持仓卡片颜色）→ 纯 CSS 追加
3. **Bug 4**（新闻截断）→ JS 小改 + CSS
4. **Bug 2**（Gauge 高度）→ CSS 调整
5. **Bug 6**（早晚报历史）→ JS 较多但独立模块
6. **Bug 5**（Actions + update_nav.py）→ 新文件 + yml 修改

---

## 通用约束提醒

- **所有 CSS 修改必须**同时处理 `[data-theme="light"]` 和 `@media (prefers-color-scheme: light) { :root:not([data-theme])` 两个日间模式入口
- **禁止**新增内联 `style` 属性到 HTML 标签（现有的渐进清理）
- **禁止**硬编码魔法数字，用 CSS 变量或有意义的命名
- **JS 模板字符串**中的样式应抽成 class
- **commit 信息格式**：`fix: 修复XXX问题` 或 `feat: 新增XXX功能`
