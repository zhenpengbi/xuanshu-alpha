#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 主动基金诊断
=========================
对 portfolio.json 中 assetType=active 的基金进行多维度诊断：

① 基金经理：姓名/公司/累计任职天数/是否仍在任
② 规模：最新规模（AKShare 规模历史接口返回空时标注「数据缺失」）
③ 超额收益 α：vs 沪深300（用 ak.fund_open_fund_info_em 净值 + 基准 NAV 计算）
④ 同类排名分位：来自 fund_individual_achievement_xq
⑤ 十大重仓股集中度：前5名/前10名占净值比例之和
⑥ 重仓股质地：复用 value_compass 的 buffett_eight_questions 穿透逻辑

⚠️ 重要发现（取数即暴露）：
  014658 官方名称"中欧融享增益一年持有期混合C"，与 portfolio.json "永赢高端装备智选混合C" 不符
  015897 官方名称"天弘中证细分化工产业主题ETF联接C"，与 portfolio.json "平安高端装备混合C" 不符
  诊断基于 AKShare 实际数据，name_mismatch=true 时请核实持仓代码。

用法：
    python3 scripts/active_fund_diagnose.py
输出：
    data/active_funds.json
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta

import akshare as ak
import pandas as pd

SCRIPT_DIR  = os.path.dirname(os.path.abspath(__file__))
ROOT        = os.path.dirname(SCRIPT_DIR)
PORTFOLIO   = os.path.join(ROOT, "data", "portfolio.json")
VC_DIR      = os.path.join(ROOT, "value_compass")
OUT_PATH    = os.path.join(ROOT, "data", "active_funds.json")

# 把 value_compass 目录加入 path，复用其评级逻辑
sys.path.insert(0, VC_DIR)
try:
    from build_value_compass import (
        fetch_stock_financials, buffett_eight_questions, summarize_fund,
        CODE_CIRCLE, CIRCLE_OF_COMPETENCE
    )
    VC_AVAILABLE = True
except Exception as e:
    VC_AVAILABLE = False
    print(f"  ⚠️  value_compass 穿透逻辑加载失败: {e}")


# ── 工具函数 ─────────────────────────────────────────────────

def safe(val, fallback="数据缺失"):
    """安全取值，None / NaN / NA → fallback 标注。"""
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return fallback
    return val


def calc_percentile(rank_str: str) -> float | None:
    """
    '512/1334' → 排名分位（0~100，越低越好：1 = top 1%）
    返回 0-100 浮点；解析失败返回 None。
    """
    try:
        num, denom = rank_str.strip().split("/")
        return round(int(num) / int(denom) * 100, 1)
    except Exception:
        return None


def calc_alpha(fund_navs: list, fund_dates: list, years: int = 3) -> dict:
    """
    粗略计算 α：基金年化收益 − 沪深300年化收益
    沪深300 用 ak.stock_zh_index_daily_em 获取，fallback 用 CSI300 近似。
    """
    try:
        cutoff = (datetime.today() - timedelta(days=years * 365)).strftime("%Y-%m-%d")
        navs_filtered = [(d, v) for d, v in zip(fund_dates, fund_navs) if str(d) >= cutoff]
        if len(navs_filtered) < 30:
            return {"fund_annual_pct": None, "benchmark_annual_pct": None,
                    "alpha_pct": None, "note": "数据不足30个交易日"}

        # 基金年化
        start_nav = float(navs_filtered[0][1])
        end_nav   = float(navs_filtered[-1][1])
        n_days    = len(navs_filtered)
        yrs       = n_days / 252
        fund_ann  = round(((end_nav / start_nav) ** (1 / yrs) - 1) * 100, 2)

        # 沪深300 同期
        try:
            df_idx = ak.stock_zh_index_daily_em(symbol="sh000300")
            df_idx = df_idx.sort_values("date")
            df_idx = df_idx[df_idx["date"].astype(str) >= cutoff]
            if len(df_idx) >= 30:
                b_start = float(df_idx.iloc[0]["close"])
                b_end   = float(df_idx.iloc[-1]["close"])
                b_ann   = round(((b_end / b_start) ** (1 / (len(df_idx) / 252)) - 1) * 100, 2)
            else:
                b_ann = None
        except Exception:
            b_ann = None   # 标注数据缺失

        alpha = round(fund_ann - b_ann, 2) if b_ann is not None else None
        return {
            "fund_annual_pct":      fund_ann,
            "benchmark_annual_pct": b_ann if b_ann else "数据缺失",
            "alpha_pct":            alpha if alpha is not None else "数据缺失",
            "benchmark":            "沪深300",
            "period_years":         round(yrs, 1),
            "note":                 "" if alpha is not None else "基准数据缺失，alpha 无法计算",
        }
    except Exception as e:
        return {"fund_annual_pct": None, "benchmark_annual_pct": "数据缺失",
                "alpha_pct": "数据缺失", "note": str(e)[:80]}


# ── 诊断建议 ─────────────────────────────────────────────────

def diagnose(info: dict) -> dict:
    """
    综合各维度给出持有建议。
    返回 {action, reasons, warnings, score}
    """
    warnings = []
    reasons  = []
    score    = 50  # 基准分 50

    # 名称不符预警
    if info.get("name_mismatch"):
        warnings.append(f"⚠️ 代码 {info['code']} 官方名称与持仓标注不符，请核实！"
                        f"官方：{info['official_name']}，"
                        f"持仓标注：{info['portfolio_name']}")

    # 同类排名分位（越低越好）
    pct = info.get("rank_percentile_ytd")
    if pct is not None:
        if pct <= 30:
            score += 20
            reasons.append(f"今年以来同类排名前 {pct:.0f}%，表现优秀")
        elif pct <= 50:
            score += 5
            reasons.append(f"今年以来同类排名前 {pct:.0f}%，表现一般")
        else:
            score -= 20
            reasons.append(f"今年以来同类排名 {pct:.0f}%（落后同类）")
            warnings.append(f"⚠️ 排名落后，建议关注是否替换")
    else:
        reasons.append("同类排名：数据缺失，无法评估")

    # 基金经理任职时长
    tenure = info.get("manager_tenure_days")
    if tenure is not None:
        yrs = tenure / 365
        if yrs < 1:
            score -= 10
            warnings.append(f"基金经理任职 {yrs:.1f} 年（不足1年），历史业绩参考价值有限")
        elif yrs >= 3:
            score += 10
            reasons.append(f"基金经理任职 {yrs:.1f} 年，管理经验相对充分")

    # Alpha
    alpha = info.get("alpha_pct")
    if isinstance(alpha, (int, float)):
        if alpha > 3:
            score += 15
            reasons.append(f"α={alpha:.1f}pt，相对沪深300有超额收益")
        elif alpha < -5:
            score -= 15
            reasons.append(f"α={alpha:.1f}pt，跑输沪深300较多")

    # 最大回撤
    dd = info.get("max_drawdown_pct")
    if isinstance(dd, (int, float)) and dd > 30:
        score -= 10
        warnings.append(f"最大回撤 {dd:.1f}%，波动较大")

    # 规模
    scale_str = info.get("scale_str", "")
    if "万" in str(scale_str):
        try:
            val = float(str(scale_str).replace("万", "").replace("亿", ""))
            if "亿" not in str(scale_str) and val < 1000:
                warnings.append(f"规模 {scale_str} 偏小（<0.1亿），有清盘风险")
        except Exception:
            pass

    # 最终建议
    if score >= 70:
        action = "可持有"
    elif score >= 50:
        action = "持有但关注"
    else:
        action = "建议评估替换"

    return {"action": action, "score": score,
            "reasons": reasons, "warnings": warnings}


# ── 主流程 ────────────────────────────────────────────────────

def diagnose_fund(code: str, portfolio_name: str) -> dict:
    result = {"code": code, "portfolio_name": portfolio_name}
    print(f"  处理 {code} ({portfolio_name})...")

    # 1. 基本信息
    try:
        df = ak.fund_individual_basic_info_xq(symbol=code)
        info = dict(zip(df["item"], df["value"]))
        result["official_name"] = safe(info.get("基金名称"))
        result["fund_type"]     = safe(info.get("基金类型"))
        result["scale_str"]     = safe(info.get("最新规模"))
        result["manager_name"]  = safe(info.get("基金经理"))
        result["company"]       = safe(info.get("基金公司"))
        result["inception_date"]= safe(info.get("成立时间"))
        result["name_mismatch"] = (
            result["official_name"] != "数据缺失" and
            portfolio_name not in str(result["official_name"]) and
            str(result["official_name"]) not in portfolio_name
        )
    except Exception as e:
        result["official_name"] = "数据缺失"
        result["name_mismatch"] = None
        print(f"    基本信息失败: {e!r:.60}")
    time.sleep(0.4)

    # 2. 经理任职天数（fund_manager_em 全量列表）
    try:
        df_mgr = ak.fund_manager_em()
        row = df_mgr[df_mgr["现任基金代码"] == code]
        if not row.empty:
            tenure = row.iloc[0].get("累计从业时间", None)
            result["manager_tenure_days"] = int(tenure) if tenure else None
        else:
            result["manager_tenure_days"] = None
    except Exception:
        result["manager_tenure_days"] = None
    time.sleep(0.3)

    # 3. 业绩排名（fund_individual_achievement_xq）
    result["performance_ranking"] = []
    result["rank_percentile_ytd"] = None
    result["max_drawdown_pct"]    = None
    try:
        df_perf = ak.fund_individual_achievement_xq(symbol=code)
        perfs = []
        for _, row in df_perf.iterrows():
            period    = str(row.get("周期", ""))
            ret       = row.get("本产品区间收益")
            dd        = row.get("本产品最大回撒")
            rank_str  = str(row.get("周期收益同类排名", ""))
            pct       = calc_percentile(rank_str)
            perfs.append({
                "period":      period,
                "return_pct":  round(float(ret), 2) if ret is not None and str(ret) != "nan" else None,
                "max_dd_pct":  round(float(dd), 2)  if dd  is not None and str(dd)  != "nan" else None,
                "rank":        rank_str,
                "percentile":  pct,
            })
            # 取今年以来的百分位 + 最大回撤
            if period in ("今年以来", "1年"):
                result["rank_percentile_ytd"] = pct
            if dd is not None and str(dd) != "nan":
                dd_v = round(float(dd), 2)
                if result["max_drawdown_pct"] is None or dd_v > result["max_drawdown_pct"]:
                    result["max_drawdown_pct"] = dd_v
        result["performance_ranking"] = perfs
    except Exception as e:
        print(f"    业绩排名失败: {e!r:.60}")
    time.sleep(0.4)

    # 4. 净值走势 → Alpha
    navs, dates = [], []
    try:
        df_nav = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        df_nav = df_nav.sort_values("净值日期")
        navs  = df_nav["单位净值"].astype(float).tolist()
        dates = df_nav["净值日期"].astype(str).tolist()
    except Exception:
        pass
    result["alpha_analysis"] = calc_alpha(navs, dates)
    result["alpha_pct"]      = result["alpha_analysis"].get("alpha_pct")
    time.sleep(0.3)

    # 5. 十大重仓股
    result["holdings_analysis"] = {"status": "数据缺失", "top_holdings": []}
    try:
        df_hold = ak.fund_portfolio_hold_em(symbol=code, date="2026")
        if df_hold is not None and not df_hold.empty:
            latest_q = df_hold["季度"].iloc[-1]
            sub = df_hold[df_hold["季度"] == latest_q].copy()
            sub["占净值比例"] = pd.to_numeric(sub["占净值比例"], errors="coerce")
            sub = sub.sort_values("占净值比例", ascending=False).head(10)
            top_list = []
            for _, r in sub.iterrows():
                top_list.append({
                    "stock_code":  str(r["股票代码"]),
                    "stock_name":  str(r["股票名称"]),
                    "ratio_pct":   round(float(r["占净值比例"]), 4),
                })
            top5_conc  = round(sum(h["ratio_pct"] for h in top_list[:5]), 2)
            top10_conc = round(sum(h["ratio_pct"] for h in top_list), 2)
            result["holdings_analysis"] = {
                "status":         "ok",
                "latest_quarter": str(latest_q),
                "top5_concentration_pct":  top5_conc,
                "top10_concentration_pct": top10_conc,
                "top_holdings":   top_list,
            }
    except Exception as e:
        print(f"    持仓失败: {e!r:.60}")
    time.sleep(0.4)

    # 6. 重仓股质地穿透（复用 value_compass）
    result["holdings_rated"] = []
    if VC_AVAILABLE and result["holdings_analysis"]["status"] == "ok":
        rated = []
        for h in result["holdings_analysis"]["top_holdings"][:7]:  # 最多7只，控制耗时
            fin    = fetch_stock_financials(h["stock_code"])
            rating = buffett_eight_questions(
                {"stock_name": h["stock_name"], "stock_code": h["stock_code"]}, fin
            )
            rated.append({
                "stock_code":  h["stock_code"],
                "stock_name":  h["stock_name"],
                "ratio_pct":   h["ratio_pct"],
                "rating":      rating["rating"],
                "rating_label":rating["rating_label"],
                "score":       rating.get("score"),
                "score_max":   rating.get("score_max"),
                "reason":      rating["rating_reason"],
            })
            print(f"    {h['stock_name']:8} → {rating['rating']}({rating['rating_label']})")
            time.sleep(0.3)
        result["holdings_rated"] = rated

        # 质地汇总
        buckets = {"绿": 0.0, "黄": 0.0, "红": 0.0, "灰": 0.0}
        total_w = sum(h["ratio_pct"] for h in result["holdings_analysis"]["top_holdings"][:7])
        for r in rated:
            w = next((h["ratio_pct"] for h in result["holdings_analysis"]["top_holdings"]
                      if h["stock_code"] == r["stock_code"]), 0.0)
            buckets[r["rating"]] += w
        norm = {k: round(v / total_w * 100, 1) if total_w else 0.0 for k, v in buckets.items()}
        gyw = norm["绿"] + norm["黄"]
        result["quality_summary"] = {
            "weight_by_rating_pct": norm,
            "green_yellow_pct": gyw,
            "verdict": (
                f"前7大重仓中约 {gyw:.0f}% 权重为绿/黄评级，" +
                ("底层质地中上" if gyw >= 60 else "质地中等，分化明显" if gyw >= 40 else "底层质地偏弱")
            )
        }

    # 7. 综合诊断
    result["diagnosis"] = diagnose(result)

    print(f"    ✓ {result['official_name']} → 建议: {result['diagnosis']['action']}")
    return result


def main():
    print(f"\n== 玄枢Alpha · 主动基金诊断 [{datetime.now().strftime('%H:%M:%S')}] ==\n")

    with open(PORTFOLIO, encoding="utf-8") as f:
        portfolio = json.load(f)

    active_holdings = [h for h in portfolio["holdings"] if h.get("assetType") == "active"]
    if not active_holdings:
        print("  未发现 assetType=active 的持仓，退出")
        return

    print(f"  待诊断: {[h['code'] for h in active_holdings]}\n")
    print(f"  value_compass 穿透逻辑: {'已加载' if VC_AVAILABLE else '未加载（跳过质地评级）'}\n")

    results = []
    for h in active_holdings:
        result = diagnose_fund(h["code"], h["name"])
        results.append(result)

    output = {
        "updated_at":       datetime.now().strftime("%Y-%m-%d %H:%M"),
        "portfolio_updateTime": portfolio.get("updateTime"),
        "funds":            results,
        "data_availability": {
            "manager_name":        "✅ fund_individual_basic_info_xq",
            "manager_tenure_days": "✅ fund_manager_em（全量列表筛选）",
            "scale_latest":        "✅ fund_individual_basic_info_xq.最新规模",
            "scale_history":       "❌ fund_open_fund_info_em规模变动返回空",
            "performance_ranking": "✅ fund_individual_achievement_xq（同类排名分位）",
            "alpha_vs_csi300":     "✅ 净值走势 + ak.stock_zh_index_daily_em（沪深300）",
            "holdings_top10":      "✅ fund_portfolio_hold_em",
            "stock_quality":       "✅ 复用 value_compass 巴菲特八问（前7大重仓）" if VC_AVAILABLE else "❌ value_compass 未加载",
        },
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存 → {OUT_PATH}")
    print("\n  诊断摘要:")
    for r in results:
        mismatch = " ⚠️名称不符!" if r.get("name_mismatch") else ""
        print(f"  {r['code']} {r['official_name']}{mismatch}")
        print(f"    排名分位: {r.get('rank_percentile_ytd','--')}%  "
              f"Alpha: {r.get('alpha_pct','--')}pt  "
              f"建议: {r['diagnosis']['action']}")


if __name__ == "__main__":
    main()
