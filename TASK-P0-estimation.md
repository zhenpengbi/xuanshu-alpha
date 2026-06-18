# 任务书：P0-① 估值分位模块

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

## 准入自检

1. **会改变操作建议吗？** → 是。有了估值分位，建议将从"观望"变为"当前估值偏高/低估，建议减仓/加仓"
2. **没有会导致错误决策吗？** → 是。毕老师无法判断持仓"贵不贵"，可能在高估时加仓
3. **优先级高于P0吗？** → 本身就是P0第一项

---

## 目标

为玄枢持仓的每个行业/指数，提供 PE/PB 近5年历史百分位，输出"低估/适中/高估"判断。

## 输出文件

`data/valuation.json`

## 数据结构

```json
{
  "updated_at": "2026-06-17 16:00",
  "valuations": [
    {
      "category": "黄金",
      "index_name": "黄金ETF(AU9999)",
      "metric": "不适用",
      "note": "大宗商品无PE/PB估值，用金银比+实际利率替代",
      "gold_silver_ratio": 88.5,
      "gold_silver_ratio_pct_5y": 72,
      "real_yield_10y": 1.85,
      "verdict": "中性偏贵",
      "verdict_score": 62
    },
    {
      "category": "AI/科技",
      "index_name": "中证人工智能指数(930713)",
      "metric": "PE_TTM",
      "current_pe": 55.3,
      "pe_pct_5y": 45,
      "current_pb": 4.2,
      "pb_pct_5y": 38,
      "verdict": "适中",
      "verdict_score": 42
    },
    {
      "category": "有色金属",
      "index_name": "中证有色金属指数(930708)",
      "metric": "PE_TTM",
      "current_pe": 22.1,
      "pe_pct_5y": 55,
      "current_pb": 2.1,
      "pb_pct_5y": 50,
      "verdict": "适中",
      "verdict_score": 53
    },
    {
      "category": "光伏/新能源",
      "index_name": "中证光伏产业指数(931151)",
      "metric": "PE_TTM",
      "current_pe": 18.5,
      "pe_pct_5y": 12,
      "current_pb": 1.5,
      "pb_pct_5y": 8,
      "verdict": "低估",
      "verdict_score": 10
    },
    {
      "category": "高端制造",
      "index_name": "中证高端装备制造指数(399377)",
      "metric": "PE_TTM",
      "current_pe": 32.0,
      "pe_pct_5y": 40,
      "current_pb": 3.0,
      "pb_pct_5y": 35,
      "verdict": "适中偏低",
      "verdict_score": 38
    },
    {
      "category": "纳指100",
      "index_name": "纳斯达克100(NDX)",
      "metric": "PE_TTM",
      "current_pe": 37.0,
      "pe_pct_5y": 85,
      "current_pb": 8.5,
      "pb_pct_5y": 82,
      "verdict": "偏贵",
      "verdict_score": 84
    },
    {
      "category": "标普500",
      "index_name": "标普500(SPX)",
      "metric": "PE_TTM",
      "current_pe": 28.5,
      "pe_pct_5y": 78,
      "current_pb": 4.8,
      "pb_pct_5y": 75,
      "verdict": "偏贵",
      "verdict_score": 77
    }
  ]
}
```

## verdict_score 定义

| 分数区间 | verdict | 含义 |
|---|---|---|
| 0-20 | 低估 | 近5年PE/PB分位≤20%，历史性便宜 |
| 20-40 | 适中偏低 | 偏便宜但不极端 |
| 40-60 | 适中 | 中间位置 |
| 60-80 | 偏贵 | 不便宜了 |
| 80-100 | 高估 | 近5年PE/PB分位≥80%，历史性偏贵 |

## 实现要求

### 新建文件：`data/valuation.py`

1. **A股行业指数估值**：使用 AKShare 接口
   - 尝试 `ak.index_value_hist_funddb(symbol="指数名", indicator="市盈率")`
   - 或 `ak.stock_zh_index_value_csindex(symbol="指数代码")` 获取中证指数估值
   - 如果以上不可用，用 `ak.index_zh_a_hist(symbol="指数代码")` 拉近5年日线，手动计算当前PE在历史中的分位数

2. **美股指数估值**：
   - 纳指100/标普500：尝试 yfinance 拉 PE，或用 catclaw-search 搜"nasdaq 100 PE ratio"获取当前值
   - 如果拉不到动态数据，硬编码一个合理的静态分位（注释标注需人工更新），后续迭代改为自动

3. **黄金（特殊处理）**：
   - 黄金无PE/PB，用两个替代指标：
     - 金银比（Gold/Silver Ratio）：AKShare `ak.futures_zh_spot_dict()` 或 catclaw-search
     - 美国10年期实际利率（TIPS yield）：catclaw-search
   - verdict_score = (gold_silver_ratio_pct_5y * 0.5 + 对 real_yield 的反向映射 * 0.5)

4. **兜底策略**：
   - 任何接口拉不到数据时，输出 `"metric": "不可用"`, `"verdict": "数据缺失"`, `"verdict_score": 50`（中性）
   - 不要因为某个指数拉取失败就整体报错

5. **运行方式**：
   - `python3 data/valuation.py` 独立运行
   - 输出 `data/valuation.json`
   - 无外部依赖（pandas/akshare 已安装）

### 接入 run_all.sh

在第2步（计算技术指标）之后、第3步（生成买卖信号）之前，新增：
```bash
echo ""
echo "【第2.5步】估值分位计算..."
python3 data/valuation.py
```

### 接入 signals.py（改动 data/signals.py）

在生成信号时，读取 `data/valuation.json`，为每个基金追加估值信息：
- 新增字段 `valuation_verdict`（低估/适中/偏贵/高估/不适用）
- 新增字段 `valuation_score`（0-100）
- **修改信号逻辑**：
  - 如果 `valuation_score >= 80`（高估）且当前信号是"观望"，改为"减仓观察"
  - 如果 `valuation_score <= 20`（低估）且当前信号是"观望"，改为"低估可加"

## 验收标准

1. `python3 data/valuation.py` 运行成功，输出 valuation.json
2. 7个品类中至少5个有真实数据（非"数据缺失"）
3. signals.json 中的信号不再全部是"观望"——至少有1-2只因估值偏离而给出不同建议
4. 整体运行时间 < 60秒

## 不要做的事

- 不要改 index.html（前端展示是下一步的事）
- 不要改 portfolio.json
- 不要装新的 pip 包（akshare/pandas/yfinance 已有）
