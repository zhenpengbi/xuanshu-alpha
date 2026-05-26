# 玄枢Alpha (XuanShu Alpha)

> AI-Powered Investment Intelligence

## 简介

玄枢Alpha 是一个 AI 驱动的个人智能投顾平台，采用深色金融终端风格设计，提供持仓管理、量化信号、市场早晚报和 AI 操作建议等功能。

## 技术栈

- **前端**：单页 HTML + 内联 CSS/JS
- **图表**：ECharts 5.x
- **部署**：GitHub Pages（纯静态）
- **风格**：深色金融终端（参考 TradingView 暗色主题）

## 功能模块

1. **资产总览** — 环形饼图 + 目标配置偏离度对比
2. **持仓明细** — 全量持仓表格，涨绿跌红配色
3. **量化信号** — 黄金/美股评分仪表盘 + VIX 恐慌指数
4. **早晚报 Timeline** — 市场新闻时间轴
5. **AI 操作建议** — 智能投顾建议卡片

## 目录结构

```
xuanshu-alpha/
├── index.html          # 主页面（单文件应用）
├── data/
│   └── portfolio.json  # 持仓数据
└── README.md           # 项目说明
```

## 本地预览

```bash
# 任意静态服务器
npx serve .
# 或直接浏览器打开 index.html
```

## 部署

推送到 GitHub 仓库，启用 GitHub Pages 即可。

## 数据更新

编辑 `data/portfolio.json` 或页面内 `portfolioData` 变量即可更新持仓数据。

---

*Built with ❤️ by 玄枢Alpha Team*
