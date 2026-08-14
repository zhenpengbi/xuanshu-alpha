#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
玄枢Alpha · 黄金/美股/有色 量化信号自动生成
===================================================
从 akshare 拉取 COMEX金/QQQ/SPY/COMEX铜/VIX/TNX/USD-CNY，
计算多维评分（趋势/动量/宏观/情绪），输出 gold_signal.json / us_signal.json / metals_signal.json。
替代手动维护，避免仪表盘"假死"显示旧分。

用法:
    python3 scripts/build_signals_quant.py            # 生成三文件
    python3 scripts/build_signals_quant.py --dry-run  # 只打印不写入
"""
import json, os, sys, math, argparse
from datetime import datetime, timezone, timedelta
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'data'))
try:
    from indicators import calc_rsi, calc_ma
except ImportError:
    calc_rsi = calc_ma = None
try:
    import akshare as ak
except ImportError:
    ak = None

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, 'data')

# 北京时间
try:
    from zoneinfo import ZoneInfo
    TZ = ZoneInfo("Asia/Shanghai")
except Exception:
    TZ = timezone(timedelta(hours=8))

def now_str():
    return datetime.now(TZ).strftime('%Y-%m-%d %H:%M')

# ── akshare 拉取辅助 ──
def _fetch_foreign(symbol):
    """COMEX 期货历史收盘序列，失败返回 []"""
    if not ak: return []
    try:
        df = ak.futures_foreign_hist(symbol=symbol)
        if df is None or len(df) == 0: return []
        col = '收盘' if '收盘' in df.columns else df.columns[-1]
        return [float(x) for x in df[col].dropna().tolist()]
    except Exception as e:
        print(f"  ⚠ {symbol} 拉取失败: {e}")
        return []

def _fetch_us_stock(symbol):
    """美股(QQQ/SPY)收盘序列"""
    if not ak: return []
    try:
        df = ak.stock_us_daily(symbol=symbol, adjust="qfq")
        if df is None or len(df) == 0: return []
        col = '收盘' if '收盘' in df.columns else 'close'
        return [float(x) for x in df[col].dropna().tolist()]
    except Exception as e:
        print(f"  ⚠ {symbol} 拉取失败: {e}")
        return []

def _fetch_vix():
    return _fetch_foreign("VX")

def _fetch_tnx():
    """10年美债收益率"""
    if not ak: return []
    try:
        df = ak.bond_zh_us_rate(start_date="20240101")
        if df is None or len(df) == 0: return []
        col = '美国国债收益率10年' if '美国国债收益率10年' in df.columns else df.columns[-1]
        return [float(x) for x in df[col].dropna().tolist()]
    except Exception as e:
        print(f"  ⚠ TNX 拉取失败: {e}")
        return []

def _fetch_usd_cny():
    """USD/CNY 中间价（DXY代理）"""
    if not ak: return []
    try:
        df = ak.currency_boc_sina(symbol="美元", start_date="20240101", end_date=datetime.now(TZ).strftime('%Y%m%d'))
        if df is None or len(df) == 0: return []
        col = '中行折算价' if '中行折算价' in df.columns else df.columns[-1]
        return [float(x) for x in df[col].dropna().tolist()]
    except Exception as e:
        print(f"  ⚠ USD/CNY 拉取失败: {e}")
        return []

# ── 评分辅助 ──
def pct_change(s, n):
    if not s or len(s) < n + 1 or s[-1-n] == 0: return 0.0
    return (s[-1] / s[-1-n] - 1) * 100

def percentile(val, series):
    if not series: return 50
    below = sum(1 for x in series if x < val)
    return round(below / len(series) * 100)

def band_score(x, lo, hi, max_score):
    """分段线性映射到 [0, max_score]"""
    if hi == lo: return max_score // 2
    r = (x - lo) / (hi - lo)
    return max(0, min(max_score, round(r * max_score)))

def clamp_score(raw, total_max):
    return max(0, min(100, int(round(raw / total_max * 100)))) if total_max else 50

def _nan_to_none(obj):
    if isinstance(obj, dict): return {k: _nan_to_none(v) for k, v in obj.items()}
    if isinstance(obj, list): return [_nan_to_none(x) for x in obj]
    if isinstance(obj, float) and math.isnan(obj): return None
    return obj

def signal_from_score(s):
    if s >= 65: return ('买入信号', '🟢')
    if s >= 45: return ('中性观望', '⚪')
    return ('减仓信号', '🔴')

# ── 黄金评分 ──
def build_gold():
    gold = _fetch_foreign("XAU")
    silver = _fetch_foreign("SI")
    oil = _fetch_foreign("CL")
    copper = _fetch_foreign("HG")
    vix = _fetch_vix()
    tnx = _fetch_tnx()
    usd = _fetch_usd_cny()
    if not gold:
        print("  ✗ 黄金数据拉取失败，跳过"); return None

    # tech (满分38: MA12+RSI9+布林9+量9)
    ma20 = calc_ma(gold, 20) if calc_ma else sum(gold[-20:])/min(20,len(gold))
    ma60 = calc_ma(gold, 60) if calc_ma else sum(gold[-60:])/min(60,len(gold))
    rsi = calc_rsi(gold, 14) if calc_rsi else 50
    std20 = (sum((x-ma20)**2 for x in gold[-20:]) / 20) ** 0.5 if len(gold) >= 20 else 0
    boll_pct = (gold[-1] - ma20) / (2*std20) if std20 else 0
    ma_score = 12 if ma20 > ma60 else (6 if ma60 == 0 else max(0, 12 - int(abs(ma20-ma60)/ma60*1000)))
    rsi_score = 9 if rsi < 30 else max(0, 9 - int((rsi-30)/40*9)) if rsi < 70 else 2
    boll_score = max(0, min(9, round((1-boll_pct) * 9))) if boll_pct < 1 else 0
    tech = ma_score + rsi_score + boll_score
    tech_detail = {
        f"tech_趋势MA20vsMA60": f"MA20={ma20:.1f}, MA60={ma60:.1f}, {'金叉' if ma20>ma60 else '死叉'}（得分 {ma_score}/12）",
        f"tech_RSI(14)": f"RSI={rsi:.1f}（COMEX）（得分 {rsi_score}/9）",
        f"tech_布林带%B": f"%B={boll_pct:.2f}（得分 {boll_score}/9）",
    }

    # macro (满分37: DXY11+TNX9+VIX分位9+金油比8)
    dxy_5d = pct_change(usd, 5) if usd else 0
    dxy_score = band_score(-dxy_5d, -1, 1, 11) if usd else 5
    tnx_val = tnx[-1] if tnx else 4.0
    tnx_score = max(0, min(9, round((5 - tnx_val) * 3))) if tnx else 5
    vix_val = vix[-1] if vix else 18
    vix_pct = percentile(vix_val, vix[-500:]) if vix else 50
    vix_score = band_score(vix_pct, 20, 90, 9)
    goil_ratio = gold[-1]/oil[-1] if oil and oil[-1] else 0
    goil_pct = percentile(goil_ratio, [gold[i]/oil[i] for i in range(-min(len(gold),len(oil),500),0) if oil[i]]) if oil and len(oil)>10 else 50
    goil_score = band_score(goil_pct, 20, 90, 8)
    macro = dxy_score + tnx_score + vix_score + goil_score
    macro_detail = {
        f"macro_DXY美元指数5日变化": f"DXY(USD/CNY代理), 5日{dxy_5d:+.2f}%（得分 {dxy_score}/11）",
        f"macro_TNX10年美债水位": f"TNX={tnx_val:.2f}%（得分 {tnx_score}/9）",
        f"macro_VIX2年历史分位": f"VIX={vix_val:.1f}, 2年分位={vix_pct}%（得分 {vix_score}/9）",
        f"macro_金价/原油比": f"金油比={goil_ratio:.1f}, 历史分位={goil_pct}%（得分 {goil_score}/8）",
    }

    # senti (满分25: 金银比10+VIX5日9+COMEXvs沪金6)
    gsr = gold[-1]/silver[-1] if silver and silver[-1] else 0
    gsr_pct = percentile(gsr, [gold[i]/silver[i] for i in range(-min(len(gold),len(silver),500),0) if silver[i]]) if silver else 50
    gsr_score = band_score(gsr_pct, 20, 90, 10)
    vix_5d = pct_change(vix, 5) if vix else 0
    vix5_score = band_score(vix_5d, -2, 10, 9) if vix else 5
    senti = gsr_score + vix5_score
    senti_detail = {
        f"senti_金银比": f"当前={gsr:.1f}, 历史分位={gsr_pct}%（得分 {gsr_score}/10）",
        f"senti_VIX5日变化": f"VIX={vix_val:.1f}, 5日{vix_5d:+.2f}%（得分 {vix5_score}/9）",
    }

    total = tech + macro + senti
    score = clamp_score(total, 38+37+25)
    sig, emoji = signal_from_score(score)
    conf = 'high' if len(gold)>60 and vix and usd else 'medium' if gold else 'low'

    return {
        "date": now_str(), "score": score, "combined_score": float(score),
        "lgbm_score_normalized": None, "lgbm_note": "quant脚本:未加载lightgbm,使用规则评分",
        "signal": sig, "emoji": emoji,
        "tech": tech, "macro": macro, "senti": senti,
        "tech_max": 38, "macro_max": 37, "senti_max": 25,
        "data_source": "akshare", "url": "",
        "price": round(gold[-1], 2),
        "price_52wh": round(max(gold[-500:]), 2) if len(gold)>10 else None,
        "price_52wl": round(min(gold[-500:]), 2) if len(gold)>10 else None,
        "pct_1w": round(pct_change(gold, 5), 2), "pct_1m": round(pct_change(gold, 22), 2), "pct_3m": round(pct_change(gold, 66), 2),
        "ma20": round(ma20, 2), "ma60": round(ma60, 2),
        "score_detail": {**tech_detail, **macro_detail, **senti_detail},
        "risk_flags": {"data_source":"akshare", "signal_confidence":conf, "confidence_reason":f"akshare实时数据 {len(gold)}日可用", "caution_notes":[]},
    }

# ── 美股评分 ──
def build_us():
    qqq = _fetch_us_stock("QQQ")
    spy = _fetch_us_stock("SPY")
    vix = _fetch_vix()
    tnx = _fetch_tnx()
    usd = _fetch_usd_cny()
    if not qqq:
        print("  ✗ QQQ 数据拉取失败，跳过"); return None

    def _score_one(prices, label):
        if not prices: return {}, 50, '中性观望', '⚪'
        ma20 = calc_ma(prices, 20) if calc_ma else sum(prices[-20:])/min(20,len(prices))
        ma60 = calc_ma(prices, 60) if calc_ma else sum(prices[-60:])/min(60,len(prices))
        rsi = calc_rsi(prices, 14) if calc_rsi else 50
        std20 = (sum((x-ma20)**2 for x in prices[-20:]) / 20) ** 0.5 if len(prices) >= 20 else 0
        boll = (prices[-1] - ma20) / (2*std20) if std20 else 0
        # tech (40: MA12+RSI10+布林10+量8 → 简化无量比，满分30)
        ma_s = 12 if ma20 > ma60 else (6 if ma60 == 0 else max(0, 12 - int(abs(ma20-ma60)/ma60*1000)))
        rsi_s = min(10, max(0, round((rsi-30)/4))) if rsi > 30 else 2  # 美股动量型,RSI高=高分
        boll_s = min(10, max(0, round(boll * 10))) if boll > 0 else 0
        tech = ma_s + rsi_s + boll_s
        # macro (30: DXY8+TNX7+VIX8+相对强弱7)
        dxy5 = pct_change(usd, 5) if usd else 0
        dxy_s = band_score(-dxy5, -1, 1, 8) if usd else 4
        tnx_val = tnx[-1] if tnx else 4.0
        tnx_s = max(0, min(7, round((5-tnx_val)*2.3))) if tnx else 4
        vix_val = vix[-1] if vix else 18
        vix_pct = percentile(vix_val, vix[-500:]) if vix else 50
        vix_s = band_score(100-vix_pct, 20, 90, 8)  # VIX低=美股高分
        macro = dxy_s + tnx_s + vix_s
        # senti (10: VIX5日5+动量5)
        vix5 = pct_change(vix, 5) if vix else 0
        vix5_s = band_score(-vix5, -5, 5, 5) if vix else 3
        senti = vix5_s
        total = tech + macro + senti
        score = clamp_score(total, 30+30+10)
        sig, emo = signal_from_score(score)
        detail = {
            f"tech_趋势MA20vsMA60": f"MA20={ma20:.1f}, MA60={ma60:.1f}（得分 {ma_s}/12）",
            f"tech_RSI(14)": f"RSI={rsi:.1f}（得分 {rsi_s}/10）",
            f"tech_布林带%B": f"%B={boll:.2f}（得分 {boll_s}/10）",
            f"macro_VIX2年分位": f"VIX={vix_val:.1f}, 分位={vix_pct}%（得分 {vix_s}/8）",
            f"senti_VIX5日变化": f"5日{vix5:+.2f}%（得分 {vix5_s}/5）",
        }
        return detail, score, sig, emo

    qqq_detail, qqq_score, qqq_sig, qqq_emo = _score_one(qqq, 'QQQ')
    spy_detail, spy_score, spy_sig, spy_emo = _score_one(spy, 'SPY')
    return {
        "date": now_str(), "data_source": "akshare", "url": "",
        "qqq_score": qqq_score, "qqq_signal": qqq_sig, "qqq_emoji": qqq_emo,
        "qqq_tech": 0, "qqq_macro": 0, "qqq_senti": 0, "qqq_val": 0,
        "spy_score": spy_score, "spy_signal": spy_sig, "spy_emoji": spy_emo,
        "spy_tech": 0, "spy_macro": 0, "spy_senti": 0, "spy_val": 0,
        "qqq_score_detail": qqq_detail, "spy_score_detail": spy_detail,
        "qqq_risk_flags": {"data_source":"akshare","signal_confidence":"medium","confidence_reason":"akshare实时","caution_notes":[]},
        "spy_risk_flags": {"data_source":"akshare","signal_confidence":"medium","confidence_reason":"akshare实时","caution_notes":[]},
        "qqq_price": round(qqq[-1], 2) if qqq else None,
        "qqq_pct_1w": round(pct_change(qqq, 5), 2) if qqq else None,
        "qqq_pct_1m": round(pct_change(qqq, 22), 2) if qqq else None,
        "qqq_pct_3m": round(pct_change(qqq, 66), 2) if qqq else None,
        "qqq_52wh": round(max(qqq[-500:]), 2) if qqq and len(qqq)>10 else None,
        "qqq_52wl": round(min(qqq[-500:]), 2) if qqq and len(qqq)>10 else None,
        "qqq_ma20": round(calc_ma(qqq, 20) if calc_ma and qqq else 0, 2),
        "qqq_ma60": round(calc_ma(qqq, 60) if calc_ma and qqq else 0, 2),
        "spy_price": round(spy[-1], 2) if spy else None,
        "spy_pct_1w": round(pct_change(spy, 5), 2) if spy else None,
        "spy_pct_1m": round(pct_change(spy, 22), 2) if spy else None,
        "spy_pct_3m": round(pct_change(spy, 66), 2) if spy else None,
        "spy_52wh": round(max(spy[-500:]), 2) if spy and len(spy)>10 else None,
        "spy_52wl": round(min(spy[-500:]), 2) if spy and len(spy)>10 else None,
        "spy_ma20": round(calc_ma(spy, 20) if calc_ma and spy else 0, 2),
        "spy_ma60": round(calc_ma(spy, 60) if calc_ma and spy else 0, 2),
    }

# ── 有色金属评分 ──
def build_metals():
    copper = _fetch_foreign("HG")
    gold = _fetch_foreign("XAU")
    vix = _fetch_vix()
    usd = _fetch_usd_cny()
    if not copper:
        print("  ✗ COMEX铜 拉取失败，跳过"); return None
    ma20 = calc_ma(copper, 20) if calc_ma else sum(copper[-20:])/min(20,len(copper))
    ma60 = calc_ma(copper, 60) if calc_ma else sum(copper[-60:])/min(60,len(copper))
    rsi = calc_rsi(copper, 14) if calc_rsi else 50
    std20 = (sum((x-ma20)**2 for x in copper[-20:]) / 20) ** 0.5 if len(copper) >= 20 else 0
    boll = (copper[-1] - ma20) / (2*std20) if std20 else 0
    # tech (38: MA12+RSI9+布林9+量9→简化无量,满分30)
    ma_s = 12 if ma20 > ma60 else (6 if ma60 == 0 else max(0, 12 - int(abs(ma20-ma60)/ma60*1000)))
    rsi_s = 9 if rsi < 30 else max(0, 9 - int((rsi-30)/40*9)) if rsi < 70 else 2
    boll_s = max(0, min(9, round((1-boll) * 9))) if boll < 1 else 0
    tech = ma_s + rsi_s + boll_s
    # macro (35: DXY10+铜3月10+金铜比7→简化,满分27)
    dxy5 = pct_change(usd, 5) if usd else 0
    dxy_s = band_score(-dxy5, -1, 1, 10) if usd else 5
    cu_3m = pct_change(copper, 66)
    cu_s = band_score(cu_3m, -5, 20, 10)
    gcr = gold[-1]/copper[-1] if gold and copper[-1] else 0
    gcr_pct = percentile(gcr, [gold[i]/copper[i] for i in range(-min(len(gold),len(copper),500),0) if copper[i]]) if gold and len(copper)>10 else 50
    gcr_s = band_score(100-gcr_pct, 20, 90, 7)  # 金铜比分位高=有色承压=低分
    macro = dxy_s + cu_s + gcr_s
    # senti (27: VIX8→简化满分8)
    vix_val = vix[-1] if vix else 18
    vix_pct = percentile(vix_val, vix[-500:]) if vix else 50
    vix_s = band_score(100-vix_pct, 20, 90, 8)  # VIX高=有色承压=低分
    senti = vix_s
    total = tech + macro + senti
    score = clamp_score(total, 30+27+8)
    sig, emo = signal_from_score(score)
    detail = {
        f"tech_趋势MA20vsMA60": f"MA20={ma20:.3f}, MA60={ma60:.3f}（得分 {ma_s}/12）",
        f"tech_RSI(14)": f"RSI={rsi:.1f}（COMEX铜）（得分 {rsi_s}/9）",
        f"tech_布林带%B": f"%B={boll:.2f}（得分 {boll_s}/9）",
        f"macro_DXY走势": f"DXY(USD/CNY), 5日{dxy5:+.2f}%（得分 {dxy_s}/10）",
        f"macro_铜价3月走势": f"3月{cu_3m:+.2f}%（得分 {cu_s}/10）",
        f"macro_金铜比分位": f"金铜比={gcr:.1f}, 分位={gcr_pct}%（得分 {gcr_s}/7）",
        f"senti_VIX恐慌指数": f"VIX={vix_val:.1f}, 分位={vix_pct}%（得分 {vix_s}/8）",
    }
    return {
        "date": now_str(), "score": score, "signal": sig, "emoji": emo,
        "tech": tech, "macro": macro, "senti": senti,
        "tech_max": 38, "macro_max": 35, "senti_max": 27,
        "price": round(copper[-1], 4), "price_unit": "美元/磅",
        "pct_1w": round(pct_change(copper, 5), 2),
        "pct_1m": round(pct_change(copper, 22), 2),
        "pct_3m": round(pct_change(copper, 66), 2),
        "ma20": round(ma20, 4), "ma60": round(ma60, 4),
        "score_detail": detail,
        "risk_flags": {"data_source":"akshare","signal_confidence":"medium","confidence_reason":"akshare实时","caution_notes":[]},
    }

# ── 写入/兜底 ──
def write_or_preserve(out_path, payload, dry_run=False):
    if payload is None:
        print(f"  ⚠ 保留旧文件 {os.path.basename(out_path)}")
        return
    payload = _nan_to_none(payload)
    if dry_run:
        print(f"  [dry-run] {os.path.basename(out_path)} → score={payload.get('score')}")
        return
    with open(out_path, 'w', encoding='utf-8') as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)
    s = payload.get('score', payload.get('qqq_score', '?'))
    print(f"  ✅ {os.path.basename(out_path)} {s}分 {payload.get('signal', payload.get('qqq_signal', ''))}")

if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--dry-run', action='store_true')
    args = ap.parse_args()
    print(f"[{now_str()}] 生成量化信号（黄金/美股/有色）...")
    if ak is None:
        print("✗ akshare 未安装，退出"); sys.exit(1)
    write_or_preserve(os.path.join(DATA, 'gold_signal.json'), build_gold(), args.dry_run)
    write_or_preserve(os.path.join(DATA, 'us_signal.json'), build_us(), args.dry_run)
    write_or_preserve(os.path.join(DATA, 'metals_signal.json'), build_metals(), args.dry_run)
    print("完成。")
