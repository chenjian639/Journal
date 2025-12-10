package com.journal.service;

import com.journal.dao.UserDao;
import com.journal.entity.User;
import com.journal.util.PasswordUtil;

import java.util.List;

/**
 * 用户服务层
 */
public class UserService {
    private UserDao userDao = new UserDao();

    /**
     * 用户注册
     */
    public Long register(String username, String password, String email, String realName) {
        // 检查用户名是否存在
        if (userDao.existsByUsername(username)) {
            throw new RuntimeException("用户名已存在");
        }
        
        User user = new User();
        user.setUsername(username);
        user.setPassword(PasswordUtil.simpleHash(password));
        user.setEmail(email);
        user.setRealName(realName);
        user.setRole("USER");
        user.setStatus(1);
        
        return userDao.insert(user);
    }

    /**
     * 用户登录
     */
    public User login(String username, String password) {
        User user = userDao.findByUsername(username);
        if (user == null) {
            throw new RuntimeException("用户不存在");
        }
        
        if (user.getStatus() != 1) {
            throw new RuntimeException("账号已被禁用");
        }
        
        String hashedPassword = PasswordUtil.simpleHash(password);
        if (!hashedPassword.equals(user.getPassword())) {
            throw new RuntimeException("密码错误");
        }
        
        // 更新最后登录时间
        userDao.updateLastLoginTime(user.getId());
        
        return user;
    }

    /**
     * 修改密码
     */
    public boolean changePassword(Long userId, String oldPassword, String newPassword) {
        User user = userDao.findById(userId);
        if (user == null) {
            throw new RuntimeException("用户不存在");
        }
        
        String hashedOldPassword = PasswordUtil.simpleHash(oldPassword);
        if (!hashedOldPassword.equals(user.getPassword())) {
            throw new RuntimeException("原密码错误");
        }
        
        String hashedNewPassword = PasswordUtil.simpleHash(newPassword);
        return userDao.updatePassword(userId, hashedNewPassword);
    }

    /**
     * 获取用户信息
     */
    public User getUserById(Long id) {
        return userDao.findById(id);
    }

    /**
     * 获取所有用户
     */
    public List<User> getAllUsers() {
        return userDao.findAll();
    }

    /**
     * 更新用户信息
     */
    public boolean updateUser(User user) {
        return userDao.update(user);
    }

    /**
     * 删除用户
     */
    public boolean deleteUser(Long id) {
        return userDao.delete(id);
    }
}
