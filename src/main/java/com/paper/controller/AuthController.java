package com.paper.controller;

import java.sql.SQLException;

import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.ResponseBody;

import com.paper.model.User;
import com.paper.service.UserService;

/**
 * 认证控制器
 * 处理用户登录、注册、验证码等认证相关的HTTP请求
 */
@Controller
@RequestMapping("/auth")
public class AuthController {

    private final UserService userService;

    public AuthController(UserService userService) {
        this.userService = userService;
    }

    /**
     * 用户登录
     */
    @PostMapping("/login")
    @ResponseBody
    public String login(String uname, String password) {
        User user = new User();
        user.setUname(uname);
        user.setPassword(password);

        try {
            if (userService.login(user)) {
                return "登录成功";
            }
            return "用户名或密码错误";
        } catch (SQLException e) {
            return "登录失败: " + e.getMessage();
        }
    }

    /**
     * 用户注册（带验证码，已关闭验证）
     */
    @PostMapping("/register")
    @ResponseBody
    public String register(String uname, String password, String email, String verifycode) 
            throws SQLException {
        User user = new User();
        user.setUname(uname);
        user.setPassword(password);
        user.setEmail(email);

        return userService.registerByEmail(user, verifycode);
    }

    /**
     * 直接注册（无需验证码）
     */
    @PostMapping("/register-direct")
    @ResponseBody
    public String registerDirect(String uname, String password, String email) 
            throws SQLException {
        User user = new User();
        user.setUname(uname);
        user.setPassword(password);
        user.setEmail(email);

        return userService.registerDirect(user);
    }

    /**
     * 发送验证码（已关闭，保留接口兼容性）
     */
    @PostMapping("/verifycode")
    @ResponseBody
    public String sendVerifyCode(String email) {
        // 邮件验证已关闭，返回提示信息
        return "邮件验证功能已关闭，请直接注册";
        // 如需开启邮件验证，取消下面代码的注释：
        // UserService userService = new UserService();
        // return userService.sendRegisterCode(email);
    }
}
