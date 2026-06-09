#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""从 value_compass.json 生成 REPORT.md（保证报告数字与取数结果一致，不手抄）。"""
import json, os

BASE = os.path.dirname(os.path.abspath(__file__))
d = json.load(open(os.path.join(BASE, "data", "value_compass.json"), encoding="utf-8"))

EMOJI = {"绿": "🟢", "黄": "🟡", "红": "🔴", "灰": "⚪"}


def fmt(v, suffix="%"):
    return f"{v}{suffix}" if v is not None else "—"


lines = []
A = lines.append

A("# 玄枢Alpha · 价值罗盘（Value Compass）—— 报告")
A("")
A("> **进阶层功能**：基于巴菲特投资框架，对持仓基金做「持仓穿透 + 底层个股价值体检」。")
A(">")
A("> 用户持有的是基金/指数，而巴菲特框架分析的是**单个公司**。因此先做**持仓穿透（look-through，透视盈余法）**——把基金穿透到前十大重仓股，再对底层个股套用巴菲特框架，最后按权重汇总成「基金底层质地视图」。")
A("")
A(f"- **生成时间**：{d['generated_at']}")
A(f"- **数据源**：{d['data_source']}")
A(f"- **方法论**：{d['methodology']}")
A("")
A("---")
A("")

# ===== 名称不一致警告（动态，仅在有不一致时展示） =====
mismatches = [f for f in d["funds"] if f.get("name_mismatch_warning")]
if mismatches:
    A("## ⚠️ 取数中发现：部分基金组合标注名与官方名称不符")
    A("")
    A("| 基金代码 | 组合中标注名称 | AKShare 官方名称 |")
    A("|---|---|---|")
    for f in mismatches:
        A(f"| `{f['fund_code']}` | {f['portfolio_labeled_name']} | **{f['official_name']}** |")
    A("")
    A("> 建议同步修正持仓表中对应的基金名称，确保标注与实际投资标的一致。")
    A("")
    A("---")
    A("")

# ===== 评级图例 =====
A("## 评级图例（巴菲特红绿灯）")
A("")
A("| 评级 | 含义 |")
A("|---|---|")
A("| 🟢 绿 | 优质可持有：生意质地优秀，符合巴菲特优质企业特征 |")
A("| 🟡 黄 | 观察：质地中等或处能力圈边缘，需持续跟踪 |")
A("| 🔴 红 | 回避：盈利能力/现金成色不足，质地偏弱 |")
A("| ⚪ 灰 | **不予评级**：超出能力圈或数据不足，诚实标注「不知道」（能力圈灵魂，不硬编结论） |")
A("")
A("> 评级**仅反映「生意质地」**，不代表「买入时机」。安全边际（内在价值 6–7 折）需结合估值另判，本版本未做估值模型，已在每只个股 Q8 诚实标注。")
A("")
A("---")
A("")

# ===== 每只基金 =====
for f in d["funds"]:
    s = f["fund_quality_summary"]
    display_name = f.get("official_name") or f.get("portfolio_labeled_name") or f["fund_code"]
    A(f"## 基金穿透：{display_name}（`{f['fund_code']}`）")
    A("")
    A(f"- **基金类型**：{f.get('fund_type', '—')}　|　**穿透季度**：{f.get('latest_quarter', '—')}")
    A(f"- **底层质地结论**：{s['verdict']}")
    w = s["weight_by_rating_in_top10_pct"]
    A(f"- **前十大重仓权重分布**：🟢绿 {w.get('绿', 0)}% / 🟡黄 {w.get('黄', 0)}% / 🔴红 {w.get('红', 0)}% / ⚪灰 {w.get('灰', 0)}%（按披露权重归一化）")
    A("")

    # 评级总表
    A("### 底层重仓股 · 巴菲特八问评级表")
    A("")
    A("| 股票 | 代码 | 占净值% | 评级 | 质地分 | ROE | 毛利率(代理) | 净利率 | 现金转化 | 资产负债率 |")
    A("|---|---|---|:--:|:--:|--:|--:|--:|--:|--:|")
    for h in f["holdings_rated"]:
        r = h["rating"]
        fin = h["financials"]
        sc = f"{r['score']}/{r['score_max']}" if r.get("score") is not None else "—"
        A(f"| {h['stock_name']} | {h['stock_code']} | {h['ratio_pct']} | "
          f"{EMOJI[r['rating']]}{r['rating']} | {sc} | "
          f"{fmt(fin.get('roe_pct'))} | {fmt(fin.get('gross_margin_pct'))} | "
          f"{fmt(fin.get('net_margin_pct'))} | {fmt(fin.get('ocf_to_netprofit_pct'))} | "
          f"{fmt(fin.get('debt_ratio_pct'))} |")
    A("")
    if f["holdings_rated"]:
        rd = f["holdings_rated"][0]["financials"].get("report_date", "")
        A(f"> 财务口径：ROE/毛利率/成长性取最近**年报（{rd} 等）**完整年度数据；负债率取最新期。"
          f"毛利率因数据集 `销售毛利率` 多缺失，以 `主营业务利润率` 作代理（已标注）。")
    A("")

    # 逐股评级理由
    A("### 评级理由（逐股）")
    A("")
    for h in f["holdings_rated"]:
        r = h["rating"]
        A(f"**{EMOJI[r['rating']]} {h['stock_name']}（{r['rating_label']}）** — {r['rating_reason']}")
        A("")
    A("---")
    A("")

# ===== 方法论 =====
A("## 方法论：巴菲特八问检查表")
A("")
A("对每只穿透出的底层个股，按以下结构化检查表打分（基于 AKShare 真实财务 + 行业常识），再映射红绿灯：")
A("")
A("| 序号 | 检查项 | 数据依据 | 权重 |")
A("|---|---|---|---|")
A("| Q1 | **能力圈** | 行业是否看得懂（消费=主场；光伏/新能源=边缘；半导体/AI算力=圈外） | 一票否决（圈外直接灰） |")
A("| Q2 | **商业模式** | 毛利率（≥40%优 / 20–40%中） | 2 分 |")
A("| Q3 | **护城河** | ROE（≥15%护城河迹象）+ ROE 多年稳定性 | 3 分 |")
A("| Q4 | **定价权** | 净利率（≥20%强定价权） | 2 分 |")
A("| Q5 | **现金含金量** | 经营现金流/净利润（≥80%利润成色高） | 2 分 |")
A("| Q6 | **抗压能力** | 资产负债率（≤50%稳健） | 1 分 |")
A("| Q7 | **成长性** | 营收/净利增速 | 参考，非评级核心 |")
A("| Q8 | **管理层 & 安全边际** | 内在价值估值 + 管理层诚信 | ⚠ 本版本未做，已诚实标注 |")
A("")
A("**评级映射**：")
A("- 能力圈内 + 质地分 ≥70% → 🟢绿；45–70% → 🟡黄；<45% → 🔴红")
A("- 能力圈边缘 → 质地再好最多 🟡黄（谨慎）")
A("- 能力圈外 / 核心财务缺 2 项以上 → ⚪灰（不予评级）")
A("")
A("**穿透质地汇总**：把底层个股评级按「占基金净值权重」加权，得到基金「底层质地」概述。")
A("")
A("---")
A("")

# ===== 非个股资产说明 =====
A("## 关于持仓中的非个股资产")
A("")
A("持仓中还包括**黄金 ETF、有色金属 ETF、纳指/标普宽基 ETF、货币基金**等。")
A("")
A("> ⚠️ **巴菲特框架不适用于这类资产**。黄金/大宗商品不产生现金流、没有 ROE、没有护城河。")
A("> 宽基 ETF 持仓分散，无法做个股质地穿透。这些资产由「资产配置 / 宏观信号」维度评估（玄枢已有黄金/有色信号模块），**不纳入价值罗盘的个股质地评级**。")
A("")
A("---")
A("")

# ===== 数据来源与局限 =====
A("## 数据来源、时间与局限")
A("")
A(f"- **数据源**：AKShare（聚合东方财富 / 公开季报披露），免费中国金融数据库。生成于 {d['generated_at']}。")
A("  - 基金前十大重仓：`ak.fund_portfolio_hold_em`")
A("  - 个股财务指标：`ak.stock_financial_analysis_indicator`")
A("  - 基金官方名称：`ak.fund_name_em`")
A("- **数据局限（诚实标注）**：")
A("  1. ETF 联接基金直接持股比例极低（前十大合计常 <3%，主体仓位是目标 ETF），披露的个股权重偏小；穿透取其**主题成分股**用于质地判断。")
A("  2. 数据集 `销售毛利率` 字段大面积缺失，已用 `主营业务利润率` 作代理。")
A("  3. 部分公司经营现金流/净利润比率缺失或异常，相应维度标 — 不计分。")
A("  4. **Q8 安全边际与管理层诚信未量化**，评级只回答「这是不是好生意」，不回答「现在买贵不贵」。")
A("  5. 凡数据不足或超出能力圈，一律 ⚪ 灰评，**绝不编造财务数字或硬凑结论**——这是产品的信任壁垒。")
A("")

# ===== 链路验证结论（动态生成） =====
A("## 链路验证结论")
A("")
A("✅ 已跑通完整链路：**基金 → 穿透前十大重仓股 → 拉取个股真实财务 → 巴菲特八问评级 → 按权重汇总基金质地**。")
A("")
for f in d["funds"]:
    s = f["fund_quality_summary"]
    w = s["weight_by_rating_in_top10_pct"]
    display_name = f.get("official_name") or f.get("portfolio_labeled_name") or f["fund_code"]
    green_pct = w.get("绿", 0)
    yellow_pct = w.get("黄", 0)
    red_pct = w.get("红", 0)
    grey_pct = w.get("灰", 0)
    A(f"- **{display_name}（{f['fund_code']}）**：🟢{green_pct}% / 🟡{yellow_pct}% / 🔴{red_pct}% / ⚪{grey_pct}% — {s['verdict']}")
A("")

out_path = os.path.join(BASE, "REPORT.md")
open(out_path, "w", encoding="utf-8").write("\n".join(lines) + "\n")
print("REPORT.md 已生成，行数:", len(lines))
