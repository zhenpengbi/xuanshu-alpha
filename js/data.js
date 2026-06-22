// ========== 玄枢Alpha - 内联 Fallback 数据 ==========
// ========== Portfolio Data — fallback inline（页面加载时会被 data/portfolio.json 覆盖）==========
// 下方数据为最后一次已知快照，仅在 fetch 失败时作兜底显示。
const portfolioData = {
    "updateTime": "2026-06-10",
    "totalAsset": 55522.55,
    "holdings": [
        {"name":"易方达黄金ETF联接C","code":"002963","amount":19074.41,"ratio":34.35,"dailyReturn":72.9,"holdingReturn":-2125.59,"holdingReturnRate":-10.03,"totalReturn":1775.65,"category":"黄金","assetType":"trend"},
        {"name":"易方达黄金ETF联接A","code":"000307","amount":8298.93,"ratio":14.95,"dailyReturn":31.55,"holdingReturn":-1200.15,"holdingReturnRate":-12.63,"totalReturn":-1200.15,"category":"黄金","assetType":"trend"},
        {"name":"南方有色金属ETF联接E","code":"010990","amount":7804.39,"ratio":14.06,"dailyReturn":211.24,"holdingReturn":-1232.34,"holdingReturnRate":-13.64,"totalReturn":-1232.34,"category":"有色金属","assetType":"trend"},
        {"name":"华夏中证光伏产业ETF发起式联接A","code":"012885","amount":5154.07,"ratio":9.28,"dailyReturn":145.66,"holdingReturn":-345.93,"holdingReturnRate":-6.29,"totalReturn":-345.93,"category":"光伏/新能源","assetType":"oscillation"},
        {"name":"天弘中证人工智能C","code":"011840","amount":4916.27,"ratio":8.86,"dailyReturn":152.37,"holdingReturn":1268.8,"holdingReturnRate":34.79,"totalReturn":2993.77,"category":"AI/科技","assetType":"oscillation"},
        {"name":"永赢高端装备智选混合发起C","code":"015790","amount":3577.13,"ratio":6.44,"dailyReturn":44.85,"holdingReturn":-422.87,"holdingReturnRate":-10.57,"totalReturn":-422.87,"category":"高端制造","assetType":"active"},
        {"name":"嘉实货币E","code":"001812","amount":2909.08,"ratio":5.24,"dailyReturn":0,"holdingReturn":0,"holdingReturnRate":0,"totalReturn":308.85,"category":"货币基金","assetType":"cash"},
        {"name":"天弘中证机器人ETF发起联接C","code":"014881","amount":1978.73,"ratio":3.56,"dailyReturn":20.63,"holdingReturn":103.73,"holdingReturnRate":5.53,"totalReturn":-108.21,"category":"AI/科技","assetType":"oscillation"},
        {"name":"平安高端装备混合发起式C","code":"025647","amount":1809.54,"ratio":3.26,"dailyReturn":20.63,"holdingReturn":-190.46,"holdingReturnRate":-9.52,"totalReturn":-190.46,"category":"高端制造","assetType":"active"}
    ],
    "targetAllocation": {"黄金":24,"AI/科技":28,"纳指100":18,"标普500":8,"有色金属":6,"光伏/新能源":6,"高端制造":10}
};

// mockTimeline 已移除——早晚报数据统一由 data/news.json 提供（见 renderTimeline）
// 若 news.json 不可用，显示「暂无资讯」空状态，不用假数据兜底
const mockTimeline = [];

