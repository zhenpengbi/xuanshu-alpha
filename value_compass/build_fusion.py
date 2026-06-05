"""
build_fusion.py — 融合决策卡生成器

读取 data/signals.json + value_compass/data/value_compass.json
生成 value_compass/data/fusion.json

⚠️ DEMO 占位映射（本期临时，下期由 build_value_compass.py 重跑真实持仓基金后按 fund_code 直接匹配替换）：
  008585 (天弘AI主题指数C)  ← 使用 014880 (天弘中证机器人ETF联接) 的价值评级
  515790 (华夏光伏ETF)      ← 使用 001631 (天弘中证食品饮料ETF联接) 的价值评级
"""

import json
import os
from datetime import datetime

# ── 持仓标的清单（6个，硬编码） ────────────────────────────────
HOLDINGS = [
    {"code": "000216", "name": "易方达黄金ETF联接C"},
    {"code": "008585", "name": "天弘AI主题指数C"},
    {"code": "017766", "name": "南方有色金属ETF联接E"},
    {"code": "515790", "name": "华夏光伏ETF"},
    {"code": "513100", "name": "纳指100ETF"},
    {"code": "513500", "name": "标普500ETF"},
]

# ── 能力圈分类 ────────────────────────────────────────────────
# 价值框架【不适用】：宏观/宽基/大宗资产，巴菲特八问无法穿透
NOT_APPLICABLE = {"000216", "017766", "513100", "513500"}
# 价值框架【适用·可穿透】：持股基金，可看穿底层持仓质地
APPLICABLE = {"008585", "515790"}

# ── DEMO 映射表（本期临时占位） ───────────────────────────────
# key=持仓基金代码, value=value_compass.json 中对应的 fund_code
DEMO_VALUE_MAP = {
    "008585": "014880",  # AI主题 ← 机器人ETF评级（DEMO）
    "515790": "001631",  # 光伏ETF ← 食品饮料ETF评级（DEMO）
}


# ── 技术信号归一化 ────────────────────────────────────────────
# signals.json 实际字段：signal ∈ {"买入", "卖出", "观望"}
def normalize_tech(signal_str):
    if signal_str == "买入":
        return "买入"
    elif signal_str == "卖出":
        return "卖出"
    else:  # "观望" 或其他
        return "持有"


# ── 价值评级归一化 ────────────────────────────────────────────
# value_compass.json 实际字段：fund_quality_summary.weight_by_rating_in_top10_pct
# 规则：绿% >= 70 → 优质；(绿+黄)% >= 60 → 合格；else → 瑕疵
def normalize_value(fund_quality_summary):
    pct = fund_quality_summary.get("weight_by_rating_in_top10_pct", {})
    green = pct.get("绿", 0.0)
    yellow = pct.get("黄", 0.0)
    if green >= 70:
        return "优质"
    elif (green + yellow) >= 60:
        return "合格"
    else:
        return "瑕疵"


# ── 决策矩阵 ─────────────────────────────────────────────────
#               价值=优质         价值=合格           价值=瑕疵
# 技术=买入   强力加仓🟢        正常加仓🟢          仅小仓试探🟡
# 技术=持有   安心持有🟢        持有观察🟡          持有但盯紧🟡
# 技术=卖出   仅波段减仓不清仓🟡  减仓🟠             清仓离场🔴
MATRIX = {
    ("买入", "优质"): {
        "action": "强力加仓",
        "reason": "技术面买入信号 + 底层质地优质，双重确认，可积极加仓",
        "level": "green",
    },
    ("买入", "合格"): {
        "action": "正常加仓",
        "reason": "技术面买入 + 质地合格，信号成立，可正常加仓",
        "level": "green",
    },
    ("买入", "瑕疵"): {
        "action": "仅小仓试探",
        "reason": "技术面出现买入信号，但底层价值存瑕疵，仅小仓试探，严控仓位",
        "level": "yellow",
    },
    ("持有", "优质"): {
        "action": "安心持有",
        "reason": "底层质地优质，技术面暂无明确方向，无需操作，安心持有",
        "level": "green",
    },
    ("持有", "合格"): {
        "action": "持有观察",
        "reason": "质地合格，技术面中性，继续持有并等待更明确的信号变化",
        "level": "yellow",
    },
    ("持有", "瑕疵"): {
        "action": "持有但盯紧",
        "reason": "底层价值存瑕疵，技术面亦无支撑，需盯紧止损线，准备减仓",
        "level": "yellow",
    },
    ("卖出", "优质"): {
        "action": "仅波段减仓不清仓",
        "reason": "技术面偏弱，但底层质地优秀，仅做波段减仓，保留核心仓位",
        "level": "yellow",
    },
    ("卖出", "合格"): {
        "action": "减仓",
        "reason": "技术面卖出信号 + 底层质地一般，建议减仓控制风险敞口",
        "level": "orange",
    },
    ("卖出", "瑕疵"): {
        "action": "清仓离场",
        "reason": "技术面卖出 + 底层价值瑕疵，双重负向确认，建议清仓离场",
        "level": "red",
    },
}


def build():
    base_dir = os.path.dirname(os.path.abspath(__file__))
    root_dir = os.path.dirname(base_dir)

    # 加载 signals.json
    signals_path = os.path.join(root_dir, "data", "signals.json")
    with open(signals_path, encoding="utf-8") as f:
        signals_data = json.load(f)
    # 实际字段：signals[].code, .signal, .reason, .rsi14, .macd_trend 等
    sig_map = {s["code"]: s for s in signals_data.get("signals", [])}

    # 加载 value_compass.json
    vc_path = os.path.join(base_dir, "data", "value_compass.json")
    with open(vc_path, encoding="utf-8") as f:
        vc_data = json.load(f)
    # 实际字段：funds[].fund_code, .fund_quality_summary, .official_name
    vc_map = {fund["fund_code"]: fund for fund in vc_data.get("funds", [])}

    items = []

    for h in HOLDINGS:
        code = h["code"]
        name = h["name"]

        # 读取技术信号（实际字段名：signal）
        sig_entry = sig_map.get(code, {})
        raw_signal = sig_entry.get("signal", "观望")
        tech_signal = normalize_tech(raw_signal)
        tech_reason = sig_entry.get("reason", "")

        if code in NOT_APPLICABLE:
            # 宏观/宽基/大宗：不参与价值矩阵
            items.append({
                "code": code,
                "name": name,
                "applicable": False,
                "tech_signal": tech_signal,
                "value_rating": "价值框架不适用(宏观/宽基资产)",
                "action": "按技术信号执行",
                "reason": (
                    f"宏观/宽基/大宗资产，巴菲特八问框架不适用，仅参考技术信号。"
                    f"当前技术面：{tech_reason or tech_signal}"
                ),
                "level": "neutral",
            })

        elif code in APPLICABLE:
            # 可穿透基金：查 DEMO 映射
            vc_code = DEMO_VALUE_MAP.get(code)
            vc_entry = vc_map.get(vc_code) if vc_code else None

            if vc_entry and "fund_quality_summary" in vc_entry:
                summary = vc_entry["fund_quality_summary"]
                value_rating = normalize_value(summary)
                verdict = summary.get("verdict", "")
                decision = MATRIX.get(
                    (tech_signal, value_rating),
                    {"action": "持有观察", "reason": "信号组合未覆盖，建议观望", "level": "yellow"},
                )
                items.append({
                    "code": code,
                    "name": name,
                    "applicable": True,
                    "tech_signal": tech_signal,
                    "value_rating": value_rating,
                    "action": decision["action"],
                    "reason": decision["reason"],
                    "level": decision["level"],
                    "value_source_note": f"DEMO映射←{vc_code}({vc_entry.get('official_name', '')})",
                    "value_verdict": verdict,
                })
            else:
                items.append({
                    "code": code,
                    "name": name,
                    "applicable": True,
                    "tech_signal": tech_signal,
                    "value_rating": "暂无价值评级",
                    "action": "持有观察",
                    "reason": "技术信号中性，价值评级数据暂缺，建议观望等待数据更新",
                    "level": "muted",
                })

    output = {
        "updated_at": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "items": items,
    }

    out_path = os.path.join(base_dir, "data", "fusion.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"✅ fusion.json 已生成 → {out_path}\n")
    print(f"  {'代码':<8} {'名称':<22} {'技术':^6} {'价值':^12} {'动作'}")
    print("  " + "─" * 68)
    for item in items:
        mark = "✓" if item["applicable"] else "○"
        print(
            f"  {mark} {item['code']:<8} {item['name']:<22}"
            f" {item['tech_signal']:^6} {item['value_rating']:^14} {item['action']}"
        )


if __name__ == "__main__":
    build()
