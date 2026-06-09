#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 价值罗盘 (Value Compass) — MVP
=========================================
基于巴菲特投资框架，对用户持仓【基金】做"持仓穿透 + 底层个股价值体检"。

链路：基金 → AKShare 穿透到前十大重仓股 → 拉取个股真实财务 → 巴菲特八问评级 → 按权重汇总基金质地

设计原则（产品信任壁垒）：
- 真实取数，取不到的字段诚实标 null，绝不编造财务数字
- 巴菲特八问基于真实可得财务 + 行业常识打分，非随机
- 看不懂 / 数据不足 → 评"灰-不予评级"（能力圈原则的灵魂）
- 货币/黄金类资产明确标注"非个股资产，框架不适用"

数据源：AKShare（东方财富/同花顺公开披露），免费中国金融数据库
"""
import json
import os
import time
import datetime as dt
import warnings

warnings.filterwarnings("ignore")
import akshare as ak
import pandas as pd

BASE = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE, "data")
os.makedirs(DATA_DIR, exist_ok=True)

# 真实可穿透持仓基金（持仓穿透分析对象）
PILOT_FUNDS = ["008585", "515790"]
PORTFOLIO_PATH = os.path.join(BASE, "..", "data", "portfolio.json")

# ---------- 工具函数 ----------

def safe_float(x):
    try:
        v = float(x)
        if pd.isna(v):
            return None
        return round(v, 4)
    except Exception:
        return None


def get_fund_official_name(code, name_table):
    if name_table is None:
        return None, None
    r = name_table[name_table["基金代码"] == code]
    if len(r):
        return r["基金简称"].values[0], r["基金类型"].values[0]
    return None, None


def fetch_fund_holdings(code, year="2026"):
    """穿透到基金最新季度前十大重仓股。返回 (latest_quarter, [ {code,name,ratio} ... ])
    联接基金(ETF联接)直接持股比例通常很小(主要持有目标ETF)，此处披露的是其穿透到的主题成分股。"""
    df = None
    last_err = None
    for attempt in range(3):
        try:
            df = ak.fund_portfolio_hold_em(symbol=code, date=year)
            break
        except Exception as e:
            last_err = e
            time.sleep(1.5)
    if df is None:
        return None, [], f"holdings_fetch_error: {repr(last_err)[:120]}"
    if df is None or len(df) == 0:
        return None, [], "no_holdings_data"
    quarters = list(df["季度"].unique())
    latest = quarters[-1]
    sub = df[df["季度"] == latest].copy()
    # 排序按占净值比例
    sub["占净值比例"] = pd.to_numeric(sub["占净值比例"], errors="coerce")
    sub = sub.sort_values("占净值比例", ascending=False).head(10)
    holds = []
    for _, row in sub.iterrows():
        holds.append({
            "stock_code": str(row["股票代码"]),
            "stock_name": str(row["股票名称"]),
            "ratio_pct": safe_float(row["占净值比例"]),  # 占基金净值比例
        })
    return latest, holds, None


def fetch_stock_financials(stock_code):
    """拉取个股核心财务指标（最新报告期）。返回 dict + 历年ROE序列。"""
    out = {
        "roe_pct": None,            # 净资产收益率
        "gross_margin_pct": None,   # 销售毛利率
        "net_margin_pct": None,     # 销售净利率
        "debt_ratio_pct": None,     # 资产负债率
        "ocf_to_netprofit_pct": None,  # 经营现金净流量/净利润（现金转化率代理）
        "rev_growth_pct": None,     # 主营业务收入增长率
        "profit_growth_pct": None,  # 净利润增长率
        "report_date": None,
        "roe_history": [],          # [(date, roe)] 近几期
        "error": None,
    }
    try:
        df = ak.stock_financial_analysis_indicator(symbol=stock_code, start_year="2020")
    except Exception as e:
        out["error"] = f"fin_error: {repr(e)[:100]}"
        return out
    if df is None or len(df) == 0:
        out["error"] = "no_fin_data"
        return out
    df = df.copy()
    df["_d"] = df["日期"].astype(str)
    df = df.sort_values("_d")
    cols = df.columns

    def col(name):
        return name if name in cols else None

    def g(row, name):
        c = col(name)
        return safe_float(row[c]) if c else None

    # 优先用最近一期【年报(12-31)】做估值门槛(ROE/成长/现金须用完整年度,避免季报年化失真)
    annuals = df[df["_d"].str.endswith("12-31")]
    use_annual = len(annuals) > 0
    base = annuals.iloc[-1] if use_annual else df.iloc[-1]
    latest = df.iloc[-1]

    out["report_date"] = str(base["日期"])
    out["report_is_annual"] = bool(use_annual)
    out["latest_period"] = str(latest["日期"])
    # ROE: 用年报(完整年度)
    out["roe_pct"] = g(base, "净资产收益率(%)")
    # 毛利率: 数据集中 销售毛利率 多为空, 用 主营业务利润率 作为毛利代理
    gm = g(base, "销售毛利率(%)")
    if gm is None:
        gm = g(base, "主营业务利润率(%)")
        out["gross_margin_source"] = "主营业务利润率(代理)"
    else:
        out["gross_margin_source"] = "销售毛利率"
    out["gross_margin_pct"] = gm
    out["net_margin_pct"] = g(base, "销售净利率(%)")
    out["debt_ratio_pct"] = g(latest, "资产负债率(%)")  # 负债率用最新即可
    # 现金转化率: 该字段为比率(0.96=96%), 转成百分比
    ocf = g(base, "经营现金净流量与净利润的比率(%)")
    if ocf is not None and abs(ocf) <= 5:  # 明显是比率而非百分比
        ocf = round(ocf * 100, 2)
    out["ocf_to_netprofit_pct"] = ocf
    out["rev_growth_pct"] = g(base, "主营业务收入增长率(%)")
    out["profit_growth_pct"] = g(base, "净利润增长率(%)")
    # 历年 ROE（仅取年报，反映可比的长期盈利能力）
    roe_c = col("净资产收益率(%)")
    if roe_c:
        src = annuals if use_annual else df
        hist = []
        for _, r in src.iterrows():
            v = safe_float(r[roe_c])
            if v is not None:
                hist.append((str(r["日期"]), v))
        out["roe_history"] = hist[-6:]
    return out


# ---------- 巴菲特八问评级 ----------
# 行业能力圈映射：哪些行业属于"普通人 + 巴菲特框架"看得懂的能力圈
# 绿/黄/红/灰：灰 = 超出能力圈或数据不足，不予评级（能力圈灵魂）

CIRCLE_OF_COMPETENCE = {
    # 看得懂、商业模式清晰、可用巴菲特框架（消费/食品饮料是巴菲特主场）
    "in": ["白酒", "食品", "饮料", "乳", "调味", "啤酒", "酒", "消费", "家电", "榨菜", "味业", "饮品", "食品饮料"],
    # 偏难但可尝试（制造/装备/新能源，需更谨慎）
    "borderline": [
        "机床", "机器人", "传动", "激光", "装备", "控制", "自动化", "电机", "工业",
        # 新能源/光伏产业链：商业模式逐步清晰但竞争格局激烈，能力圈边缘
        "光伏", "新能源", "逆变器", "储能", "硅片", "组件", "电池",
        "电器", "电气", "电网", "电力", "能源",
        "安防", "视频", "监控",
    ],
    # 超出能力圈（高度技术/半导体/AI算力，普通人难判断长期格局）
    "out": [
        "半导体", "芯片", "算力", "GPU", "光刻", "存储", "科技", "讯飞", "线程", "诺威",
        "服务器", "传感器", "曙光", "芯原",
    ],
}


# 个股代码→能力圈的显式映射（优先级高于关键词法，补充遗漏/纠正误判）
CODE_CIRCLE = {
    # 食品饮料/消费 - 能力圈内
    "600887": "in",   # 伊利(乳业)
    "000895": "in",   # 双汇(肉制)
    # 高端制造/工业 - 能力圈边缘
    "300124": "borderline",  # 汇川技术(工控)
    "002139": "borderline",  # 拓邦(智能控制)
    "300607": "borderline",  # 拓斯达(机器人装备)
    "002236": "borderline",  # 大华(安防/视频)
    # 008585 天弘AI主题 重仓股
    "300502": "borderline",  # 新易盛(光模块/光通信)
    "300308": "borderline",  # 中际旭创(光模块)
    "688256": "out",          # 寒武纪(AI芯片设计)
    "688008": "out",          # 澜起科技(内存接口芯片)
    "603019": "out",          # 中科曙光(高性能服务器/算力)
    "002415": "borderline",  # 海康威视(安防视频)
    "603501": "out",          # 豪威集团(CMOS图像传感器)
    "688521": "out",          # 芯原股份(芯片IP授权)
    "300442": "borderline",  # 润泽科技(数据中心IDC)
    "002230": "out",          # 科大讯飞(AI语音/NLP)
    # 515790 华夏光伏ETF 重仓股
    "600089": "borderline",  # 特变电工(输变电/新能源装备)
    "601012": "borderline",  # 隆基绿能(光伏硅片/组件)
    "300274": "borderline",  # 阳光电源(光伏逆变器)
    "000100": "borderline",  # TCL科技(面板+光伏)
    "605117": "borderline",  # 德业股份(逆变器/储能)
    "600438": "borderline",  # 通威股份(光伏电池片+饲料)
    "300751": "borderline",  # 迈为股份(光伏设备)
    "300757": "borderline",  # 罗博特科(光伏设备/自动化)
    "601877": "borderline",  # 正泰电器(低压电器+光伏)
    "002129": "borderline",  # TCL中环(单晶硅片)
    "300763": "borderline",  # 锦浪科技(逆变器)
    "002506": "borderline",  # 协鑫集成(光伏组件)
    "002459": "borderline",  # 晶澳科技(光伏组件)
    "002335": "borderline",  # 科华数据(UPS/数据中心)
    "688472": "borderline",  # 阿特斯(光伏组件)
}


def classify_circle(stock_name, stock_code):
    if stock_code in CODE_CIRCLE:
        return CODE_CIRCLE[stock_code]
    nm = stock_name
    for kw in CIRCLE_OF_COMPETENCE["out"]:
        if kw in nm:
            return "out"
    for kw in CIRCLE_OF_COMPETENCE["in"]:
        if kw in nm:
            return "in"
    for kw in CIRCLE_OF_COMPETENCE["borderline"]:
        if kw in nm:
            return "borderline"
    return "unknown"


def buffett_eight_questions(stock, fin):
    """
    巴菲特八问检查表，基于真实财务 + 行业常识。
    返回 {checks:{...}, rating, rating_reason, score}
    rating: 绿(优质可持有)/黄(观察)/红(回避)/灰(不予评级)
    """
    name = stock["stock_name"]
    code = stock["stock_code"]
    circle = classify_circle(name, code)
    checks = {}
    notes = []

    # Q1 能力圈：是否看得懂这门生意
    if circle == "out":
        checks["Q1_能力圈"] = "✗ 超出能力圈（高技术壁垒/格局难判断）"
        # 直接灰评，能力圈灵魂：不懂就不评
        return {
            "circle": circle,
            "checks": checks,
            "rating": "灰",
            "rating_label": "不予评级",
            "rating_reason": f"{name} 属于高技术/半导体/AI算力领域，长期竞争格局超出巴菲特框架与普通投资者能力圈，诚实标注「不知道」，不强行评级。",
            "score": None,
        }
    elif circle == "in":
        checks["Q1_能力圈"] = "✓ 在能力圈内（消费/食品饮料，商业模式清晰）"
    elif circle == "borderline":
        checks["Q1_能力圈"] = "△ 能力圈边缘（高端制造/工业自动化，需谨慎）"
    else:
        checks["Q1_能力圈"] = "？ 难以判断行业归属"

    # 数据可得性闸门：核心财务缺失太多 → 灰
    core = [fin.get("roe_pct"), fin.get("gross_margin_pct"), fin.get("net_margin_pct")]
    missing = sum(1 for x in core if x is None)
    if missing >= 2 or fin.get("error"):
        checks["数据"] = f"✗ 核心财务数据不足（缺{missing}/3，{fin.get('error') or ''}）"
        return {
            "circle": circle,
            "checks": checks,
            "rating": "灰",
            "rating_label": "不予评级",
            "rating_reason": f"{name} 核心财务数据缺失（{fin.get('error') or '披露不全'}），无法基于真实数据评估，诚实标注数据不足，不评级。",
            "score": None,
        }

    score = 0
    maxs = 0

    # Q2 商业模式 / 盈利能力：毛利率
    gm = fin.get("gross_margin_pct")
    maxs += 2
    if gm is not None:
        if gm >= 40:
            score += 2; checks["Q2_商业模式(毛利率)"] = f"✓ 毛利率 {gm}%（高，盈利质量好）"
        elif gm >= 20:
            score += 1; checks["Q2_商业模式(毛利率)"] = f"△ 毛利率 {gm}%（中等）"
        else:
            checks["Q2_商业模式(毛利率)"] = f"✗ 毛利率 {gm}%（偏低）"
    else:
        checks["Q2_商业模式(毛利率)"] = "？ 毛利率缺失"

    # Q3 护城河 / 长期回报：ROE（巴菲特最看重，>15% 为优）
    roe = fin.get("roe_pct")
    maxs += 3
    if roe is not None:
        if roe >= 15:
            score += 3; checks["Q3_护城河(ROE)"] = f"✓ ROE {roe}%（≥15%，护城河迹象明显）"
        elif roe >= 8:
            score += 1; checks["Q3_护城河(ROE)"] = f"△ ROE {roe}%（一般）"
        else:
            checks["Q3_护城河(ROE)"] = f"✗ ROE {roe}%（偏弱）"
        # ROE 稳定性加分
        hist = [v for _, v in fin.get("roe_history", [])]
        if len(hist) >= 4 and min(hist[-4:]) >= 10:
            checks["Q3b_ROE稳定性"] = f"✓ 近期 ROE 持续 ≥10%（{[round(h,1) for h in hist[-4:]]}）"
        elif len(hist) >= 4:
            checks["Q3b_ROE稳定性"] = f"△ ROE 波动（{[round(h,1) for h in hist[-4:]]}）"
    else:
        checks["Q3_护城河(ROE)"] = "？ ROE 缺失"

    # Q4 定价权 / 净利率
    nm_ = fin.get("net_margin_pct")
    maxs += 2
    if nm_ is not None:
        if nm_ >= 20:
            score += 2; checks["Q4_定价权(净利率)"] = f"✓ 净利率 {nm_}%（强定价权）"
        elif nm_ >= 8:
            score += 1; checks["Q4_定价权(净利率)"] = f"△ 净利率 {nm_}%（中等）"
        else:
            checks["Q4_定价权(净利率)"] = f"✗ 净利率 {nm_}%（薄利）"
    else:
        checks["Q4_定价权(净利率)"] = "？ 净利率缺失"

    # Q5 现金含金量：经营现金流/净利润
    ocf = fin.get("ocf_to_netprofit_pct")
    maxs += 2
    if ocf is not None:
        if ocf >= 80:
            score += 2; checks["Q5_现金含金量"] = f"✓ 经营现金流/净利润 {ocf}%（利润含金量高）"
        elif ocf >= 50:
            score += 1; checks["Q5_现金含金量"] = f"△ 现金转化 {ocf}%（一般）"
        else:
            checks["Q5_现金含金量"] = f"✗ 现金转化 {ocf}%（利润成色存疑）"
    else:
        checks["Q5_现金含金量"] = "？ 现金流数据缺失"

    # Q6 抗压 / 财务稳健：资产负债率
    dr = fin.get("debt_ratio_pct")
    maxs += 1
    if dr is not None:
        if dr <= 50:
            score += 1; checks["Q6_抗压(负债率)"] = f"✓ 资产负债率 {dr}%（稳健）"
        elif dr <= 65:
            checks["Q6_抗压(负债率)"] = f"△ 资产负债率 {dr}%（偏高）"
        else:
            checks["Q6_抗压(负债率)"] = f"✗ 资产负债率 {dr}%（高杠杆）"
    else:
        checks["Q6_抗压(负债率)"] = "？ 负债率缺失"

    # Q7 成长性：营收/净利增长（辅助）
    rg = fin.get("rev_growth_pct"); pg = fin.get("profit_growth_pct")
    if rg is not None or pg is not None:
        checks["Q7_成长性"] = f"营收增速 {rg}% / 净利增速 {pg}%（参考，非评级核心）"
    else:
        checks["Q7_成长性"] = "？ 成长性数据缺失"

    # Q8 管理层 / 安全边际：MVP 无法量化估值（缺乏内在价值模型），诚实标注
    checks["Q8_管理层&安全边际"] = "⚠ 本MVP未做内在价值估算与管理层诚信调查，安全边际维度暂缺，评级仅反映「生意质地」非「买入时机」"

    # 评级映射（基于质地分占比）
    pct = score / maxs if maxs else 0
    if circle == "borderline":
        # 能力圈边缘：质地再好最多给黄（谨慎）
        if pct >= 0.6:
            rating, label = "黄", "观察"
            reason = f"{name} 生意质地达标（质地分 {score}/{maxs}），但属能力圈边缘的高端制造/工业领域，长期格局不确定性较高，谨慎评「黄-观察」。"
        elif pct >= 0.35:
            rating, label = "黄", "观察"
            reason = f"{name} 质地中等（{score}/{maxs}）且处能力圈边缘，评「黄-观察」。"
        else:
            rating, label = "红", "回避"
            reason = f"{name} 质地偏弱（{score}/{maxs}），评「红-回避」。"
    else:  # in circle
        if pct >= 0.7:
            rating, label = "绿", "优质可持有"
            reason = f"{name} 质地优秀（质地分 {score}/{maxs}）：高ROE/高毛利/现金成色好，符合巴菲特优质消费股特征。注：未做安全边际估值，是否「便宜」需另判。"
        elif pct >= 0.45:
            rating, label = "黄", "观察"
            reason = f"{name} 质地中上（{score}/{maxs}），部分指标一般，评「黄-观察」。"
        else:
            rating, label = "红", "回避"
            reason = f"{name} 质地偏弱（{score}/{maxs}），盈利能力/现金成色不足，评「红-回避」。"

    return {
        "circle": circle,
        "checks": checks,
        "rating": rating,
        "rating_label": label,
        "rating_reason": reason,
        "score": score,
        "score_max": maxs,
        "score_pct": round(pct, 3),
    }


# ---------- 基金质地汇总 ----------

def summarize_fund(holdings_rated):
    """按占净值比例（穿透权重）汇总底层质地。"""
    buckets = {"绿": 0.0, "黄": 0.0, "红": 0.0, "灰": 0.0}
    total_w = 0.0
    for h in holdings_rated:
        w = h.get("ratio_pct") or 0.0
        total_w += w
        buckets[h["rating"]["rating"]] += w
    # 归一化（仅就披露的前十大权重内部占比）
    norm = {k: (round(v / total_w * 100, 1) if total_w else 0.0) for k, v in buckets.items()}
    green_yellow = norm["绿"] + norm["黄"]
    if buckets["灰"] / total_w >= 0.5 if total_w else False:
        verdict = "底层多为超出能力圈/数据不足的标的，质地难判断（诚实保留）"
    elif green_yellow >= 70:
        verdict = f"前十大重仓中约 {green_yellow}% 权重落在绿/黄评级公司，底层质地中上"
    elif green_yellow >= 40:
        verdict = f"前十大重仓中约 {green_yellow}% 权重为绿/黄，质地中等，分化明显"
    else:
        verdict = "底层质地偏弱或多为回避/不评级标的，需谨慎"
    return {
        "weight_by_rating_in_top10_pct": norm,
        "top10_disclosed_weight_pct": round(total_w, 2),
        "verdict": verdict,
    }


# ---------- 主流程 ----------

def main():
    print("== 价值罗盘 MVP 取数开始 ==")
    # 基金官方名称表
    try:
        name_table = ak.fund_name_em()
    except Exception as e:
        print("fund_name_em 失败:", repr(e)[:100])
        name_table = None

    # 读取用户 portfolio 中文名（可能过期）
    portfolio_names = {}
    try:
        with open(PORTFOLIO_PATH, encoding="utf-8") as f:
            pf = json.load(f)
        for h in pf.get("holdings", []):
            portfolio_names[h["code"]] = h["name"]
    except Exception:
        pass

    result = {
        "generated_at": dt.datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "data_source": "AKShare（东方财富公开披露：基金季报前十大重仓 + A股财务分析指标）",
        "methodology": "持仓穿透(look-through) + 巴菲特八问质地评级 + 权重汇总",
        "funds": [],
    }

    for code in PILOT_FUNDS:
        print(f"\n--- 基金 {code} ---")
        official_name, fund_type = get_fund_official_name(code, name_table)
        labeled_name = portfolio_names.get(code)
        name_mismatch = (official_name and labeled_name and official_name not in labeled_name
                         and labeled_name not in (official_name or ""))
        latest_q, holds, herr = fetch_fund_holdings(code)
        print(f"  官方名称: {official_name} | 组合标注名: {labeled_name} | 最新季度: {latest_q}")
        if name_mismatch:
            print(f"  ⚠️ 名称不一致！组合标注[{labeled_name}] vs 官方[{official_name}]")

        rated = []
        for h in holds:
            time.sleep(0.3)
            fin = fetch_stock_financials(h["stock_code"])
            rating = buffett_eight_questions(h, fin)
            rated.append({
                **h,
                "financials": fin,
                "rating": rating,
            })
            print(f"    {h['stock_name']:<6} {h['stock_code']} -> {rating['rating']}({rating['rating_label']}) "
                  f"ROE={fin.get('roe_pct')} GM={fin.get('gross_margin_pct')}")

        summary = summarize_fund(rated) if rated else {"verdict": "无可穿透持仓数据", "weight_by_rating_in_top10_pct": {}}

        result["funds"].append({
            "fund_code": code,
            "official_name": official_name,
            "fund_type": fund_type,
            "portfolio_labeled_name": labeled_name,
            "name_mismatch_warning": bool(name_mismatch),
            "latest_quarter": latest_q,
            "holdings_error": herr,
            "holdings_rated": rated,
            "fund_quality_summary": summary,
        })

    out_path = os.path.join(DATA_DIR, "value_compass.json")
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n✅ JSON 写入: {out_path}")
    return result


if __name__ == "__main__":
    main()
