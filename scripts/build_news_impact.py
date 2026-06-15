#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 新闻情绪→持仓影响分析
=====================================
读取 data/news.json 每条新闻的 impact 字段，按持仓标的做渠道映射，
统计利多/利空/中性条数，计算情绪净值，输出 data/news_impact.json。

news.json 支持两种格式（自动识别）：
  旧格式: {"updated":"...", "period":"...", "items":[...]}
  新格式: {"updated":"...", "history":[{"date":"...","period":"...","items":[...]}, ...]}

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

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ROOT       = os.path.dirname(SCRIPT_DIR)
NEWS_JSON  = os.path.join(ROOT, "data", "news.json")
OUT_PATH   = os.path.join(ROOT, "data", "news_impact.json")

# 持仓标的清单
HOLDINGS = [
    {"code": "000216", "name": "易方达黄金ETF联接C"},
    {"code": "008585", "name": "天弘AI主题指数C"},
    {"code": "017766", "name": "南方有色金属ETF联接E"},
    {"code": "515790", "name": "华夏光伏ETF"},
    {"code": "513100", "name": "纳指100ETF"},
    {"code": "513500", "name": "标普500ETF"},
]

# 持仓代码 → 新闻 impact 渠道
CHANNEL_MAP = {
    "000216": "gold",
    "017766": "ashare",
    "515790": "ashare",
    "008585": "ashare",
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
    从 news.json 中提取最新一期新闻条目，兼容旧格式和新 history 格式。
    Returns:
        (items: list, date_str: str, period_str: str)
    可复用：任何需要读取 news.json 最新条目的场景均可调用。
    """
    # 新格式：history 数组
    if "history" in news_data and news_data["history"]:
        latest = news_data["history"][0]  # history[0] 为最新
        return (
            latest.get("items", []),
            latest.get("date", news_data.get("updated", "")),
            latest.get("period", ""),
        )
    # 旧格式：顶层 items
    return (
        news_data.get("items", []),
        news_data.get("updated", ""),
        news_data.get("period", ""),
    )


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
