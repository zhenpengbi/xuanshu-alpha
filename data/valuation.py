#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 估值分位模块
========================
为持仓7个品类提供 PE/PB 历史分位判断，回答"现在贵不贵"。

品类覆盖：
  AI/科技     930713  中证人工智能指数    csindex-home (含滚动PE历史)
  有色金属    930708  中证有色金属指数    csindex-home
  光伏/新能源  931151  中证新能源指数      csindex-home
  高端制造    399377  中证高端装备指数    cnindex(仅价格) → 价格分位兜底
  纳指100     QQQ     纳斯达克100 ETF    yfinance(trailingPE)
  标普500     SPY     标普500 ETF        yfinance(trailingPE)
  黄金        —      无PE/PB，固定"不适用"

数据获取策略（三级降级）：
  1) ak.stock_zh_index_hist_csindex → 包含"滚动市盈率"5年日线（中证体系指数）
  2) ak.index_hist_cni → 仅价格5年日线，用价格分位替代PE分位（深交所399系指数）
  3) 兜底 → verdict="数据缺失", score=50

美股：yfinance trailingPE + 绝对阈值估算分位
兜底：接口失败不报错，该品类 verdict="数据缺失", score=50

verdict 规则（PE/价格 5年历史分位）：
  < 30  → 低估，   score = 20
  30-50 → 适中偏低，score = 35
  50-70 → 适中，   score = 50
  70-85 → 偏贵，   score = 70
  ≥ 85  → 高估，   score = 88

输出：data/valuation.json
"""

import json
import os
import time
import warnings
from datetime import datetime, timedelta

warnings.filterwarnings("ignore")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
OUT_PATH = os.path.join(BASE_DIR, "valuation.json")

# ── 品类定义 ──────────────────────────────────────────────────
CATEGORIES = [
    {
        "category":   "AI/科技",
        "index_name": "中证人工智能(930713)",
        "index_code": "930713",
        "source":     "csindex",
    },
    {
        "category":   "有色金属",
        "index_name": "中证有色金属(930708)",
        "index_code": "930708",
        "source":     "csindex",
    },
    {
        "category":   "光伏/新能源",
        "index_name": "中证新能源(931151)",
        "index_code": "931151",
        "source":     "csindex",
    },
    {
        "category":   "高端制造",
        "index_name": "中证高端装备(399377)",
        "index_code": "399377",
        "source":     "cnindex",   # 仅价格，用价格分位兜底
    },
    {
        "category":   "纳指100",
        "index_name": "纳斯达克100(NDX/QQQ)",
        "index_code": "QQQ",
        "source":     "yfinance",
    },
    {
        "category":   "标普500",
        "index_name": "标普500(SPX/SPY)",
        "index_code": "SPY",
        "source":     "yfinance",
    },
    {
        "category":   "黄金",
        "index_name": "黄金(XAUUSD)",
        "index_code": None,
        "source":     "none",
    },
]


# ── 工具函数 ──────────────────────────────────────────────────
def _verdict_from_pct(pct: float):
    """根据历史分位给出 verdict 和 score。"""
    if pct < 30:
        return "低估", 20
    elif pct < 50:
        return "适中偏低", 35
    elif pct < 70:
        return "适中", 50
    elif pct < 85:
        return "偏贵", 70
    else:
        return "高估", 88


def _pct_rank(series: list, current: float) -> float:
    """当前值在历史序列中的百分位（0-100）。"""
    if not series or current is None:
        return 50.0
    below = sum(1 for v in series if v <= current)
    return round(below / len(series) * 100, 1)


# ── A股（中证体系）：stock_zh_index_hist_csindex ──────────────
def _fetch_csindex_pe(code: str):
    """
    通过 stock_zh_index_hist_csindex 拉取5年日线历史（含"滚动市盈率"字段）。
    返回 (current_pe, pe_pct_5y) 或抛出异常。
    """
    import akshare as ak
    import pandas as pd

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=5 * 365 + 90)

    df = ak.stock_zh_index_hist_csindex(
        symbol=code,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )
    if df is None or df.empty:
        raise ValueError("空数据")

    # 找 PE 列（滚动市盈率 / peg 等）
    pe_col = next(
        (c for c in df.columns
         if "市盈率" in c or "PE" in c.upper() or c.lower() == "peg"),
        None,
    )
    if pe_col is None:
        raise ValueError(f"未找到PE列，现有列: {df.columns.tolist()}")

    df[pe_col] = pd.to_numeric(df[pe_col], errors="coerce")
    df = df.dropna(subset=[pe_col])

    if len(df) < 60:
        raise ValueError(f"有效PE行数不足: {len(df)}")

    pe_series  = df[pe_col].tolist()
    current_pe = round(pe_series[-1], 2)
    pe_pct     = _pct_rank(pe_series[:-1], current_pe)

    return current_pe, pe_pct


# ── A股（深交所国证体系）：index_hist_cni → 价格分位 ──────────
def _fetch_cnindex_price_pct(code: str):
    """
    通过 index_hist_cni 拉取价格历史，用价格分位近似代替 PE 分位。
    注意：价格分位≠PE分位，仅作兜底参考，verdict 会标注"(价格分位)"。
    返回 (current_close, price_pct_5y) 或抛出异常。
    """
    import akshare as ak
    import pandas as pd

    end_date   = datetime.today()
    start_date = end_date - timedelta(days=5 * 365 + 90)

    df = ak.index_hist_cni(
        symbol=code,
        start_date=start_date.strftime("%Y%m%d"),
        end_date=end_date.strftime("%Y%m%d"),
    )
    if df is None or df.empty:
        raise ValueError("空数据")

    close_col = next((c for c in df.columns if "收盘" in c), None)
    if close_col is None:
        raise ValueError(f"未找到收盘列，现有列: {df.columns.tolist()}")

    df[close_col] = pd.to_numeric(df[close_col], errors="coerce")
    df = df.dropna(subset=[close_col])

    if len(df) < 60:
        raise ValueError(f"有效价格行数不足: {len(df)}")

    price_series  = df[close_col].tolist()
    current_close = round(price_series[-1], 2)
    price_pct     = _pct_rank(price_series[:-1], current_close)

    return current_close, price_pct


# ── 美股：三级降级策略 ────────────────────────────────────────
# 兜底校准值（2026Q2 参考，季度更新）
_US_FALLBACK_PE = {
    "QQQ": 35.0,   # 纳指100 2026Q2 校准值
    "SPY": 24.0,   # 标普500 2026Q2 校准值
}

# 校准值有效期：当前校准值为2026Q2数据，有效期到Q3初
CALIBRATION_EXPIRY = "2026-09-30"


def _fetch_yfinance_pe(ticker: str):
    """
    Level-1：yfinance trailingPE。
    返回 (current_pe, source) 或 None。
    """
    try:
        import yfinance as yf
        info = yf.Ticker(ticker).info
        pe   = info.get("trailingPE") or info.get("forwardPE")
        if pe is None:
            return None
        return round(float(pe), 2), "yfinance"
    except Exception as e:
        print(f"    yfinance({ticker}) 失败: {e}")
        return None


def _fetch_akshare_us_pe(ticker: str):
    """
    Level-2：AKShare 美股实时行情 stock_us_spot_em，尝试获取 PE。
    返回 (current_pe, source) 或 None。
    """
    try:
        import akshare as ak
        # stock_us_spot_em 返回全量美股，含市盈率列
        df = ak.stock_us_spot_em()
        if df is None or df.empty:
            return None
        # 列名可能是"市盈率"或"动态市盈率"
        pe_col = next((c for c in df.columns if "市盈率" in c), None)
        name_col = next((c for c in df.columns if "名称" in c or "代码" in c), None)
        code_col = next((c for c in df.columns if c in ("代码", "symbol", "Symbol")), None)
        if pe_col is None or code_col is None:
            return None
        # ticker 映射：QQQ/SPY 在 AKShare 里通常带后缀
        row = df[df[code_col].str.upper().str.contains(ticker.upper(), na=False)]
        if row.empty:
            return None
        pe_val = row.iloc[0][pe_col]
        import pandas as pd
        pe_val = pd.to_numeric(pe_val, errors="coerce")
        if pe_val is None or pe_val != pe_val:  # NaN check
            return None
        return round(float(pe_val), 2), "akshare"
    except Exception as e:
        print(f"    akshare_us_pe({ticker}) 失败: {e}")
        return None


def _fetch_us_pe_with_fallback(ticker: str):
    """
    三级降级：yfinance → AKShare → 硬编码校准值。
    返回 (current_pe, source_note)，source_note 写入 pe_note。
    """
    # Level-1
    result = _fetch_yfinance_pe(ticker)
    if result:
        return result[0], "绝对PE估算(无5年序列)"

    # Level-2
    result = _fetch_akshare_us_pe(ticker)
    if result:
        print(f"    akshare({ticker}) 补救成功: PE={result[0]}")
        return result[0], "AKShare实时PE(无5年序列)"

    # Level-3：硬编码校准值
    fallback = _US_FALLBACK_PE.get(ticker)
    if fallback:
        print(f"    使用兜底校准值 {ticker} PE={fallback}")
        return fallback, "fallback_calibration(2026Q2参考值)"

    return None, None


def _pe_to_pct_us(pe: float) -> float:
    """美股 ETF PE 绝对阈值 → 伪分位（0-100）。"""
    # QQQ/SPY 历史 PE 范围约 [14, 50]，以 24 为中位参考
    if pe < 18:
        return 15.0
    elif pe < 22:
        return 30.0
    elif pe < 26:
        return 45.0
    elif pe < 32:
        return 60.0
    elif pe < 40:
        return 75.0
    else:
        return 90.0


# ── 单品类处理 ────────────────────────────────────────────────
def _process_category(cat: dict) -> dict:
    source = cat["source"]
    base = {
        "category":      cat["category"],
        "index_name":    cat["index_name"],
        "current_pe":    None,
        "pe_pct_5y":     None,
        "current_pb":    None,
        "pb_pct_5y":     None,
        "verdict":       "数据缺失",
        "verdict_score": 50,
        "pe_note":       None,   # 额外说明（如"价格分位"）
    }

    # 黄金：无估值框架
    if source == "none":
        base["verdict"]       = "不适用"
        base["verdict_score"] = 50
        return base

    # A股（中证体系）：有 PE 历史
    if source == "csindex":
        try:
            current_pe, pe_pct = _fetch_csindex_pe(cat["index_code"])
            base["current_pe"] = current_pe
            base["pe_pct_5y"]  = pe_pct
            verdict, score = _verdict_from_pct(pe_pct)
            base["verdict"]       = verdict
            base["verdict_score"] = score
        except Exception as e:
            print(f"    csindex({cat['index_code']}) 失败: {e}")
        return base

    # A股（深交所国证体系）：仅价格分位
    if source == "cnindex":
        try:
            current_close, price_pct = _fetch_cnindex_price_pct(cat["index_code"])
            base["current_pe"] = None
            base["pe_pct_5y"]  = price_pct
            base["pe_note"]    = "价格5年分位(无PE历史)"
            verdict, score = _verdict_from_pct(price_pct)
            base["verdict"]       = verdict
            base["verdict_score"] = score
        except Exception as e:
            print(f"    cnindex({cat['index_code']}) 失败: {e}")
        return base

    # 美股（三级降级：yfinance → AKShare → 硬编码校准值）
    if source == "yfinance":
        current_pe, pe_note = _fetch_us_pe_with_fallback(cat["index_code"])
        if current_pe is not None:
            base["current_pe"] = current_pe
            base["pe_note"]    = pe_note
            pct_proxy = _pe_to_pct_us(current_pe)
            base["pe_pct_5y"]  = pct_proxy
            verdict, score = _verdict_from_pct(pct_proxy)
            base["verdict"]       = verdict
            base["verdict_score"] = score
        return base

    return base


# ── 主流程 ────────────────────────────────────────────────────
def main():
    print(f"== 玄枢Alpha · 估值分位模块 [{datetime.now().strftime('%H:%M:%S')}] ==\n")

    valuations = []
    for cat in CATEGORIES:
        print(f"--- {cat['category']} ({cat['index_code'] or '无'}) ---")
        try:
            row = _process_category(cat)
        except Exception as e:
            print(f"  ✗ 未捕获异常: {e}")
            row = {
                "category":      cat["category"],
                "index_name":    cat["index_name"],
                "current_pe":    None,
                "pe_pct_5y":     None,
                "current_pb":    None,
                "pb_pct_5y":     None,
                "verdict":       "数据缺失",
                "verdict_score": 50,
                "pe_note":       None,
            }

        if row["current_pe"] is not None:
            pe_str = f"PE={row['current_pe']:.1f}"
        elif row["pe_pct_5y"] is not None:
            pe_str = "PE=N/A(用价格分位)"
        else:
            pe_str = "PE=N/A"

        pct_str = f"  5y分位={row['pe_pct_5y']}%" if row["pe_pct_5y"] is not None else ""
        note_str = f"  [{row.get('pe_note','')}]" if row.get("pe_note") else ""
        print(f"  {pe_str}{pct_str}{note_str}  → {row['verdict']}(score={row['verdict_score']})")

        valuations.append(row)
        time.sleep(0.3)

    # 校准值过期检测
    warnings = []
    used_fallback = any(
        v.get("pe_note") and "fallback_calibration" in v.get("pe_note", "")
        for v in valuations
    )
    today_str = datetime.today().strftime("%Y-%m-%d")
    if used_fallback and today_str > CALIBRATION_EXPIRY:
        warn_msg = f"PE校准值已过期（2026Q2），请更新US_PE_FALLBACK（有效期至{CALIBRATION_EXPIRY}）"
        warnings.append(warn_msg)
        print(f"\n  !!! 警告: {warn_msg}")

    output = {
        "updated_at": datetime.today().strftime("%Y-%m-%d"),
        "valuations": valuations,
    }
    if warnings:
        output["warnings"] = warnings
    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n✅ 估值分位完成 → {OUT_PATH}")
    ok = sum(1 for v in valuations if v["verdict"] not in ("数据缺失",))
    print(f"   {ok}/{len(CATEGORIES)} 个品类有效估值")


if __name__ == "__main__":
    main()
