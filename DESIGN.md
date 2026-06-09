# 玄枢Alpha — 产品设计与开发文档

## 一、产品定位

**玄枢Alpha** 是一个 AI 驱动的个人智能投顾平台，面向个人投资者提供资产配置管理、买卖决策分析、基金推荐及市场情绪洞察服务。

### 核心价值主张

> 市面没有一个产品同时做到"中国基金持仓管理 + AI量化信号 + 新闻情绪映射 + 操作建议"

### 为什么要做？

| 维度 | 回答 |
|---|---|
| 个人刚需 | 支付宝持有~5.6万资产，需要系统化管理+决策辅助，而不是凭感觉操作 |
| 能力证明 | 作为"AI超级个体"的核心产品——一个人用AI搭建了完整投顾系统 |
| 对外演示 | 给面试官/觅游/行业交流展示：AI+量化+产品力的完整闭环 |
| 差异化 | 不是又一个行情软件，而是**AI驱动的决策引擎**——有观点、有建议、能解释 |

---

## 二、命名由来

### 「玄枢」

- **玄**：出自《道德经》第一章"玄之又玄，众妙之门"，意为深远洞察、幽微之变
- **枢**：出自《庄子·齐物论》"枢始得其环中，以应无穷"——站在枢纽位置应对无穷变化
- **天文渊源**：天枢星（α Ursae Majoris）是北斗七星第一颗星，"玄"在道教天文中指北极/北斗方位。"玄枢"即北斗之枢纽，掌控方位与时运

### 「Alpha」

- 金融术语，意为"超额收益"——超越市场基准的投资回报
- 华尔街通用语言，一听就知道是投资产品

### 组合立意

> 以东方道家的深邃洞察力，把握市场决策的关键枢纽，获取超越基准的超额收益

---

## 三、Logo 设计

### 设计理念

Logo 融合三层道教招财元素，同时暗合金融视觉语言：

```
┌─────────────────────────────────┐
│     ○ 外圈 = 铜钱（天圆）       │
│   ┌───┐                        │
│   │   │ 中央方孔 = 地方（聚财） │
│   └───┘                        │
│                          ★ 摇光 │
│                     ★ 开阳      │
│                ★ 玉衡           │
│           ★ 天权                │
│      ★ 天玑                     │
│    ★ 天璇                       │
│  ◎ 天枢（呼吸光环）             │
│  ↑ "玄枢"之名                  │
│                                 │
│     七星连线 = 上升趋势线        │
│         玄枢 ALPHA              │
└─────────────────────────────────┘
```

### 三层寓意

1. **北斗七星** — 道教以斗柄转向判断节气、时运，正是量化择时之本。天枢星=玄枢，是七星之首
2. **铜钱纹（天圆地方）** — 道教聚财第一符，外圆内方代表财气通达
3. **上升趋势线** — 七星连线自然形成一条上升K线，暗示Alpha超额收益

### 动态效果

- 天枢星带呼吸光环（3秒周期脉冲动画），代表"枢纽"持续运转
- 金色渐变（#f7d774 → #f0b90b → #d4a017），财气、专业、高级感

### 技术实现

- 格式：SVG（矢量，无限缩放）
- 文件：`/logo.svg`
- 配色：金色渐变 + 星光径向渐变 + 高斯模糊发光滤镜

---

## 四、竞品分析

| 产品 | 类型 | 做了什么 | 没做什么 |
|---|---|---|---|
| **支付宝「智能理财助理」** | 平台内置 | 持仓展示、基金诊断、简单问答 | 无量化模型、建议倾向卖自家产品（利益冲突） |
| **蚂蚁财富「帮你投」** | 持牌投顾 | 全委托组合管理 | 黑箱、不透明、用户无决策权 |
| **雪球蛋卷** | 组合策略 | 指数基金组合、估值表 | 被动策略、无AI、无个性化 |
| **且慢** | 策略投顾 | 长赢计划、专业组合 | 收费、策略固定、无实时新闻联动 |
| **富途/老虎** | 行情终端 | 图表专业、数据全 | 看为主不做决策、港美股为主 |
| **Kimi/豆包理财问答** | AI对话 | 泛理财知识问答 | 无持仓数据、无量化模型、不跟踪 |
| **PortfolioVisualizer** | 回测工具 | 学术级资产配置 | 英文、无中国基金、无AI |
| **Copilot Money/Monarch** | AI记账 | 自动同步银行数据 | 美国市场、不支持A股/支付宝 |

### 我们的差异化优势

| 竞品普遍缺的 | 我们有的 |
|---|---|
| AI驱动的买卖建议 | ✅ gold-quant 量化信号 + 宏观情绪 + 估值分位综合决策 |
| 中国基金/支付宝持仓管理 | ✅ 直接支持支付宝截图 OCR |
| 实时新闻→持仓影响映射 | ✅ 早晚报标注对黄金/A股/美股/零售的影响 |
| 个性化资产配置诊断 | ✅ 基于目标仓位实时对比偏离度 |
| 恐慌情绪驱动的择时 | ✅ VIX + 贸易战舆情 + 技术面超卖识别 |
| 独立第三方视角 | ✅ 没有利益冲突，只看数据说话 |

---

## 五、产品架构

### 系统架构图

```
┌─────────────────────────────────────────┐
│        玄枢Alpha Web 页面（前端）        │
│  ┌──────┐ ┌──────┐ ┌──────┐ ┌────────┐ │
│  │早晚报│ │量化信号│ │持仓管理│ │操作建议│ │
│  └──┬───┘ └──┬───┘ └──┬───┘ └───┬────┘ │
└─────┼────────┼────────┼─────────┼───────┘
      │        │        │         │
      ▼        ▼        ▼         ▼
  cron早晚报  gold-quant  持仓JSON   综合决策引擎
  （已有）    （已有）    （新建）    （新建）
```

### 与现有系统关系

| 现有组件 | 角色 | 保留/改造 |
|---|---|---|
| gold_signal.py | 黄金量化信号引擎 | ✅ 保留，输出JSON供页面读取 |
| us_market_signal.py | 美股量化信号引擎 | ✅ 保留，输出JSON供页面读取 |
| NoCode 量化大屏 | 轻量快速查看入口 | ✅ 保留（内部用） |
| 早晚报 cron | 信息聚合层 | ✅ 保留，新增结构化JSON归档 |
| asset-planner skill | 资产配置诊断 | ✅ 复用逻辑 |

新平台是现有系统的**上层消费者**，不替代任何已有组件。

### 功能模块

| 模块 | 功能 | 数据源 |
|---|---|---|
| 📰 早晚报 | 宏观新闻 + 每条对持仓的影响判断 | cron 早晚报 JSON |
| 📊 量化信号 | 黄金评分 + 美股评分 + VIX + 综合 | gold/us_latest_result.json |
| 💰 持仓管理 | 支付宝实际持仓 → 对比目标仓位 → 偏离度 | portfolio.json |
| 📈 净值曲线 | 每只基金历史净值走势图 | AKShare / 天天基金 |
| 🎯 操作建议 | 综合三层数据，给出买/卖/持有结论 | 决策引擎 |
| 🔍 基金发现 | 恐慌高位时推荐超跌ETF + 入手时机 | 筛选引擎 |

---

## 六、技术方案

### 技术栈

| 层级 | 选型 | 理由 |
|---|---|---|
| 前端框架 | 纯 HTML + Vanilla JS | 零依赖、部署简单、GitHub Pages 友好 |
| UI 框架 | TailwindCSS（CDN） | 快速原型、深色主题支持好 |
| 图表库 | ECharts 5.x | 金融级图表（K线、仪表盘、面积图） |
| 数据格式 | JSON 静态文件 | cron 每日写入，页面 fetch 读取 |
| 部署 | GitHub Pages | 免费、HTTPS、自定义域名 |
| 数据更新 | OpenClaw cron | 每日自动运行脚本更新数据文件 |

### 设计风格

- **深色金融终端风格**（参考 TradingView / 富途牛牛 Web 版）
- 主背景：#0d1117
- 卡片背景：#161b22
- 金色强调：#f0b90b（Logo、标题、关键数据）
- 涨：#00d4aa（绿）
- 跌：#ff6b6b（红）
- 文字：#e6edf3（主）/ #8b949e（次）
- 数字字体：tabular-nums（等宽对齐）

### 目录结构

```
xuanshu-alpha/
├── index.html          # 主页面（单文件应用）
├── logo.svg            # Logo SVG 源文件
├── logo.html           # Logo 预览页
├── DESIGN.md           # 本文档（产品设计+开发文档）
├── README.md           # 项目说明
├── data/
│   ├── portfolio.json  # 持仓数据
│   ├── gold_signal.json    # （待接入）黄金信号
│   ├── us_signal.json      # （待接入）美股信号
│   └── news.json           # （待接入）早晚报数据
└── scripts/
    ├── update_data.sh      # （待建）每日数据更新脚本
    └── fetch_nav.py        # （待建）基金净值抓取
```

---

## 七、持仓数据格式

### 当前持仓（2026-05-26 快照）

| 基金 | 代码 | 金额(元) | 占比 | 持有收益率 | 品类 |
|---|---|---|---|---|---|
| 易方达黄金ETF联接C | 002963 | 20,135.58 | 35.75% | -5.02% | 黄金 |
| 易方达黄金ETF联接A | 159934 | 8,759.41 | 15.55% | -7.79% | 黄金 |
| 南方有色金属ETF联接E | 020882 | 8,417.12 | 14.95% | -6.86% | 有色金属 |
| 华夏中证光伏产业ETF联接A | 013301 | 5,679.89 | 10.09% | +3.27% | 光伏/新能源 |
| 天弘中证人工智能主题指数C | 001631 | 5,189.88 | 9.22% | +42.29% | AI/科技 |
| 永赢高端装备智选混合C | 014658 | 3,970.70 | 7.05% | -0.73% | 高端制造 |
| 天弘中证机器人ETF联接C | 014880 | 2,031.17 | 3.61% | +8.33% | AI/科技 |
| 平安高端装备混合C | 015897 | 1,999.72 | 3.55% | -0.01% | 高端制造 |
| 余额宝 | 000198 | 132.59 | 0.23% | 0 | 货币基金 |

**总资产：56,316.06 元**

### 目标配置

| 品类 | 目标占比 | 实际占比 | 偏离 |
|---|---|---|---|
| 黄金 | 24% | 51.30% | +27.30%（严重超配） |
| AI/科技 | 38% | 12.83% | -25.17%（严重低配） |
| 纳指100 | 24% | 0% | -24%（完全缺失） |
| 标普500 | 10% | 0% | -10%（完全缺失） |
| 有色金属 | 4% | 14.95% | +10.95%（超配） |

### portfolio.json 数据结构

```json
{
  "updateTime": "2026-05-26",
  "totalAsset": 56316.06,
  "holdings": [
    {
      "name": "基金名称",
      "code": "基金代码",
      "amount": 20135.58,
      "ratio": 35.75,
      "dailyReturn": 96.99,
      "holdingReturn": -1064.42,
      "holdingReturnRate": -5.02,
      "totalReturn": 2836.82,
      "category": "黄金"
    }
  ],
  "targetAllocation": {
    "黄金": 24,
    "AI/科技": 38,
    "纳指100": 24,
    "标普500": 10,
    "有色金属": 4
  }
}
```

---

## 八、开发计划

> **状态总览（截至 2026-06-09）：四个阶段全部完成 ✅，四层架构补齐，P0/P1/P2 能力全部上线。**

### 第一阶段：MVP 骨架 ✅ 已完成

- [x] 项目初始化
- [x] 持仓数据 JSON
- [x] 页面骨架（6大模块）
- [x] Logo SVG 设计
- [x] 深色金融终端风格（暖黑×翡翠绿金 新中式 · 方向C）
- [x] ECharts 图表（饼图、柱状图、仪表盘）

### 第二阶段：数据接入 ✅ 已完成

- [x] 接入真实量化信号（gold/us/metals_signal.json → data/signals.json）
- [x] 基金历史净值曲线（AKShare，scripts/fetch_nav.py → data/nav.json）
- [x] 早晚报 JSON 归档 + 页面读取（data/news.json，独立 cron 维护）
- [x] 持仓 OCR 更新能力（scripts/portfolio_ocr.py，截图→自动更新 portfolio.json）

### 第三阶段：智能化 ✅ 已完成

- [x] AI 操作建议引擎（data/rebalance.py，综合信号+持仓偏离）
- [x] 价值罗盘（巴菲特八问）+ 融合决策卡（技术×价值双确认矩阵）
- [x] 价值罗盘接真实持仓穿透（008585/515790 真实十大重仓）
- [x] 趋势资产建议优化（基于回测：趋势型→长期持有，震荡型→技术择时）
- [x] 基金发现/推荐引擎（scripts/fund_scanner.py，恐慌时扫描超跌ETF）
- [x] 新闻情绪→持仓影响联动（scripts/build_news_impact.py）
- [x] 资产再平衡计算器（data/rebalance.py）

### 第四阶段：上线部署 ✅ 已完成

- [x] GitHub 仓库创建（zhenpengbi/xuanshu-alpha）
- [x] GitHub Pages 部署（https://zhenpengbi.github.io/xuanshu-alpha/）
- [x] 每日 cron 自动更新数据并 push（.github/workflows/daily.yml，工作日 16:30）
- [x] 每周回测自动更新（.github/workflows/weekly_backtest.yml，周一 09:00）
- [x] 信号速报大象推送（cron 30224af9，工作日 17:00）
- [ ] 自定义域名（可选，未做）

### P3 待办（锦上添花，不急）

- [ ] 持仓盈亏历史曲线（买入成本 vs 现价）
- [ ] 移动端适配
- [ ] 自定义域名

---

## 九、已搭载 Skill 清单

| Skill | 用途 | 状态 |
|---|---|---|
| asset-planner | 资产配置诊断（四层金字塔模型） | ✅ 已安装 |
| astock-sentiment | A股+港股情绪指数 | ✅ 已安装 |
| stock-market-watch | 实时行情查询 | ✅ 已安装 |
| catclaw-search | 搜索宏观新闻/政策 | ✅ 已安装 |
| xueqiu-stock-discussion | 雪球舆情/散户情绪 | ✅ 已安装 |
| earnings-analyst | 财报解读（关联持仓公司） | ✅ 已安装 |
| 基金净值数据接口 | 历史净值曲线 | ✅ 已实现（scripts/fetch_nav.py，AKShare）|
| 基金筛选推荐引擎 | 恐慌时推荐超跌ETF | ✅ 已实现（scripts/fund_scanner.py）|

---

## 十、本地开发指南

### 环境要求

- Node.js 或 Python（仅用于本地 HTTP Server）
- 浏览器（Chrome/Firefox）
- Git

### 快速启动

```bash
# 克隆仓库
git clone https://github.com/zhenpengbi/xuanshu-alpha.git
cd xuanshu-alpha

# 启动本地预览
python3 -m http.server 8080
# 访问 http://localhost:8080
```

### 数据更新

```bash
# 手动更新持仓数据
# 编辑 data/portfolio.json

# 接入量化信号（从 gold-quant 目录复制）
cp ~/gold-quant/gold_latest_result.json data/gold_signal.json
cp ~/gold-quant/us_latest_result.json data/us_signal.json
```

### MacBook 本地开发

项目可在 MacBook 上继续开发：

```bash
# 1. 克隆到本地
cd ~/Documents
git clone https://github.com/zhenpengbi/xuanshu-alpha.git
cd xuanshu-alpha

# 2. 本地预览
python3 -m http.server 8080
open http://localhost:8080

# 3. 修改后推送
git add -A
git commit -m "your changes"
git push origin main
```

---

## 十一、项目运行架构（四层）

```
第一层 数据自动化
  fetch_prices.py → data/prices.json
  data/indicators.py → data/indicators.json
  data/signals.py → data/signals.json（量化信号）
  scripts/fetch_nav.py → data/nav.json（基金净值曲线）
  （独立 cron）→ data/news.json（早晚报新闻）
        ↓
第二层 策略信号
  data/signals.json（黄金/美股/有色信号）
  scripts/signal_push.py → 大象推送（cron 30224af9，每日简报+突变加急）
        ↓
第三层 回测系统
  backtest/backtest_engine.py → backtest/data/backtest.json（3年真实回测）
        ↓
第四层 智能建议
  value_compass/build_value_compass.py → value_compass/data/value_compass.json（价值评级）
  value_compass/build_fusion.py → value_compass/data/fusion.json（技术×价值融合决策）
  data/rebalance.py → data/rebalance.json（再平衡清单）
        ↓
工具层
  scripts/portfolio_ocr.py（截图→更新持仓）
  scripts/build_news_impact.py → data/news_impact.json（新闻情绪→持仓影响）
  scripts/fund_scanner.py → data/fund_recommendations.json（超跌ETF雷达）
        ↓
前端 index.html（单文件，读所有 *.json 渲染）
```

### 自动化调度

| 调度 | 频率 | 内容 |
|---|---|---|
| .github/workflows/daily.yml | 工作日 16:30（UTC 08:30）| run_all.sh 全链路更新数据并 push |
| .github/workflows/weekly_backtest.yml | 周一 09:00 | 重跑回测更新 backtest.json |
| cron 30224af9（小老大沙箱）| 工作日 17:00 | signal_push.py 信号速报推大象 |
| 新闻 cron（独立）| 每晚 20:30 | 生成 news.json 并 push |

> ⚠️ run_all.sh 末尾的 `python3 -m http.server` 在 GitHub Actions 会卡死，workflow 里只跑数据生成步骤，不跑 http.server。

---

## 十二、脚本 & 数据文件清单

### 核心脚本

| 脚本 | 作用 | 输出 |
|---|---|---|
| fetch_prices.py | 拉行情 | data/prices.json |
| data/indicators.py | 算技术指标 | data/indicators.json |
| data/signals.py | 生成量化信号 | data/signals.json |
| data/rebalance.py | 再平衡计算 | data/rebalance.json |
| scripts/fetch_nav.py | 拉基金净值 | data/nav.json |
| scripts/portfolio_ocr.py | 持仓截图OCR更新 | data/portfolio.json |
| scripts/build_news_impact.py | 新闻情绪→持仓影响 | data/news_impact.json |
| scripts/fund_scanner.py | 超跌ETF扫描 | data/fund_recommendations.json |
| scripts/signal_push.py | 信号速报大象推送 | （推大象，存快照）|
| value_compass/build_value_compass.py | 价值评级（十大重仓穿透）| value_compass/data/value_compass.json |
| value_compass/build_fusion.py | 技术×价值融合决策 | value_compass/data/fusion.json |
| backtest/backtest_engine.py | 3年策略回测 | backtest/data/backtest.json |

### portfolio_ocr.py 用法

```bash
python3 scripts/portfolio_ocr.py 截图.png            # 交互确认后写入
python3 scripts/portfolio_ocr.py 截图.png --dry-run  # 只看识别结果不写入
python3 scripts/portfolio_ocr.py 截图.png --yes      # 直接写入不询问
```

### 持仓代码映射

| 代码 | 名称 | 资产类型 |
|---|---|---|
| 000216 | 易方达黄金ETF联接C | trend（趋势）→长期持有 |
| 008585 | 天弘AI主题指数C | oscillation（震荡）→技术择时 |
| 017766 | 南方有色金属ETF联接E | trend（趋势）→长期持有 |
| 513100 | 纳指100ETF | trend（趋势）→长期持有 |
| 513500 | 标普500ETF | trend（趋势）→长期持有 |
| 515790 | 华夏光伏ETF | oscillation（震荡）→技术择时 |

### ⚠️ 协作禁区（多端开发避免冲突）

- `data/news.json` — 独立新闻 cron 维护，**任何开发不要改**
- `scripts/signal_push.py` — 信号推送脚本，跑在小老大沙箱
- Claude Code（MacBook）负责代码开发+push；小老大（沙箱）负责架构/推送/pull同步核对。两端用同一 PAT，谁推都行，pull 同步。

---

## 十三、设计决策记录

| 日期 | 决策 | 原因 |
|---|---|---|
| 2026-05-26 | 项目命名「玄枢Alpha」 | 东方道家洞察力 + 西方超额收益，对外演示有文化底蕴又有专业辨识度 |
| 2026-05-26 | Logo 采用北斗七星 + 铜钱纹 | 天枢星=玄枢之名来源；七星连线=上升趋势线；铜钱=道教聚财符 |
| 2026-05-26 | 深色金融终端风格 | 参考 TradingView/富途，专业感强，对外演示有质感 |
| 2026-05-26 | 单文件 HTML 架构 | 零依赖、GitHub Pages 直接部署、便于迭代 |
| 2026-05-26 | 保留现有 gold-quant 系统 | 新平台是上层消费者，不替代现有组件 |
| 2026-05-26 | 集成早晚报 | 形成"信息→分析→决策"完整闭环 |
| 2026-06-05 | CatPaw + Claude Code 协作开发模式 | 小老大当架构师/产品，Claude Code（MacBook）写代码+push；沙箱 pull 同步核对 |
| 2026-06-05 | GitHub Actions 自动化用内置 GITHUB_TOKEN | 不用 PAT，permissions: contents:write 即可自动 push |
| 2026-06-09 | 价值罗盘接真实持仓穿透 | 用 akshare 拉 008585/515790 真实十大重仓股，彻底清除 DEMO 数据 |
| 2026-06-09 | 趋势资产不做技术择时 | 回测证明黄金/纳指/标普择时跑输买入持有（少赚11-22pt），改为长期持有/定投 |
| 2026-06-09 | 信号推送频率 = 每日简报+突变加急 | 避免噪音，只在信号变化时🚨加急推送 |
| 2026-06-09 | 基金雷达仅恐慌高位触发 | avg_sell_score>=2 才扫描超跌ETF，避免平时乱推荐 |

---

## 十四、里程碑

### 2026-06-09：一日七个 commit，四层架构补齐

| Commit | 内容 |
|---|---|
| dc1aeb3 | 价值罗盘接真实持仓（008585/515790）|
| a124c1e | 回测系统（3年真实数据 + ECharts 净值曲线）|
| 1a8f953 | 信号速报推送脚本 |
| 7215bda | 持仓 OCR 工具 |
| dc19e16 | 趋势资产建议优化（基于回测）|
| 35e0bfb | 新闻情绪→持仓影响联动 |
| 23f7512 | 基金雷达超跌ETF推荐引擎 |

**回测核心洞察**：信号策略只对震荡型资产有效（AI主题 α+8.8pt、光伏 α+1.6pt）；对趋势型资产（黄金/纳指/标普）择时反而拖累，买入持有完胜。这个洞察已落地到融合卡资产分类逻辑。

---

_文档创建于 2026-05-26，最近更新 2026-06-09。_
