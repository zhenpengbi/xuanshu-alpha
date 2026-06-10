"""
build_fusion.py — 融合决策卡生成器

读取 data/portfolio.json（权威来源，动态加载）
    + data/signals.json（技术信号）
    + value_compass/data/value_compass.json（价值评级）
生成 value_compass/data/fusion.json

禁止硬编码基金代码；所有标的从 portfolio.json 动态加载。

资产分类由 portfolio.json 的 assetType 字段决定：
  trend       — 黄金/有色金属（宏观/大宗），回测证明信号择时跑输买入持有
  oscillation — AI/科技/光伏（成长型），技术信号×价值面双确认有效
  active      — 高端制造（主动管理），参考 active_funds.json 诊断结论
  cash        — 货币基金（子弹），跳过不出现在融合卡
"""

import json
import os
from datetime import datetime

# ── 路径 ─────────────────────────────────────────────────────
_BASE_DIR = os.path.dirname(os.path.abspath(__file__))
_ROOT_DIR = os.path.dirname(_BASE_DIR)

def _load_portfolio():
    path = os.path.join(_ROOT_DIR, "data", "portfolio.json")
    with open(path, encoding="utf-8") as f:
        return json.load(f)

# ── 从 portfolio.json 动态构建配置（禁止硬编码旧代码）────────────
_pf = _load_portfolio()
_holdings_raw = [h for h in _pf.get("holdings", []) if h.get("assetType") != "cash"]

HOLDINGS = [{"code": h["code"], "name": h["name"]} for h in _holdings_raw]

NOT_APPLICABLE = {h["code"] for h in _holdings_raw if h.get("assetType") == "trend"}
APPLICABLE     = {h["code"] for h in _holdings_raw if h.get("assetType") in ("oscillation", "active")}

ASSET_TYPE = {h["code"]: h.get("assetType", "unknown") for h in _holdings_raw}

# ── 趋势型资产：回测 Alpha 标注（旧代码参考，新代码写通用结论）────
_TREND_BACKTEST_NOTE = {
    # 黄金（两只）
    "002963": "回测参考：黄金择时长期跑输买入持有（α约-21pt），建议长期持有核心仓位",
    "000307": "回测参考：黄金择时长期跑输买入持有（α约-21pt），建议长期持有核心仓位",
    # 有色金属
    "010990": "回测参考：有色金属择时跑输买入持有（α约-2pt），建议以持有为主",
}

# ── 信号代理映射（oscillation/active → signals.json 中的代理代码）
# signals.json 由 data/signals.py 生成，其 FUNDS 列表与 portfolio.json 不完全一致
# 用最接近的品类代理基金
_SIGNAL_PROXY = {
    # AI/科技 → signals.json 的 AI 代理（待 signals.py 更新后可直接匹配）
    "011840": "011840",  # 直接匹配（若 signals.json 有）
    "014881": "011840",  # 机器人ETF 用 AI主题 作代理
    # 光伏
    "012885": "012885",  # 直接匹配（若 signals.json 有）
    # active（主动基金不依赖技术信号，此处仅保留以便未来扩展）
    "015790": None,
    "025647": None,
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
        # 先用信号代理映射查找，再直接查，最后默认观望
        proxy_code = _SIGNAL_PROXY.get(code, code)
        sig_entry  = sig_map.get(proxy_code) or sig_map.get(code) or {}
        raw_signal  = sig_entry.get("signal", "观望")
        tech_signal = normalize_tech(raw_signal)
        tech_reason = sig_entry.get("reason", "")

        if code in NOT_APPLICABLE:
            # 趋势型资产：回测证明信号择时跑输买入持有，建议长期持有
            backtest_note = _TREND_BACKTEST_NOTE.get(code, "")
            items.append({
                "code": code,
                "name": name,
                "asset_type": ASSET_TYPE.get(code, "trend"),
                "applicable": False,
                "tech_signal": tech_signal,
                "value_rating": "价值框架不适用(宏观/宽基资产)",
                "action": "长期持有",
                "reason": (
                    f"回测显示趋势型资产择时跑输买入持有，建议长期持有或定投，不做短线择时。"
                    f"{backtest_note}。"
                    f"当前技术信号仅供参考：{tech_reason or tech_signal}"
                ),
                "level": "neutral",
            })

        elif code in APPLICABLE:
            asset_type_val = ASSET_TYPE.get(code, "oscillation")
            vc_entry = vc_map.get(code)

            # ── active 主动基金：专用逻辑 ──────────────────────────
            if asset_type_val == "active":
                # 主动基金不走技术×价值矩阵；建议来自 active_funds.json
                items.append({
                    "code": code,
                    "name": name,
                    "asset_type": "active",
                    "applicable": True,
                    "tech_signal": tech_signal,
                    "value_rating": "主动管理型",
                    "action": "见主动基诊断",
                    "reason": (
                        f"主动管理型基金，巴菲特穿透框架结论仅供参考。"
                        f"重仓为高端制造/航天/国防电子，多数超出巴菲特能力圈（灰评）。"
                        f"详细建议见「主动基诊断」模块。"
                    ),
                    "level": "neutral",
                    "value_source_note": f"真实持仓穿透 {vc_entry.get('latest_quarter', '') if vc_entry else ''}",
                })

            # ── oscillation 震荡型：技术×价值矩阵 ────────────────────
            elif vc_entry and "fund_quality_summary" in vc_entry:
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
                    "asset_type": asset_type_val,
                    "applicable": True,
                    "tech_signal": tech_signal,
                    "value_rating": value_rating,
                    "action": decision["action"],
                    "reason": decision["reason"],
                    "level": decision["level"],
                    "value_source_note": f"真实持仓穿透 {vc_entry.get('latest_quarter', '')}",
                    "value_verdict": verdict,
                })
            else:
                items.append({
                    "code": code,
                    "name": name,
                    "asset_type": ASSET_TYPE.get(code, "oscillation"),
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
