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


# ── 主生成函数 ────────────────────────────────────────────────
def generate_signals(indicators, portfolio_map=None, valuation_map=None):
    """
    向后兼容：portfolio_map/valuation_map 可为 None（兜底纯技术逻辑）。
    """
    if portfolio_map is None:
        portfolio_map = {}
    if valuation_map is None:
        valuation_map = {}

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

        # ── 趋势型 ────────────────────────────────────────────
        if asset_type == "trend":
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

    return signals


# ── 入口 ─────────────────────────────────────────────────────
if __name__ == "__main__":
    with open(_INDICATORS_PATH, encoding="utf-8") as f:
        data = json.load(f)

    indicators    = data.get("indicators", [])
    portfolio_map = _load_portfolio_map()
    valuation_map = _load_valuation_map()

    if not portfolio_map:
        print("  ⚠ portfolio.json 读取失败，使用纯技术逻辑")
    if not valuation_map:
        print("  ⚠ valuation.json 读取失败，估值字段为 null")

    signals = generate_signals(indicators, portfolio_map, valuation_map)

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
