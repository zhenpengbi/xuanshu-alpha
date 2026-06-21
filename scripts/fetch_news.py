#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 自动新闻抓取脚本
==============================
从公开数据源自动抓取持仓相关财经新闻，自动归类渠道并生成 impact 字段，
写入 data/news.json（供 build_news_impact.py 消费）。

数据源：
  1. akshare.stock_news_em  — 东方财富关键词搜索新闻（按主题关键词）
  2. akshare.news_cctv       — 新闻联播文字稿（宏观面）

自动归类逻辑：
  搜索关键词自带渠道归属 → 自动判定 impact 字段（利多/利空/中性）

用法：
    python3 scripts/fetch_news.py                # 按当前时段写入
    python3 scripts/fetch_news.py --period morning  # 指定早报
    python3 scripts/fetch_news.py --period evening  # 指定晚报
    python3 scripts/fetch_news.py --dry-run      # 仅打印不写入

输出：
    data/news.json（新格式：morning/evening 双分区）
"""

import json
import os
import re
import sys
import time
import argparse
from datetime import date, datetime, timedelta

# ─── 路径配置 ────────────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_ROOT  = os.path.dirname(_SCRIPT_DIR)
NEWS_JSON   = os.path.join(_PROJ_ROOT, "data", "news.json")

# ─── 渠道 → 分类标签 ─────────────────────────────────────────────────────────
CHANNEL_LABELS = {
    "gold":   "黄金",
    "nasdaq": "美股",
    "ashare": "A股",
    "retail": "美团",
}

# ─── 搜索主题（关键词 → 渠道归类）────────────────────────────────────────────
# 每个关键词用 stock_news_em 搜索，结果归入对应渠道
SEARCH_TOPICS = [
    # 黄金
    {"keyword": "黄金",   "channel": "gold",   "label": "黄金"},
    {"keyword": "贵金属", "channel": "gold",   "label": "黄金"},
    # 美股/美联储
    {"keyword": "美联储", "channel": "nasdaq", "label": "美股"},
    {"keyword": "纳斯达克", "channel": "nasdaq", "label": "美股"},
    # A股/科技
    {"keyword": "人工智能", "channel": "ashare", "label": "A股"},
    {"keyword": "光伏",   "channel": "ashare", "label": "A股"},
    {"keyword": "有色金属", "channel": "ashare", "label": "A股"},
    {"keyword": "机器人", "channel": "ashare", "label": "A股"},
    # 美团/零售
    {"keyword": "美团",   "channel": "retail", "label": "美团"},
    {"keyword": "即时零售", "channel": "retail", "label": "美团"},
]

# ─── 利多/利空关键词 ─────────────────────────────────────────────────────────
BULLISH_KEYWORDS = [
    "上涨", "大涨", "飙升", "反弹", "突破", "新高", "利好", "增持",
    "买入", "超预期", "盈利", "增长", "复苏", "降息", "宽松", "刺激",
    "回暖", "放量", "强势", "回升", "牛市", "超买",
    "减亏", "扭亏", "市占率", "龙头", "净流入", "抢筹",
]

BEARISH_KEYWORDS = [
    "下跌", "大跌", "暴跌", "重挫", "回落", "新低", "利空", "减持", "卖出",
    "亏损", "衰退", "加息", "紧缩", "鹰派", "恐慌", "抛售", "回调",
    "承压", "疲软", "下行", "熊市", "超卖", "跳水",
    "盈利转亏", "由盈转亏", "净亏损", "净流出",
]


def _classify_channel(title: str, content: str) -> str:
    """
    根据标题+内容关键词判断新闻属于哪个渠道（无默认渠道时使用）。
    """
    CHANNEL_KEYWORDS = {
        "gold": ["黄金", "金价", "伦敦金", "COMEX", "贵金属", "白银", "避险", "央行购金"],
        "nasdaq": ["纳斯达克", "纳指", "标普", "美股", "美联储", "FOMC", "加息", "降息", "芯片", "半导体", "英伟达", "AMD", "科技股", "道指"],
        "ashare": ["A股", "沪深", "创业板", "科创板", "光伏", "新能源", "有色金属", "铜价", "人工智能", "机器人", "算力", "数据中心"],
        "retail": ["美团", "外卖", "即时零售", "闪购", "本地生活", "配送", "骑手", "餐饮"],
    }
    text = title + " " + content
    scores = {}
    for ch, keywords in CHANNEL_KEYWORDS.items():
        score = sum(1 for kw in keywords if kw in text)
        if score > 0:
            scores[ch] = score
    if scores:
        return max(scores, key=scores.get)
    return "ashare"


def _classify_sentiment(title: str, content: str) -> str:
    """根据标题+内容关键词判断利多/利空/中性。"""
    text = title + " " + content
    bull = sum(1 for kw in BULLISH_KEYWORDS if kw in text)
    bear = sum(1 for kw in BEARISH_KEYWORDS if kw in text)
    if bull > bear:
        return "利多"
    elif bear > bull:
        return "利空"
    return "中性"


def _generate_reason(title: str, content: str, channel: str, sentiment: str) -> str:
    """根据渠道和情绪生成简短 reason。"""
    label = CHANNEL_LABELS.get(channel, "")
    if sentiment == "利多":
        return f"该消息对{label}持仓构成正面催化。"
    elif sentiment == "利空":
        return f"该消息对{label}持仓构成短期压力。"
    return f"该消息对{label}持仓影响偏中性。"


def _truncate_content(content: str, max_len: int = 200) -> str:
    """截断过长内容用于 summary"""
    content = content.strip().replace("\n", " ").replace("\r", "")
    if len(content) <= max_len:
        return content
    return content[:max_len - 3] + "..."


def _is_duplicate_title(title: str, seen_titles: set) -> bool:
    """检查标题是否重复（去除数字和标点后比对）"""
    # 简化标题用于去重：去掉日期数字、连字符等
    simplified = re.sub(r'[\d\-—_]+', '', title)
    simplified = simplified.strip()
    return simplified in seen_titles


# ─── 新闻抓取 ────────────────────────────────────────────────────────────────

def fetch_topic_news() -> list:
    """
    按主题关键词从东方财富搜索新闻，归类后返回 items 列表。
    每个关键词搜最近 10 条，按渠道归类，去重后按发布时间排序。
    """
    import akshare as ak

    all_items = []
    seen_titles = set()

    for topic in SEARCH_TOPICS:
        keyword = topic["keyword"]
        channel = topic["channel"]
        ch_label = CHANNEL_LABELS.get(channel, "")

        try:
            df = ak.stock_news_em(symbol=keyword)
        except Exception as e:
            print(f"  ⚠️  关键词「{keyword}」抓取失败: {e}")
            continue

        if df is None or df.empty:
            continue

        count = 0
        for _, row in df.iterrows():
            title = str(row.get("新闻标题", "")).strip()
            content = str(row.get("新闻内容", "")).strip()
            source = str(row.get("文章来源", "")).strip()
            pub_time = str(row.get("发布时间", "")).strip()

            if not title or _is_duplicate_title(title, seen_titles):
                continue

            # 过滤：只保留最近 3 天的新闻（覆盖周末场景）
            try:
                news_date = datetime.strptime(pub_time[:10], "%Y-%m-%d")
                if (datetime.now() - news_date).days > 2:
                    continue
            except (ValueError, IndexError):
                pass

            # 过滤：排除"ETF主力榜""ETF融资榜"等流水条目
            if any(kw in title for kw in ["ETF主力榜", "ETF融资榜", "ETF融券榜", "龙虎榜"]):
                continue

            seen_titles.add(re.sub(r'[\d\-—_]+', '', title).strip())
            count += 1

            # 自动归类（搜索关键词自带渠道归属，但允许被内容关键词覆盖）
            actual_channel = _classify_channel(title, content) if channel == "ashare" else channel
            sentiment = _classify_sentiment(title, content)

            # 构建 impact 字段
            impact = {"gold": "中性", "ashare": "中性", "nasdaq": "中性", "retail": "中性"}
            impact[actual_channel] = sentiment

            # 分类标签
            period_label = "早报" if datetime.now().hour < 13 else "晚报"
            time_tag = f"{period_label} · {ch_label}"

            item = {
                "time": time_tag,
                "title": title,
                "summary": _truncate_content(content),
                "source": source or "东方财富",
                "impact": impact,
                "reason": _generate_reason(title, content, actual_channel, sentiment),
                "_pub_time": pub_time,  # 临时字段，排序用
            }
            all_items.append(item)

        print(f"  ✓ 「{keyword}」→ {count} 条")
        time.sleep(0.3)  # 避免请求过快

    # 按发布时间倒序排序
    all_items.sort(key=lambda x: x.get("_pub_time", ""), reverse=True)

    # 去掉临时字段
    for item in all_items:
        item.pop("_pub_time", None)

    return all_items


def fetch_cctv_news() -> list:
    """
    抓取新闻联播文字稿，提取与持仓相关的宏观新闻。
    """
    import akshare as ak

    items = []
    all_keywords = []
    for topic in SEARCH_TOPICS:
        all_keywords.append(topic["keyword"])

    # 尝试今天和昨天
    for days_back in range(2):
        target_date = date.today() - timedelta(days=days_back)
        date_str = target_date.strftime("%Y%m%d")

        try:
            df = ak.news_cctv(date=date_str)
        except Exception:
            continue

        if df is None or df.empty:
            continue

        period_label = "早报" if datetime.now().hour < 13 else "晚报"

        for _, row in df.iterrows():
            title = str(row.get("title", "")).strip()
            content = str(row.get("content", "")).strip()
            if not title:
                continue

            text = title + " " + content
            matched_keywords = [kw for kw in all_keywords if kw in text]
            if not matched_keywords:
                continue

            ch = _classify_channel(title, content)
            sentiment = _classify_sentiment(title, content)
            impact = {"gold": "中性", "ashare": "中性", "nasdaq": "中性", "retail": "中性"}
            impact[ch] = sentiment

            ch_label = CHANNEL_LABELS.get(ch, "")
            time_tag = f"{period_label} · 宏观"

            items.append({
                "time": time_tag,
                "title": title,
                "summary": _truncate_content(content, 150),
                "source": "新闻联播/CCTV",
                "impact": impact,
                "reason": _generate_reason(title, content, ch, sentiment),
            })

        if items:
            break  # 找到数据就停止

    return items


def merge_and_dedup(topic_items: list, cctv_items: list) -> list:
    """
    合并主题新闻和新闻联播，去重（按标题），新闻联播优先。
    """
    seen = set()
    merged = []

    for item in cctv_items:
        simplified = re.sub(r'[\d\-—_]+', '', item["title"]).strip()
        if simplified not in seen:
            seen.add(simplified)
            merged.append(item)

    for item in topic_items:
        simplified = re.sub(r'[\d\-—_]+', '', item["title"]).strip()
        if simplified not in seen:
            seen.add(simplified)
            merged.append(item)

    return merged


def fetch_all_news(period: str = None) -> list:
    """
    抓取全部新闻并返回合并去重后的 items 列表。
    """
    if period is None:
        period = "morning" if datetime.now().hour < 13 else "evening"

    period_label = "早报" if period == "morning" else "晚报"
    print(f"\n📡 玄枢Alpha 新闻抓取 — {period_label}")
    print("=" * 50)

    # 1. 主题关键词新闻
    print("\n[1/2] 搜索主题新闻（东方财富关键词搜索）...")
    topic_items = fetch_topic_news()
    print(f"  ✅ 抓取到 {len(topic_items)} 条主题新闻")

    # 2. 新闻联播
    print("\n[2/2] 抓取新闻联播（CCTV）...")
    cctv_items = fetch_cctv_news()
    print(f"  ✅ 抓取到 {len(cctv_items)} 条相关联播")

    # 3. 合并去重
    items = merge_and_dedup(topic_items, cctv_items)

    # 4. 限制条数（最多 12 条）
    items = items[:12]

    print(f"\n📊 合计：{len(items)} 条新闻（去重后，最多 12 条）")

    return items


def write_news(period: str, items: list, dry_run: bool = False) -> None:
    """
    将新闻写入 news.json，使用 build_news_json.write_news_section。
    """
    if dry_run:
        print("\n🏁 DRY RUN 模式，不写入文件")
        for i, item in enumerate(items, 1):
            print(f"  {i}. [{item['time']}] {item['title']}")
            print(f"     impact: {item['impact']} | {item['reason']}")
        return

    if not items:
        print("\n⚠️  无新闻条目，跳过写入")
        return

    # 导入并调用 build_news_json 的写入函数
    sys.path.insert(0, _PROJ_ROOT)
    from scripts.build_news_json import write_news_section

    result = write_news_section(period=period, items=items)
    print(f"\n✅ 已写入 data/news.json — {period} 分区，{len(items)} 条")


def main():
    parser = argparse.ArgumentParser(
        description="玄枢Alpha 自动新闻抓取脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--period", choices=["morning", "evening"],
        help="指定时段（默认按当前时间自动判断）",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="仅打印抓取结果，不写入文件",
    )

    args = parser.parse_args()

    period = args.period or ("morning" if datetime.now().hour < 13 else "evening")
    items = fetch_all_news(period)
    write_news(period, items, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
