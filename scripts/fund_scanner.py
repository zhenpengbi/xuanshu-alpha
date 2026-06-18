#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 基金雷达（超跌 ETF 扫描推荐）
==========================================
当市场恐慌情绪高位时（signals.json 平均 sell_score ≥ 阈值），
主动扫描超跌 ETF，辅助发现抄底/反弹机会。

筛选逻辑：
  1. 恐慌触发：avg_sell_score >= PANIC_THRESHOLD (默认 2.0)
     否则输出空列表 + "当前无超跌机会"
  2. ETF 池：A 股主流 ETF（fund_etf_spot_em）
  3. 规模过滤：流通市值 >= MIN_SCALE_BILLION 亿元（默认 5）
  4. 排除：已持仓的6只标的
  5. 近20日跌幅 >= DROP_THRESHOLD (默认 15%)
     → 为控制 API 请求数，先按今日涨跌幅排序取前 TOP_CANDIDATES 只，
       再逐一拉取20日历史计算真实跌幅
  6. 技术得分：RSI14 < 35 → 超跌反弹信号；否则 → 继续观望

输出：data/fund_recommendations.json

用法：
    python3 scripts/fund_scanner.py
    python3 scripts/fund_scanner.py --force   # 跳过恐慌触发条件强制扫描

依赖：
    pip install akshare pandas  （已在项目依赖中）
"""

import argparse
import json
import os
import time
from datetime import datetime, timedelta

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT         = os.path.dirname(SCRIPT_DIR)
SIGNALS_JSON = os.path.join(ROOT, "data", "signals.json")
PORTFOLIO_JSON = os.path.join(ROOT, "data", "portfolio.json")
OUT_PATH     = os.path.join(ROOT, "data", "fund_recommendations.json")

# ── 可调参数 ──────────────────────────────────────────────────
PANIC_THRESHOLD    = 2.0   # 平均 sell_score 触发门槛
MIN_SCALE_BILLION  = 5.0   # 最小规模（亿元）（恐慌深度扫描）
MIN_SCALE_UNDERVAL = 3.0   # 最小规模（亿元）（低估常态扫描）
DROP_THRESHOLD     = 15.0  # 近20日跌幅门槛（%）（恐慌深度扫描）
DROP_THRESHOLD_UV  = 10.0  # 近60日跌幅门槛（%）（低估常态扫描）
RSI_OVERSOLD_UV    = 40    # RSI 低估门槛（低估常态扫描）
TOP_CANDIDATES     = 40    # 初筛候选数（按今日跌幅排序）
MAX_RECOMMENDATIONS = 8    # 最终推荐条数
MAX_UNDERVALUED    = 8     # 低估扫描最终条数


# ── 工具函数 ─────────────────────────────────────────────────

def load_current_holdings() -> set:
    """从 portfolio.json 动态读取所有持仓基金代码，返回 set。"""
    if not os.path.exists(PORTFOLIO_JSON):
        print("  ⚠️ portfolio.json 未找到，持仓排除集合为空")
        return set()
    try:
        with open(PORTFOLIO_JSON, "r", encoding="utf-8") as f:
            d = json.load(f)
        holdings = d.get("holdings", [])
        codes = {str(h.get("code", "")).strip() for h in holdings if h.get("code")}
        print(f"  已持仓标的（排除）: {sorted(codes)}")
        return codes
    except Exception as e:
        print(f"  ⚠️ portfolio.json 解析失败: {e}")
        return set()


def load_signals() -> dict:
    """读取 signals.json，返回 avg_sell_score 和详细数据。"""
    if not os.path.exists(SIGNALS_JSON):
        return {"avg_sell_score": 0, "signals": []}
    with open(SIGNALS_JSON, "r", encoding="utf-8") as f:
        d = json.load(f)
    sigs = d.get("signals", [])
    avg = sum(s.get("sell_score", 0) for s in sigs) / len(sigs) if sigs else 0
    return {"avg_sell_score": round(avg, 2), "signals": sigs}


def calc_rsi(prices: list, period: int = 14) -> float | None:
    """计算 RSI(14)，数据不足时返回 None。"""
    if len(prices) < period + 1:
        return None
    changes = [prices[i] - prices[i - 1] for i in range(1, len(prices))]
    gains   = [max(c, 0) for c in changes]
    losses  = [max(-c, 0) for c in changes]
    avg_g = sum(gains[:period]) / period
    avg_l = sum(losses[:period]) / period
    for i in range(period, len(changes)):
        avg_g = (avg_g * (period - 1) + gains[i]) / period
        avg_l = (avg_l * (period - 1) + losses[i]) / period
    return round(100 - 100 / (1 + avg_g / avg_l), 2) if avg_l else 100.0


def fetch_etf_history(code: str, days: int = 25) -> list[float] | None:
    """
    拉取 ETF 历史收盘价序列。
    days: 目标获取天数（交易日），为保证 RSI 预热会多取若干天。
    先尝试 fund_etf_hist_em（东方财富），失败则用 fund_etf_hist_sina。
    """
    import akshare as ak
    end   = datetime.today()
    # 按日历天数估算：交易日约为日历天的 2/3，多留50%余量
    calendar_days = max(45, int(days * 2.2))
    start = end - timedelta(days=calendar_days)
    start_str = start.strftime("%Y%m%d")
    end_str   = end.strftime("%Y%m%d")
    try:
        df = ak.fund_etf_hist_em(
            symbol=code, period="daily",
            start_date=start_str, end_date=end_str, adjust="qfq"
        )
        prices = df.sort_values("日期")["收盘"].astype(float).tolist()[-days:]
        return prices if len(prices) >= 5 else None
    except Exception:
        pass
    try:
        df = ak.fund_etf_hist_sina(symbol="sh" + code)
        cutoff = start.strftime("%Y-%m-%d")
        df = df[df["date"].astype(str) >= cutoff].sort_values("date")
        prices = df["close"].astype(float).tolist()[-days:]
        return prices if len(prices) >= 5 else None
    except Exception:
        return None


def fetch_etf_history_20d(code: str) -> list[float] | None:
    """向后兼容别名：拉取近25日价格（用于恐慌深度扫描）。"""
    return fetch_etf_history(code, days=25)


def compute_drop(prices: list, window: int = 20) -> float | None:
    """从价格序列计算近 window 日跌幅（正数 = 跌幅）。"""
    if len(prices) < 2:
        return None
    use = prices[-min(window, len(prices)):]
    drop_pct = (use[0] - use[-1]) / use[0] * 100  # 正 = 跌
    return round(drop_pct, 2)


def compute_drop_20d(prices: list) -> float | None:
    """向后兼容别名：近20日跌幅。"""
    return compute_drop(prices, window=20)


def parse_scale(val) -> float:
    """
    从 fund_etf_spot_em 的 流通市值/总市值 字段解析亿元数值。
    东方财富接口单位为元（如 13022554679），转换为亿元 = 除以1e8。
    """
    if val is None:
        return 0.0
    try:
        v = float(str(val).replace(",", "").strip())
        # fund_etf_spot_em 返回的是元为单位的整数/浮点
        return round(v / 1e8, 4)
    except (ValueError, TypeError):
        return 0.0


# ── ETF行情数据获取（公共逻辑）─────────────────────────────────

def _fetch_etf_spot_df(current_holdings: set):
    """
    拉取全市场 ETF 行情 DataFrame，解析规模列、排除已持仓，返回处理后的 df。
    返回 (df, code_col, name_col, scale_col_ok) 或 (None, ...) 失败时。
    """
    import akshare as ak
    import pandas as pd

    print("  获取 ETF 行情数据...")
    try:
        df = ak.fund_etf_spot_em()
    except Exception as e:
        print(f"  ✗ fund_etf_spot_em 失败: {e}")
        return None, None, None

    print(f"  共 {len(df)} 只 ETF")
    code_col = "代码" if "代码" in df.columns else df.columns[0]
    name_col = next((c for c in df.columns if "名称" in c or "简称" in c), None)

    # 规模字段
    scale_col = next(
        (c for c in df.columns if "市值" in c or "规模" in c or "净资产" in c),
        None
    )
    if scale_col:
        df["_scale_bn"] = df[scale_col].apply(parse_scale)
    else:
        print(f"  ⚠️ 未找到规模字段（{list(df.columns[:8])}…），跳过规模过滤")
        df["_scale_bn"] = 0.0

    # 排除已持仓
    df = df[~df[code_col].isin(current_holdings)]

    # 今日涨跌幅列
    change_col = next((c for c in df.columns if "涨跌幅" in c), None)
    if change_col:
        df["_chg"] = pd.to_numeric(df[change_col], errors="coerce").fillna(0)
    else:
        df["_chg"] = 0.0

    return df, code_col, name_col


# ── 主流程 ────────────────────────────────────────────────────

def scan_etfs(current_holdings: set) -> list[dict]:
    """恐慌深度扫描逻辑（近20日跌幅 >= DROP_THRESHOLD，RSI<35），返回推荐列表。"""
    df, code_col, name_col = _fetch_etf_spot_df(current_holdings)
    if df is None:
        return []

    # ── 规模过滤（恐慌扫描标准：5亿）──
    df = df[df["_scale_bn"] >= MIN_SCALE_BILLION]
    print(f"  规模 >= {MIN_SCALE_BILLION}亿：{len(df)} 只")

    # ── 今日涨跌幅排序，取前 TOP_CANDIDATES ──
    df = df.sort_values("_chg").head(TOP_CANDIDATES)

    # ── 逐一拉取近20日历史 ──
    candidates = []
    print(f"  对前 {min(len(df), TOP_CANDIDATES)} 只候选拉取20日历史...")

    for _, row in df.iterrows():
        code = str(row[code_col]).zfill(6)
        name = str(row[name_col]) if name_col else code
        scale_bn  = row.get("_scale_bn", 0.0)
        today_chg = row.get("_chg", 0.0)

        prices = fetch_etf_history_20d(code)
        if not prices:
            continue

        drop_20d = compute_drop_20d(prices)
        if drop_20d is None or drop_20d < DROP_THRESHOLD:
            continue   # 未达20日跌幅门槛

        rsi14 = calc_rsi(prices)
        if rsi14 is not None and rsi14 < 35:
            signal = "超跌反弹"
            reason = f"近20日跌幅 {drop_20d:.1f}%，RSI={rsi14:.1f}<35（超卖区间），具备技术反弹条件"
        else:
            signal = "继续观望"
            reason = f"近20日跌幅 {drop_20d:.1f}%，RSI={rsi14:.1f if rsi14 else 'N/A'}（未进超卖区间，反弹信号不明确）"

        candidates.append({
            "code":          code,
            "name":          name,
            "drop_20d_pct":  drop_20d,
            "today_chg_pct": round(today_chg, 2),
            "scale_bn":      round(scale_bn, 2),
            "rsi14":         rsi14,
            "signal":        signal,
            "reason":        reason,
            "risk_warning":  (
                "⚠️ 超跌ETF风险较高，建议小仓位分批介入，严格止损。"
                "以上仅为量化扫描，不构成投资建议，操作需自行判断风险。"
            ),
        })
        time.sleep(0.3)   # 避免接口限速

    # 按跌幅排序，超跌反弹信号优先，最多返回 MAX_RECOMMENDATIONS 条
    candidates.sort(key=lambda x: (x["signal"] != "超跌反弹", -x["drop_20d_pct"]))
    return candidates[:MAX_RECOMMENDATIONS]


def scan_undervalued(current_holdings: set) -> list[dict]:
    """
    低估常态扫描（无需恐慌触发）。
    筛选条件：近60日跌幅 >= DROP_THRESHOLD_UV(10%) 且 RSI14 < RSI_OVERSOLD_UV(40)。
    规模门槛：MIN_SCALE_UNDERVAL(3亿) —— 比恐慌扫描宽松。
    输出字段含 drop_60d_pct/rsi14/signal（超跌反弹/低位观察）。
    """
    df, code_col, name_col = _fetch_etf_spot_df(current_holdings)
    if df is None:
        return []

    # ── 规模过滤（低估扫描标准：3亿）──
    df = df[df["_scale_bn"] >= MIN_SCALE_UNDERVAL]
    print(f"  [低估扫描] 规模 >= {MIN_SCALE_UNDERVAL}亿：{len(df)} 只")

    # ── 取今日跌幅最大的前 TOP_CANDIDATES 只，再拉60日历史 ──
    df = df.sort_values("_chg").head(TOP_CANDIDATES)
    print(f"  [低估扫描] 对前 {min(len(df), TOP_CANDIDATES)} 只候选拉取60日历史...")

    candidates = []
    for _, row in df.iterrows():
        code = str(row[code_col]).zfill(6)
        name = str(row[name_col]) if name_col else code
        scale_bn  = row.get("_scale_bn", 0.0)
        today_chg = row.get("_chg", 0.0)

        # 拉取近65日价格（保证60交易日够用 + RSI预热）
        prices = fetch_etf_history(code, days=65)
        if not prices:
            continue

        drop_60d = compute_drop(prices, window=60)
        if drop_60d is None or drop_60d < DROP_THRESHOLD_UV:
            continue   # 未达60日跌幅门槛

        rsi14 = calc_rsi(prices)
        if rsi14 is None or rsi14 >= RSI_OVERSOLD_UV:
            continue   # RSI 不满足低估条件

        if rsi14 < 30:
            signal = "超跌反弹"
            reason = f"近60日跌幅 {drop_60d:.1f}%，RSI={rsi14:.1f}<30（深度超卖），关注反弹机会"
        else:
            signal = "低位观察"
            reason = f"近60日跌幅 {drop_60d:.1f}%，RSI={rsi14:.1f}（低位区间），可小仓位试探"

        candidates.append({
            "code":          code,
            "name":          name,
            "drop_60d_pct":  drop_60d,
            "today_chg_pct": round(today_chg, 2),
            "scale_bn":      round(scale_bn, 2),
            "rsi14":         rsi14,
            "signal":        signal,
            "reason":        reason,
        })
        time.sleep(0.3)

    # 超跌反弹优先，再按60日跌幅降序
    candidates.sort(key=lambda x: (x["signal"] != "超跌反弹", -x["drop_60d_pct"]))
    return candidates[:MAX_UNDERVALUED]


def main():
    ap = argparse.ArgumentParser(description="玄枢Alpha · 基金雷达扫描")
    ap.add_argument("--force", action="store_true", help="跳过恐慌触发条件强制深度扫描")
    args = ap.parse_args()

    print(f"\n== 玄枢Alpha · 基金雷达 [{datetime.now().strftime('%H:%M:%S')}] ==\n")

    # ── 0. 动态读取已持仓排除集合 ──
    current_holdings = load_current_holdings()

    # ── 1. 读取信号，判断恐慌触发 ──
    sig_data = load_signals()
    avg_sell = sig_data["avg_sell_score"]
    n_sigs   = len(sig_data["signals"])
    print(f"  signals.json: {n_sigs} 只标的，avg_sell_score = {avg_sell:.2f}（门槛 {PANIC_THRESHOLD}）")

    panic_triggered = args.force or avg_sell >= PANIC_THRESHOLD

    # ── 2. 低估常态扫描（无论是否恐慌，每次都运行）──
    print("\n-- 低估常态扫描（近60日跌幅 ≥10% & RSI<40）--")
    try:
        undervalued = scan_undervalued(current_holdings)
    except Exception as e:
        print(f"  ✗ 低估扫描失败: {e}")
        undervalued = []
    print(f"  低估机会：{len(undervalued)} 条")

    # ── 3. 恐慌深度扫描（可选）──
    if not panic_triggered:
        recs = []
        panic_msg = f"当前无超跌机会（avg_sell_score={avg_sell:.2f} < {PANIC_THRESHOLD}，市场情绪平稳）"
        print(f"  ⟳ 恐慌深度扫描未触发：{panic_msg}")
    else:
        print(f"\n-- 🚨 恐慌信号触发（avg_sell_score={avg_sell:.2f}），开始深度扫描超跌 ETF... --")
        try:
            recs = scan_etfs(current_holdings)
        except Exception as e:
            print(f"  ✗ 深度扫描失败: {e}")
            recs = []
        if not recs:
            panic_msg = "已触发恐慌扫描，但未发现符合条件的超跌 ETF（跌幅/规模条件未满足）"
        else:
            panic_msg = f"发现 {len(recs)} 只超跌 ETF，请结合基本面判断后操作"

    # ── 4. 写出 fund_recommendations.json ──
    output = {
        "updated_at":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "triggered":       panic_triggered,
        "avg_sell_score":  avg_sell,
        "panic_threshold": PANIC_THRESHOLD,
        "scan_params": {
            "panic_scan": {
                "min_scale_bn":       MIN_SCALE_BILLION,
                "drop_threshold_pct": DROP_THRESHOLD,
                "rsi_oversold":       35,
            },
            "undervalued_scan": {
                "min_scale_bn":       MIN_SCALE_UNDERVAL,
                "drop_60d_pct":       DROP_THRESHOLD_UV,
                "rsi_threshold":      RSI_OVERSOLD_UV,
            },
        },
        "message":         panic_msg,
        "recommendations": recs,
        "undervalued":     undervalued,
        "disclaimer":      "以上仅为量化扫描结果，不构成投资建议，投资者需自行承担风险",
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写入 {OUT_PATH}")
    print(f"   深度扫描：{panic_msg}")
    if undervalued:
        print(f"   低估机会：{len(undervalued)} 条")
        for r in undervalued:
            print(f"  [{r['signal']:6}] {r['code']} {r['name']:<20} "
                  f"近60日跌{r['drop_60d_pct']:.1f}% RSI={r['rsi14']}")
    if recs:
        print(f"   超跌推荐：")
        for r in recs:
            print(f"  [{r['signal']:6}] {r['code']} {r['name']:<20} "
                  f"跌{r['drop_20d_pct']:.1f}% RSI={r['rsi14']}")


if __name__ == "__main__":
    main()
