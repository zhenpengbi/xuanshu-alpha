// ========== 玄枢Alpha - 内联 Fallback 数据 ==========
// ========== Portfolio Data — fallback inline（页面加载时会被 data/portfolio.json 覆盖）==========
// 下方数据为最后一次已知快照，仅在 fetch 失败时作兜底显示。
const portfolioData = {
    "updateTime": "2026-08-14",
    "totalAsset": 59347.52,
    "holdings": [
        {"name":"易方达黄金ETF联接C","code":"002963","amount":22214.42,"ratio":37.43,"dailyReturn":-140.56,"holdingReturn":-1894.58,"holdingReturnRate":-7.86,"totalReturn":2006.66,"category":"黄金","assetType":"trend"},
        {"name":"易方达黄金ETF联接A","code":"000307","amount":8330.75,"ratio":14.04,"dailyReturn":-52.41,"holdingReturn":-1168.33,"holdingReturnRate":-12.30,"totalReturn":-1168.33,"category":"黄金","assetType":"trend"},
        {"name":"南方有色金属ETF联接E","code":"010990","amount":7791.11,"ratio":13.13,"dailyReturn":-289.65,"holdingReturn":-1245.62,"holdingReturnRate":-13.78,"totalReturn":-1245.62,"category":"有色金属","assetType":"trend"},
        {"name":"天弘中证人工智能主题ETF联接C","code":"011840","amount":6254.35,"ratio":10.54,"dailyReturn":-15.27,"holdingReturn":1006.88,"holdingReturnRate":19.19,"totalReturn":2731.85,"category":"AI/科技","assetType":"oscillation"},
        {"name":"华夏中证光伏产业ETF联接A","code":"012885","amount":4443.39,"ratio":7.49,"dailyReturn":-76.03,"holdingReturn":-1056.61,"holdingReturnRate":-19.21,"totalReturn":-1056.61,"category":"光伏/新能源","assetType":"oscillation"},
        {"name":"永赢高端装备智选混合C","code":"015790","amount":4085.14,"ratio":6.88,"dailyReturn":11.69,"holdingReturn":-914.86,"holdingReturnRate":-18.30,"totalReturn":-914.86,"category":"高端制造","assetType":"active"},
        {"name":"平安高端装备混合C","code":"025647","amount":2533.98,"ratio":4.27,"dailyReturn":-2.42,"holdingReturn":-466.02,"holdingReturnRate":-15.53,"totalReturn":-466.02,"category":"高端制造","assetType":"active"},
        {"name":"嘉实货币E","code":"001812","amount":2000.05,"ratio":3.37,"dailyReturn":0.05,"holdingReturn":310.16,"holdingReturnRate":0,"totalReturn":310.16,"category":"货币基金","assetType":"cash"},
        {"name":"天弘中证机器人ETF联接C","code":"014881","amount":1694.33,"ratio":2.85,"dailyReturn":-27.22,"holdingReturn":-180.66,"holdingReturnRate":-9.64,"totalReturn":-392.61,"category":"AI/科技","assetType":"oscillation"}
    ],
    "targetAllocation": {"黄金":24,"AI/科技":28,"纳指100":18,"标普500":8,"有色金属":6,"光伏/新能源":6,"高端制造":10}
};

// mockTimeline 已移除——早晚报数据统一由 data/news.json 提供（见 renderTimeline）
// 若 news.json 不可用，显示「暂无资讯」空状态，不用假数据兜底
const mockTimeline = [];

