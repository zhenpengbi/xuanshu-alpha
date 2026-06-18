# 任务书：P0.5 决策引擎升级 — 让玄枢真正能出操作指令

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

## 背景

P0（估值分位 + 组合风险 + 信号重构）已于 2026-06-17 全部完成。但跑出来的信号仍然不能直接指导操作：
- 8只基金没有一只给出"买入"信号
- 纳指100/标普500 估值数据缺失（verdict="数据缺失"，score默认50）
- 震荡型 buy_score≥3 门槛太高，历史上几乎不触发
- 黄金两只基金给出矛盾建议（一个"持有"一个"定投补仓"）
- 再平衡只到品类层面，没有细化到具体基金代码和金额

**目标：改完后，信号引擎能给出可直接执行的操作指令（具体到"赎回X基金¥N → 买入Y基金¥M"），组合年化收益率目标10%+。**

---

## 任务清单（共4项改动，全部在 data/ 目录下的 Python 脚本）

### 任务1：修复纳指/标普估值数据缺失（改 `data/valuation.py`）

**问题**：yfinance 在 GitHub Actions 境外服务器拉 QQQ/SPY 的 trailingPE 经常失败（返回 None），导致 valuation.json 里纳指100和标普500 verdict="数据缺失"，score=50。

**方案**：增加 AKShare 兜底路径。AKShare 的 `stock_us_fundamental_spot` 接口可拉美股基本面数据（含PE）。如果 AKShare 也失败，再用硬编码的合理区间估算：

```python
# 美股 PE 兜底估算（2026年6月参考值，每季度人工校准一次）
US_PE_FALLBACK = {
    "QQQ": {"pe": 35.0, "note": "人工校准值(2026Q2)，建议每季度更新"},
    "SPY": {"pe": 24.0, "note": "人工校准值(2026Q2)，建议每季度更新"},
}
```

**改动范围**：仅改 `data/valuation.py` 的 `_fetch_yfinance_pe()` 函数，增加 AKShare → 硬编码兜底两级降级。

**验收标准**：
- `python3 data/valuation.py` 运行后，valuation.json 里纳指100和标普500 的 verdict 不再是"数据缺失"
- 有真实PE数据时用真实数据，没有时用兜底值并在 pe_note 标注来源

---

### 任务2：信号阈值校准 + 同品类合并（改 `data/signals.py`）

**问题A — 阈值太高**：
当前震荡型买入条件是 `buy_score >= 3`，但技术评分满分只有 5（RSI 2 + MA 2 + MACD 1），需要三个指标里两个给出强信号。实际上 RSI<30 超卖极少出现，导致买入信号几乎永远不触发。

**改动**：
```python
# 旧：buy_score >= 3 → 买入
# 新：buy_score >= 2 且 val_score <= 50 → "可加仓"
#     buy_score >= 2 且 val_score <= 30 → "买入"  
#     buy_score >= 3 → 保留原逻辑不变（强信号）
```

具体修改 `_oscillation_signal()` 函数，在现有 `buy_score >= 3` 判断之前，增加 `buy_score >= 2` 的中等强度信号分支：
```python
# 在现有 buy_score>=3 分支之前，插入：
if buy_score >= 2 and val_score <= 30:
    signal = "低估可加"
    signal_type = "oscillation_val_buy"
    reason = f"{base_reason}；估值{val_verdict}(score={val_score})支持买入"
    action = f"{name} 技术偏多(buy={buy_score})+估值低估(score={val_score})，建议分批加仓"
elif buy_score >= 2 and val_score <= 50:
    signal = "可小幅加"
    signal_type = "oscillation_light_add"
    reason = f"{base_reason}；估值{val_verdict}适中，可试探"
    action = f"{name} 技术偏多(buy={buy_score})+估值适中(score={val_score})，可小幅试探加仓"
```

同理卖出方向，在 `sell_score >= 3` 之前增加 `sell_score >= 2 and val_score >= 70` 的中等减仓信号。

**问题B — 同品类矛盾**：
黄金有两只基金（002963 超配10.4pt → "持有"；000307 低配9.1pt → "定投补仓"），因为信号引擎按单只基金判断，不看品类总仓位。

**改动**：在 `_trend_signal()` 函数开头增加品类层面仓位判断。新增一个辅助函数 `_category_deviation()`：

```python
def _category_deviation(code: str, portfolio_map: dict) -> float:
    """计算该基金所属品类的整体偏离度（正=超配，负=低配）"""
    pf_info = portfolio_map.get(code, {})
    category = pf_info.get("category", "")
    target = pf_info.get("target_ratio", 0)
    # 同品类所有基金的 ratio 求和
    total_ratio = sum(
        v.get("ratio", 0) for v in portfolio_map.values()
        if v.get("category") == category
    )
    return round(total_ratio - target, 1)
```

在 `_trend_signal()` 里用品类总偏离替代单基金偏离来决定信号方向：
- 品类整体超配 → 所有该品类基金统一信号"持有"（不矛盾）
- 品类整体低配 → 只对**最大持仓**基金建议"持有"，对其他基金建议"定投补仓"
- 这样黄金两只基金要么都是"持有"（品类超配时），要么合理分配补仓建议

**验收标准**：
- 同品类基金不再出现矛盾信号
- 震荡型基金在 buy_score=2 + 低估时能触发"低估可加"信号
- `python3 data/signals.py` 运行后，信号分布不再全部是"持有/观望/高估警惕"

---

### 任务3：再平衡操作具体化（改 `data/rebalance.py`）

**问题**：当前 rebalance.json 只输出品类层面的建议（如"AI/科技可小幅加仓¥3917"），但不告诉用户具体买哪只基金、赎回哪只基金。

**改动**：在 `main()` 函数的 output 中，新增一个 `operations` 数组，将品类级建议拆解为基金级操作指令：

```python
# 新增 operations 数组结构
"operations": [
    {
        "type": "sell",           # sell / buy / transfer
        "fund_code": "002963",
        "fund_name": "易方达黄金ETF联接C",
        "category": "黄金",
        "amount": 4424.27,
        "reason": "黄金超配28pt，减仓最大持仓归位",
        "priority": 1             # 1=最优先
    },
    {
        "type": "buy",
        "fund_code": "011840",    # 或新建仓的具体ETF代码
        "fund_name": "天弘中证人工智能C",
        "category": "AI/科技",
        "amount": 2000.00,
        "reason": "AI/科技低配14.9pt，补仓",
        "priority": 2
    },
]
```

**拆解规则**（新增函数 `build_operations()`）：
1. **卖出拆解**：品类需减仓时，从该品类持仓金额最大的基金开始赎回
2. **买入拆解**：品类需加仓时
   - 已持有该品类基金 → 加仓最大持仓基金（集中度换效率）
   - 待建仓品类（纳指100/标普500）→ 推荐具体基金代码：
     - 纳指100 → 513100（华夏纳斯达克100ETF）或 159501（广发纳斯达克100ETF）
     - 标普500 → 513500（博时标普500ETF）
   - 推荐理由附在 reason 里（跟踪误差小、费率低、规模大）
3. **资金对冲**：卖出总额 ≈ 买入总额（资金平衡）
4. **优先级**：按 `abs(deviation_pt)` 排序，偏离最大的最优先

**重要**：operations 是在现有 actions 数组之外新增的字段，不改动 actions 的任何逻辑。

**验收标准**：
- rebalance.json 里出现 `operations` 数组
- 每条 operation 有明确的基金代码、金额、方向（buy/sell）
- 卖出总额和买入总额基本平衡（允许±500元误差，多出来的进余额宝）
- 待建仓品类有具体推荐基金代码

---

### 任务4：更新 GUARDRAILS.md

把 P0 清单标记为已完成，替换为 P0.5 清单：

```markdown
## 当前 P0.5 清单（P0 已完成 ✅）

- [ ] 纳指/标普估值数据补齐（解决"数据缺失"导致信号失效）
- [ ] 信号阈值校准 + 同品类合并（解决"全部观望"和矛盾建议）
- [ ] 再平衡操作具体化（从品类级到基金级可执行指令）
```

---

## 不要改的文件

- `index.html` — 本次不涉及前端
- `data/news.json` — 独立 cron 维护
- `scripts/signal_push.py` — 跑在沙箱
- `data/portfolio.json` — 持仓数据，不改
- `data/risk.py` — 风险模块，本次不改

## 执行顺序

1. 先改 `data/valuation.py`（任务1），运行验证
2. 改 `data/signals.py`（任务2），运行验证
3. 改 `data/rebalance.py`（任务3），运行 `data/signals.py` → `data/rebalance.py` 串行验证
4. 改 `GUARDRAILS.md`（任务4）
5. 最后跑一次完整 `./run_all.sh`，确认全链路无报错
6. `git add -A && git commit -m "P0.5: decision engine upgrade - actionable signals & fund-level operations" && git push`

## 验收总标准

运行 `./run_all.sh` 后：
1. `valuation.json` 7个品类全部有 verdict（无"数据缺失"）
2. `signals.json` 至少有 1 只基金信号不是"持有/观望/高估警惕"
3. `rebalance.json` 包含 `operations` 数组，有具体基金级买卖指令
4. 同品类基金（如黄金两只）信号不矛盾
