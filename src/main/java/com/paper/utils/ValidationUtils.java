package com.paper.utils;

import java.util.regex.Pattern;

/**
 * 输入验证工具类
 * 提供统一的输入验证方法，防止安全漏洞
 * 
 * @author PaperMaster Team
 * @version 1.0
 * @since 2024-12-18
 */
public class ValidationUtils {

    // 邮箱正则表达式
    private static final Pattern EMAIL_PATTERN = Pattern.compile(
            "^[A-Za-z0-9+_.-]+@[A-Za-z0-9.-]+\\.[A-Za-z]{2,}$"
    );

    // 用户名正则：字母、数字、下划线，2-20位
    private static final Pattern USERNAME_PATTERN = Pattern.compile(
            "^[a-zA-Z0-9_\\u4e00-\\u9fa5]{2,20}$"
    );

    // 文件名安全正则：防止路径遍历
    private static final Pattern SAFE_FILENAME_PATTERN = Pattern.compile(
            "^[a-zA-Z0-9._-]+$"
    );

    /**
     * 验证邮箱格式
     * 
     * @param email 邮箱地址
     * @return 是否有效
     */
    public static boolean isValidEmail(String email) {
        if (email == null || email.isEmpty()) {
            return false;
        }
        return EMAIL_PATTERN.matcher(email).matches();
    }

    /**
     * 验证用户名格式
     * 
     * @param username 用户名
     * @return 是否有效
     */
    public static boolean isValidUsername(String username) {
        if (username == null || username.isEmpty()) {
            return false;
        }
        return USERNAME_PATTERN.matcher(username).matches();
    }

    /**
     * 验证密码强度
     * 
     * @param password 密码
     * @return 错误信息，null表示验证通过
     */
    public static String validatePassword(String password) {
        if (password == null || password.isEmpty()) {
            return "密码不能为空";
        }
        if (password.length() < 6) {
            return "密码长度不能少于6位";
        }
        if (password.length() > 50) {
            return "密码长度不能超过50位";
        }
        return null;
    }

    /**
     * 验证文件名是否安全（防止路径遍历攻击）
     * 
     * @param filename 文件名
     * @return 是否安全
     */
    public static boolean isSafeFilename(String filename) {
        if (filename == null || filename.isEmpty()) {
            return false;
        }
        // 检查是否包含路径遍历字符
        if (filename.contains("..") || filename.contains("/") || filename.contains("\\")) {
            return false;
        }
        return SAFE_FILENAME_PATTERN.matcher(filename).matches();
    }

    /**
     * 检查字符串是否为空或仅包含空白字符
     * 
     * @param str 字符串
     * @return 是否为空
     */
    public static boolean isBlank(String str) {
        return str == null || str.trim().isEmpty();
    }

    /**
     * 检查字符串是否非空
     * 
     * @param str 字符串
     * @return 是否非空
     */
    public static boolean isNotBlank(String str) {
        return !isBlank(str);
    }

    /**
     * 清理用户输入，防止XSS攻击
     * 
     * @param input 用户输入
     * @return 清理后的字符串
     */
    public static String sanitize(String input) {
        if (input == null) {
            return null;
        }
        return input.replace("<", "&lt;")
                    .replace(">", "&gt;")
                    .replace("\"", "&quot;")
                    .replace("'", "&#x27;");
    }
}
