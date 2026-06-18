#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 再平衡建议（真实持仓版）
=====================================
数据来源：
  - data/portfolio.json  持仓金额（真实快照，由 update_portfolio.py 维护）
  - data/signals.json    技术信号（振荡型标的判断加减方向）

设计要点：
  - 分母 = 总资产 − 余额宝（余额宝作子弹，不计入再平衡盘）
  - targetAllocation 从 portfolio.json 读取（已在 Task 1 更新为 7 类 100%）
  - 三重判定逻辑：
      trend       → 持有/小幅减，附回测结论（择时跑输买入持有）
      oscillation → 结合 signals.json 当前技术信号加减
      active      → 读 active_funds.json 真实诊断（P1 已接入）
      待建仓      → actual=0 but target>0，标记缺口金额

用法：
    python3 data/rebalance.py
输出：
    data/rebalance.json
"""

import json
import os
from datetime import datetime

SCRIPT_DIR   = os.path.dirname(os.path.abspath(__file__))
ROOT         = os.path.dirname(SCRIPT_DIR)
PORTFOLIO    = os.path.join(ROOT, "data", "portfolio.json")
SIGNALS      = os.path.join(ROOT, "data", "signals.json")
ACTIVE_FUNDS = os.path.join(ROOT, "data", "active_funds.json")
OUT_PATH     = os.path.join(ROOT, "data", "rebalance.json")

REBALANCE_THRESHOLD = 5.0   # 触发建议的偏差门槛（百分点）

# ── 资产类型映射 ─────────────────────────────────────────────
ASSET_TYPE_MAP = {
    "黄金":       "trend",
    "有色金属":   "trend",
    "纳指100":    "trend",
    "标普500":    "trend",
    "AI/科技":    "oscillation",
    "光伏/新能源": "oscillation",
    "高端制造":   "active",
    "货币基金":   "cash",
}

# ── 振荡型→信号代理基金（从 signals.json 查对应技术信号） ─────────
SIGNAL_PROXY = {
    "AI/科技":    "008585",   # 天弘AI主题指数C 作为 AI/科技类信号代理
    "光伏/新能源": "515790",  # 华夏光伏ETF 作为光伏类信号代理
}

# ── 趋势型回测结论备注 ────────────────────────────────────────
TREND_BACKTEST = {
    "黄金":    "回测3年信号择时α=-21.8pt（策略+4.9% vs 持有+26.7%），建议长期持有核心仓位",
    "有色金属":"回测3年信号择时α=-2.3pt，趋势型资产以持有为主",
    "纳指100": "回测3年信号择时α=-22.0pt（策略+9.9% vs 持有+31.9%），建议分批定投建仓",
    "标普500":  "回测3年信号择时α=-11.6pt（策略+11.9% vs 持有+23.5%），建议分批定投建仓",
}


# ── 信号归一化 ───────────────────────────────────────────────
def load_signals() -> dict:
    """返回 {code: signal_str} 和 {code: entry}"""
    if not os.path.exists(SIGNALS):
        return {}
    with open(SIGNALS, encoding="utf-8") as f:
        d = json.load(f)
    return {s["code"]: s for s in d.get("signals", [])}


def load_active_diagnoses() -> dict:
    """
    读取 data/active_funds.json，返回 {code: diagnosis_dict}。
    active_fund_diagnose.py 未运行时返回 {}。
    """
    if not os.path.exists(ACTIVE_FUNDS):
        return {}
    try:
        with open(ACTIVE_FUNDS, encoding="utf-8") as f:
            d = json.load(f)
        return {f["code"]: f for f in d.get("funds", [])}
    except Exception:
        return {}


def get_category_signal(category: str, sig_map: dict) -> str | None:
    """获取某类别对应的技术信号（买入/卖出/观望），找不到返回 None。"""
    proxy = SIGNAL_PROXY.get(category)
    if not proxy:
        return None
    entry = sig_map.get(proxy)
    if not entry:
        return None
    return entry.get("signal", "观望")


# ── 三重判定逻辑 ─────────────────────────────────────────────
def decide_action(
    category: str,
    asset_type: str,
    actual_pct: float,
    target_pct: float,
    deviation: float,
    deviation_amount: float,
    signal: str | None,
    active_diag: dict | None = None,   # 主动基金诊断结果（来自 active_funds.json）
) -> dict:
    """
    返回 {"action", "reason", "priority", "recommend_amount"}
    priority: high / medium / low
    recommend_amount: 正=建议操作金额（元），None=无具体金额建议
    """
    # ── 待建仓：实际持仓为零但目标>0 ─────────────────────────────
    if actual_pct == 0 and target_pct > 0:
        note = TREND_BACKTEST.get(category, "")
        return {
            "action":           "待建仓",
            "reason":           (
                f"目标配置 {target_pct}%，当前持仓为零，缺口约 ¥{abs(deviation_amount):,.0f}。"
                f"{note}"
            ),
            "priority":         "medium",
            "recommend_amount": abs(deviation_amount),
        }

    # ── trend 资产 ───────────────────────────────────────────────
    if asset_type == "trend":
        backtest = TREND_BACKTEST.get(category, "趋势型资产，择时效果有限")
        if deviation > REBALANCE_THRESHOLD:
            return {
                "action":           "持有/小幅减",
                "reason":           (
                    f"超配 {deviation:+.1f}pt（实际 {actual_pct:.1f}% vs 目标 {target_pct}%），"
                    f"但趋势型资产不建议大幅择时减仓。{backtest}。"
                    f"如有资金需求可小幅赎回约 ¥{min(abs(deviation_amount)*0.3, 5000):,.0f} 归位。"
                ),
                "priority":         "low",
                "recommend_amount": min(abs(deviation_amount) * 0.3, 5000),
            }
        elif deviation < -REBALANCE_THRESHOLD:
            return {
                "action":           "可定投补仓",
                "reason":           (
                    f"低配 {deviation:+.1f}pt（实际 {actual_pct:.1f}% vs 目标 {target_pct}%），"
                    f"建议以定投方式补仓，避免择时。{backtest}"
                ),
                "priority":         "medium",
                "recommend_amount": abs(deviation_amount),
            }
        else:
            return {
                "action":   "持有",
                "reason":   f"偏差 {deviation:+.1f}pt，在容忍区间内（±{REBALANCE_THRESHOLD}pt），无需操作",
                "priority": "low",
                "recommend_amount": None,
            }

    # ── oscillation 资产 ─────────────────────────────────────────
    if asset_type == "oscillation":
        signal = signal or "观望"
        if deviation > REBALANCE_THRESHOLD:
            if signal == "卖出":
                return {
                    "action":           "减仓",
                    "reason":           f"超配 {deviation:+.1f}pt + 技术信号{signal}，双重确认建议减仓至目标位",
                    "priority":         "high",
                    "recommend_amount": abs(deviation_amount),
                }
            elif signal == "买入":
                return {
                    "action":           "暂缓减仓",
                    "reason":           f"超配 {deviation:+.1f}pt 但技术信号{signal}，建议暂缓减仓，等待信号转弱",
                    "priority":         "medium",
                    "recommend_amount": None,
                }
            else:
                return {
                    "action":           "小幅减仓",
                    "reason":           f"超配 {deviation:+.1f}pt，技术面{signal}，可适量减仓归位",
                    "priority":         "medium",
                    "recommend_amount": abs(deviation_amount) * 0.5,
                }
        elif deviation < -REBALANCE_THRESHOLD:
            if signal == "买入":
                return {
                    "action":           "加仓",
                    "reason":           f"低配 {deviation:+.1f}pt + 技术信号{signal}，双重确认建议加仓",
                    "priority":         "high",
                    "recommend_amount": abs(deviation_amount),
                }
            elif signal == "卖出":
                return {
                    "action":           "暂缓加仓",
                    "reason":           f"低配 {deviation:+.1f}pt 但技术信号{signal}，建议等待信号好转再补仓",
                    "priority":         "low",
                    "recommend_amount": None,
                }
            else:
                return {
                    "action":           "可小幅加仓",
                    "reason":           f"低配 {deviation:+.1f}pt，技术面{signal}，可小幅补仓",
                    "priority":         "medium",
                    "recommend_amount": abs(deviation_amount) * 0.5,
                }
        else:
            return {
                "action":   "持有观察",
                "reason":   f"偏差 {deviation:+.1f}pt 在容忍区间内，按技术信号 [{signal}] 灵活操作",
                "priority": "low",
                "recommend_amount": None,
            }

    # ── active 资产（主动基金，优先读 active_funds.json 诊断）────────
    if asset_type == "active":
        if active_diag:
            d_action  = active_diag.get("diagnosis", {}).get("action", "持有但关注")
            d_reasons = active_diag.get("diagnosis", {}).get("reasons", [])
            d_warns   = active_diag.get("diagnosis", {}).get("warnings", [])
            official  = active_diag.get("official_name", "")
            mismatch  = active_diag.get("name_mismatch", False)
            pct_rank  = active_diag.get("rank_percentile_ytd")
            alpha     = active_diag.get("alpha_pct")

            parts = []
            if mismatch:
                parts.append(f"⚠️ 代码与名称不符（官方:{official}）")
            if pct_rank:
                parts.append(f"同类排名前{pct_rank:.0f}%")
            if isinstance(alpha, (int, float)):
                parts.append(f"α={alpha:+.1f}pt")
            parts += d_reasons[:2]
            reason_str = "；".join(parts) if parts else "已运行主动基诊断，请查看 active_funds.json"
            if d_warns:
                reason_str += "  |  警告：" + d_warns[0]

            # 动作映射到再平衡建议
            if d_action == "建议评估替换":
                action = "建议调研替换"
                priority = "medium"
            elif d_action == "持有但关注":
                action = "持有观察"
                priority = "low"
            else:
                action = "可持有"
                priority = "low"

            return {
                "action":           action,
                "reason":           reason_str,
                "priority":         priority,
                "recommend_amount": None,
                "active_diag_ref":  True,
            }
        else:
            return {
                "action":   "待主动基诊断",
                "reason":   (
                    f"主动型基金（偏差 {deviation:+.1f}pt），需结合基金经理策略判断。"
                    f"请先运行 python3 scripts/active_fund_diagnose.py 生成诊断报告。"
                ),
                "priority": "low",
                "recommend_amount": None,
            }

    # ── 其他 ─────────────────────────────────────────────────────
    return {
        "action": "持有", "reason": "类型未识别，维持原仓", "priority": "low",
        "recommend_amount": None,
    }


# ── 子弹分配建议 ─────────────────────────────────────────────
def build_bullet_plan(bullet_amount: float, actions: list) -> list:
    """
    根据余额宝可用资金，按优先级给出分配建议：
      1. 待建仓 类别（高优先级）
      2. 低配但偏差>5pt 的 oscillation/trend 类别
    """
    plan = []
    remaining = bullet_amount
    # 按优先级排序
    priority_order = {"high": 0, "medium": 1, "low": 2}
    candidates = [a for a in actions
                  if a["action"] in ("待建仓", "加仓", "可小幅加仓", "可定投补仓")
                  and (a.get("recommend_amount") or 0) > 0]
    candidates.sort(key=lambda x: priority_order.get(x["priority"], 3))

    for c in candidates:
        if remaining <= 10:
            break
        alloc = min(remaining, c.get("recommend_amount") or 0, bullet_amount)
        if alloc <= 0:
            continue
        plan.append({
            "category": c["category"],
            "action":   c["action"],
            "alloc":    round(alloc, 2),
            "note":     f"从余额宝调入 ¥{alloc:,.0f} → {c['category']}",
        })
        remaining = round(remaining - alloc, 2)

    return plan


# ── 具体操作指令生成 ──────────────────────────────────────────
def build_operations(actions: list, invest_holdings: list, total_value: float, portfolio: dict) -> list:
    """
    生成具体可执行的操作指令（operations 数组）。

    卖出：品类超配 → 赎回持仓最大的基金，金额 = 超配比例 × 总资产 × 50%（取整到百）
    买入：品类低配/待建仓 → 买入持仓最小的基金（待建仓从 target/fund_recommendations.json 取），
          金额 = 低配比例 × 总资产 × 30%（取整到百）
    """
    operations = []

    # 按持仓金额建索引：{category: [(amount, code, name), ...]}
    cat_holdings: dict = {}
    for h in invest_holdings:
        cat = h.get("category", "")
        if not cat:
            continue
        cat_holdings.setdefault(cat, []).append((h.get("amount", 0), h["code"], h["name"]))

    # 加载可选推荐基金（待建仓用）
    fund_rec_path = os.path.join(ROOT, "data", "fund_recommendations.json")
    fund_rec: dict = {}
    if os.path.exists(fund_rec_path):
        try:
            with open(fund_rec_path, encoding="utf-8") as f:
                fund_rec = json.load(f)
        except Exception:
            pass

    target_alloc = portfolio.get("targetAllocation", {})

    for a in actions:
        cat         = a["category"]
        deviation   = a["deviation"]          # 正=超配，负=低配
        asset_type  = a["asset_type"]
        action_str  = a["action"]

        # ── 卖出（超配 > 5pt）──────────────────────────────────
        if deviation > 5 and asset_type in ("trend", "oscillation"):
            holdings_in_cat = cat_holdings.get(cat, [])
            if not holdings_in_cat:
                continue
            # 选持仓金额最大的基金
            holdings_in_cat_sorted = sorted(holdings_in_cat, key=lambda x: -x[0])
            sell_fund_amount, sell_code, sell_name = holdings_in_cat_sorted[0]

            raw_amount = (deviation / 100) * total_value * 0.5
            amount = max(int(round(raw_amount / 100) * 100), 100)

            # 不卖超过持仓本身
            amount = min(amount, int(sell_fund_amount // 100 * 100))
            if amount <= 0:
                continue

            operations.append({
                "action":     "sell",
                "fund_code":  sell_code,
                "fund_name":  sell_name,
                "amount":     amount,
                "reason":     f"{cat}品类超配{deviation:.1f}pt，赎回持仓最大的基金约¥{amount:,}以归位",
            })

        # ── 买入（低配 < -5pt 或待建仓）────────────────────────
        elif (deviation < -5 or a.get("actual_pct", 0) == 0) and asset_type in ("trend", "oscillation"):
            holdings_in_cat = cat_holdings.get(cat, [])
            low_deviation   = abs(deviation) if deviation < 0 else float(target_alloc.get(cat, 0))

            if holdings_in_cat:
                # 选持仓最小的
                holdings_in_cat_sorted = sorted(holdings_in_cat, key=lambda x: x[0])
                _, buy_code, buy_name = holdings_in_cat_sorted[0]
            else:
                # 待建仓：从 portfolio.json target 里找，再到 fund_recommendations.json
                buy_code = None
                buy_name = None
                # 先尝试 fund_recommendations
                rec_entry = fund_rec.get(cat)
                if rec_entry:
                    buy_code = rec_entry.get("code")
                    buy_name = rec_entry.get("name", cat + "推荐基金")
                if not buy_code:
                    # 没有推荐，标注待选
                    buy_code = "TBD"
                    buy_name = f"{cat}（待选基金）"

            raw_amount = (low_deviation / 100) * total_value * 0.3
            amount = max(int(round(raw_amount / 100) * 100), 100)

            operations.append({
                "action":     "buy",
                "fund_code":  buy_code,
                "fund_name":  buy_name,
                "amount":     amount,
                "reason":     (f"{cat}品类低配{abs(deviation):.1f}pt（目标{target_alloc.get(cat,0)}%/实际{a.get('actual_pct',0):.1f}%），"
                               f"分批建仓约¥{amount:,}"),
            })

    return operations


# ── 主流程 ────────────────────────────────────────────────────

def main():
    # 1. 读取持仓
    with open(PORTFOLIO, encoding="utf-8") as f:
        portfolio = json.load(f)

    holdings   = portfolio["holdings"]
    target_map = portfolio.get("targetAllocation", {})
    update_time = portfolio.get("updateTime", "unknown")

    # 2. 区分余额宝（子弹）和投资性持仓
    bullet = next((h for h in holdings if h.get("assetType") == "cash"), None)
    bullet_amount = bullet["amount"] if bullet else 0.0
    invest_holdings = [h for h in holdings if h.get("assetType") != "cash"]

    # 3. 分母 = 总资产 - 余额宝（子弹不计入再平衡）
    total_value = round(sum(h["amount"] for h in invest_holdings), 2)

    # 4. 按 category 聚合真实金额
    cat_amount: dict[str, float] = {}
    for h in invest_holdings:
        cat = h["category"]
        cat_amount[cat] = round(cat_amount.get(cat, 0) + h["amount"], 2)

    # 5. 读取技术信号和主动基诊断
    sig_map      = load_signals()
    active_diags = load_active_diagnoses()

    # 对每个 active 类别，找最差的诊断结果（代表最需要关注的持仓）
    def get_active_diag_for_category(cat: str) -> dict | None:
        """取该类别下诊断评分最低（最需要关注）的持仓诊断。"""
        fund_codes = [h["code"] for h in invest_holdings
                      if h.get("category") == cat and h.get("assetType") == "active"]
        if not fund_codes:
            return None
        diags = [active_diags[c] for c in fund_codes if c in active_diags]
        if not diags:
            return None
        # 取诊断 score 最低（最差）的那个
        return min(diags, key=lambda d: d.get("diagnosis", {}).get("score", 100))

    # 6. 对每个目标类别计算偏差并决策
    all_categories = set(list(target_map.keys()) + list(cat_amount.keys()))
    actions = []
    for cat in sorted(all_categories):
        target_pct    = float(target_map.get(cat, 0))
        actual_amount = cat_amount.get(cat, 0.0)
        actual_pct    = round(actual_amount / total_value * 100, 2) if total_value else 0.0
        deviation     = round(actual_pct - target_pct, 2)
        target_amount = round(target_pct / 100 * total_value, 2)
        deviation_amount = round(deviation / 100 * total_value, 2)

        asset_type  = ASSET_TYPE_MAP.get(cat, "unknown")
        signal      = get_category_signal(cat, sig_map)
        active_diag = get_active_diag_for_category(cat) if asset_type == "active" else None
        decision    = decide_action(
            cat, asset_type, actual_pct, target_pct,
            deviation, deviation_amount, signal, active_diag
        )

        needs_action = abs(deviation) >= REBALANCE_THRESHOLD or actual_pct == 0

        entry = {
            "category":       cat,
            "asset_type":     asset_type,
            "target_pct":     target_pct,
            "actual_pct":     actual_pct,
            "actual_amount":  actual_amount,
            "target_amount":  target_amount,
            "deviation":      deviation,
            "deviation_amount": deviation_amount,
            "signal":         signal,
            "action":         decision["action"],
            "reason":         decision["reason"],
            "priority":       decision["priority"],
            "recommend_amount": decision.get("recommend_amount"),
            "needs_action":   needs_action,
        }
        if decision.get("active_diag_ref"):
            entry["active_diag_ref"] = True
        actions.append(entry)

    # 按优先级 + 偏差绝对值排序
    prio = {"high": 0, "medium": 1, "low": 2}
    actions.sort(key=lambda x: (prio.get(x["priority"], 3), -abs(x["deviation"])))

    # 7. 子弹分配建议
    bullet_plan = build_bullet_plan(bullet_amount, actions)

    # 7b. 具体操作指令
    operations = build_operations(actions, invest_holdings, total_value, portfolio)

    # 8. 构造输出
    output = {
        "portfolio_updateTime": update_time,
        "updated_at":           datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_value":          total_value,
        "rebalance_threshold_pct": REBALANCE_THRESHOLD,
        "bullet": {
            "code":          bullet["code"] if bullet else "000198",
            "name":          bullet["name"] if bullet else "余额宝",
            "amount":        bullet_amount,
            "description":   "货币基金作为子弹，不计入再平衡盘，优先补低配/待建仓类别",
            "plan":          bullet_plan,
        },
        "operations": operations,
        "actions": actions,
        "summary": {
            "overweight":          [a["category"] for a in actions if a["deviation"] > REBALANCE_THRESHOLD],
            "underweight":         [a["category"] for a in actions if 0 < a["actual_pct"] < a["target_pct"] and abs(a["deviation"]) > REBALANCE_THRESHOLD],
            "to_establish":        [a["category"] for a in actions if a["actual_pct"] == 0 and a["target_pct"] > 0],
            "pending_diagnosis":   [a["category"] for a in actions if a["asset_type"] == "active"],
        },
    }

    with open(OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    # ── 打印摘要 ──────────────────────────────────────────────
    print(f"\n玄枢Alpha · 再平衡建议（真实持仓）")
    print(f"  持仓快照: {update_time}  |  投资性资产: ¥{total_value:,.2f}  |  子弹: ¥{bullet_amount:,.2f}\n")
    print(f"  {'类别':<12} {'类型':^10} {'目标':>6} {'实际':>6} {'偏差':>7} {'信号':^6} {'建议'}")
    print("  " + "─" * 72)
    for a in sorted(actions, key=lambda x: x["category"]):
        sign = "+" if a["deviation"] >= 0 else ""
        sig  = a["signal"] or "—"
        print(f"  {a['category']:<12} {a['asset_type']:^10} "
              f"{a['target_pct']:>5.1f}% {a['actual_pct']:>5.1f}%  "
              f"{sign}{a['deviation']:>5.1f}pt  {sig:^6}  {a['action']}")
    print(f"\n  待建仓: {output['summary']['to_establish']}")
    print(f"  超配  : {output['summary']['overweight']}")
    print(f"  低配  : {output['summary']['underweight']}")
    print(f"\n✅ 已保存 → {OUT_PATH}")


if __name__ == "__main__":
    main()
