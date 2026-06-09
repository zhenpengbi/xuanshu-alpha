#!/bin/bash
# 玄枢Alpha — 量化数据全量更新脚本

set -e
cd "$(dirname "${BASH_SOURCE[0]}")"

echo "=========================================="
echo "  玄枢Alpha 量化数据全量更新"
echo "  $(date '+%Y-%m-%d %H:%M:%S')"
echo "=========================================="

echo ""
echo "【第1步】拉取实时行情..."
python3 fetch_prices.py

echo ""
echo "【第2步】计算技术指标（RSI14 / MA5 / MA20 / MACD）..."
python3 data/indicators.py

echo ""
echo "【第3步】生成买卖信号..."
python3 data/signals.py

echo ""
echo "【第4步】新闻情绪→持仓影响分析..."
python3 scripts/build_news_impact.py

echo ""
echo "【第5步】基金雷达（超跌扫描，avg_sell_score>=2时触发）..."
python3 scripts/fund_scanner.py

echo ""
echo "【第6步】计算再平衡建议..."
python3 data/rebalance.py

echo ""
echo "【第5步】价值罗盘（可选：仅在重仓股变动时重跑）..."
# python3 value_compass/build_value_compass.py
# python3 value_compass/build_fusion.py

# ── 策略回测（每周跑一次即可，数据量大约1-2分钟）───────────────
# 加 --backtest 参数时执行，例如：  ./run_all.sh --backtest
if [[ "${1}" == "--backtest" ]]; then
    echo ""
    echo "【第8步】策略回测（--backtest 模式）..."
    python3 backtest/backtest_engine.py
fi

echo ""
echo "=========================================="
echo "  ✅ 全量更新完成！"
echo "  策略回测：./run_all.sh --backtest（每周）"
echo "  价值罗盘：python3 value_compass/build_value_compass.py（重仓变动时重跑）"
echo "=========================================="
echo ""
echo "启动本地预览 → http://localhost:8080"
echo "（按 Ctrl+C 停止服务器）"
echo ""
python3 -m http.server 8080
