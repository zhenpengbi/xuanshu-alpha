import akshare as ak
import json
import os
from datetime import datetime, timedelta

# ── 从 portfolio.json 动态加载标的，禁止硬编码 ─────────────────────
_DIR  = os.path.dirname(os.path.abspath(__file__))          # data/
_ROOT = os.path.dirname(_DIR)                               # 项目根

def load_funds():
    """读取 portfolio.json，返回需要计算指标的基金列表（跳过 cash）。"""
    path = os.path.join(_DIR, "portfolio.json")
    with open(path, encoding="utf-8") as f:
        pf = json.load(f)
    return [
        {"code": h["code"], "name": h["name"]}
        for h in pf.get("holdings", [])
        if h.get("assetType") != "cash"
    ]


def fetch_price_series(code: str, trading_days: int = 60) -> list[float]:
    """
    用 fund_open_fund_info_em 拉单位净值走势，取最近 trading_days 个交易日数据。
    开放式基金与 ETF联接均适用（统一接口，无需区分类型）。
    """
    df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
    if df is None or len(df) == 0:
        raise ValueError(f"{code}: 净值走势返回空")
    df = df.sort_values("净值日期")
    prices = df["单位净值"].astype(float).tolist()
    return prices[-trading_days:]


def calc_rsi(prices, period=14):
    if len(prices) < period + 1:
        return None
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains   = [max(c, 0) for c in changes]
    losses  = [max(-c, 0) for c in changes]
    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period
    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
    if avg_loss == 0:
        return 100.0
    rs = avg_gain / avg_loss
    return round(100 - (100 / (1 + rs)), 2)


def calc_ma(prices, period):
    if len(prices) < period:
        return None
    return round(sum(prices[-period:]) / period, 6)


def calc_ema(prices, period):
    if len(prices) < period:
        return None
    k = 2 / (period + 1)
    ema = sum(prices[:period]) / period
    for p in prices[period:]:
        ema = p * k + ema * (1 - k)
    return ema


def calc_macd(prices, fast=12, slow=26, signal=9):
    if len(prices) < slow + signal:
        return None, None, None
    k_fast = 2 / (fast + 1)
    k_slow = 2 / (slow + 1)
    k_sig  = 2 / (signal + 1)
    ema_fast = sum(prices[:fast]) / fast
    ema_slow = sum(prices[:slow]) / slow
    dif_vals = []
    for i in range(slow, len(prices)):
        ema_fast = prices[i] * k_fast + ema_fast * (1 - k_fast)
        ema_slow = prices[i] * k_slow + ema_slow * (1 - k_slow)
        dif_vals.append(ema_fast - ema_slow)
    if len(dif_vals) < signal:
        return None, None, None
    dea = sum(dif_vals[:signal]) / signal
    for d in dif_vals[signal:]:
        dea = d * k_sig + dea * (1 - k_sig)
    dif  = dif_vals[-1]
    hist = round((dif - dea) * 2, 8)
    return round(dif, 8), round(dea, 8), hist


if __name__ == "__main__":
    print(f"[{datetime.now().strftime('%H:%M:%S')}] 开始计算技术指标...\n")

    funds   = load_funds()
    results = []

    for fund in funds:
        code, name = fund["code"], fund["name"]
        print(f"  处理 {name} ({code})...")
        try:
            prices = fetch_price_series(code, trading_days=60)
            if len(prices) < 26:
                print(f"    ✗ 数据不足 ({len(prices)} 条，需≥26)")
                continue

            rsi        = calc_rsi(prices)
            ma5        = calc_ma(prices, 5)
            ma20       = calc_ma(prices, 20)
            prev_ma5   = calc_ma(prices[:-1], 5)  if len(prices) > 5  else None
            prev_ma20  = calc_ma(prices[:-1], 20) if len(prices) > 20 else None
            macd_dif, macd_dea, macd_hist = calc_macd(prices)
            macd_trend = "bullish" if macd_hist and macd_hist > 0 else "bearish"

            result = {
                "code":         code,
                "name":         name,
                "rsi14":        rsi,
                "ma5":          ma5,
                "ma20":         ma20,
                "prev_ma5":     prev_ma5,
                "prev_ma20":    prev_ma20,
                "macd_dif":     macd_dif,
                "macd_dea":     macd_dea,
                "macd_hist":    macd_hist,
                "macd_trend":   macd_trend,
                "latest_price": round(prices[-1], 6),
                "prices_used":  len(prices),
            }
            results.append(result)
            print(f"    ✓ RSI={rsi}  MA5={ma5}  MA20={ma20}  MACD_hist={macd_hist}")

        except Exception as e:
            print(f"    ✗ 错误: {e}")

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "indicators": results,
    }
    out_path = os.path.join(_DIR, "indicators.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已保存 {len(results)}/{len(funds)} 条到 {out_path}")
