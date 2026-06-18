# 任务书：顶部锚点导航 + 早晚报渲染修复 + 持仓盈亏历史曲线

## 启动命令
```
cd /Users/noah/Documents/AI\ work/xuanshu-alpha && claude --dangerously-skip-permissions
```

---

⚠️ 【开发规范】请先阅读并遵守：
- 代码精简原则：不写冗余代码，不过度封装，不重复造轮子
- 复用优先：已有的函数/逻辑必须复用，不新建功能相同的函数
- 单文件约束：玄枢是单文件 HTML 应用（index.html），新增代码必须精简，避免膨胀
- CSS 复用：已有的 CSS 变量和 class 优先复用，不新增功能重复的样式
- 删除旧代码：新功能替代旧实现时，必须删除被替代的代码
- 行数预算意识：每次改动关注 index.html 总行数变化，尽量控制增量

⚠️ 【准入检查】请先阅读 GUARDRAILS.md，确认本任务通过准入检查后再执行。
若任务不符合准入条件，请拒绝执行并说明原因。

---

## 任务一：顶部锚点快捷导航条（PC端）

### 期望效果
- header 下方新增一条**粘性导航条**（sticky），页面滚动时固定在顶部
- 导航条包含当前所有主要模块的锚点链接，点击平滑滚动到对应 section
- 视觉风格：与现有深色金融终端风格一致，半透明背景+毛玻璃，高度紧凑（一行，约36-40px）
- 当前可见的 section 对应的导航项应有高亮态（滚动时自动切换）
- 768px 以下隐藏（移动端屏幕宝贵，不显示）

### 锚点列表（按页面从上到下顺序）
| 导航文字 | 目标 section |
|---|---|
| 决策 | data-panel="decision" 第一个 section |
| 行情 | data-panel="overview" 实时行情 |
| 持仓 | data-panel="overview" 持仓明细 |
| 信号 | data-panel="signals" 量化信号 |
| 回测 | data-panel="strategy" 策略回测 |
| 早晚报 | data-panel="news" 市场早晚报 |
| 融合 | data-panel="signals" 融合决策卡 |
| 雷达 | data-panel="news" 基金雷达 |
| 操作 | data-panel="advice" AI操作建议 |

### 实现要求
- 每个目标 section 需要有唯一 id（如果当前没有，请添加）
- 使用 IntersectionObserver 检测当前可见 section，自动高亮对应导航项
- 点击导航项 scrollIntoView({ behavior: 'smooth' })
- sticky 定位：top 值要避开现有 header（header 约 64px 高）

---

## 任务二：早晚报渲染时序修复（已有 commit 但需确认）

### 问题
`renderTimeline()` 依赖 `window.newsData`，但该变量在 `loadSignals()` 中才被赋值。之前 `renderTimeline()` 在 `loadSignals()` 之前被调用，导致永远显示"暂无资讯"。

### 已做的修复（commit dd22235）
- 删除了 DOMContentLoaded 中提前调用的 `renderTimeline()`
- 在 `loadSignals()` 之后新增了 `renderTimeline()` 调用

### 你需要做的
- `git pull` 后确认该修复已生效
- 本地打开页面验证早晚报区域是否正常渲染 data/news.json 的内容
- 如果仍有问题，排查并修复

---

## 任务三：持仓盈亏历史曲线

### 期望效果
- 在"持仓明细"区域下方（或持仓跟踪区块内），展示一条组合净值曲线
- X轴：日期（最近60个交易日）
- Y轴：组合总市值（或归一化为基准100的净值曲线）
- 数据来源：`data/nav.json` 中各基金的 navs 数组 × portfolio.json 中各基金持仓份额

### 数据生成
- 新建 `data/portfolio_history.py`
- 读取 nav.json（各基金60日净值）+ portfolio.json（各基金持仓金额 amount）
- 计算每日组合总市值 = Σ(基金i的当日净值 / 基金i的最新净值 × 基金i的amount)
- 输出 `data/portfolio_history.json`：
```json
{
  "dates": ["2026-04-01", ...],
  "values": [55000, 55120, ...],
  "base_value": 55522,
  "returns_pct": [0, 0.22, ...]
}
```

### 前端展示
- 使用 ECharts 折线图（复用现有 ECharts 实例化模式）
- 样式与回测模块的净值曲线保持一致
- 显示：起始值、当前值、区间收益率

### daily.yml
- 在 fetch_nav.py 之后、position_tracker.py 之前加入：`python3 data/portfolio_history.py`

---

## 验收标准
1. PC端 header 下方出现粘性导航条，点击可平滑跳转到对应模块
2. 滚动时当前可见模块的导航项自动高亮
3. 768px 以下导航条隐藏
4. 早晚报区域正常展示 news.json 数据（不再显示"暂无资讯"）
5. 持仓明细下方出现60日组合净值曲线
6. `git push` 后 GitHub Actions 能成功运行（portfolio_history.py 无报错）
