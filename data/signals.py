import json
import os
from datetime import datetime

# ── 路径 ─────────────────────────────────────────────────────
_SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
_ROOT          = os.path.dirname(_SCRIPT_DIR)
_PORTFOLIO_PATH = os.path.join(_ROOT, "data", "portfolio.json")
_VALUATION_PATH = os.path.join(_ROOT, "data", "valuation.json")
_INDICATORS_PATH = os.path.join(_ROOT, "data", "indicators.json")
_OUT_PATH      = os.path.join(_ROOT, "data", "signals.json")


# ── 加载辅助数据 ──────────────────────────────────────────────
def _load_valuation_map():
    """返回 {category: {verdict, verdict_score}} 的映射，读取失败返回 {}。"""
    try:
        with open(_VALUATION_PATH, encoding="utf-8") as f:
            data = json.load(f)
        return {
            v["category"]: {
                "verdict":       v.get("verdict", "数据缺失"),
                "verdict_score": v.get("verdict_score", 50),
            }
            for v in data.get("valuations", [])
        }
    except Exception:
        return {}


def _load_portfolio_map():
    """
    返回 {code: {asset_type, category, ratio, target_ratio}} 的映射。
    读取失败返回 {}。
    """
    try:
        with open(_PORTFOLIO_PATH, encoding="utf-8") as f:
            pf = json.load(f)
        target = pf.get("targetAllocation", {})
        result = {}
        for h in pf.get("holdings", []):
            code     = h["code"]
            cat      = h.get("category", "")
            ratio    = h.get("ratio", 0)          # 当前持仓占比（%）
            t_ratio  = target.get(cat, 0)          # 目标占比（%）
            result[code] = {
                "asset_type":   h.get("assetType", "oscillation"),
                "category":     cat,
                "ratio":        ratio,
                "target_ratio": t_ratio,
            }
        return result
    except Exception:
        return {}


def _load_portfolio_raw() -> dict:
    """返回完整的 portfolio.json 原始数据，读取失败返回 {}。"""
    try:
        with open(_PORTFOLIO_PATH, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# ── 技术评分（原逻辑，不变）────────────────────────────────────
def _tech_score(item: dict):
    """计算买入/卖出技术评分及原因，返回 (buy_score, sell_score, reasons)。"""
    rsi        = item.get("rsi14")
    ma5        = item.get("ma5")
    ma20       = item.get("ma20")
    prev_ma5   = item.get("prev_ma5")
    prev_ma20  = item.get("prev_ma20")
    macd_hist  = item.get("macd_hist")

    buy_score  = 0
    sell_score = 0
    reasons    = []

    if rsi is not None:
        if rsi < 30:
            buy_score += 2
            reasons.append(f"RSI超卖({rsi:.1f}<30)→买入")
        elif rsi > 70:
            sell_score += 2
            reasons.append(f"RSI超买({rsi:.1f}>70)→卖出")
        elif rsi < 45:
            buy_score += 1
            reasons.append(f"RSI偏低({rsi:.1f})")
        elif rsi > 60:
            sell_score += 1
            reasons.append(f"RSI偏高({rsi:.1f})")

    if all(v is not None for v in [ma5, ma20, prev_ma5, prev_ma20]):
        if prev_ma5 < prev_ma20 and ma5 >= ma20:
            buy_score += 2
            reasons.append("金叉(MA5上穿MA20)")
        elif prev_ma5 > prev_ma20 and ma5 <= ma20:
            sell_score += 2
            reasons.append("死叉(MA5下穿MA20)")
        elif ma5 > ma20:
            buy_score += 1
            reasons.append("MA5>MA20多头")
        else:
            sell_score += 1
            reasons.append("MA5<MA20空头")

    if macd_hist is not None:
        if macd_hist > 0:
            buy_score += 1
            reasons.append("MACD柱正向")
        else:
            sell_score += 1
            reasons.append("MACD柱负向")

    return buy_score, sell_score, reasons


# ── 趋势型信号（不择时，只看仓位偏离+估值）────────────────────
def _trend_signal(item: dict, pf_info: dict, val_score: int, val_verdict: str):
    """
    回测铁律：趋势型资产择时有害，改为仓位管理建议。
    deviation_pt = 当前比例 - 目标比例（正=超配，负=低配）
    注：估值"不适用"/"数据缺失"时，仅按仓位偏离判断，不依赖估值分数。
    """
    ratio        = pf_info.get("ratio", 0)
    target_ratio = pf_info.get("target_ratio", 0)
    deviation_pt = round(ratio - target_ratio, 1)
    name         = item.get("name", "")
    # 估值无效时（黄金无PE、数据缺失）score不参与判断，视为估值中性(=50)
    val_na       = val_verdict in ("不适用", "数据缺失")
    eff_score    = 50 if val_na else val_score

    if deviation_pt < -5 and eff_score <= 60:
        signal      = "定投补仓"
        signal_type = "trend_dca"
        val_str     = "估值无阻力" if val_na else f"估值{val_verdict}"
        reason      = f"低配{abs(deviation_pt):.1f}pt，{val_str}，可分批补入"
        action      = (f"{name} 当前{ratio:.1f}% 低于目标{target_ratio:.1f}%，缺口{abs(deviation_pt):.1f}pt；"
                       f"{val_str}(score={eff_score})，建议分批定投补仓")
    elif deviation_pt > 5 and eff_score >= 70:
        signal      = "可减仓"
        signal_type = "trend_trim"
        reason      = f"超配{deviation_pt:.1f}pt且估值{val_verdict}，可适当减仓"
        action      = (f"{name} 当前{ratio:.1f}% 超目标{target_ratio:.1f}%达{deviation_pt:.1f}pt；"
                       f"估值{val_verdict}(score={eff_score})，建议减至目标附近")
    elif deviation_pt > 5 and eff_score < 70:
        signal      = "持有"
        signal_type = "trend_hold"
        val_str     = "估值无阻力" if val_na else f"估值{val_verdict}"
        reason      = f"虽超配{deviation_pt:.1f}pt但{val_str}，暂不减仓"
        action      = (f"{name} 虽超配{deviation_pt:.1f}pt（当前{ratio:.1f}%/目标{target_ratio:.1f}%），"
                       f"但{val_str}(score={eff_score})；回测优于择时，维持持有")
    else:
        signal      = "持有"
        signal_type = "trend_hold"
        reason      = "买入持有策略，回测优于择时"
        dev_str     = (f"超配{deviation_pt:.1f}pt" if deviation_pt > 0
                       else (f"低配{abs(deviation_pt):.1f}pt" if deviation_pt < -1 else "接近目标"))
        action      = (f"{name} 仓位{dev_str}(当前{ratio:.1f}%/目标{target_ratio:.1f}%)；"
                       f"回测证明趋势型择时跑输持有，维持持有")

    return signal, signal_type, reason, action, deviation_pt


# ── 震荡型信号（技术+估值双确认）─────────────────────────────
def _oscillation_signal(item: dict, pf_info: dict, buy_score: int, sell_score: int,
                        val_score: int, val_verdict: str, tech_reasons: list):
    name         = item.get("name", "")
    ratio        = pf_info.get("ratio", 0)
    target_ratio = pf_info.get("target_ratio", 0)
    deviation_pt = round(ratio - target_ratio, 1)

    base_reason = " · ".join(tech_reasons) if tech_reasons else "指标中性"

    if buy_score >= 3 and val_score <= 40:
        signal      = "买入"
        signal_type = "oscillation_buy"
        reason      = f"{base_reason}；估值{val_verdict}支持"
        action      = f"{name} 技术买入信号(buy={buy_score})，估值{val_verdict}(score={val_score})，可建仓/加仓"
    elif buy_score >= 3 and val_score <= 70:
        signal      = "可加仓"
        signal_type = "oscillation_add"
        reason      = f"{base_reason}；估值{val_verdict}，轻仓可加"
        action      = f"{name} 技术买入信号(buy={buy_score})，估值{val_verdict}(score={val_score})，可小幅加仓"
    elif buy_score >= 3 and val_score > 70:
        signal      = "观望（估值不支持）"
        signal_type = "oscillation_watch_val"
        reason      = f"{base_reason}；但估值{val_verdict}(score={val_score})偏高，信号无效"
        action      = f"{name} 技术信号偏多但估值{val_verdict}(score={val_score})，等待回调至合理区间再介入"
    # ── 中等买入门槛（buy_score>=2）─────────────────────────────
    elif buy_score >= 2 and val_score <= 30:
        signal      = "低估可加"
        signal_type = "oscillation_add_low"
        reason      = f"{base_reason}；估值{val_verdict}(score={val_score})低位，中等技术信号确认"
        action      = f"{name} 技术偏多(buy={buy_score})且估值处于低位(score={val_score}，{val_verdict})，可分批加仓"
    elif buy_score >= 2 and val_score <= 50:
        signal      = "可加仓"
        signal_type = "oscillation_add_mid"
        reason      = f"{base_reason}；估值{val_verdict}(score={val_score})适中，技术信号偏多"
        action      = f"{name} 技术偏多(buy={buy_score})，估值{val_verdict}(score={val_score})，可小仓位介入"
    # ── 卖出方向（sell_score>=2 + 估值偏高）──────────────────────
    elif sell_score >= 2 and val_score >= 70:
        signal      = "谨慎持有"
        signal_type = "oscillation_caution"
        reason      = f"{base_reason}；估值{val_verdict}(score={val_score})偏高，技术趋弱"
        action      = f"{name} 技术趋弱(sell={sell_score})且估值偏高(score={val_score}，{val_verdict})，建议谨慎持有，不加仓"
    elif sell_score >= 3 and val_score >= 60:
        signal      = "减仓"
        signal_type = "oscillation_sell"
        reason      = f"{base_reason}；估值{val_verdict}偏高，技术+估值双杀"
        action      = f"{name} 技术卖出信号(sell={sell_score})+估值{val_verdict}(score={val_score})，建议减仓"
    elif sell_score >= 3 and val_score < 60:
        signal      = "观望"
        signal_type = "oscillation_watch"
        reason      = f"{base_reason}；估值{val_verdict}尚可，暂观望"
        action      = f"{name} 技术偏弱(sell={sell_score})但估值{val_verdict}(score={val_score})，不急减仓，持仓观望"
    elif val_score <= 20:
        signal      = "低估可加"
        signal_type = "oscillation_val_low"
        reason      = f"估值{val_verdict}(score={val_score})，技术中性，估值驱动可小加"
        action      = f"{name} 估值处于低位(score={val_score}，{val_verdict})，技术中性，可分批小额加仓"
    elif val_score >= 80:
        signal      = "高估警惕"
        signal_type = "oscillation_val_high"
        reason      = f"估值{val_verdict}(score={val_score})，注意高估风险"
        action      = f"{name} 估值偏高(score={val_score}，{val_verdict})，持仓需谨慎，等待回调"
    else:
        signal      = "持有观察"
        signal_type = "oscillation_hold"
        reason      = base_reason + "；信号中性，持仓观察"
        dev_str     = f"偏离{deviation_pt:+.1f}pt" if abs(deviation_pt) > 1 else "接近目标"
        action      = f"{name} 技术中性(buy={buy_score}/sell={sell_score})，估值{val_verdict}(score={val_score})，仓位{dev_str}，继续持仓观察"

    return signal, signal_type, reason, action, deviation_pt


# ── 品类聚合偏离计算 ──────────────────────────────────────────
def _build_category_deviation(portfolio_map: dict) -> dict:
    """
    计算每个品类的总实际占比和目标占比，返回：
    {category: {"total_ratio": float, "target_ratio": float, "deviation": float,
                "codes": [code,...], "amounts_by_code": {code: ratio}}}
    用于同品类合并信号（避免同品类内矛盾信号）。
    """
    cat_info: dict = {}
    for code, info in portfolio_map.items():
        cat = info.get("category", "")
        if not cat:
            continue
        if cat not in cat_info:
            cat_info[cat] = {
                "total_ratio":   0.0,
                "target_ratio":  info.get("target_ratio", 0),
                "deviation":     0.0,
                "codes":         [],
                "ratios_by_code": {},
            }
        cat_info[cat]["total_ratio"]  = round(cat_info[cat]["total_ratio"] + info.get("ratio", 0), 2)
        cat_info[cat]["codes"].append(code)
        cat_info[cat]["ratios_by_code"][code] = info.get("ratio", 0)

    for cat, v in cat_info.items():
        v["deviation"] = round(v["total_ratio"] - v["target_ratio"], 2)

    return cat_info


# ── 主生成函数 ────────────────────────────────────────────────
def generate_signals(indicators, portfolio_map=None, valuation_map=None, portfolio_raw=None):
    """
    向后兼容：portfolio_map/valuation_map 可为 None（兜底纯技术逻辑）。
    同品类合并逻辑：趋势型资产按品类整体偏离决定统一方向。
    portfolio_raw: 完整 portfolio.json 数据，用于扫描待建仓品类（pendingFunds）。
    """
    if portfolio_map is None:
        portfolio_map = {}
    if valuation_map is None:
        valuation_map = {}
    if portfolio_raw is None:
        portfolio_raw = {}

    # 预计算品类整体偏离
    cat_deviation_map = _build_category_deviation(portfolio_map)

    signals = []

    for item in indicators:
        code = item["code"]
        name = item["name"]

        # 持仓信息（含 assetType / category / ratio）
        pf_info    = portfolio_map.get(code, {})
        asset_type = pf_info.get("asset_type", "oscillation")
        category   = pf_info.get("category", "")

        # 估值信息（按 category 匹配）
        val_info    = valuation_map.get(category, {})
        val_score   = val_info.get("verdict_score", 50) if val_info else 50
        val_verdict = val_info.get("verdict", "数据缺失") if val_info else "数据缺失"
        has_val     = bool(val_info)

        # 技术评分（所有类型都算，趋势型不用但保留字段）
        buy_score, sell_score, tech_reasons = _tech_score(item)

        # ── cash：跳过 ────────────────────────────────────────
        if asset_type == "cash":
            continue

        # ── 趋势型：同品类合并，按品类整体偏离统一方向 ───────────
        if asset_type == "trend":
            cat_dev_info  = cat_deviation_map.get(category, {})
            cat_deviation = cat_dev_info.get("deviation", pf_info.get("ratio", 0) - pf_info.get("target_ratio", 0))
            cat_target    = cat_dev_info.get("target_ratio", pf_info.get("target_ratio", 0))
            cat_total     = cat_dev_info.get("total_ratio", pf_info.get("ratio", 0))
            codes_in_cat  = cat_dev_info.get("codes", [code])
            ratios_by_code = cat_dev_info.get("ratios_by_code", {code: pf_info.get("ratio", 0)})

            # 品类整体超配：同品类所有基金统一"持有"（用品类整体偏离覆盖 pf_info）
            # 品类整体低配：只对该品类中持仓最小的那只建议"定投补仓"，其余"持有"
            is_smallest_in_cat = (
                len(codes_in_cat) <= 1
                or ratios_by_code.get(code, 0) == min(ratios_by_code.get(c, 0) for c in codes_in_cat)
            )

            # 构造品类整体视角的 pf_info（用品类加总偏离替换单只偏离）
            cat_pf_info = dict(pf_info)
            cat_pf_info["ratio"]        = cat_total
            cat_pf_info["target_ratio"] = cat_target

            if cat_deviation > 5:
                # 品类整体超配：所有基金统一持有，不论单只偏离
                signal      = "持有"
                signal_type = "trend_hold_cat_overweight"
                reason      = (f"品类{category}整体超配{cat_deviation:+.1f}pt"
                               f"（合计{cat_total:.1f}%/目标{cat_target:.1f}%），不择时减仓")
                action      = (f"{name} 所属品类{category}整体超配{cat_deviation:.1f}pt，"
                               f"趋势型不建议择时减仓，维持持有")
                deviation_pt = round(pf_info.get("ratio", 0) - pf_info.get("target_ratio", 0), 1)
            elif cat_deviation < -5:
                # 品类整体低配：只对持仓最小的基金建议补仓，集中一只
                if is_smallest_in_cat:
                    signal, signal_type, reason, action, deviation_pt = _trend_signal(
                        item, cat_pf_info, val_score, val_verdict
                    )
                    # 补仓理由改为品类整体视角
                    reason = (f"品类{category}整体低配{abs(cat_deviation):.1f}pt，"
                              f"集中补仓持仓最小的{name}")
                    action = (f"{name} 是{category}中持仓最小的基金({pf_info.get('ratio',0):.1f}%)；"
                              f"品类合计{cat_total:.1f}%/目标{cat_target:.1f}%，"
                              f"建议集中定投补仓此只，不分散")
                else:
                    signal      = "持有"
                    signal_type = "trend_hold_cat_concentrate"
                    reason      = (f"品类{category}整体低配，但集中补仓{name}以外的持仓更小的基金")
                    action      = (f"{name} 属{category}低配品类，但已有更小持仓的基金需优先补仓，维持持有")
                    deviation_pt = round(pf_info.get("ratio", 0) - pf_info.get("target_ratio", 0), 1)
            else:
                signal, signal_type, reason, action, deviation_pt = _trend_signal(
                    item, pf_info, val_score, val_verdict
                )

        # ── 震荡型 / 主动型（active 同震荡型逻辑）─────────────
        else:
            signal, signal_type, reason, action, deviation_pt = _oscillation_signal(
                item, pf_info, buy_score, sell_score, val_score, val_verdict, tech_reasons
            )

        signals.append({
            # ── 原有字段（向后兼容）──────────────────────
            "code":       code,
            "name":       name,
            "rsi14":      item.get("rsi14"),
            "ma5":        item.get("ma5"),
            "ma20":       item.get("ma20"),
            "macd_hist":  item.get("macd_hist"),
            "macd_trend": item.get("macd_trend", ""),
            "signal":     signal,
            "reason":     reason,
            "buy_score":  buy_score,
            "sell_score": sell_score,
            # ── 新增字段 ──────────────────────────────────
            "asset_type":        asset_type,
            "signal_type":       signal_type,
            "valuation_verdict": val_verdict if has_val else None,
            "valuation_score":   val_score   if has_val else None,
            "deviation_pt":      deviation_pt,
            "action_detail":     action,
        })

    # ── 待建仓品类扫描 ────────────────────────────────────────
    # 找出 targetAllocation 中实际持仓为0但目标>0的品类，生成建仓建议信号
    target_alloc  = portfolio_raw.get("targetAllocation", {})
    pending_funds = portfolio_raw.get("pendingFunds", {})
    holdings      = portfolio_raw.get("holdings", [])

    # 已持仓品类集合
    held_categories = {h.get("category", "") for h in holdings if h.get("assetType") != "cash"}

    for cat, target_pct in target_alloc.items():
        if target_pct <= 0:
            continue
        if cat in held_categories:
            continue  # 已有持仓，跳过
        # 该品类无任何持仓 → 生成待建仓信号
        val_info    = valuation_map.get(cat, {})
        val_score   = val_info.get("verdict_score", 50) if val_info else 50
        val_verdict = val_info.get("verdict", "数据缺失") if val_info else "数据缺失"

        # 从 pendingFunds 读取备选基金
        pf_entry    = pending_funds.get(cat, {})
        primary     = pf_entry.get("primary", {})
        fund_code   = primary.get("code", "TBD")
        fund_name   = primary.get("name", cat + "（待选）")

        # 按估值分位决定信号文字
        if val_score <= 40:
            signal      = "低估可建仓"
            action      = f"估值低位(score={val_score}，{val_verdict})，{cat}目标仓位{target_pct}%，可开始分批建仓"
        elif val_score <= 60:
            signal      = "估值适中可试水"
            action      = f"估值适中(score={val_score}，{val_verdict})，{cat}目标仓位{target_pct}%，可小额开始建仓"
        elif val_score <= 80:
            signal      = "估值偏贵等回调"
            action      = f"估值偏高(score={val_score}，{val_verdict})，建议等待{cat}估值回落再建仓"
        else:
            signal      = "高估暂缓建仓"
            action      = f"估值过高(score={val_score}，{val_verdict})，暂不建仓{cat}，等候回调"

        reason = f"{cat}当前持仓为0(目标{target_pct}%)，{val_verdict}(score={val_score})"

        signals.append({
            "code":              fund_code,
            "name":              fund_name,
            "rsi14":             None,
            "ma5":               None,
            "ma20":              None,
            "macd_hist":         None,
            "macd_trend":        "",
            "signal":            signal,
            "reason":            reason,
            "buy_score":         0,
            "sell_score":        0,
            "asset_type":        "pending",
            "signal_type":       "pending_build",
            "valuation_verdict": val_verdict,
            "valuation_score":   val_score,
            "deviation_pt":      -float(target_pct),  # 完全空仓 = 目标全缺口
            "action_detail":     action,
        })

    return signals


# ── 入口 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    with open(_INDICATORS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    indicators    = data.get("indicators", [])
    portfolio_map = _load_portfolio_map()
    valuation_map = _load_valuation_map()
    portfolio_raw = _load_portfolio_raw()

    if not portfolio_map:
        print("  portfolio.json 读取失败，使用纯技术逻辑")
    if not valuation_map:
        print("  valuation.json 读取失败，估值字段为 null")
    if not portfolio_raw:
        print("  portfolio_raw 读取失败，跳过待建仓品类扫描")

    signals = generate_signals(indicators, portfolio_map, valuation_map, portfolio_raw)

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "signals": signals,
    }

    with open(_OUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成 {len(signals)} 条信号 → data/signals.json\n")

    # 统计信号分布
    from collections import Counter
    sig_counter = Counter(s["signal"] for s in signals)
    print(f"  信号分布: {dict(sig_counter)}\n")

    # 按 asset_type 分组打印
    ICONS = {
        "买入": "▲", "可加仓": "△", "定投补仓": "↗",
        "减仓": "▼", "可减仓": "↘",
        "观望": "─", "观望（估值不支持）": "─", "持有": "●", "持有观察": "◎",
        "低估可加": "★", "高估警惕": "⚠",
    }
    for s in signals:
        icon = ICONS.get(s["signal"], "?")
        at   = f"[{s['asset_type'][:4]}]"
        print(f"  {icon} {at} {s['name']:24s}  {s['signal']:12s}  {s['action_detail']}")
