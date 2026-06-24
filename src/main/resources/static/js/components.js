// 公共组件 - 导航栏和页面基础结构

// 渲染导航栏
function renderNavbar() {
    const user = localStorage.getItem('currentUser');
    const isLoggedIn = !!user;
    
    return `
    <nav class="navbar">
        <a href="/index.html" class="navbar-brand">
            <i class="fas fa-graduation-cap"></i>
            PaperMaster
        </a>
        <div class="navbar-menu">
            <a href="/index.html">首页</a>
            <a href="/journal/rankings">期刊排名</a>
            <a href="/analysis.html">期刊分析</a>
            <a href="/keyword_analysis.html">关键词分析</a>
            ${isLoggedIn ? '<a href="/report_download.html">报告下载</a>' : ''}
            ${isLoggedIn ? '<a href="/user/profile.html">个人中心</a>' : ''}
            ${isLoggedIn ? 
                '<a href="#" id="logoutLink">登出</a>' : 
                `<a href="/auth/login.html?redirect=${encodeURIComponent(window.location.pathname)}">登录</a><a href="/auth/register.html" class="btn btn-primary">注册</a>`
            }
        </div>
    </nav>`;
}

// 初始化导航栏
function initNavbar() {
    const navContainer = document.getElementById('navbar-container');
    if (navContainer) {
        navContainer.innerHTML = renderNavbar();
        
        // 绑定登出事件
        const logoutLink = document.getElementById('logoutLink');
        if (logoutLink) {
            logoutLink.addEventListener('click', (e) => {
                e.preventDefault();
                localStorage.removeItem('currentUser');
                window.location.href = '/index.html';
            });
        }

        // 管理员：在导航栏最右侧追加“管理员面板”入口
        try {
            const current = getCurrentUser();
            const uname = current && current.uname ? current.uname : '';
            if (uname) {
                fetch('/admin/me?uname=' + encodeURIComponent(uname))
                    .then(r => r.json())
                    .then(json => {
                        if (!json || json.success === false || !json.isAdmin) return;
                        const menu = navContainer.querySelector('.navbar-menu');
                        if (!menu) return;
                        const a = document.createElement('a');
                        a.href = '/admin_panel.html';
                        a.textContent = '管理员面板';
                        menu.appendChild(a);
                    })
                    .catch(() => {});
            }
        } catch (e) {
            // ignore
        }
    }
}

// 检查是否需要登录
function requireLogin(redirectUrl) {
    const user = localStorage.getItem('currentUser');
    if (!user) {
        window.location.href = '/auth/login.html?redirect=' + encodeURIComponent(redirectUrl);
        return false;
    }
    return true;
}

// 检查登录状态
function isLoggedIn() {
    return localStorage.getItem('currentUser') !== null;
}

// 获取当前用户
function getCurrentUser() {
    const user = localStorage.getItem('currentUser');
    return user ? JSON.parse(user) : null;
}

// Toast 提示
function showToast(message, type = 'info') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    
    toast.offsetHeight;
    toast.classList.add('show');
    
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// 页面加载时初始化导航栏
document.addEventListener('DOMContentLoaded', initNavbar);
