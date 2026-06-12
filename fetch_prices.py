import akshare as ak
import json
import os
from datetime import datetime

# ── 从 portfolio.json 动态加载标的，禁止硬编码 ─────────────────────
_ROOT = os.path.dirname(os.path.abspath(__file__))
_PORTFOLIO_PATH = os.path.join(_ROOT, "data", "portfolio.json")

def load_funds():
    """读取 portfolio.json，返回需要拉行情的基金列表（跳过 cash）。"""
    with open(_PORTFOLIO_PATH, encoding="utf-8") as f:
        pf = json.load(f)
    return [
        {"code": h["code"], "name": h["name"]}
        for h in pf.get("holdings", [])
        if h.get("assetType") != "cash"
    ]


def fetch_fund(code: str, name: str) -> dict | None:
    """
    统一用 fund_open_fund_info_em 拉单位净值走势（开放式基金 & ETF联接均适用）。
    返回 {code, name, price, change_pct, updated_at} 或 None（失败时）。
    """
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or len(df) == 0:
            raise ValueError("空数据")
        latest = df.iloc[-1]
        price      = float(latest["单位净值"])
        change_pct = float(latest["日增长率"]) if "日增长率" in df.columns else 0.0
        updated_at = str(latest["净值日期"])
        return {
            "code":       code,
            "name":       name,
            "price":      round(price, 4),
            "change_pct": round(change_pct, 2),
            "updated_at": updated_at,
        }
    except Exception as e:
        print(f"  ✗ {name} ({code}): {e}")
        return None


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始拉取行情...\n")

    funds   = load_funds()
    results = []

    for fund in funds:
        result = fetch_fund(fund["code"], fund["name"])
        if result:
            sign = "+" if result["change_pct"] >= 0 else ""
            print(f"  ✓ {result['name']:28s} {result['code']}  "
                  f"净值 {result['price']:.4f}  "
                  f"涨跌幅 {sign}{result['change_pct']:.2f}%  "
                  f"({result['updated_at']})")
            results.append(result)

    out_path = os.path.join(_ROOT, "data", "prices.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存 {len(results)}/{len(funds)} 条到 {out_path}")
