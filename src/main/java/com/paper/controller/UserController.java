package com.paper.controller;

import java.sql.SQLException;
import java.util.HashMap;
import java.util.Map;

import org.mindrot.jbcrypt.BCrypt;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;

import com.paper.model.User;
import com.paper.service.UserService;
import com.paper.utils.ResponseUtils;
import com.paper.utils.ValidationUtils;

/**
 * 用户控制器
 * <p>处理用户主页、修改密码等用户相关的HTTP请求</p>
 * 
 * <h3>API 列表：</h3>
 * <ul>
 *   <li>GET /user/info - 获取用户信息</li>
 *   <li>POST /user/change-password - 修改密码</li>
 *   <li>POST /user/change-email - 修改邮箱</li>
 * </ul>
 * 
 * @author PaperMaster Team
 * @version 1.0
 * @since 2024-12-18
 */
@Controller
@RequestMapping("/user")
public class UserController {

    private final UserService userService;

    public UserController(UserService userService) {
        this.userService = userService;
    }

    /**
     * 获取用户信息
     * 
     * @param uname 用户名
     * @return 用户信息（uname, email）
     */
    @GetMapping("/info")
    @ResponseBody
    public Map<String, Object> getUserInfo(@RequestParam String uname) {
        if (ValidationUtils.isBlank(uname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        
        try {
            User user = userService.getUserByUsername(uname.trim());
            
            if (user != null) {
                Map<String, Object> data = new HashMap<>();
                data.put("uname", user.getUname());
                data.put("email", user.getEmail());
                return ResponseUtils.success("success", data);
            } else {
                return ResponseUtils.error("用户不存在");
            }
        } catch (SQLException e) {
            return ResponseUtils.error("获取用户信息失败: " + e.getMessage());
        }
    }

    /**
     * 修改密码
     * 
     * @param uname 用户名
     * @param oldPassword 旧密码
     * @param newPassword 新密码（最少6位）
     * @return 修改结果
     */
    @PostMapping("/change-password")
    @ResponseBody
    public Map<String, Object> changePassword(
            @RequestParam String uname,
            @RequestParam String oldPassword,
            @RequestParam String newPassword) {
        
        // 参数验证
        if (ValidationUtils.isBlank(uname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        
        String passwordError = ValidationUtils.validatePassword(newPassword);
        if (passwordError != null) {
            return ResponseUtils.error(passwordError);
        }
        
        try {
            // 验证旧密码
            User user = new User();
            user.setUname(uname.trim());
            user.setPassword(oldPassword);
            
            if (!userService.login(user)) {
                return ResponseUtils.error("原密码错误");
            }
            
            // 加密新密码并更新
            String hashedPassword = BCrypt.hashpw(newPassword, BCrypt.gensalt());
            User updateUser = new User();
            updateUser.setUname(uname.trim());
            updateUser.setPassword(hashedPassword);
            
            String result = userService.updatePassword(updateUser);
            
            if (result.isEmpty()) {
                return ResponseUtils.success("密码修改成功");
            } else {
                return ResponseUtils.error("密码修改失败: " + result);
            }
            
        } catch (SQLException e) {
            return ResponseUtils.error("修改密码失败: " + e.getMessage());
        }
    }

    /**
     * 修改邮箱
     * 
     * @param uname 用户名
     * @param newEmail 新邮箱地址
     * @return 修改结果
     */
    @PostMapping("/change-email")
    @ResponseBody
    public Map<String, Object> changeEmail(
            @RequestParam String uname,
            @RequestParam String newEmail) {
        
        // 参数验证
        if (ValidationUtils.isBlank(uname)) {
            return ResponseUtils.error("用户名不能为空");
        }
        
        if (ValidationUtils.isNotBlank(newEmail) && !ValidationUtils.isValidEmail(newEmail)) {
            return ResponseUtils.error("邮箱格式不正确");
        }
        
        try {
            String result = userService.updateEmail(uname.trim(), newEmail);
            
            if ("success".equals(result)) {
                return ResponseUtils.success("邮箱修改成功");
            } else {
                return ResponseUtils.error(result);
            }
            
        } catch (SQLException e) {
            return ResponseUtils.error("修改邮箱失败: " + e.getMessage());
        }
    }
}
