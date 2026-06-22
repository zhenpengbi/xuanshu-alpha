// ========== 玄枢Alpha - PWA Banner + Tab 导航 + 锚点导航 ==========
// ========== iOS PWA 安装引导 Banner ==========
(function initPwaBanner() {
    // 只在 iOS Safari、未安装为 PWA 时显示
    const isIos = /iphone|ipad|ipod/i.test(navigator.userAgent);
    const isInStandaloneMode = ('standalone' in window.navigator) && window.navigator.standalone;
    const dismissed = (function() {
        try { return sessionStorage.getItem('pwaBannerDismissed') === '1'; } catch(_) { return false; }
    })();
    const banner = document.getElementById('pwaBanner');
    const closeBtn = document.getElementById('pwaBannerClose');
    if (!banner) return;

    if (isIos && !isInStandaloneMode && !dismissed && window.innerWidth <= 768) {
        // 延迟 2.5s 显示，避免页面加载时打扰
        setTimeout(() => { banner.style.display = 'flex'; }, 2500);
    }

    if (closeBtn) {
        closeBtn.addEventListener('click', () => {
            banner.style.display = 'none';
            try { sessionStorage.setItem('pwaBannerDismissed', '1'); } catch(_) {}
        });
    }
})();

// ========== 移动端 Tab 导航 ==========
(function initTabNav() {
    const nav = document.getElementById('tabNav');
    if (!nav) return;

    // 获取所有带 data-panel 的 section
    const allPanelSections = () =>
        document.querySelectorAll('.section[data-panel]');

    function switchTab(panel) {
        // 更新按钮状态
        nav.querySelectorAll('.tab-btn').forEach(btn => {
            btn.classList.toggle('active', btn.dataset.panel === panel);
        });
        // 切换 section 显示
        allPanelSections().forEach(sec => {
            sec.classList.toggle('panel-active', sec.dataset.panel === panel);
        });
        // 记住当前 tab
        try { sessionStorage.setItem('activePanel', panel); } catch(_) {}
        // ECharts 在 display:none panel 里 init 时宽高=0，切回后需 resize
        requestAnimationFrame(() => {
            if (panel === 'signals') {
                // 回测图（原 strategy）+ 信号仪表盘
                if (typeof _btChart   !== 'undefined' && _btChart)   _btChart.resize();
                if (typeof _goldChart !== 'undefined' && _goldChart) _goldChart.resize();
                if (typeof _usChart   !== 'undefined' && _usChart)   _usChart.resize();
            }
            if (panel === 'overview') {
                if (typeof _pieChart !== 'undefined' && _pieChart) _pieChart.resize();
                if (typeof _barChart !== 'undefined' && _barChart) _barChart.resize();
            }
        });
        // 滚回顶部（移动端体验）
        window.scrollTo({ top: 0, behavior: 'smooth' });
    }

    // Tab 按钮点击
    nav.addEventListener('click', e => {
        const btn = e.target.closest('.tab-btn');
        if (btn) switchTab(btn.dataset.panel);
    });

    // 初始化：移动端激活第一个 tab，其余隐藏
    function initMobile() {
        if (window.innerWidth > 768) return;
        const saved = (function() {
            try { return sessionStorage.getItem('activePanel'); } catch(_) { return null; }
        })();
        switchTab(saved || 'overview');
    }

    // 宽度变化时重置（从桌面拉到移动端）
    window.addEventListener('resize', () => {
        if (window.innerWidth <= 768) {
            const activeBtnPanel = (nav.querySelector('.tab-btn.active') || {}).dataset?.panel;
            if (activeBtnPanel) switchTab(activeBtnPanel);
        } else {
            // 桌面：移除所有 panel-active（CSS 不生效，但保持 DOM 干净）
            allPanelSections().forEach(sec => sec.classList.remove('panel-active'));
        }
    });

    // 页面加载后初始化
    document.addEventListener('DOMContentLoaded', initMobile);
})();

// ========== 顶部锚点导航 ==========
(function initAnchorNav() {
    const nav = document.getElementById('anchorNav');
    if (!nav) return;

    // 点击平滑滚动
    nav.addEventListener('click', e => {
        const btn = e.target.closest('.anav-btn');
        if (!btn) return;
        const target = document.getElementById(btn.dataset.anchor);
        if (target) target.scrollIntoView({ behavior: 'smooth', block: 'start' });
    });

    // IntersectionObserver 滚动高亮
    const btns = nav.querySelectorAll('.anav-btn');
    const anchors = [...btns].map(b => document.getElementById(b.dataset.anchor)).filter(Boolean);
    if (!anchors.length) return;

    let _active = null;
    const obs = new IntersectionObserver(entries => {
        entries.forEach(entry => {
            if (entry.isIntersecting) {
                const id = entry.target.id;
                if (_active === id) return;
                _active = id;
                btns.forEach(b => b.classList.toggle('anav-active', b.dataset.anchor === id));
            }
        });
    }, { rootMargin: '-20% 0px -70% 0px', threshold: 0 });

    anchors.forEach(el => obs.observe(el));
})();

