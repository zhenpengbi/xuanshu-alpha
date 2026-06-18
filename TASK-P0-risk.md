# 任务书：P0-② 组合风险仪表盘

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

1. **会改变操作建议吗？** → 是。集中度预警直接告诉用户"你的大宗暴露63%太高，需要分散"
2. **没有会导致错误决策吗？** → 是。毕老师可能在高度相关的资产上继续加仓
3. **优先级高于P0吗？** → 本身就是P0第二项

---

## 目标

计算组合级别的风险度量指标，包括：波动率、最大回撤、相关性矩阵、大类集中度预警。

## 输出文件

`data/risk.json`

## 数据结构

```json
{
  "updated_at": "2026-06-17 16:00",
  "portfolio_risk": {
    "annualized_volatility_pct": 18.5,
    "max_drawdown_pct": -15.3,
    "sharpe_ratio": 0.85,
    "risk_level": "中高",
    "risk_comment": "组合年化波动率18.5%，属于中高风险偏积极型"
  },
  "concentration": {
    "top1_category": "黄金",
    "top1_pct": 49.3,
    "top2_category": "有色金属",
    "top2_pct": 14.06,
    "commodity_total_pct": 63.36,
    "alerts": [
      {
        "type": "category_overweight",
        "message": "黄金类占比49.3%，超过单一类别安全线40%",
        "severity": "high"
      },
      {
        "type": "macro_concentration",
        "message": "大宗商品类（黄金+有色金属）合计63.4%，超过大类安全线50%",
        "severity": "high"
      }
    ]
  },
  "correlation_matrix": {
    "categories": ["黄金", "有色金属", "AI/科技", "光伏/新能源", "高端制造"],
    "matrix": [
      [1.00, 0.65, 0.12, 0.08, 0.15],
      [0.65, 1.00, 0.30, 0.25, 0.35],
      [0.12, 0.30, 1.00, 0.72, 0.68],
      [0.08, 0.25, 0.72, 1.00, 0.75],
      [0.15, 0.35, 0.68, 0.75, 1.00]
    ],
    "high_correlation_pairs": [
      {"pair": "光伏/新能源 × 高端制造", "corr": 0.75, "note": "同属A股制造业成长赛道，高度共振"}
    ]
  },
  "stress_test": {
    "scenarios": [
      {
        "name": "黄金回调10%",
        "portfolio_impact_pct": -4.93,
        "comment": "黄金占比49%，10%回调直接拖累组合近5%"
      },
      {
        "name": "A股整体回调15%",
        "portfolio_impact_pct": -5.67,
        "comment": "AI/光伏/高端制造/有色合计37.8%暴露在A股"
      },
      {
        "name": "大宗商品全面走弱20%",
        "portfolio_impact_pct": -12.67,
        "comment": "黄金+有色63.4%暴露，大宗全面走弱影响极大"
      }
    ]
  }
}
```

## 实现要求

### 新建文件：`data/risk.py`

1. **读取历史净值数据**：
   - 从 `data/nav_history/` 目录读取各基金的历史净值（由 fetch_prices.py 生成）
   - 如果 `nav_history/` 不存在或数据不足，用 AKShare `ak.fund_open_fund_info_em(symbol=基金代码, indicator="累计净值走势")` 拉取近1年日度净值
   - 兜底：如果拉不到数据，用 portfolio.json 中的 dailyReturn 估算近期波动率

2. **组合波动率计算**：
   - 按持仓权重加权计算组合日收益率序列
   - 年化波动率 = 日波动率 × √252
   - 最大回撤 = max(peak - trough) / peak
   - 夏普比率 = (年化收益 - 2.5%) / 年化波动率（无风险利率取2.5%）

3. **相关性矩阵**：
   - 按 category 分组，计算各品类日收益率的 Pearson 相关系数
   - 同品类内多只基金（如两只黄金）合并为一个品类序列（按金额加权）
   - 标记相关系数 > 0.7 的配对为"高相关"

4. **集中度预警规则**：
   | 条件 | severity | 消息模板 |
   |---|---|---|
   | 单一category占比 > 40% | high | "{category}类占比{pct}%，超过单一类别安全线40%" |
   | 大宗商品（黄金+有色）> 50% | high | "大宗商品类合计{pct}%，超过大类安全线50%" |
   | A股成长（AI+光伏+高端制造）> 60% | medium | "A股成长赛道合计{pct}%，回调风险集中" |
   | 任意两品类相关系数 > 0.8 | medium | "{A} × {B} 相关性{corr}，分散效果有限" |

5. **压力测试**（简化版）：
   - 固定3个场景，按持仓比例简单线性计算影响
   - 场景①：黄金-10%
   - 场景②：A股整体-15%（AI+光伏+高端制造+有色）
   - 场景③：大宗全面-20%（黄金+有色）

6. **risk_level 判定**：
   | 年化波动率 | risk_level |
   |---|---|
   | < 8% | 低 |
   | 8-15% | 中 |
   | 15-22% | 中高 |
   | > 22% | 高 |

### 接入 run_all.sh

在第6步（再平衡建议）之后，新增：
```bash
echo ""
echo "【第7步】组合风险度量..."
python3 data/risk.py
```

### 接入 rebalance.py（小改动）

在 `data/rebalance.py` 中读取 `data/risk.json`，在 actions 列表中：
- 如果某个 category 触发了 concentration alert (severity=high)，在该 category 的 action 中追加 `"risk_alert": "集中度过高"`
- 如果组合 risk_level 为"高"，在输出中新增 `"portfolio_risk_warning": "组合整体风险偏高，建议降低波动"`

## 验收标准

1. `python3 data/risk.py` 运行成功，输出 risk.json
2. concentration.alerts 至少有2条（黄金超配+大宗合计超标）
3. stress_test 3个场景都有合理数值
4. 如果净值数据拉不到，兜底输出合理估算值（不报错）
5. 整体运行时间 < 30秒

## 不要做的事

- 不要改 index.html（前端展示是下一步的事）
- 不要改 portfolio.json
- 不要装新的 pip 包
