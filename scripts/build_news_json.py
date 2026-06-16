#!/usr/bin/env python3
"""
build_news_json.py — 玄枢早晚报数据写入脚本
=============================================
供 cron 调用，根据当前时段（早报/晚报）将新闻条目写入 data/news.json。

data/news.json 新格式：
{
  "updated": "YYYY-MM-DD",
  "morning": { "period": "早报", "items": [...] },
  "evening": { "period": "晚报", "items": [...] }
}

合并规则：
  - 写入早报时保留同一天的 evening 旧数据
  - 写入晚报时保留同一天的 morning 旧数据
  - 如果是新的一天，清空另一时段旧数据

用法（供 cron 脚本调用）：
  from scripts.build_news_json import write_news_section
  write_news_section(period='morning', items=[...])

或直接命令行测试（使用占位条目）：
  python3 scripts/build_news_json.py --period morning --dry-run
"""

import json
import os
import sys
import argparse
from datetime import date, datetime

# ─── 路径配置 ────────────────────────────────────────────────────────────────
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJ_ROOT  = os.path.dirname(_SCRIPT_DIR)
NEWS_JSON   = os.path.join(_PROJ_ROOT, "data", "news.json")

# ─── 时段判断 ────────────────────────────────────────────────────────────────
def current_period() -> str:
    """
    根据当前时刻判断时段：
      00:00–12:59 → 'morning'（早报）
      13:00–23:59 → 'evening'（晚报）
    """
    return "morning" if datetime.now().hour < 13 else "evening"


# ─── 核心写入函数 ─────────────────────────────────────────────────────────────
def write_news_section(
    period: str,          # 'morning' 或 'evening'
    items: list,          # 新闻条目列表
    today: str = None,    # YYYY-MM-DD，默认当天
    news_path: str = NEWS_JSON,
) -> dict:
    """
    将 items 写入 news.json 对应时段分区，保留另一时段同天数据。

    Returns:
        更新后的完整 news.json 内容（dict）
    """
    assert period in ("morning", "evening"), f"period 必须是 morning 或 evening，收到: {period}"

    today = today or date.today().strftime("%Y-%m-%d")
    other = "evening" if period == "morning" else "morning"
    period_label = "早报" if period == "morning" else "晚报"

    # 读取旧数据
    old: dict = {}
    if os.path.exists(news_path):
        try:
            with open(news_path, "r", encoding="utf-8") as f:
                old = json.load(f)
        except (json.JSONDecodeError, IOError):
            old = {}

    old_date = old.get("updated", "")

    # 判断是否需要保留另一时段数据（同一天才保留）
    if old_date == today and isinstance(old.get(other), dict):
        other_section = old[other]
    else:
        # 跨天 → 清空另一时段
        other_section = {"period": ("晚报" if other == "evening" else "早报"), "items": []}

    new_data = {
        "updated": today,
        period: {
            "period": period_label,
            "items": items,
        },
        other: other_section,
    }

    with open(news_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"[build_news_json] ✅ 已写入 {period_label} ({len(items)} 条) → {news_path}")
    return new_data


# ─── 旧格式迁移工具 ────────────────────────────────────────────────────────────
def migrate_legacy(news_path: str = NEWS_JSON) -> bool:
    """
    将旧格式 {"updated":..., "period":..., "items":[...]} 迁移到新格式。
    已是新格式则跳过。Returns True 若执行了迁移。
    """
    if not os.path.exists(news_path):
        return False

    with open(news_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    # 已是新格式
    if "morning" in data or "evening" in data:
        return False

    # 旧格式迁移
    legacy_period = data.get("period", "晚报")
    section_key   = "morning" if legacy_period == "早报" else "evening"
    other_key     = "evening" if section_key == "morning" else "morning"
    other_label   = "晚报" if other_key == "evening" else "早报"

    new_data = {
        "updated": data.get("updated", date.today().strftime("%Y-%m-%d")),
        section_key: {
            "period": legacy_period,
            "items": data.get("items", []),
        },
        other_key: {
            "period": other_label,
            "items": [],
        },
    }

    with open(news_path, "w", encoding="utf-8") as f:
        json.dump(new_data, f, ensure_ascii=False, indent=2)

    print(f"[build_news_json] 🔄 旧格式已迁移 → {section_key} 分区")
    return True


# ─── CLI 入口 ─────────────────────────────────────────────────────────────────
def _build_sample_items(period_label: str) -> list:
    """生成测试占位条目（dry-run 用）"""
    now_str = datetime.now().strftime("%H:%M")
    prefix  = period_label + " · 测试"
    return [
        {
            "time": f"{prefix} ({now_str})",
            "title": f"【{period_label}测试条目】build_news_json.py dry-run 写入验证",
            "summary": "此条目由 dry-run 模式生成，可安全删除。",
            "source": "build_news_json/test",
            "impact": {"gold": "中性", "ashare": "中性", "nasdaq": "中性", "retail": "中性"},
            "reason": "测试条目，不代表真实影响判断。",
        }
    ]


def main():
    parser = argparse.ArgumentParser(
        description="玄枢早晚报数据写入脚本",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例：
  python3 scripts/build_news_json.py --migrate          # 迁移旧格式
  python3 scripts/build_news_json.py --period morning   # dry-run 写入早报测试条目
  python3 scripts/build_news_json.py --period evening   # dry-run 写入晚报测试条目
  python3 scripts/build_news_json.py --auto             # 按当前时间自动判断时段 dry-run
        """,
    )
    parser.add_argument("--period",  choices=["morning", "evening"], help="指定时段")
    parser.add_argument("--auto",    action="store_true", help="自动按当前时间判断时段")
    parser.add_argument("--migrate", action="store_true", help="迁移旧格式 news.json")
    parser.add_argument("--path",    default=NEWS_JSON,  help=f"news.json 路径 (默认: {NEWS_JSON})")

    args = parser.parse_args()

    if args.migrate:
        changed = migrate_legacy(args.path)
        if not changed:
            print("[build_news_json] news.json 已是新格式，无需迁移。")
        return

    period = args.period or (current_period() if args.auto else None)
    if not period:
        parser.print_help()
        sys.exit(1)

    label  = "早报" if period == "morning" else "晚报"
    items  = _build_sample_items(label)
    write_news_section(period=period, items=items, news_path=args.path)


if __name__ == "__main__":
    main()
