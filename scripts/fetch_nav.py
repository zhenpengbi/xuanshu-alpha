#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""玄枢Alpha 基金历史净值抓取
读取 data/portfolio.json 中的持仓基金，抓取最近 N 个交易日单位净值，
输出 data/nav.json 供前端净值曲线 sparkline 使用。
货币基金（嘉实货币E 001812 等无单位净值走势）跳过。
"""
import json
import os
import sys

import akshare as ak

BASE = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
PORTFOLIO = os.path.join(BASE, "data", "portfolio.json")
OUT = os.path.join(BASE, "data", "nav.json")
DAYS = 60  # 取最近 N 个交易日

# 货币基金 / 无单位净值走势的 code 跳过
SKIP_CODES = {"001812"}  # 嘉实货币E（货币基金，无单位净值走势）


def fetch_one(code):
    df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    df = df.tail(DAYS)
    navs = [round(float(x), 4) for x in df["单位净值"].tolist()]
    dates = [str(d) for d in df["净值日期"].tolist()]
    return {
        "navs": navs,
        "dates": dates,
        "first": navs[0],
        "last": navs[-1],
        "change": round((navs[-1] / navs[0] - 1) * 100, 2) if navs[0] else 0,
    }


def main():
    with open(PORTFOLIO, "r", encoding="utf-8") as f:
        portfolio = json.load(f)

    result = {}
    for h in portfolio["holdings"]:
        code = h["code"]
        name = h["name"]
        if code in SKIP_CODES:
            print(f"  skip  {code} {name} (货币基金)")
            continue
        try:
            data = fetch_one(code)
            result[code] = data
            print(f"  ok    {code} {name}  {data['dates'][-1]} 净值={data['last']} 区间{data['change']:+.2f}%")
        except Exception as e:
            print(f"  FAIL  {code} {name}: {e}", file=sys.stderr)

    out = {
        "updated": result and result[list(result)[0]]["dates"][-1] or "",
        "days": DAYS,
        "funds": result,
    }
    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(out, f, ensure_ascii=False, indent=2)
    print(f"\n✅ 写入 {OUT}（{len(result)} 只基金）")


if __name__ == "__main__":
    main()
