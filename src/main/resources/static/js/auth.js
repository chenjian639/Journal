// Auth Logic

async function handleLogin(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    const uname = formData.get('uname');
    
    try {
        const response = await fetch('/auth/login', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.text();
        
        if (result.includes('登录成功')) {
            // 保存用户信息到localStorage
            localStorage.setItem('currentUser', JSON.stringify({
                uname: uname,
                email: ''
            }));
            
            showToast('登录成功！正在跳转...', 'success');
            
            // 检查是否有重定向参数
            const urlParams = new URLSearchParams(window.location.search);
            const redirect = urlParams.get('redirect');
            
            setTimeout(() => {
                window.location.href = redirect || '/index.html';
            }, 1000);
        } else {
            showToast(result, 'error');
        }
    } catch (error) {
        console.error('Login error:', error);
        showToast('登录请求失败', 'error');
    }
}

async function handleRegister(event) {
    event.preventDefault();
    
    const form = event.target;
    const formData = new FormData(form);
    
    // Validate passwords match
    const password = formData.get('password');
    const confirmPassword = formData.get('confirmPassword');
    
    if (password !== confirmPassword) {
        showToast('两次输入的密码不一致', 'error');
        return;
    }
    
    try {
        // Using register-direct as verifycode is disabled
        const response = await fetch('/auth/register-direct', {
            method: 'POST',
            body: formData
        });
        
        const result = await response.text();
        
        if (result.includes('成功') || result.includes('success')) {
            showToast('注册成功！请登录', 'success');
            setTimeout(() => {
                window.location.href = '/auth/login.html';
            }, 1500);
        } else {
            showToast(result, 'error');
        }
    } catch (error) {
        console.error('Register error:', error);
        showToast('注册请求失败', 'error');
    }
}

// Attach listeners
document.addEventListener('DOMContentLoaded', () => {
    const loginForm = document.getElementById('loginForm');
    if (loginForm) {
        loginForm.addEventListener('submit', handleLogin);
    }
    
    const registerForm = document.getElementById('registerForm');
    if (registerForm) {
        registerForm.addEventListener('submit', handleRegister);
    }
});
