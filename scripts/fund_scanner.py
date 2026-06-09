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
ROOT       = os.path.dirname(SCRIPT_DIR)
SIGNALS_JSON = os.path.join(ROOT, "data", "signals.json")
OUT_PATH     = os.path.join(ROOT, "data", "fund_recommendations.json")

# ── 可调参数 ──────────────────────────────────────────────────
PANIC_THRESHOLD    = 2.0   # 平均 sell_score 触发门槛
MIN_SCALE_BILLION  = 5.0   # 最小规模（亿元）
DROP_THRESHOLD     = 15.0  # 近20日跌幅门槛（%，正数表示下跌幅度）
TOP_CANDIDATES     = 40    # 初筛候选数（按今日跌幅排序）
MAX_RECOMMENDATIONS = 8    # 最终推荐条数

# 已持仓标的（排除）
CURRENT_HOLDINGS = {"000216", "008585", "017766", "515790", "513100", "513500"}


# ── 工具函数 ─────────────────────────────────────────────────

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


def fetch_etf_history_20d(code: str) -> list[float] | None:
    """
    拉取 ETF 近25日收盘价（多拉5天作为 RSI 预热缓冲）。
    先尝试 fund_etf_hist_em（东方财富），失败则用 fund_etf_hist_sina。
    """
    import akshare as ak
    end   = datetime.today()
    start = end - timedelta(days=45)   # 多取一些，保证有25个交易日
    start_str = start.strftime("%Y%m%d")
    end_str   = end.strftime("%Y%m%d")
    try:
        df = ak.fund_etf_hist_em(
            symbol=code, period="daily",
            start_date=start_str, end_date=end_str, adjust="qfq"
        )
        prices = df.sort_values("日期")["收盘"].astype(float).tolist()[-25:]
        return prices if len(prices) >= 5 else None
    except Exception:
        pass
    try:
        df = ak.fund_etf_hist_sina(symbol="sh" + code)
        cutoff = start.strftime("%Y-%m-%d")
        df = df[df["date"].astype(str) >= cutoff].sort_values("date")
        prices = df["close"].astype(float).tolist()[-25:]
        return prices if len(prices) >= 5 else None
    except Exception:
        return None


def compute_drop_20d(prices: list) -> float | None:
    """从价格序列计算近20日跌幅（取最近20日，正数=跌幅）。"""
    if len(prices) < 2:
        return None
    use = prices[-min(20, len(prices)):]
    drop_pct = (use[0] - use[-1]) / use[0] * 100  # 正 = 跌
    return round(drop_pct, 2)


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


# ── 主流程 ────────────────────────────────────────────────────

def scan_etfs() -> list[dict]:
    """核心扫描逻辑，返回推荐列表。"""
    import akshare as ak
    import pandas as pd

    print("  获取 ETF 行情数据...")
    try:
        df = ak.fund_etf_spot_em()
    except Exception as e:
        print(f"  ✗ fund_etf_spot_em 失败: {e}")
        return []

    print(f"  共 {len(df)} 只 ETF")

    # ── 规模过滤 ──
    # 检测规模列名（不同 akshare 版本字段名可能不同）
    scale_col = next(
        (c for c in df.columns if "市值" in c or "规模" in c or "净资产" in c),
        None
    )
    if scale_col:
        df["_scale_bn"] = df[scale_col].apply(parse_scale)
        df = df[df["_scale_bn"] >= MIN_SCALE_BILLION]
        print(f"  规模 >= {MIN_SCALE_BILLION}亿：{len(df)} 只")
    else:
        print(f"  ⚠️ 未找到规模字段（{list(df.columns[:8])}…），跳过规模过滤")
        df["_scale_bn"] = 0.0

    # ── 排除已持仓 ──
    code_col = "代码" if "代码" in df.columns else df.columns[0]
    df = df[~df[code_col].isin(CURRENT_HOLDINGS)]

    # ── 今日涨跌幅排序（最大跌幅在前）──
    change_col = next(
        (c for c in df.columns if "涨跌幅" in c),
        None
    )
    if change_col:
        df["_chg"] = pd.to_numeric(df[change_col], errors="coerce").fillna(0)
        df = df.sort_values("_chg").head(TOP_CANDIDATES)
    else:
        df = df.head(TOP_CANDIDATES)

    name_col = next((c for c in df.columns if "名称" in c or "简称" in c), None)

    # ── 逐一拉取近20日历史 ──
    candidates = []
    print(f"  对前 {min(len(df), TOP_CANDIDATES)} 只候选拉取20日历史...")

    for _, row in df.iterrows():
        code = str(row[code_col]).zfill(6)
        name = str(row[name_col]) if name_col else code
        scale_bn = row.get("_scale_bn", 0.0)
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


def main():
    ap = argparse.ArgumentParser(description="玄枢Alpha · 基金雷达扫描")
    ap.add_argument("--force", action="store_true", help="跳过恐慌触发条件强制扫描")
    args = ap.parse_args()

    print(f"\n== 玄枢Alpha · 基金雷达 [{datetime.now().strftime('%H:%M:%S')}] ==\n")

    # ── 1. 读取信号，判断是否触发扫描 ──
    sig_data = load_signals()
    avg_sell = sig_data["avg_sell_score"]
    n_sigs   = len(sig_data["signals"])
    print(f"  signals.json: {n_sigs} 只标的，avg_sell_score = {avg_sell:.2f}（门槛 {PANIC_THRESHOLD}）")

    triggered = args.force or avg_sell >= PANIC_THRESHOLD

    if not triggered:
        output = {
            "updated_at":     datetime.now().strftime("%Y-%m-%d %H:%M"),
            "triggered":      False,
            "avg_sell_score": avg_sell,
            "panic_threshold": PANIC_THRESHOLD,
            "message":        f"当前无超跌机会（avg_sell_score={avg_sell:.2f} < {PANIC_THRESHOLD}，市场情绪平稳）",
            "recommendations": [],
        }
        with open(OUT_PATH, "w", encoding="utf-8") as f:
            json.dump(output, f, ensure_ascii=False, indent=2)
        print(f"  ⟳ 未触发扫描：{output['message']}")
        print(f"✅ 已写入 {OUT_PATH}（空列表）")
        return

    print(f"  🚨 恐慌信号触发（avg_sell_score={avg_sell:.2f}），开始扫描超跌 ETF...\n")

    # ── 2. 执行扫描 ──
    try:
        recs = scan_etfs()
    except Exception as e:
        print(f"  ✗ 扫描失败: {e}")
        recs = []

    if not recs:
        msg = "已触发恐慌扫描，但未发现符合条件的超跌 ETF（跌幅/规模条件未满足）"
    else:
        msg = f"发现 {len(recs)} 只超跌 ETF，请结合基本面判断后操作"

    output = {
        "updated_at":      datetime.now().strftime("%Y-%m-%d %H:%M"),
        "triggered":       True,
        "avg_sell_score":  avg_sell,
        "panic_threshold": PANIC_THRESHOLD,
        "scan_params": {
            "min_scale_bn":     MIN_SCALE_BILLION,
            "drop_threshold_pct": DROP_THRESHOLD,
            "rsi_oversold":     35,
        },
        "message":         msg,
        "recommendations": recs,
        "disclaimer":      "以上仅为量化扫描结果，不构成投资建议，投资者需自行承担风险",
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 已写入 {OUT_PATH}")
    print(f"   {msg}\n")
    for r in recs:
        print(f"  [{r['signal']:6}] {r['code']} {r['name']:<20} "
              f"跌{r['drop_20d_pct']:.1f}% RSI={r['rsi14']}")


if __name__ == "__main__":
    main()
