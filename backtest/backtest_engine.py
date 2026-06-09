#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 策略回测引擎
========================
复用 data/signals.py 信号逻辑（RSI14 / MA5 / MA20 / MACD），对历史价格逐日生成
买卖信号，回测「信号策略」vs「买入持有」基准，输出性能指标和净值曲线。

策略规则（与 data/signals.py 完全对齐）：
  buy_score  >= 3 且 buy  > sell → 买入信号
  sell_score >= 3 且 sell > buy  → 卖出信号
  其余                           → 持有（观望）

评分权重：
  RSI <  30 → buy  +2    RSI >  70 → sell +2
  RSI <  45 → buy  +1    RSI >  60 → sell +1
  MA5 上穿 MA20 (金叉) → buy  +2
  MA5 下穿 MA20 (死叉) → sell +2
  MA5 > MA20 → buy +1    MA5 < MA20 → sell +1
  MACD柱 > 0 → buy +1    MACD柱 < 0 → sell +1

执行规则：
  信号在第 t 日 EOD 产生 → 第 t+1 日收盘价执行（避免当日信号当日成交的盯盘偏差）

输出：backtest/data/backtest.json
"""

import akshare as ak
import json
import os
import time
from datetime import datetime, timedelta

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, "data")
os.makedirs(DATA_DIR, exist_ok=True)

FUNDS = [
    {"code": "000216", "name": "易方达黄金ETF联接C",   "type": "open"},
    {"code": "008585", "name": "天弘AI主题指数C",       "type": "open"},
    {"code": "017766", "name": "南方有色金属ETF联接E",  "type": "open"},
    {"code": "515790", "name": "华夏光伏ETF",           "type": "etf"},
    {"code": "513100", "name": "纳指100ETF",            "type": "etf"},
    {"code": "513500", "name": "标普500ETF",            "type": "etf"},
]

LOOKBACK_YEARS = 3       # 拉取历史年数
RISK_FREE_RATE  = 0.02   # 年化无风险利率（用于夏普计算）
TRADING_DAYS    = 252    # 年化基数


# ── 数据拉取 ─────────────────────────────────────────────────

def fetch_history(fund: dict, years: int = 3):
    """
    拉取基金历史日频价格序列。
    开放式基金用单位净值，ETF 用复权收盘价。
    返回 (dates: list[str], prices: list[float])，按日期升序。
    """
    end   = datetime.today()
    start = end - timedelta(days=years * 365 + 90)   # 多拉 90 天作指标预热缓冲
    start_str = start.strftime("%Y%m%d")
    end_str   = end.strftime("%Y%m%d")

    last_err = None
    for attempt in range(3):
        try:
            if fund["type"] == "open":
                df = ak.fund_open_fund_info_em(symbol=fund["code"], indicator="单位净值走势")
                df = df.sort_values("净值日期").reset_index(drop=True)
                cutoff = start.strftime("%Y-%m-%d")
                df = df[df["净值日期"].astype(str) >= cutoff]
                dates  = [str(d) for d in df["净值日期"].tolist()]
                prices = df["单位净值"].astype(float).tolist()
            else:
                # 主接口：fund_etf_hist_em（东方财富，列名：日期/收盘）
                try:
                    df = ak.fund_etf_hist_em(
                        symbol=fund["code"], period="daily",
                        start_date=start_str, end_date=end_str,
                        adjust="qfq"
                    )
                    df = df.sort_values("日期").reset_index(drop=True)
                    dates  = [str(d) for d in df["日期"].tolist()]
                    prices = df["收盘"].astype(float).tolist()
                except Exception:
                    # 备用接口：fund_etf_hist_sina（新浪，列名：date/close）
                    # 对 513100、513500 等频繁被主接口超时的 ETF 尤其有效
                    df = ak.fund_etf_hist_sina(symbol="sh" + fund["code"])
                    df = df.sort_values("date").reset_index(drop=True)
                    cutoff = start.strftime("%Y-%m-%d")
                    df = df[df["date"].astype(str) >= cutoff]
                    dates  = [str(d) for d in df["date"].tolist()]
                    prices = df["close"].astype(float).tolist()
            return dates, prices
        except Exception as e:
            last_err = e
            time.sleep(2)

    raise RuntimeError(f"{fund['code']} 数据拉取失败（3次重试）: {repr(last_err)[:120]}")


# ── 指标计算（与 data/indicators.py 完全对齐）─────────────────

def calc_rsi_series(prices: list, period: int = 14) -> list:
    """对整个序列逐日计算 RSI，预热期返回 None。"""
    n = len(prices)
    result = [None] * n
    if n < period + 1:
        return result

    changes = [prices[i] - prices[i - 1] for i in range(1, n)]
    gains   = [max(c, 0.0) for c in changes]
    losses  = [max(-c, 0.0) for c in changes]

    avg_gain = sum(gains[:period]) / period
    avg_loss = sum(losses[:period]) / period

    for i in range(period, len(changes)):
        avg_gain = (avg_gain * (period - 1) + gains[i]) / period
        avg_loss = (avg_loss * (period - 1) + losses[i]) / period
        if avg_loss == 0:
            result[i + 1] = 100.0
        else:
            rs = avg_gain / avg_loss
            result[i + 1] = round(100 - 100 / (1 + rs), 4)

    return result


def calc_ma_series(prices: list, period: int) -> list:
    """简单移动平均，预热期返回 None。"""
    n = len(prices)
    result = [None] * n
    for i in range(period - 1, n):
        result[i] = sum(prices[i - period + 1 : i + 1]) / period
    return result


def calc_macd_hist_series(prices: list,
                           fast: int = 12, slow: int = 26, signal: int = 9) -> list:
    """MACD 柱状值序列，预热期返回 None。"""
    n = len(prices)
    result = [None] * n
    min_len = slow + signal
    if n < min_len:
        return result

    k_fast = 2 / (fast + 1)
    k_slow = 2 / (slow + 1)
    k_sig  = 2 / (signal + 1)

    ema_fast = sum(prices[:fast]) / fast
    ema_slow = sum(prices[:slow]) / slow
    dif_list = []   # (price_index, dif_value)

    for i in range(slow, n):
        ema_fast = prices[i] * k_fast + ema_fast * (1 - k_fast)
        ema_slow = prices[i] * k_slow + ema_slow * (1 - k_slow)
        dif_list.append((i, ema_fast - ema_slow))

    if len(dif_list) < signal:
        return result

    dea = sum(d[1] for d in dif_list[:signal]) / signal
    for j, (i, dif) in enumerate(dif_list):
        if j < signal:
            continue
        dea = dif * k_sig + dea * (1 - k_sig)
        result[i] = (dif - dea) * 2   # MACD 柱 = (DIF - DEA) * 2

    return result


# ── 信号生成（与 data/signals.py 完全对齐）────────────────────

WARMUP = 36   # 预热期天数（slow=26 + signal=9 + 1 = 36，保守取）


def generate_daily_signals(prices: list) -> list:
    """
    逐日生成 'buy' / 'sell' / 'hold' 信号；预热期返回 None。
    信号产生时刻：day t EOD；执行时刻：day t+1（在 run_backtest 中处理）。
    """
    n = len(prices)
    rsi_s  = calc_rsi_series(prices, 14)
    ma5_s  = calc_ma_series(prices, 5)
    ma20_s = calc_ma_series(prices, 20)
    macd_s = calc_macd_hist_series(prices)

    signals = [None] * n

    for i in range(WARMUP, n):
        rsi       = rsi_s[i]
        ma5       = ma5_s[i]
        ma20      = ma20_s[i]
        prev_ma5  = ma5_s[i - 1]
        prev_ma20 = ma20_s[i - 1]
        macd_hist = macd_s[i]

        # 数据不完整时跳过
        if any(v is None for v in [rsi, ma5, ma20, prev_ma5, prev_ma20, macd_hist]):
            signals[i] = "hold"
            continue

        buy_score = sell_score = 0

        # RSI 维度
        if rsi < 30:
            buy_score += 2
        elif rsi > 70:
            sell_score += 2
        elif rsi < 45:
            buy_score += 1
        elif rsi > 60:
            sell_score += 1

        # MA 金叉/死叉 + 多空头
        golden_cross = prev_ma5 < prev_ma20 and ma5 >= ma20
        death_cross  = prev_ma5 > prev_ma20 and ma5 <= ma20
        if golden_cross:
            buy_score += 2
        elif death_cross:
            sell_score += 2
        elif ma5 > ma20:
            buy_score += 1
        else:
            sell_score += 1

        # MACD 柱方向
        if macd_hist > 0:
            buy_score += 1
        else:
            sell_score += 1

        if buy_score >= 3 and buy_score > sell_score:
            signals[i] = "buy"
        elif sell_score >= 3 and sell_score > buy_score:
            signals[i] = "sell"
        else:
            signals[i] = "hold"

    return signals


# ── 回测引擎 ─────────────────────────────────────────────────

def run_backtest(prices: list, signals: list):
    """
    长多策略回测。
      - 信号为 'buy'  且当前空仓 → 第二日入场（以第二日收盘价建仓）
      - 信号为 'sell' 且当前持仓 → 第二日离场（以第二日收盘价平仓）
      - 若持仓到末日仍未收到卖出信号，按末日收盘价强制平仓

    返回 (strategy_nav, benchmark_nav, trades)
      strategy_nav: list[float], 从1.0开始
      benchmark_nav: list[float], 从1.0开始
      trades: list[dict]  每笔完整交易记录
    """
    n = len(prices)
    strategy_nav = [1.0] * n

    in_position  = False
    entry_price  = 0.0
    base_nav     = 1.0   # 上次建仓或平仓时的净值
    entry_day    = -1
    pending      = None  # 'buy' / 'sell' —— 昨日信号，今日执行

    trades = []

    for i in range(n):
        # ── 执行上一日信号 ──
        if pending == "buy" and not in_position:
            in_position = True
            entry_price = prices[i]
            entry_day   = i
            base_nav    = strategy_nav[i - 1] if i > 0 else 1.0
            pending     = None

        elif pending == "sell" and in_position:
            exit_ret = prices[i] / entry_price
            trade_ret_pct = round((exit_ret - 1) * 100, 3)
            cash_nav = base_nav * exit_ret
            trades.append({
                "buy_day":      entry_day,
                "sell_day":     i,
                "buy_price":    round(entry_price, 6),
                "sell_price":   round(prices[i], 6),
                "return_pct":   trade_ret_pct,
            })
            in_position = False
            base_nav    = cash_nav
            entry_price = 0.0
            pending     = None

        # ── 更新今日净值 ──
        if in_position:
            strategy_nav[i] = base_nav * (prices[i] / entry_price)
        else:
            strategy_nav[i] = base_nav

        # ── 记录今日信号，留给明日执行 ──
        sig = signals[i]
        if sig == "buy"  and not in_position:
            pending = "buy"
        elif sig == "sell" and in_position:
            pending = "sell"
        # hold / None → pending 不变（不要覆盖已有的 pending）

    # ── 收盘时仍持仓 → 以最后一日价格计入，但不强制平仓（保留开放头寸） ──
    # strategy_nav[-1] 已在循环中按持仓价更新，无需额外处理

    # ── 基准：买入持有，归一化至1.0 ──
    p0 = prices[0]
    benchmark_nav = [round(prices[i] / p0, 6) for i in range(n)]

    return strategy_nav, benchmark_nav, trades


# ── 绩效指标 ─────────────────────────────────────────────────

def compute_metrics(nav: list) -> dict:
    """从净值序列计算年化收益、最大回撤、夏普比率。"""
    n = len(nav)
    if n < 2:
        return {"total_return_pct": 0.0, "annual_return_pct": 0.0,
                "max_drawdown_pct": 0.0, "sharpe": 0.0}

    total_ret = nav[-1] / nav[0] - 1
    years     = n / TRADING_DAYS
    ann_ret   = ((1 + total_ret) ** (1 / years) - 1) if years > 0 else 0.0

    # 最大回撤
    peak   = nav[0]
    max_dd = 0.0
    for v in nav:
        if v > peak:
            peak = v
        dd = (peak - v) / peak if peak > 0 else 0.0
        if dd > max_dd:
            max_dd = dd

    # 夏普（日收益序列）
    daily_rets = [(nav[i] / nav[i - 1]) - 1 for i in range(1, n)]
    if daily_rets:
        avg_dr = sum(daily_rets) / len(daily_rets)
        var    = sum((r - avg_dr) ** 2 for r in daily_rets) / len(daily_rets)
        std_dr = var ** 0.5
        rf_d   = RISK_FREE_RATE / TRADING_DAYS
        sharpe = ((avg_dr - rf_d) / std_dr * TRADING_DAYS ** 0.5) if std_dr > 0 else 0.0
    else:
        sharpe = 0.0

    return {
        "total_return_pct":  round(total_ret   * 100, 2),
        "annual_return_pct": round(ann_ret      * 100, 2),
        "max_drawdown_pct":  round(-max_dd      * 100, 2),  # 负数表示回撤幅度
        "sharpe":            round(sharpe, 2),
    }


def compute_trade_metrics(trades: list) -> dict:
    """统计胜率和交易笔数。"""
    if not trades:
        return {"win_rate_pct": 0.0, "trade_count": 0}
    win_count = sum(1 for t in trades if t["return_pct"] > 0)
    return {
        "win_rate_pct": round(win_count / len(trades) * 100, 1),
        "trade_count":  len(trades),
    }


# ── 降采样（减小 JSON 体积）────────────────────────────────────

def downsample(dates: list, series_list: list, target: int = 120):
    """
    将数据降采样至约 target 个点。
    返回 (ds_dates, [ds_series1, ds_series2, ...])
    """
    n = len(dates)
    if n <= target:
        return dates, series_list
    step = max(1, n // target)
    indices = list(range(0, n, step))
    if indices[-1] != n - 1:
        indices.append(n - 1)
    ds_dates = [dates[i] for i in indices]
    ds_series = [[s[i] for i in indices] for s in series_list]
    return ds_dates, ds_series


# ── 主流程 ────────────────────────────────────────────────────

def main():
    print(f"== 玄枢Alpha · 策略回测引擎 [{datetime.now().strftime('%H:%M:%S')}] ==")
    print(f"   信号逻辑: RSI14 / MA5/MA20 金叉死叉 / MACD柱  |  回测年限: {LOOKBACK_YEARS}年\n")

    results = []

    for fund in FUNDS:
        print(f"--- {fund['name']} ({fund['code']}) ---")

        # 1. 拉取历史数据
        try:
            dates, prices = fetch_history(fund, years=LOOKBACK_YEARS)
        except Exception as e:
            print(f"  ✗ 拉取失败: {e}")
            continue

        if len(prices) < WARMUP + 30:
            print(f"  ✗ 数据不足 ({len(prices)} 天，需 >{WARMUP + 30} 天)")
            continue

        print(f"  数据: {dates[0]} ~ {dates[-1]} ({len(dates)} 天)")

        # 2. 逐日生成信号
        signals = generate_daily_signals(prices)

        # 3. 运行回测
        strategy_nav, benchmark_nav, trades = run_backtest(prices, signals)

        # 4. 从预热结束日起切片，双边归一化到1.0
        act_start = WARMUP
        s_nav_raw = strategy_nav[act_start:]
        b_nav_raw = benchmark_nav[act_start:]
        d_slice   = dates[act_start:]

        s0 = s_nav_raw[0] if s_nav_raw[0] else 1.0
        b0 = b_nav_raw[0] if b_nav_raw[0] else 1.0
        s_nav_norm = [round(v / s0, 6) for v in s_nav_raw]
        b_nav_norm = [round(v / b0, 6) for v in b_nav_raw]

        # 5. 绩效指标
        s_metrics = compute_metrics(s_nav_norm)
        b_metrics = compute_metrics(b_nav_norm)
        t_metrics = compute_trade_metrics(trades)

        # 6. 降采样净值曲线
        ds_dates, ds_series = downsample(d_slice, [s_nav_norm, b_nav_norm], target=150)
        ds_strategy, ds_benchmark = ds_series

        # 7. 汇总
        results.append({
            "code":         fund["code"],
            "name":         fund["name"],
            "period_start": d_slice[0],
            "period_end":   d_slice[-1],
            "data_days":    len(d_slice),
            "metrics": {
                "strategy":  {**s_metrics, **t_metrics},
                "benchmark": b_metrics,
            },
            "nav_curve": {
                "dates":     ds_dates,
                "strategy":  [round(v, 4) for v in ds_strategy],
                "benchmark": [round(v, 4) for v in ds_benchmark],
            },
        })

        # 打印摘要
        s = s_metrics
        b = b_metrics
        alpha = round(s["annual_return_pct"] - b["annual_return_pct"], 1)
        sign  = "+" if alpha >= 0 else ""
        print(f"  策略: 年化{s['annual_return_pct']:+.1f}%  回撤{s['max_drawdown_pct']:.1f}%  "
              f"夏普{s['sharpe']:.2f}  胜率{t_metrics['win_rate_pct']:.0f}%  "
              f"{t_metrics['trade_count']}笔交易")
        print(f"  基准: 年化{b['annual_return_pct']:+.1f}%  回撤{b['max_drawdown_pct']:.1f}%  "
              f"夏普{b['sharpe']:.2f}  Alpha: {sign}{alpha}pt")

    # 输出 JSON
    output = {
        "updated_at":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "strategy_desc":   "RSI14/MA5/MA20/MACD 综合信号策略（买入持有≥3分确认，卖出≥3分确认；信号t日EOD产生，t+1日执行）",
        "benchmark_desc":  "买入持有基准（全程持有不操作，归一化至1.0）",
        "risk_free_rate_pct": RISK_FREE_RATE * 100,
        "lookback_years":  LOOKBACK_YEARS,
        "results":         results,
    }

    out_path = os.path.join(DATA_DIR, "backtest.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 回测完成 → {out_path}")
    print(f"   {len(results)}/{len(FUNDS)} 个标的成功")


if __name__ == "__main__":
    main()
