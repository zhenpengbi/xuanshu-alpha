import json
from datetime import datetime

# 目标仓位配置
TARGET_ALLOCATION = [
    {"code": "000216", "name": "易方达黄金ETF联接C",   "target_pct": 24.0, "category": "黄金"},
    {"code": "008585", "name": "天弘AI主题指数C",       "target_pct": 30.0, "category": "AI/科技"},
    {"code": "017766", "name": "南方有色金属ETF联接E",  "target_pct":  8.0, "category": "有色金属"},
    {"code": "515790", "name": "华夏光伏ETF",           "target_pct":  4.0, "category": "光伏"},
    {"code": "513100", "name": "纳指100ETF",            "target_pct": 24.0, "category": "纳指100"},
    {"code": "513500", "name": "标普500ETF",            "target_pct": 10.0, "category": "标普500"},
]

# 假设持仓份额（模拟市场波动后的实际持仓，非等比目标值，体现现实偏差）
# 实际使用时请替换为真实持仓份额
ASSUMED_SHARES = {
    "000216": 4500,   # 黄金ETF联接C：黄金配置偏多（历史超配）
    "008585": 7200,   # AI主题指数C：AI配置偏少（赎回了一部分）
    "017766": 1350,   # 有色金属ETF联接E：有色略微超配
    "515790": 1500,   # 光伏ETF：光伏跌多了，份额缩水
    "513100": 6200,   # 纳指100ETF：纳指涨幅大，市值占比偏高
    "513500": 1800,   # 标普500ETF：标普略低配
}

REBALANCE_THRESHOLD = 5.0  # 偏差超过5%触发再平衡


if __name__ == "__main__":
    # 读取当前价格
    with open("data/prices.json", "r", encoding="utf-8") as f:
        prices_list = json.load(f)
    prices_map = {p["code"]: p for p in prices_list}

    # 计算各标的当前市值
    holdings = []
    total_value = 0.0
    for t in TARGET_ALLOCATION:
        code = t["code"]
        if code not in prices_map:
            print(f"  ✗ {code} 价格数据缺失，跳过")
            continue
        price = prices_map[code]["price"]
        shares = ASSUMED_SHARES.get(code, 0)
        value = round(price * shares, 2)
        total_value += value
        holdings.append({**t, "price": price, "shares": shares, "value": value})

    # 计算实际占比和偏差
    actions = []
    print(f"\n  {'标的':<22} {'目标':>6} {'实际':>6} {'偏差':>7} {'状态'}")
    print("  " + "-" * 56)

    for h in holdings:
        actual_pct = round(h["value"] / total_value * 100, 2) if total_value else 0.0
        deviation = round(actual_pct - h["target_pct"], 2)
        deviation_amount = round(deviation / 100 * total_value, 2)
        needs_rebalance = abs(deviation) >= REBALANCE_THRESHOLD

        flag = "⚠️ 再平衡" if needs_rebalance else "✓ 正常"
        sign = "+" if deviation >= 0 else ""
        print(f"  {h['name']:<22} {h['target_pct']:>5.1f}% {actual_pct:>5.1f}%  {sign}{deviation:>5.1f}pt  {flag}")

        actions.append({
            "code": h["code"],
            "name": h["name"],
            "category": h["category"],
            "target_pct": h["target_pct"],
            "actual_pct": actual_pct,
            "value": h["value"],
            "shares": h["shares"],
            "price": h["price"],
            "deviation": deviation,
            "deviation_amount": deviation_amount,
            "needs_rebalance": needs_rebalance,
        })

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "total_value": round(total_value, 2),
        "rebalance_threshold_pct": REBALANCE_THRESHOLD,
        "actions": actions,
    }

    with open("data/rebalance.json", "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    needs_count = sum(1 for a in actions if a["needs_rebalance"])
    print(f"\n  总市值: ¥{total_value:,.2f}")
    print(f"\n✅ 已保存 → data/rebalance.json  ({needs_count} 个标的需再平衡)")
