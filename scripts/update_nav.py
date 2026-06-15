#!/usr/bin/env python3
"""
每日净值更新脚本
从 akshare 拉取最新净值，更新 data/portfolio.json 中的每日收益
可复用：任何基于 akshare 的基金净值查询场景均可调用 get_fund_nav()
"""
import json
import akshare as ak
from datetime import datetime, timedelta
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent.parent / 'data'
PORTFOLIO_PATH = DATA_DIR / 'portfolio.json'


def get_fund_nav(code: str, days: int = 5) -> dict:
    """
    获取基金最近N天净值数据
    Args:
        code: 基金代码（6位）
        days: 获取最近几天的数据
    Returns:
        {'nav': float, 'date': str, 'nav_chg': float, 'nav_chg_pct': float} 或 None
    """
    try:
        df = ak.fund_open_fund_info_em(symbol=code, indicator="单位净值走势")
        if df is None or df.empty:
            return None
        df = df.tail(days)
        latest = df.iloc[-1]
        prev = df.iloc[-2] if len(df) >= 2 else df.iloc[-1]
        return {
            'nav': float(latest['单位净值']),
            'date': str(latest['净值日期']),
            'nav_chg': float(latest['单位净值']) - float(prev['单位净值']),
            'nav_chg_pct': round((float(latest['单位净值']) - float(prev['单位净值'])) / float(prev['单位净值']) * 100, 4)
        }
    except Exception as e:
        print(f"[WARN] 基金 {code} 净值获取失败: {e}")
        return None


def update_portfolio():
    """读取 portfolio.json，逐只基金更新最新净值和日收益"""
    portfolio = json.loads(PORTFOLIO_PATH.read_text(encoding='utf-8'))
    holdings = portfolio.get('holdings', [])

    today_str = datetime.now().strftime('%Y-%m-%d')
    total_daily_return = 0.0

    for h in holdings:
        code = h.get('code', '')
        if not code or h.get('category') == '货币':
            # 货币基金日收益极小，跳过
            continue

        nav_info = get_fund_nav(code)
        if not nav_info:
            continue

        # 用 nav_chg_pct 乘以持仓金额估算日收益
        daily_return = round(h.get('amount', 0) * nav_info['nav_chg_pct'] / 100, 2)
        h['dailyReturn'] = daily_return
        total_daily_return += daily_return
        print(f"  {h['name']}({code}): 净值{nav_info['nav']}({nav_info['date']}), 日收益≈{daily_return}")

    portfolio['updateTime'] = today_str
    portfolio['dailyReturn'] = round(total_daily_return, 2)

    PORTFOLIO_PATH.write_text(json.dumps(portfolio, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f"\n✅ portfolio.json 已更新，日期={today_str}，总日收益={total_daily_return:.2f}")


if __name__ == '__main__':
    update_portfolio()
