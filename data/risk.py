#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 组合风险仪表盘
==========================
计算组合级别风险度量，回答"风险多大"。

计算内容：
  1. 组合波动率  = 按持仓权重加权日收益标准差 × sqrt(252)
  2. 最大回撤    = max(peak-trough)/peak（近1年）
  3. 夏普比率    = (年化收益 - 2.5%) / 年化波动率
  4. risk_level  = 低(<8%) / 中(8-15%) / 中高(15-22%) / 高(>22%)

集中度预警（按 category 汇总持仓比例）：
  - 单品类 > 40%               → severity:high
  - 大宗(黄金+有色) > 50%      → severity:high
  - A股成长(AI+光伏+高端) > 60% → severity:medium

相关性矩阵：按 category 分组算 Pearson 相关系数，>0.7 标记

压力测试（3场景，按持仓比例线性估算）：
  - 黄金回调10%
  - A股整体回调15%（AI+光伏+高端制造+有色）
  - 大宗全面走弱20%（黄金+有色）

数据来源：
  优先：ak.fund_open_fund_info_em(indicator="累计净值走势") → 近1年日净值
  兜底：用 portfolio.json 的 dailyReturn / totalAsset 估算

输出：data/risk.json
"""

import json
import math
import os
import time
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

BASE_DIR      = os.path.dirname(os.path.abspath(__file__))
ROOT          = os.path.dirname(BASE_DIR)
PORTFOLIO_PATH = os.path.join(ROOT, "data", "portfolio.json")
OUT_PATH      = os.path.join(ROOT, "data", "risk.json")

# 无风险利率（年化 2.5%）
RF_ANNUAL = 0.025
# 每年交易日
TRADING_DAYS = 252


# ── 读取持仓 ──────────────────────────────────────────────────
def _load_portfolio():
    with open(PORTFOLIO_PATH, encoding="utf-8") as f:
        return json.load(f)


# ── 拉取单基金近1年日净值序列 ────────────────────────────────
def _fetch_nav_series(code: str, name: str):
    """
    用 fund_open_fund_info_em indicator='累计净值走势' 拉近1年净值。
    返回 list[float]（日净值序列，已排序从旧到新），长度不足30时返回 None。
    """
    try:
        import akshare as ak
        import pandas as pd

        df = ak.fund_open_fund_info_em(symbol=code, indicator="累计净值走势")
        if df is None or df.empty:
            return None

        # 列：净值日期 | 累计净值（或单位净值）| 日增长率（可选）
        date_col = df.columns[0]
        # 精确匹配：跳过包含"日期"的列，优先取"累计净值"/"单位净值"
        nav_col = next(
            (c for c in df.columns if ("净值" in c or "NAV" in c.upper()) and "日期" not in c),
            df.columns[1],
        )

        df[date_col] = pd.to_datetime(df[date_col], errors="coerce")
        df = df.dropna(subset=[date_col]).sort_values(date_col)

        cutoff = pd.Timestamp(datetime.today() - timedelta(days=370))
        df1y = df[df[date_col] >= cutoff].copy()

        if len(df1y) < 30:
            return None

        navs = pd.to_numeric(df1y[nav_col], errors="coerce").dropna().tolist()
        return navs if len(navs) >= 30 else None

    except Exception as e:
        print(f"    ✗ {name}({code}) 净值拉取失败: {e}")
        return None


# ── 日收益率序列 ─────────────────────────────────────────────
def _nav_to_daily_returns(navs: list) -> list:
    """累计净值序列 → 日收益率列表（len = len(navs)-1）。"""
    returns = []
    for i in range(1, len(navs)):
        if navs[i - 1] > 0:
            returns.append((navs[i] - navs[i - 1]) / navs[i - 1])
    return returns


# ── 组合波动率（加权） ────────────────────────────────────────
def _portfolio_volatility(returns_map: dict, weights: dict) -> float:
    """
    加权日收益率 → 组合年化波动率。
    returns_map: {code: [日收益率]}（每条列表从旧到新）
    weights:     {code: 权重(0-1)}
    """
    import statistics

    # 取所有持仓的最短公共长度（尾部对齐：取各序列最后 min_len 个元素）
    valid = {k: v for k, v in returns_map.items() if v and len(v) > 20}
    if not valid:
        return None

    min_len = min(len(v) for v in valid.values())
    if min_len < 20:
        return None

    total_weight = sum(weights.get(k, 0) for k in valid)
    if total_weight == 0:
        return None

    # 对齐：每支基金取最后 min_len 个日收益（时间上最近的 min_len 天）
    aligned = {k: v[-min_len:] for k, v in valid.items()}

    # 组合日收益序列 = Σ w_i * r_i(t)
    portfolio_daily = [
        sum((weights.get(k, 0) / total_weight) * aligned[k][t] for k in aligned)
        for t in range(min_len)
    ]

    if len(portfolio_daily) < 2:
        return None

    std = statistics.stdev(portfolio_daily)
    return round(std * math.sqrt(TRADING_DAYS) * 100, 2)  # 转百分比


# ── 最大回撤 ─────────────────────────────────────────────────
def _max_drawdown(navs: list) -> float:
    """计算净值序列的最大回撤（%）。"""
    if not navs or len(navs) < 2:
        return 0.0
    peak = navs[0]
    max_dd = 0.0
    for v in navs[1:]:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0
        if dd > max_dd:
            max_dd = dd
    return round(max_dd * 100, 2)


# ── 组合最大回撤（加权净值） ──────────────────────────────────
def _portfolio_drawdown(nav_map: dict, weights: dict) -> float:
    """用加权净值序列计算组合最大回撤。"""
    valid = {k: v for k, v in nav_map.items() if v and len(v) > 5}
    if not valid:
        return None

    min_len = min(len(v) for v in valid.values())
    total_weight = sum(weights.get(k, 0) for k in valid)
    if total_weight == 0 or min_len < 5:
        return None

    # 尾部对齐：取各序列最后 min_len 个净值
    aligned = {k: v[-min_len:] for k, v in valid.items()}

    portfolio_nav = [
        sum((weights.get(k, 0) / total_weight) * aligned[k][t] for k in aligned)
        for t in range(min_len)
    ]

    return _max_drawdown(portfolio_nav)


# ── 夏普比率 ─────────────────────────────────────────────────
def _sharpe(annualized_vol_pct: float, nav_map: dict, weights: dict) -> float:
    """
    Sharpe = (年化收益 - RF) / 年化波动率
    年化收益 = 用加权净值序列的首尾计算
    """
    if not annualized_vol_pct or annualized_vol_pct == 0:
        return None

    valid = {k: v for k, v in nav_map.items() if v and len(v) > 5}
    if not valid:
        return None

    min_len = min(len(v) for v in valid.values())
    total_weight = sum(weights.get(k, 0) for k in valid)
    if total_weight == 0 or min_len < 5:
        return None

    # 尾部对齐后取首末
    aligned = {k: v[-min_len:] for k, v in valid.items()}
    nav_start = sum((weights[k] / total_weight) * aligned[k][0]  for k in aligned if k in weights)
    nav_end   = sum((weights[k] / total_weight) * aligned[k][-1] for k in aligned if k in weights)

    if nav_start <= 0:
        return None

    total_return = (nav_end - nav_start) / nav_start
    # 换算年化（假设 min_len ≈ 交易日数）
    years = min_len / TRADING_DAYS
    if years <= 0:
        return None
    annual_return = (1 + total_return) ** (1 / years) - 1

    sharpe = (annual_return - RF_ANNUAL) / (annualized_vol_pct / 100)
    return round(sharpe, 2)


# ── 风险等级 ─────────────────────────────────────────────────
def _risk_level(vol_pct: float) -> str:
    if vol_pct is None:
        return "未知"
    if vol_pct < 8:
        return "低"
    elif vol_pct < 15:
        return "中"
    elif vol_pct < 22:
        return "中高"
    else:
        return "高"


# ── 集中度预警 ───────────────────────────────────────────────
def _concentration_alerts(holdings: list) -> dict:
    """
    按 category 汇总持仓比例，返回 {categories:{...}, alerts:[...]}
    跳过 cash 类。
    """
    cat_ratio = {}
    total_non_cash = 0.0
    for h in holdings:
        if h.get("assetType") == "cash":
            continue
        cat = h.get("category", "其他")
        ratio = h.get("ratio", 0)
        cat_ratio[cat] = cat_ratio.get(cat, 0) + ratio
        total_non_cash += ratio

    alerts = []

    # 规则1：单品类 > 40%
    for cat, r in sorted(cat_ratio.items(), key=lambda x: -x[1]):
        if r > 40:
            alerts.append({
                "type":     "concentration_single",
                "severity": "high",
                "category": cat,
                "ratio":    round(r, 1),
                "message":  f"{cat}占比{r:.1f}%，超过安全线40%",
            })

    # 规则2：大宗（黄金+有色）> 50%
    bulk = cat_ratio.get("黄金", 0) + cat_ratio.get("有色金属", 0)
    if bulk > 50:
        alerts.append({
            "type":     "concentration_bulk",
            "severity": "high",
            "category": "黄金+有色金属",
            "ratio":    round(bulk, 1),
            "message":  f"大宗商品（黄金+有色）占比{bulk:.1f}%，超过安全线50%",
        })

    # 规则3：A股成长（AI+光伏+高端制造）> 60%
    growth_a = (cat_ratio.get("AI/科技", 0)
                + cat_ratio.get("光伏/新能源", 0)
                + cat_ratio.get("高端制造", 0))
    if growth_a > 60:
        alerts.append({
            "type":     "concentration_growth_a",
            "severity": "medium",
            "category": "AI/科技+光伏/新能源+高端制造",
            "ratio":    round(growth_a, 1),
            "message":  f"A股成长（AI+光伏+高端制造）占比{growth_a:.1f}%，超过安全线60%",
        })

    return {
        "categories": {k: round(v, 1) for k, v in sorted(cat_ratio.items(), key=lambda x: -x[1])},
        "alerts": alerts,
    }


# ── 相关性矩阵 ───────────────────────────────────────────────
def _correlation_matrix(returns_map: dict, category_map: dict) -> dict:
    """
    按 category 合并（同类取平均）后算 Pearson 相关系数矩阵。
    returns_map:  {code: [日收益率]}
    category_map: {code: category}
    """
    import statistics

    # 按 category 分组，多支基金合并为平均
    cat_returns: dict = {}
    for code, rets in returns_map.items():
        if not rets:
            continue
        cat = category_map.get(code)
        if cat is None or cat == "货币基金":
            continue
        if cat not in cat_returns:
            cat_returns[cat] = []
        cat_returns[cat].append(rets)

    # 对齐长度（取最短）
    if len(cat_returns) < 2:
        return {"categories": list(cat_returns.keys()), "matrix": [], "high_correlation_pairs": []}

    for cat in cat_returns:
        min_l = min(len(r) for r in cat_returns[cat])
        cat_returns[cat] = [r[-min_l:] for r in cat_returns[cat]]

    # 各类平均日收益序列
    cat_avg: dict = {}
    for cat, rets_list in cat_returns.items():
        n = len(rets_list)
        min_l = min(len(r) for r in rets_list)
        avg = [sum(rets_list[i][t] for i in range(n)) / n for t in range(min_l)]
        cat_avg[cat] = avg

    cats = sorted(cat_avg.keys())
    # 对齐所有类
    min_len = min(len(v) for v in cat_avg.values())
    for cat in cats:
        cat_avg[cat] = cat_avg[cat][-min_len:]

    def _pearson(x: list, y: list) -> float:
        n = len(x)
        if n < 5:
            return None
        mx = sum(x) / n
        my = sum(y) / n
        num   = sum((x[i] - mx) * (y[i] - my) for i in range(n))
        dx    = math.sqrt(sum((xi - mx) ** 2 for xi in x))
        dy    = math.sqrt(sum((yi - my) ** 2 for yi in y))
        if dx == 0 or dy == 0:
            return None
        return round(num / (dx * dy), 3)

    matrix = []
    high_pairs = []
    for i, ci in enumerate(cats):
        row = []
        for j, cj in enumerate(cats):
            if i == j:
                row.append(1.0)
            elif j < i:
                row.append(matrix[j][i])
            else:
                corr = _pearson(cat_avg[ci], cat_avg[cj])
                row.append(corr if corr is not None else None)
                if corr is not None and corr > 0.7:
                    high_pairs.append({
                        "pair":        f"{ci} vs {cj}",
                        "correlation": corr,
                    })
        matrix.append(row)

    return {
        "categories": cats,
        "matrix":     matrix,
        "high_correlation_pairs": high_pairs,
    }


# ── 压力测试 ──────────────────────────────────────────────────
def _stress_test(cat_ratio: dict) -> list:
    """3个场景压力测试，返回列表。"""
    gold_ratio   = cat_ratio.get("黄金", 0) / 100
    color_ratio  = cat_ratio.get("有色金属", 0) / 100
    ai_ratio     = cat_ratio.get("AI/科技", 0) / 100
    pv_ratio     = cat_ratio.get("光伏/新能源", 0) / 100
    mfg_ratio    = cat_ratio.get("高端制造", 0) / 100

    scenarios = [
        {
            "name":                 "黄金回调10%",
            "description":          "假设黄金价格下跌10%",
            "portfolio_impact_pct": round(-(gold_ratio * 10), 2),
        },
        {
            "name":                 "A股整体回调15%",
            "description":          "AI+光伏+高端制造+有色金属同步下跌15%",
            "portfolio_impact_pct": round(-(ai_ratio + pv_ratio + mfg_ratio + color_ratio) * 15, 2),
        },
        {
            "name":                 "大宗全面走弱20%",
            "description":          "黄金+有色金属同步下跌20%",
            "portfolio_impact_pct": round(-(gold_ratio + color_ratio) * 20, 2),
        },
    ]
    return scenarios


# ── 兜底：用 dailyReturn 估算波动率 ──────────────────────────
def _fallback_vol_from_portfolio(portfolio: dict) -> float:
    """
    兜底方法：用 portfolio.json 的 dailyReturn 和 totalAsset 反推
    单日收益率，再用恒定方法估算波动率（很粗略）。
    """
    total   = portfolio.get("totalAsset", 0)
    daily_r = portfolio.get("dailyReturn", 0)
    if total <= 0:
        return None
    daily_ret = daily_r / total
    # 假设波动率 ≈ |单日收益| × 1.5 × sqrt(252)（粗估）
    vol = abs(daily_ret) * 1.5 * math.sqrt(TRADING_DAYS) * 100
    return round(vol, 2)


# ── 主流程 ────────────────────────────────────────────────────
def main():
    print(f"== 玄枢Alpha · 组合风险仪表盘 [{datetime.now().strftime('%H:%M:%S')}] ==\n")

    portfolio = _load_portfolio()
    holdings  = portfolio.get("holdings", [])
    total_asset = portfolio.get("totalAsset", 1)

    # 非 cash 持仓
    active_holdings = [h for h in holdings if h.get("assetType") != "cash"]

    # ── Step1: 拉取净值序列 ────────────────────────────────────
    print("--- [Step1] 拉取近1年净值序列 ---")
    nav_map     = {}   # {code: [累计净值]}
    returns_map = {}   # {code: [日收益率]}
    weights     = {}   # {code: 权重(0-1)}
    cat_map     = {}   # {code: category}

    for h in active_holdings:
        code   = h["code"]
        name   = h["name"]
        ratio  = h.get("ratio", 0)
        cat    = h.get("category", "其他")
        cat_map[code] = cat

        if ratio <= 0:
            continue

        weights[code] = ratio / 100.0

        navs = _fetch_nav_series(code, name)
        if navs:
            nav_map[code]     = navs
            returns_map[code] = _nav_to_daily_returns(navs)
            print(f"  ✓ {name}({code}) → {len(navs)} 个净值点")
        else:
            print(f"  ✗ {name}({code}) → 净值获取失败，跳过")

        time.sleep(0.2)

    # ── Step2: 组合波动率 ─────────────────────────────────────
    print("\n--- [Step2] 计算组合波动率 ---")
    vol_pct = _portfolio_volatility(returns_map, weights)
    if vol_pct is None:
        vol_pct = _fallback_vol_from_portfolio(portfolio)
        vol_note = "兜底估算(净值不足)"
        print(f"  使用兜底估算: {vol_pct}%")
    else:
        vol_note = "加权日收益率实算"
        print(f"  组合年化波动率: {vol_pct}%")

    # ── Step3: 最大回撤 ────────────────────────────────────────
    print("\n--- [Step3] 最大回撤 ---")
    dd_pct = _portfolio_drawdown(nav_map, weights)
    if dd_pct is None:
        # 兜底：用个别基金的最大回撤加权
        if nav_map:
            dd_list = []
            for code, navs in nav_map.items():
                dd = _max_drawdown(navs)
                dd_list.append((weights.get(code, 0), dd))
            tw = sum(w for w, _ in dd_list)
            dd_pct = round(sum(w * d for w, d in dd_list) / tw, 2) if tw > 0 else None
        print(f"  最大回撤(加权平均): {dd_pct}%")
    else:
        print(f"  组合最大回撤: {dd_pct}%")

    # ── Step4: 夏普比率 ───────────────────────────────────────
    print("\n--- [Step4] 夏普比率 ---")
    sharpe = _sharpe(vol_pct, nav_map, weights)
    print(f"  夏普比率: {sharpe}")

    # ── Step5: 风险等级 ────────────────────────────────────────
    level = _risk_level(vol_pct)
    print(f"\n  风险等级: {level}  (波动率={vol_pct}%)")

    # ── Step6: 集中度预警 ─────────────────────────────────────
    print("\n--- [Step5] 集中度预警 ---")
    concentration = _concentration_alerts(holdings)
    alerts = concentration["alerts"]
    print(f"  品类分布: {concentration['categories']}")
    for a in alerts:
        sev_icon = "🔴" if a["severity"] == "high" else "🟡"
        print(f"  {sev_icon} [{a['severity'].upper()}] {a['message']}")
    if not alerts:
        print("  ✓ 无集中度预警")

    # ── Step7: 相关性矩阵 ─────────────────────────────────────
    print("\n--- [Step6] 相关性矩阵 ---")
    corr = _correlation_matrix(returns_map, cat_map)
    cats_used = corr["categories"]
    high_pairs = corr["high_correlation_pairs"]
    print(f"  覆盖品类: {cats_used}")
    if high_pairs:
        for p in high_pairs:
            print(f"  ⚠ 高相关: {p['pair']}  r={p['correlation']}")
    else:
        print("  ✓ 无高相关对（>0.7）")

    # ── Step8: 压力测试 ────────────────────────────────────────
    print("\n--- [Step7] 压力测试 ---")
    stress = _stress_test(concentration["categories"])
    for s in stress:
        print(f"  {s['name']}: 组合影响 {s['portfolio_impact_pct']:.2f}%")

    # ── 汇总输出 ──────────────────────────────────────────────
    output = {
        "updated_at": datetime.today().strftime("%Y-%m-%d"),
        "portfolio_risk": {
            "volatility":       vol_pct,
            "volatility_note":  vol_note if vol_pct else None,
            "drawdown":         dd_pct,
            "sharpe":           sharpe,
            "risk_level":       level,
        },
        "concentration": concentration,
        "correlation_matrix": corr,
        "stress_test": stress,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 组合风险仪表盘完成 → {OUT_PATH}")
    print(f"   风险等级={level}  波动率={vol_pct}%  最大回撤={dd_pct}%  夏普={sharpe}")
    print(f"   集中度预警 {len(alerts)} 条  高相关对 {len(high_pairs)} 对")


if __name__ == "__main__":
    main()
