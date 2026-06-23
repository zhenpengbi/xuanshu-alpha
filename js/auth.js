// ========== 玄枢Alpha - 访问控制 ==========
// PIN 以 SHA-256 哈希存储，源码公开也无法反推原始 PIN。
// 修改 PIN：运行 hashPin('新PIN') 取得哈希值，替换 CORRECT_HASH。

const AUTH = (function () {

    // ── 配置区 ──────────────────────────────────────────────────
    const CORRECT_HASH = '8242f1ad6f41ed06355584e4d2bc4271e19aa445ce0b5e0ecb0b2e60bbe04edf';
    const STORAGE_KEY  = 'xuanshu_auth_v2';
    const MAX_ATTEMPTS = 5;           // 连续错误次数上限
    const LOCKOUT_MS   = 60 * 1000;  // 锁定时长（毫秒）
    // ────────────────────────────────────────────────────────────

    // ── SHA-256 工具（Web Crypto API）──
    async function sha256(str) {
        const buf = await crypto.subtle.digest(
            'SHA-256', new TextEncoder().encode(str)
        );
        return Array.from(new Uint8Array(buf))
            .map(b => b.toString(16).padStart(2, '0')).join('');
    }

    // ── 验证状态 ──
    function isUnlocked() {
        if (!CORRECT_HASH) return true;                      // 未配置 PIN，直接放行
        return localStorage.getItem(STORAGE_KEY) === CORRECT_HASH;
    }

    function unlock() {
        localStorage.setItem(STORAGE_KEY, CORRECT_HASH);
    }

    function lock() {
        localStorage.removeItem(STORAGE_KEY);
    }

    // ── 错误计数（防暴力破解）──
    function getAttemptInfo() {
        try { return JSON.parse(sessionStorage.getItem('xuanshu_attempts') || '{}'); }
        catch { return {}; }
    }
    function saveAttemptInfo(info) {
        sessionStorage.setItem('xuanshu_attempts', JSON.stringify(info));
    }

    // ── 锁屏 UI ──
    function buildLockScreen() {
        const el = document.getElementById('lockScreen');
        if (!el) return;

        const pinInput  = document.getElementById('pinInput');
        const pinBtn    = document.getElementById('pinSubmit');
        const pinErr    = document.getElementById('pinError');
        const pinStatus = document.getElementById('pinStatus');

        async function tryUnlock() {
            const info = getAttemptInfo();
            const now  = Date.now();

            // 锁定期间禁止输入
            if (info.lockedUntil && now < info.lockedUntil) {
                const secs = Math.ceil((info.lockedUntil - now) / 1000);
                showError(`密码错误次数过多，请 ${secs} 秒后重试`);
                return;
            }

            const pin  = pinInput.value.trim();
            if (!pin) { pinInput.focus(); return; }

            // 哈希比对
            pinBtn.disabled = true;
            if (pinStatus) pinStatus.textContent = '验证中…';
            const hash = await sha256(pin);

            if (hash === CORRECT_HASH) {
                // ✅ 通过
                unlock();
                el.classList.add('lock-unlocking');
                setTimeout(() => el.remove(), 500);
                saveAttemptInfo({});
            } else {
                // ❌ 失败
                info.count = (info.count || 0) + 1;
                if (info.count >= MAX_ATTEMPTS) {
                    info.lockedUntil = Date.now() + LOCKOUT_MS;
                    info.count = 0;
                }
                saveAttemptInfo(info);

                const remaining = MAX_ATTEMPTS - (info.count || 0);
                showError(
                    info.lockedUntil && Date.now() < info.lockedUntil
                        ? `密码错误次数过多，锁定 ${LOCKOUT_MS / 1000} 秒`
                        : `密码错误${remaining > 0 ? `，还剩 ${remaining} 次机会` : ''}`
                );
                pinInput.value = '';
                pinInput.focus();
                pinBtn.disabled = false;
                if (pinStatus) pinStatus.textContent = '';
            }
        }

        function showError(msg) {
            if (!pinErr) return;
            pinErr.textContent = msg;
            pinErr.classList.add('visible');
            setTimeout(() => pinErr.classList.remove('visible'), 3000);
        }

        pinBtn.addEventListener('click', tryUnlock);
        pinInput.addEventListener('keydown', e => { if (e.key === 'Enter') tryUnlock(); });
        pinInput.focus();
    }

    // ── 公开 API ──
    return {
        init() {
            if (isUnlocked()) {
                document.getElementById('lockScreen')?.remove();
                return;
            }
            buildLockScreen();
        },

        lock() {
            lock();
            location.reload();
        },

        // 辅助：在控制台运行 AUTH.hashPin('你的PIN') 获取哈希值
        async hashPin(pin) {
            const h = await sha256(pin);
            console.log(`PIN "${pin}" 的 SHA-256 哈希值：\n${h}`);
            return h;
        }
    };
})();

document.addEventListener('DOMContentLoaded', () => AUTH.init());
