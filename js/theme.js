// ========== 玄枢Alpha - 主题切换 + ECharts 配色 ==========
// ========== Theme Switcher ==========
(function initTheme() {
    const STORAGE_KEY = 'xuanshu-theme';
    const themeMap = {
        dark:  { icon: '🌙', label: '夜间' },
        light: { icon: '☀️', label: '日间' },
        auto:  { icon: '🖥️', label: '自动' }
    };

    // 同步 html.light 类——CSS 通过该类统一覆盖日间样式，无需双写选择器
    function syncLightClass(theme) {
        const isLight = theme === 'light' ||
            (theme === 'auto' && window.matchMedia('(prefers-color-scheme: light)').matches);
        document.documentElement.classList.toggle('light', isLight);
    }

    function applyTheme(theme) {
        const html = document.documentElement;
        if (theme === 'auto') {
            html.removeAttribute('data-theme');
        } else {
            html.setAttribute('data-theme', theme);
        }
        syncLightClass(theme);
        // 更新按钮文字
        const t = themeMap[theme] || themeMap.dark;
        const iconEl = document.getElementById('themeIcon');
        const labelEl = document.getElementById('themeLabel');
        if (iconEl) iconEl.textContent = t.icon;
        if (labelEl) labelEl.textContent = t.label;
        // 更新选中态
        document.querySelectorAll('.theme-option').forEach(el => {
            el.classList.toggle('selected', el.dataset.theme === theme);
        });
        // 更新 meta theme-color
        const metaColor = theme === 'light' ? '#f0f4ff' : '#070d1a';
        document.querySelector('meta[name="theme-color"]').content = metaColor;
        // 图表重新应用配色
        if (window._recolorCharts) window._recolorCharts();
    }

    function savedTheme() {
        return localStorage.getItem(STORAGE_KEY) || 'auto';
    }

    // 跟随系统偏好变化时同步 html.light 类（仅当用户选择「自动」时生效）
    window.matchMedia('(prefers-color-scheme: light)')
        .addEventListener('change', () => {
            if (savedTheme() === 'auto') syncLightClass('auto');
        });

    // 页面加载立即应用（防止白闪）
    applyTheme(savedTheme());

    document.addEventListener('DOMContentLoaded', function() {
        const btn = document.getElementById('themeToggleBtn');
        const popover = document.getElementById('themePopover');
        if (!btn || !popover) return;

        // 应用已保存主题
        applyTheme(savedTheme());

        // 切换浮层开关：用 getBoundingClientRect 动态定位，兼容任意 header 高度和屏幕宽度
        btn.addEventListener('click', function(e) {
            e.stopPropagation();
            const isOpen = popover.classList.toggle('open');
            btn.setAttribute('aria-expanded', isOpen);
            if (isOpen) {
                const rect = btn.getBoundingClientRect();
                // 弹窗紧贴按钮下方，右对齐按钮右侧
                const gap = 8;
                const popoverTop = rect.bottom + gap;
                // 从视口右边缘量右侧距离，保证弹窗不超出屏幕左边
                const rightOffset = window.innerWidth - rect.right;
                popover.style.top   = popoverTop + 'px';
                popover.style.right = Math.max(4, rightOffset) + 'px';
                popover.style.left  = 'auto'; // 重置，防止之前设置残留
            }
        });

        // 选择主题
        popover.addEventListener('click', function(e) {
            const option = e.target.closest('.theme-option');
            if (!option) return;
            const theme = option.dataset.theme;
            localStorage.setItem(STORAGE_KEY, theme);
            applyTheme(theme);
            popover.classList.remove('open');
            btn.setAttribute('aria-expanded', 'false');
        });

        // 点击外部关闭
        document.addEventListener('click', function(e) {
            if (!btn.contains(e.target) && !popover.contains(e.target)) {
                popover.classList.remove('open');
                btn.setAttribute('aria-expanded', 'false');
            }
        });

        // 键盘关闭
        document.addEventListener('keydown', function(e) {
            if (e.key === 'Escape') {
                popover.classList.remove('open');
                btn.setAttribute('aria-expanded', 'false');
            }
        });
    });
})();

// ========== ECharts 颜色工具：从 CSS Variables 读取主题色 ==========
function getCssVar(varName) {
    return getComputedStyle(document.documentElement).getPropertyValue(varName).trim();
}
function getChartColors() {
    const accent  = getCssVar('--accent')  || '#00c8ff';
    const green   = getCssVar('--green')   || '#00e5a0';
    const blue    = getCssVar('--blue')    || '#4a9eff';
    const purple  = getCssVar('--purple')  || '#8b5cf6';
    const dim     = getCssVar('--text-secondary') || '#8ba8d0';
    const muted   = getCssVar('--text-muted')     || '#4d6a90';
    const textPrimary = getCssVar('--text-primary') || '#e8f0fe';
    const bgTooltip   = getCssVar('--bg-secondary') || 'rgba(12,20,38,.9)';
    const lineColor   = getCssVar('--accent-line')  || 'rgba(0,200,255,.22)';
    const border  = getCssVar('--border-color') || 'rgba(0,200,255,.1)';
    return { accent, green, blue, purple, dim, muted, textPrimary, bgTooltip, lineColor, border };
}

// ========== 主题切换时重绘所有 ECharts 图表 ==========
window._recolorCharts = function() {
    // 延迟 60ms 确保 CSS 变量已完成切换
    setTimeout(function() {
        if (_pieChart)  renderPieChart();
        if (_barChart)  renderBarChart();
        // Gauges 重绘
        if (signalData && (signalData.gold || signalData.us)) renderGauges();
        // 回测图表重绘
        if (_btChart && _btData && _btSelected) {
            const r = _btData.results && _btData.results.find(x => x.code === _btSelected);
            if (r) renderBtChart(r);
        }
        // sparkline 重绘（drawSparkline 已读 getCssVar）
        renderHoldings();
    }, 60);
};

