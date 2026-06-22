#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 新闻情绪→持仓影响分析
=====================================
读取 data/news.json 每条新闻的 impact 字段，按持仓标的做渠道映射，
统计利多/利空/中性条数，计算情绪净值，输出 data/news_impact.json。

news.json 支持三种格式（自动识别）：
  旧格式:    {"updated":"...", "period":"...", "items":[...]}
  history:   {"updated":"...", "history":[{"date":"...","period":"...","items":[...]}, ...]}
  早晚报:    {"updated":"...", "morning":{"period":"早报","items":[...]}, "evening":{"period":"晚报","items":[...]}}

持仓→新闻渠道映射（impact 字段的 key）：
  000216 黄金       → gold
  513100 纳指100    → nasdaq
  513500 标普500    → nasdaq
  008585 AI主题     → ashare
  515790 光伏ETF    → ashare
  017766 有色金属   → ashare

情绪净值 = 利多条数 - 利空条数
  > 0  → 偏多
  < 0  → 偏空
  = 0  → 中性

用法：
    python3 scripts/build_news_impact.py
输出：
    data/news_impact.json
"""

import json
import os
from datetime import datetime

SCRIPT_DIR        = os.path.dirname(os.path.abspath(__file__))
ROOT              = os.path.dirname(SCRIPT_DIR)
NEWS_JSON         = os.path.join(ROOT, "data", "news.json")
OUT_PATH          = os.path.join(ROOT, "data", "news_impact.json")
NEWS_HISTORY_JSON = os.path.join(ROOT, "data", "news_history.json")

# 持仓标的清单（与 positions.json 同步）
HOLDINGS = [
    {"code": "002963", "name": "易方达黄金ETF联接C"},
    {"code": "000307", "name": "易方达黄金ETF联接A"},
    {"code": "011840", "name": "天弘中证人工智能C"},
    {"code": "010990", "name": "南方有色金属ETF联接E"},
    {"code": "012885", "name": "华夏光伏ETF联接A"},
    {"code": "513100", "name": "纳指100ETF"},
    {"code": "513500", "name": "标普500ETF"},
    {"code": "015790", "name": "永赢高端装备混合C"},
    {"code": "014881", "name": "天弘机器人ETF联接C"},
    {"code": "025647", "name": "平安高端装备混合C"},
]

# 持仓代码 → 新闻 impact 渠道
CHANNEL_MAP = {
    "002963": "gold",
    "000307": "gold",
    "011840": "ashare",
    "010990": "ashare",
    "012885": "ashare",
    "015790": "ashare",
    "014881": "ashare",
    "025647": "ashare",
    "513100": "nasdaq",
    "513500": "nasdaq",
}

# 情绪权重（利多/利空比中性更重要，用于选 top_impact_news）
SENTIMENT_WEIGHT = {"利多": 2, "利空": 2, "中性": 0}


def build_impact(news_items: list, channel: str) -> dict:
    """
    统计某渠道的情绪分布，并挑选最相关的3条新闻。
    相关性：非中性优先，相同情绪内按原始顺序（越前越新）保留。
    """
    bullish = bearish = neutral = 0
    non_neutral_news = []
    neutral_news     = []

    for item in news_items:
        impact  = item.get("impact", {})
        val     = impact.get(channel, "中性")
        title   = item.get("title", "")
        time_   = item.get("time", "")
        summary = item.get("summary", "")

        rec = {"title": title, "time": time_, "summary": summary, "sentiment": val}
        if val == "利多":
            bullish += 1
            non_neutral_news.append(rec)
        elif val == "利空":
            bearish += 1
            non_neutral_news.append(rec)
        else:
            neutral += 1
            neutral_news.append(rec)

    # 填满3条：先非中性，不足再补中性
    top3 = (non_neutral_news + neutral_news)[:3]

    score = bullish - bearish
    if score > 0:
        label = "偏多"
    elif score < 0:
        label = "偏空"
    else:
        label = "中性"

    return {
        "bullish_count":   bullish,
        "bearish_count":   bearish,
        "neutral_count":   neutral,
        "sentiment_score": score,
        "sentiment_label": label,
        "top_impact_news": top3,
    }


def extract_latest_items(news_data: dict) -> tuple:
    """
    从 news.json 中提取最新一期新闻条目，兼容三种格式：
      1. 新格式 morning/evening 双分区：合并所有非空分区的条目
      2. history 数组格式（滚动7天窗口）：取 history[0]
      3. 旧格式：顶层 items 数组
    Returns:
        (items: list, date_str: str, period_str: str)
    可复用：任何需要读取 news.json 最新条目的场景均可调用。
    """
    # ── 新格式：morning/evening 双分区 ──
    if "morning" in news_data or "evening" in news_data:
        date_str = news_data.get("updated", "")
        all_items = []
        period_parts = []
        # 优先晚报（更新），其次早报，合并所有有效条目
        for key in ("evening", "morning"):
            sec = news_data.get(key, {})
            if isinstance(sec, dict) and sec.get("items"):
                all_items = sec["items"] + all_items  # 晚报在前
                p = sec.get("period", "")
                if p:
                    period_parts.append(p)
        period_str = "/".join(reversed(period_parts)) if period_parts else ""
        return (all_items, date_str, period_str)

    # ── history 数组格式（滚动7天窗口）──
    if "history" in news_data and news_data["history"]:
        latest = news_data["history"][0]  # history[0] 为最新
        return (
            latest.get("items", []),
            latest.get("date", news_data.get("updated", "")),
            latest.get("period", ""),
        )

    # ── 旧格式：顶层 items ──
    return (
        news_data.get("items", []),
        news_data.get("updated", ""),
        news_data.get("period", ""),
    )


def _append_to_history(news_data: dict, date_str: str, period_str: str, items: list,
                       max_records: int = 60):
    """
    把当期新闻记录追加到 news_history.json。
    按 date + period 去重，最多保留 max_records 条（最新在前）。
    """
    if not items:
        return

    # 读取现有历史
    if os.path.exists(NEWS_HISTORY_JSON):
        try:
            with open(NEWS_HISTORY_JSON, "r", encoding="utf-8") as f:
                history_data = json.load(f)
        except Exception:
            history_data = {"records": []}
    else:
        history_data = {"records": []}

    records = history_data.get("records", [])

    # 去重 key：date + period
    dedup_key = f"{date_str}|{period_str}"
    records = [r for r in records if f"{r.get('date','')}|{r.get('period','')}" != dedup_key]

    # 新记录插到最前（最新在前）
    records.insert(0, {
        "date":   date_str,
        "period": period_str,
        "items":  items,
    })

    # 保留最近 max_records 条
    records = records[:max_records]

    history_data["records"]    = records
    history_data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")

    with open(NEWS_HISTORY_JSON, "w", encoding="utf-8") as f:
        json.dump(history_data, f, ensure_ascii=False, indent=2)

    print(f"  news_history.json: {len(records)} 条历史记录")


def main():
    if not os.path.exists(NEWS_JSON):
        print(f"❌ {NEWS_JSON} 不存在，请先运行新闻更新脚本")
        return

    with open(NEWS_JSON, "r", encoding="utf-8") as f:
        news_data = json.load(f)

    news_items, news_date, news_period = extract_latest_items(news_data)
    if not news_items:
        print("⚠️  news.json 中无新闻条目")

    results = []
    for h in HOLDINGS:
        code    = h["code"]
        channel = CHANNEL_MAP.get(code, "ashare")
        impact  = build_impact(news_items, channel)
        results.append({
            "code":    code,
            "name":    h["name"],
            "channel": channel,
            **impact,
        })

    output = {
        "updated_at":  datetime.now().strftime("%Y-%m-%d %H:%M"),
        "news_date":   news_date,
        "news_period": news_period,
        "total_news":  len(news_items),
        "items":       results,
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # ── 追加到 news_history.json（早报和晚报分别写入，按 date+period 去重）──
    # 优先从 morning/evening 双分区格式中分别提取，确保每期独立记录
    if "morning" in news_data or "evening" in news_data:
        date_str = news_data.get("updated", news_date)
        for key, label in (("morning", "早报"), ("evening", "晚报")):
            sec = news_data.get(key, {})
            if isinstance(sec, dict) and sec.get("items"):
                _append_to_history(news_data, date_str, label, sec["items"])
    else:
        # 旧格式/history 格式，沿用原逻辑
        _append_to_history(news_data, news_date, news_period, news_items)

    # ── 打印摘要 ──────────────────────────────────────────────
    print(f"✅ news_impact.json → {OUT_PATH}")
    print(f"   新闻期：{output['news_date']} {output['news_period']} · 共 {len(news_items)} 条\n")
    print(f"  {'代码':<8} {'名称':<22} {'利多':>4} {'利空':>4} {'中性':>4} {'净值':>6} {'标签'}")
    print("  " + "─" * 62)
    for r in results:
        sign = "+" if r["sentiment_score"] > 0 else ""
        bar_bull = "▇" * r["bullish_count"]
        bar_bear = "▇" * r["bearish_count"]
        print(
            f"  {r['code']:<8} {r['name']:<22}"
            f" {r['bullish_count']:>4} {r['bearish_count']:>4}"
            f" {r['neutral_count']:>4} {sign}{r['sentiment_score']:>5} "
            f" {r['sentiment_label']}"
        )


if __name__ == "__main__":
    main()
