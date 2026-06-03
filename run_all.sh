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
echo "【第4步】计算再平衡建议..."
python3 data/rebalance.py

echo ""
echo "=========================================="
echo "  ✅ 全量更新完成！"
echo "=========================================="
echo ""
echo "启动本地预览 → http://localhost:8080"
echo "（按 Ctrl+C 停止服务器）"
echo ""
python3 -m http.server 8080
