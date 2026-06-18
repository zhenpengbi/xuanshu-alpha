#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 止盈止损跟踪器
============================
从 positions.json 读取 status="open" 的持仓，
从 nav.json 获取最新净值，计算当前收益率，
并判断止损/止盈/移动止损是否触发。

触发后将 status 改为 "alert"（提醒用户，不自动关闭），
写回 positions.json。

用法：
    python3 scripts/position_tracker.py          # 更新现有 positions.json
    python3 scripts/position_tracker.py --init   # 从 portfolio.json 重新初始化
"""

import argparse
import json
import os
from datetime import datetime

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
ROOT          = os.path.dirname(SCRIPT_DIR)
POSITIONS_JSON = os.path.join(ROOT, "data", "positions.json")
PORTFOLIO_JSON = os.path.join(ROOT, "data", "portfolio.json")
NAV_JSON       = os.path.join(ROOT, "data", "nav.json")


# ── 工具函数 ──────────────────────────────────────────────────

def load_json(path: str, default=None):
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(path: str, data):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def get_latest_nav(funds_map: dict, code: str):
    """从 nav.json 的 funds.{code}.navs 取最后一个值。"""
    entry = funds_map.get(str(code))
    if not entry:
        return None
    navs = entry.get("navs", [])
    return float(navs[-1]) if navs else None


# ── 初始化：从 portfolio.json 生成持仓记录 ─────────────────────

def init_positions() -> dict:
    """根据 portfolio.json 当前持仓生成初始 positions.json。"""
    portfolio = load_json(PORTFOLIO_JSON)
    if not portfolio:
        raise FileNotFoundError(f"portfolio.json 不存在: {PORTFOLIO_JSON}")

    nav_data  = load_json(NAV_JSON, {})
    funds_nav = nav_data.get("funds", {})

    update_time = portfolio.get("updateTime", datetime.today().strftime("%Y-%m-%d"))
    positions = []

    for h in portfolio.get("holdings", []):
        if h.get("category") == "货币基金":
            continue
        code      = str(h.get("code", "")).strip()
        entry_nav = get_latest_nav(funds_nav, code)

        positions.append({
            "fund_code":         code,
            "fund_name":         h.get("name", ""),
            "entry_date":        update_time,
            "entry_nav":         entry_nav,
            "amount":            h.get("amount", 0),
            "status":            "open",
            "stop_loss_pct":     None,   # None = 使用 config 全局默认
            "take_profit_pct":   None,
            "trailing_stop_pct": None,
            "current_nav":       entry_nav,
            "highest_nav":       entry_nav,
            "current_return_pct": 0.0,
            "triggered":         None,
        })
        print(f"  init  {code} {h.get('name','')}  entry_nav={entry_nav}")

    output = {
        "config": {
            "stop_loss_pct":     -8,
            "take_profit_pct":   15,
            "trailing_stop_pct": -5,
        },
        "positions": positions,
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
    }
    return output


# ── 核心更新逻辑 ──────────────────────────────────────────────

def update_positions(data: dict, funds_nav: dict) -> tuple[dict, list]:
    """
    更新每条 open 持仓的 current_nav / highest_nav / current_return_pct，
    并判断止损/止盈/移动止损触发。
    返回 (updated_data, alert_list)。
    """
    config     = data.get("config", {})
    global_sl  = float(config.get("stop_loss_pct",     -8))
    global_tp  = float(config.get("take_profit_pct",   15))
    global_tsl = float(config.get("trailing_stop_pct", -5))

    alerts = []

    for pos in data.get("positions", []):
        if pos.get("status") not in ("open",):
            continue

        code      = str(pos.get("fund_code", "")).strip()
        entry_nav = pos.get("entry_nav")
        if not entry_nav:
            continue

        current_nav = get_latest_nav(funds_nav, code)
        if current_nav is None:
            print(f"  nav 缺失: {code}，跳过")
            continue

        entry_nav   = float(entry_nav)
        current_nav = float(current_nav)

        # 更新 highest_nav
        old_high    = float(pos.get("highest_nav") or entry_nav)
        highest_nav = max(old_high, current_nav)

        # 计算当前收益率
        current_return_pct = round((current_nav - entry_nav) / entry_nav * 100, 2)

        # 个人覆盖 > 全局默认
        sl  = float(pos["stop_loss_pct"])     if pos.get("stop_loss_pct")     is not None else global_sl
        tp  = float(pos["take_profit_pct"])   if pos.get("take_profit_pct")   is not None else global_tp
        tsl = float(pos["trailing_stop_pct"]) if pos.get("trailing_stop_pct") is not None else global_tsl

        # 判断触发
        triggered = None
        if current_return_pct <= sl:
            triggered = "stop_loss"
        elif current_return_pct >= tp:
            triggered = "take_profit"
        else:
            trailing_drawdown = (highest_nav - current_nav) / highest_nav * 100
            if trailing_drawdown >= abs(tsl):
                triggered = "trailing_stop"

        pos["current_nav"]       = round(current_nav, 4)
        pos["highest_nav"]       = round(highest_nav, 4)
        pos["current_return_pct"] = current_return_pct
        pos["triggered"]         = triggered

        if triggered:
            pos["status"] = "alert"
            alerts.append({
                "fund_code": code,
                "fund_name": pos.get("fund_name", ""),
                "triggered": triggered,
                "current_return_pct": current_return_pct,
                "sl": sl, "tp": tp, "tsl": tsl,
            })
            print(f"  [ALERT] {code} {pos.get('fund_name','')} -> {triggered}  return={current_return_pct:.2f}%")
        else:
            print(f"  ok     {code} {pos.get('fund_name','')}  return={current_return_pct:.2f}%")

    data["updated_at"] = datetime.now().strftime("%Y-%m-%d %H:%M")
    return data, alerts


# ── 主入口 ────────────────────────────────────────────────────

def main():
    ap = argparse.ArgumentParser(description="玄枢Alpha · 持仓跟踪器")
    ap.add_argument("--init", action="store_true", help="从 portfolio.json 重新初始化 positions.json")
    args = ap.parse_args()

    print(f"\n== 玄枢Alpha · 持仓跟踪 [{datetime.now().strftime('%H:%M:%S')}] ==\n")

    if args.init or not os.path.exists(POSITIONS_JSON):
        print("  初始化 positions.json ...")
        data = init_positions()
        save_json(POSITIONS_JSON, data)
        print(f"\n  已初始化 {len(data['positions'])} 条持仓记录")
        print(f"  写入 -> {POSITIONS_JSON}")
        return

    data     = load_json(POSITIONS_JSON, {})
    nav_data = load_json(NAV_JSON, {})
    if not nav_data:
        print("  nav.json 不存在，无法更新净值")
        return

    funds_nav = nav_data.get("funds", {})
    open_count = sum(1 for p in data.get("positions", []) if p.get("status") == "open")
    print(f"  open 持仓: {open_count} 条\n")

    data, alerts = update_positions(data, funds_nav)
    save_json(POSITIONS_JSON, data)

    print(f"\n  写入 -> {POSITIONS_JSON}")
    if alerts:
        print(f"\n  [警告] {len(alerts)} 条持仓触发提醒:")
        for a in alerts:
            label = {"stop_loss": f"触发止损({a['sl']}%)",
                     "take_profit": f"触发止盈(+{a['tp']}%)",
                     "trailing_stop": f"移动止损触发({a['tsl']}%)"}.get(a["triggered"], a["triggered"])
            print(f"    {a['fund_code']} {a['fund_name']} -> {label}  收益率={a['current_return_pct']:.2f}%")
    else:
        print("  所有持仓均在止盈止损范围内")

    print("\n  完成")


if __name__ == "__main__":
    main()
