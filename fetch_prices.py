import akshare as ak
import json
from datetime import datetime

FUNDS = [
    {"code": "000216", "name": "易方达黄金ETF联接C",   "type": "open"},
    {"code": "008585", "name": "天弘AI主题指数C",       "type": "open"},
    {"code": "017766", "name": "南方有色金属ETF联接E",  "type": "open"},
    {"code": "515790", "name": "华夏光伏ETF",           "type": "etf"},
    {"code": "513100", "name": "纳指100ETF",            "type": "etf"},
    {"code": "513500", "name": "标普500ETF",            "type": "etf"},
]


def fetch_open_fund(code, name):
    df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    latest = df.iloc[-1]
    price = float(latest["单位净值"])
    change_pct = float(latest["日增长率"]) if "日增长率" in df.columns else 0.0
    updated_at = str(latest["净值日期"])
    return {
        "code": code,
        "name": name,
        "price": round(price, 4),
        "change_pct": round(change_pct, 2),
        "updated_at": updated_at,
    }


def fetch_etf_spot(code, name):
    df = ak.fund_etf_spot_em()
    row = df[df["代码"] == code]
    if row.empty:
        raise ValueError(f"ETF {code} not found in spot data")
    r = row.iloc[0]
    return {
        "code": code,
        "name": name,
        "price": round(float(r["最新价"]), 4),
        "change_pct": round(float(r["涨跌幅"]), 2),
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }


# 缓存 ETF 实时表，避免重复请求
_etf_spot_df = None

def fetch(fund):
    global _etf_spot_df
    try:
        if fund["type"] == "open":
            return fetch_open_fund(fund["code"], fund["name"])
        else:
            if _etf_spot_df is None:
                _etf_spot_df = ak.fund_etf_spot_em()
            row = _etf_spot_df[_etf_spot_df["代码"] == fund["code"]]
            if row.empty:
                raise ValueError(f"ETF {fund['code']} not found")
            r = row.iloc[0]
            return {
                "code": fund["code"],
                "name": fund["name"],
                "price": round(float(r["最新价"]), 4),
                "change_pct": round(float(r["涨跌幅"]), 2),
                "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
            }
    except Exception as e:
        print(f"  ✗ {fund['name']} ({fund['code']}): {e}")
        return None


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始拉取行情...\n")
    results = []
    for fund in FUNDS:
        result = fetch(fund)
        if result:
            sign = "+" if result["change_pct"] >= 0 else ""
            print(f"  ✓ {result['name']:20s} {result['code']}  "
                  f"净值/价格 {result['price']:.4f}  "
                  f"涨跌幅 {sign}{result['change_pct']:.2f}%  "
                  f"({result['updated_at']})")
            results.append(result)

    out_path = "data/prices.json"
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存 {len(results)}/{len(FUNDS)} 条到 {out_path}")
