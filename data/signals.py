import json
from datetime import datetime


def generate_signals(indicators):
    signals = []

    for item in indicators:
        rsi = item.get("rsi14")
        ma5 = item.get("ma5")
        ma20 = item.get("ma20")
        prev_ma5 = item.get("prev_ma5")
        prev_ma20 = item.get("prev_ma20")
        macd_hist = item.get("macd_hist")
        macd_trend = item.get("macd_trend", "")

        buy_score = 0
        sell_score = 0
        reasons = []

        # RSI signal
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

        # MA crossover (golden/death cross)
        if all(v is not None for v in [ma5, ma20, prev_ma5, prev_ma20]):
            golden_cross = prev_ma5 < prev_ma20 and ma5 >= ma20
            death_cross = prev_ma5 > prev_ma20 and ma5 <= ma20

            if golden_cross:
                buy_score += 2
                reasons.append(f"金叉(MA5上穿MA20)")
            elif death_cross:
                sell_score += 2
                reasons.append(f"死叉(MA5下穿MA20)")
            elif ma5 > ma20:
                buy_score += 1
                reasons.append("MA5>MA20多头")
            else:
                sell_score += 1
                reasons.append("MA5<MA20空头")

        # MACD histogram direction
        if macd_hist is not None:
            if macd_hist > 0:
                buy_score += 1
                reasons.append("MACD柱正向")
            else:
                sell_score += 1
                reasons.append("MACD柱负向")

        # Final signal: need score >= 3 to trigger
        if buy_score >= 3 and buy_score > sell_score:
            signal = "买入"
        elif sell_score >= 3 and sell_score > buy_score:
            signal = "卖出"
        else:
            signal = "观望"

        signals.append({
            "code": item["code"],
            "name": item["name"],
            "rsi14": rsi,
            "ma5": ma5,
            "ma20": ma20,
            "macd_hist": macd_hist,
            "macd_trend": macd_trend,
            "signal": signal,
            "reason": " · ".join(reasons) if reasons else "指标中性，建议观望",
            "buy_score": buy_score,
            "sell_score": sell_score,
        })

    return signals


if __name__ == "__main__":
    with open("data/indicators.json", "r", encoding="utf-8") as f:
        data = json.load(f)

    indicators = data.get("indicators", [])
    signals = generate_signals(indicators)

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "signals": signals,
    }

    with open("data/signals.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ 已生成 {len(signals)} 条信号 → data/signals.json\n")
    for s in signals:
        icon = "▲ 买入" if s["signal"] == "买入" else "▼ 卖出" if s["signal"] == "卖出" else "— 观望"
        print(f"  {icon}  {s['name']:20s}  {s['reason']}")
