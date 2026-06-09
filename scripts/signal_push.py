#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha 信号推送脚本（方向一 · 方案C：每日简报 + 突变加急）

逻辑：
1. 拉取线上 signals.json + fusion.json（GitHub Pages）
2. 与上次快照对比，检测信号/动作突变
3. 生成每日简报文案（突变时顶部加 🚨 加急标记）
4. 输出到 stdout（由 cron agentTurn 读取后推送大象）

快照存储：~/.openclaw/xuanshu-alpha/last_snapshot.json（持久化目录）
"""
import json
import os
import sys
import urllib.request
from datetime import datetime

SIGNALS_URL = "https://zhenpengbi.github.io/xuanshu-alpha/data/signals.json"
FUSION_URL = "https://zhenpengbi.github.io/xuanshu-alpha/value_compass/data/fusion.json"

SNAPSHOT_DIR = os.path.expanduser("~/.openclaw/xuanshu-alpha")
SNAPSHOT_FILE = os.path.join(SNAPSHOT_DIR, "last_snapshot.json")

LEVEL_EMOJI = {"red": "🔴", "yellow": "🟡", "green": "🟢", "neutral": "⚪"}
SIGNAL_EMOJI = {"买入": "📈", "卖出": "📉", "持有": "➡️", "观望": "👀"}


def fetch_json(url):
    req = urllib.request.Request(url, headers={"User-Agent": "xuanshu-alpha-push/1.0"})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.loads(r.read().decode("utf-8"))


def load_snapshot():
    if os.path.exists(SNAPSHOT_FILE):
        try:
            return json.load(open(SNAPSHOT_FILE, encoding="utf-8"))
        except Exception:
            return {}
    return {}


def save_snapshot(snap):
    os.makedirs(SNAPSHOT_DIR, exist_ok=True)
    json.dump(snap, open(SNAPSHOT_FILE, "w", encoding="utf-8"),
              ensure_ascii=False, indent=2)


def main():
    try:
        signals = fetch_json(SIGNALS_URL)
        fusion = fetch_json(FUSION_URL)
    except Exception as e:
        print(f"❌ 玄枢Alpha 信号推送失败：无法拉取线上数据 — {e}")
        sys.exit(1)

    sig_map = {s["code"]: s for s in signals.get("signals", [])}
    fus_items = fusion.get("items", [])

    # 当前快照（用于对比）
    cur_snap = {}
    for it in fus_items:
        code = it["code"]
        cur_snap[code] = {
            "tech_signal": it.get("tech_signal"),
            "action": it.get("action"),
            "level": it.get("level"),
            "value_rating": it.get("value_rating"),
        }

    old_snap = load_snapshot()
    old_items = old_snap.get("items", {})

    # 检测突变
    changes = []
    for code, cur in cur_snap.items():
        old = old_items.get(code)
        name = next((it["name"] for it in fus_items if it["code"] == code), code)
        if old is None:
            continue  # 首次运行不算突变
        diffs = []
        if old.get("tech_signal") != cur.get("tech_signal"):
            diffs.append(f"技术信号 {old.get('tech_signal')}→{cur.get('tech_signal')}")
        if old.get("action") != cur.get("action"):
            diffs.append(f"操作建议 {old.get('action')}→{cur.get('action')}")
        if old.get("value_rating") != cur.get("value_rating"):
            diffs.append(f"价值评级 {old.get('value_rating')}→{cur.get('value_rating')}")
        if diffs:
            changes.append((name, code, diffs))

    # 生成文案
    lines = []
    is_urgent = len(changes) > 0

    if is_urgent:
        lines.append("🚨【玄枢Alpha 信号突变 · 加急】")
        lines.append("")
        for name, code, diffs in changes:
            lines.append(f"⚠️ {name}（{code}）")
            for d in diffs:
                lines.append(f"　• {d}")
        lines.append("")
        lines.append("─" * 12)
        lines.append("")

    lines.append(f"📊 玄枢Alpha 今日信号速报")
    lines.append(f"🕐 数据时间：{fusion.get('updated_at', 'N/A')}")
    lines.append("")

    for it in fus_items:
        code = it["code"]
        name = it["name"]
        level = it.get("level", "neutral")
        emoji = LEVEL_EMOJI.get(level, "⚪")
        tech = it.get("tech_signal", "-")
        action = it.get("action", "-")
        applicable = it.get("applicable", False)

        sig = sig_map.get(code, {})
        rsi = sig.get("rsi14")
        rsi_str = f" RSI{rsi:.0f}" if rsi is not None else ""

        if applicable:
            # 主动权益：技术×价值双确认
            verdict = it.get("value_verdict", "")
            lines.append(f"{emoji} {name}")
            lines.append(f"　技术：{tech}{rsi_str} ｜ 价值：{it.get('value_rating', '-')}")
            lines.append(f"　👉 {action}")
        else:
            # 宏观/宽基：仅技术信号
            lines.append(f"{emoji} {name}：{tech}{rsi_str} → {action}")
        lines.append("")

    lines.append("─" * 12)
    lines.append("🔗 详情：https://zhenpengbi.github.io/xuanshu-alpha/")

    text = "\n".join(lines)
    print(text)

    # 保存当前快照
    save_snapshot({
        "updated_at": fusion.get("updated_at"),
        "pushed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "items": cur_snap,
    })


if __name__ == "__main__":
    main()
