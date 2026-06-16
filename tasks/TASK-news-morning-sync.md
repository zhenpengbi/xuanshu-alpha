# 任务书：玄枢早报新闻数据同步
- 日期：2026-06-16
- 状态：待开发
- 执行者：Claude Code (MacBook)

---

## 背景

玄枢的早晚报模块数据来自 `data/news.json`。目前只有每天 20:30 的晚报 cron 会更新这个文件并 push 到 GitHub。早上 9:00 的早报 cron 只生成学城文档，不更新 news.json，导致白天访问玄枢时早晚报模块没有当日数据。

## 需求

新增早报数据同步机制，确保每天上午玄枢也有最新新闻数据。

## 方案

由沙箱端小老大新增一个 cron 任务（不需要 Claude Code 做），但**前端需要适配**数据结构变更。

### 数据结构变更

当前 `news.json` 结构（旧格式）：
```json
{
  "updated": "YYYY-MM-DD",
  "period": "晚报",
  "items": [...]
}
```

改造后支持早晚报共存（新格式）：
```json
{
  "updated": "YYYY-MM-DD",
  "morning": {
    "period": "早报",
    "items": [...]
  },
  "evening": {
    "period": "晚报",
    "items": [...]
  }
}
```

## 前端改动

### 1. 数据读取兼容

- 读取 news.json 时兼容新旧格式：
  - 旧格式：顶层 `items` 数组
  - 新格式：`morning` / `evening` 分区
- 展示逻辑：优先显示最新时段的数据
  - 当前是上午 → 显示 morning
  - 下午/晚间 → 显示 evening
  - 如果 evening 还没生成则回退显示 morning

### 2. UI 改造

- 早晚报模块标题旁增加 Tab 切换（「早报 ☀️」/「晚报 🌙」）
- 默认选中最新有数据的 Tab
- 无数据的 Tab 显示「暂无数据，稍后更新」

### 3. 时间显示

每条新闻的 `time` 字段已包含「早报 ·」或「晚报 ·」前缀，保持现有展示逻辑不变。

## 数据生成脚本改动

新增 `scripts/build_news_json.py`（供 cron 调用）：

- **输入**：搜索到的新闻列表
- **输出**：写入 `data/news.json`，根据当前时段写入 morning 或 evening 字段
- **合并规则**：
  - 写入早报时保留 evening 旧数据（如果同一天的话）
  - 写入晚报时保留 morning 旧数据
  - 如果是新的一天，清空前一天的数据

## 文件改动范围

| 文件 | 改动说明 |
|------|----------|
| `index.html` | 早晚报模块 UI + 数据读取逻辑改造 |
| `scripts/build_news_json.py` | 新增，供 cron 调用生成合并数据 |
| `data/news.json` | 结构变更（向后兼容） |

## 验收标准

- [ ] 前端兼容新旧两种 news.json 格式
- [ ] Tab 切换早报/晚报正常
- [ ] 默认显示最新有数据的时段
- [ ] build_news_json.py 能正确合并早晚报数据（不互相覆盖）
- [ ] 无数据时有友好提示而非空白
