# 任务书：玄枢前端「更新持仓」功能
- 日期：2026-06-16
- 状态：待开发
- 执行者：Claude Code (MacBook)

---

## 背景

玄枢Alpha（https://zhenpengbi.github.io/xuanshu-alpha/）是纯前端单页应用，部署在 GitHub Pages。当前持仓更新依赖人工通过 CLI 脚本或告知 AI 助手，需要在页面内增加自主更新入口。

## 需求

在玄枢页面新增「更新持仓」功能，用户可直接在页面编辑持仓数据并提交到 GitHub 仓库。

## 功能规格

### 1. 入口

页面右上角或持仓模块标题栏新增「✏️ 更新持仓」按钮。

### 2. 编辑面板（Modal 或 Drawer）

- 预填当前 portfolio.json 的所有持仓条目
- 每只基金显示：
  - 名称（只读）
  - 代码（只读）
  - **金额**（可编辑）
  - **今日收益**（可编辑）
  - **持有收益**（可编辑）
  - **持有收益率**（可编辑）
  - **累计收益**（可编辑）
- 占比（ratio）由系统自动计算，不可手动输入
- 支持「新增基金」和「删除基金」操作

### 3. 自动计算

- 提交前自动重算：`totalAsset = sum(各基金 amount)`，每只基金 `ratio = amount / totalAsset * 100`
- 占比四舍五入误差校正到最大持仓
- `updateTime` 自动填当天日期

### 4. 提交到 GitHub

- 使用 GitHub Contents API：
  ```
  PUT https://api.github.com/repos/zhenpengbi/xuanshu-alpha/contents/data/portfolio.json
  ```
- 需要 Personal Access Token (PAT)，首次使用弹出输入框让用户填入，存入 localStorage（key: `xuanshu_github_pat`）
- 提交 commit message 格式：`chore: 更新持仓快照 YYYY-MM-DD (总额¥XX,XXX)`
- 提交成功后显示 toast「✅ 已提交，约 2 分钟后生效」
- 同时更新 index.html 内联的 portfolioData 块（通过同一 API 读取 index.html → 替换 → PUT）

### 5. 校验

- 金额必须 > 0
- 集中度预警：单只 > 25% 时黄色提示
- 提交前二次确认弹窗

## 技术约束

- 纯前端实现，不引入新框架（现有技术栈：Vanilla JS + TailwindCSS CDN + ECharts）
- GitHub API 调用使用 fetch，PAT 通过 Authorization header 传递
- 兼容移动端（手机上也能方便编辑）
- 深色主题风格保持一致（#0d1117 背景、#161b22 卡片、#f0b90b 金色强调）

## 文件改动范围

| 文件 | 改动说明 |
|------|----------|
| `index.html` | 新增编辑面板 UI + JS 逻辑 |
| `data/portfolio.json` | 通过 GitHub API 远程更新（不改本地） |

## 验收标准

- [ ] 点击「更新持仓」弹出编辑面板，预填当前数据
- [ ] 修改金额后占比自动重算
- [ ] PAT 首次输入后存 localStorage，下次免输入
- [ ] 提交后 data/portfolio.json 和 index.html 内联块均更新
- [ ] 手机端可正常操作
- [ ] 提交失败（网络/权限）有明确错误提示
