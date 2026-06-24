// Profile Page Logic - 依赖 components.js

// 设置当前用户
function setCurrentUser(user) {
    localStorage.setItem('currentUser', JSON.stringify(user));
}

// 清除当前用户
function clearCurrentUser() {
    localStorage.removeItem('currentUser');
}

// 加载用户信息
async function loadUserInfo() {
    const user = getCurrentUser();
    
    if (!user) {
        window.location.href = '/auth/login.html';
        return;
    }
    
    document.getElementById('profileUsername').textContent = user.uname;
    document.getElementById('profileEmail').textContent = user.email || '未设置邮箱';
    document.getElementById('uname').value = user.uname;
    document.getElementById('email').value = user.email || '';
    
    // 从服务器获取最新信息
    try {
        const response = await fetch(`/user/info?uname=${encodeURIComponent(user.uname)}`);
        const data = await response.json();
        
        if (data.success) {
            document.getElementById('profileEmail').textContent = data.email || '未设置邮箱';
            document.getElementById('email').value = data.email || '';
            setCurrentUser({ uname: data.uname, email: data.email });
        }
    } catch (error) {
        console.error('获取用户信息失败:', error);
    }
}

// 修改邮箱
async function handleProfileSubmit(event) {
    event.preventDefault();
    
    const user = getCurrentUser();
    if (!user) {
        window.location.href = '/auth/login.html';
        return;
    }
    
    const newEmail = document.getElementById('email').value;
    const formData = new FormData();
    formData.append('uname', user.uname);
    formData.append('newEmail', newEmail);
    
    try {
        const response = await fetch('/user/change-email', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('邮箱修改成功', 'success');
            setCurrentUser({ ...user, email: newEmail });
            document.getElementById('profileEmail').textContent = newEmail || '未设置邮箱';
        } else {
            showToast(data.message || '修改失败', 'error');
        }
    } catch (error) {
        console.error('修改邮箱失败:', error);
        showToast('请求失败，请稍后重试', 'error');
    }
}

// 修改密码
async function handlePasswordSubmit(event) {
    event.preventDefault();
    
    const user = getCurrentUser();
    if (!user) {
        window.location.href = '/auth/login.html';
        return;
    }
    
    const oldPassword = document.getElementById('oldPassword').value;
    const newPassword = document.getElementById('newPassword').value;
    const confirmNewPassword = document.getElementById('confirmNewPassword').value;
    
    if (newPassword !== confirmNewPassword) {
        showToast('两次输入的新密码不一致', 'error');
        return;
    }
    
    if (newPassword.length < 6) {
        showToast('新密码长度不能少于6位', 'error');
        return;
    }
    
    const formData = new FormData();
    formData.append('uname', user.uname);
    formData.append('oldPassword', oldPassword);
    formData.append('newPassword', newPassword);
    
    try {
        const response = await fetch('/user/change-password', {
            method: 'POST',
            body: formData
        });
        const data = await response.json();
        
        if (data.success) {
            showToast('密码修改成功', 'success');
            document.getElementById('passwordForm').reset();
        } else {
            showToast(data.message || '修改失败', 'error');
        }
    } catch (error) {
        console.error('修改密码失败:', error);
        showToast('请求失败，请稍后重试', 'error');
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    loadUserInfo();
    
    const profileForm = document.getElementById('profileForm');
    if (profileForm) {
        profileForm.addEventListener('submit', handleProfileSubmit);
    }
    
    const passwordForm = document.getElementById('passwordForm');
    if (passwordForm) {
        passwordForm.addEventListener('submit', handlePasswordSubmit);
    }
});
