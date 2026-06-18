#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 组合历史市值计算
=============================
用 nav.json 各基金每日净值 × portfolio.json 持仓金额，
计算最近60交易日的每日组合总市值，输出 data/portfolio_history.json。

用法：
    python3 data/portfolio_history.py
输出：
    data/portfolio_history.json
"""

import json
import os
from datetime import datetime

BASE_DIR    = os.path.dirname(os.path.abspath(__file__))
NAV_PATH    = os.path.join(BASE_DIR, "nav.json")
PORT_PATH   = os.path.join(BASE_DIR, "portfolio.json")
OUT_PATH    = os.path.join(BASE_DIR, "portfolio_history.json")


def main():
    nav_data  = json.load(open(NAV_PATH,  encoding="utf-8"))
    portfolio = json.load(open(PORT_PATH, encoding="utf-8"))

    funds_nav = nav_data.get("funds", {})
    holdings  = portfolio.get("holdings", [])

    # 货币基金视为固定面值 1.0，不纳入涨跌计算（持面值）
    # 每只基金：entry_nav = nav.json 第一个值（视为建仓参考）；持仓金额 = portfolio.amount
    # 每日总市值 = sum(holding.amount * (nav_i / nav_0)) for each fund that has nav data

    # 收集所有基金的 dates 序列，取交集（对齐日期）
    fund_series = {}  # code -> {date: nav}
    for h in holdings:
        code = str(h.get("code", "")).strip()
        entry = funds_nav.get(code)
        if not entry:
            continue
        dates = entry.get("dates", [])
        navs  = entry.get("navs",  [])
        if len(dates) != len(navs) or not dates:
            continue
        fund_series[code] = dict(zip(dates, navs))

    if not fund_series:
        print("  nav.json 中没有可用的基金净值序列，跳过")
        return

    # 所有基金都有净值的日期集合（交集）
    all_dates_sets = [set(v.keys()) for v in fund_series.values()]
    common_dates = sorted(set.intersection(*all_dates_sets) if all_dates_sets else set())

    # 取最近60个交易日
    common_dates = common_dates[-60:]

    if not common_dates:
        print("  没有公共日期，跳过")
        return

    # 对每只基金，以第一个公共日期的净值为基准，计算相对涨跌
    base_navs = {}  # code -> nav at first date
    for code, nav_map in fund_series.items():
        base_nav = nav_map.get(common_dates[0])
        if base_nav:
            base_navs[code] = float(base_nav)

    # 持仓金额映射
    amount_map = {str(h.get("code","")).strip(): float(h.get("amount", 0)) for h in holdings}

    # 计算每日组合总市值
    series = []
    for date in common_dates:
        total = 0.0
        for code, nav_map in fund_series.items():
            nav_today = nav_map.get(date)
            base_nav  = base_navs.get(code)
            amount    = amount_map.get(code, 0)
            if nav_today is not None and base_nav and base_nav > 0 and amount > 0:
                # 市值 = 持仓金额 × (今日净值 / 基准净值)
                total += amount * (float(nav_today) / base_nav)
        series.append({"date": date, "value": round(total, 2)})

    # 计算区间收益率
    start_val   = series[0]["value"]  if series else 0
    current_val = series[-1]["value"] if series else 0
    ret_pct     = round((current_val - start_val) / start_val * 100, 2) if start_val else 0

    output = {
        "updated_at":    datetime.now().strftime("%Y-%m-%d"),
        "start_value":   round(start_val, 2),
        "current_value": round(current_val, 2),
        "return_pct":    ret_pct,
        "series":        series,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"  组合历史市值: {len(series)} 个交易日  起始={start_val:.0f}  当前={current_val:.0f}  "
          f"区间收益率={ret_pct:+.2f}%")
    print(f"  写入 -> {OUT_PATH}")


if __name__ == "__main__":
    main()
