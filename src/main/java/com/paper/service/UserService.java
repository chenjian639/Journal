package com.paper.service;

import java.sql.SQLException;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Properties;
import java.util.Random;

import org.mindrot.jbcrypt.BCrypt;
import org.springframework.stereotype.Service;

import com.paper.config.EnvConfig;
import com.paper.dao.MySQLHelper;
import com.paper.model.User;

import jakarta.mail.Authenticator;
import jakarta.mail.Message;
import jakarta.mail.MessagingException;
import jakarta.mail.PasswordAuthentication;
import jakarta.mail.Session;
import jakarta.mail.Transport;
import jakarta.mail.internet.InternetAddress;
import jakarta.mail.internet.MimeMessage;

/**
 * 用户服务类
 * 负责用户认证、注册、邮件验证等业务逻辑
 */
@Service
public class UserService {

    private final MySQLHelper mysqlHelper;

    @SuppressWarnings("MismatchedCollectionQueryUpdate")
    private static final Map<String, String> verificationCodeMap = new HashMap<>();

    @SuppressWarnings("MismatchedCollectionQueryUpdate")
    private static final Map<String, Long> codeExpireTimeMap = new HashMap<>();

    public UserService(MySQLHelper mysqlHelper) {
        this.mysqlHelper = mysqlHelper;
    }

    /**
     * 用户登录验证
     */
    public boolean login(User user) throws SQLException {
        String sql = "SELECT password FROM users WHERE uname = ?";
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql, user.getUname());
        if (rows == null || rows.isEmpty()) {
            return false;
        }
        String storedHashedPassword = getString(rows.get(0).get("password"));
        return storedHashedPassword != null && BCrypt.checkpw(user.getPassword(), storedHashedPassword);
    }

    /**
     * 修改密码（入参 password 应为已加密后的值）
     */
    public String updatePassword(User user) throws SQLException {
        String sql = "UPDATE users SET password = ? WHERE uname = ?";
        return mysqlHelper.executeSQL(sql, user.getPassword(), user.getUname());
    }

    /**
     * 修改邮箱
     */
    public String updateEmail(String uname, String newEmail) throws SQLException {
        if (newEmail != null && !newEmail.isEmpty()) {
            String checkSql = "SELECT 1 FROM users WHERE email = ? AND uname != ? LIMIT 1";
            List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(checkSql, newEmail, uname);
            if (rows != null && !rows.isEmpty()) {
                return "该邮箱已被其他用户使用";
            }
        }

        String sql = "UPDATE users SET email = ? WHERE uname = ?";
        String result = mysqlHelper.executeSQL(sql, newEmail, uname);
        return result.isEmpty() ? "success" : result;
    }

    /**
     * 根据用户名获取用户信息
     */
    public User getUserByUsername(String uname) throws SQLException {
        String sql = "SELECT uname, email FROM users WHERE uname = ?";
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql, uname);
        if (rows == null || rows.isEmpty()) {
            return null;
        }

        Map<String, Object> row = rows.get(0);
        User user = new User();
        user.setUname(getString(row.get("uname")));
        user.setEmail(getString(row.get("email")));
        return user;
    }

    /**
     * 发送注册验证码到邮箱
     */
    public String sendRegisterCode(String email) {
        try {
            if (email == null || email.isBlank()) {
                return "邮箱不能为空";
            }
            if (isEmailExists(email)) {
                return "该邮箱已被注册";
            }
        } catch (SQLException e) {
            return "数据库查询失败：" + e.getMessage();
        }

        if (!EnvConfig.isMailEnabled()) {
            return "邮件验证未启用";
        }

        String code = generateRandomCode();
        verificationCodeMap.put(email, code);
        codeExpireTimeMap.put(email, System.currentTimeMillis());

        String host = EnvConfig.get(EnvConfig.MAIL_HOST, "smtp.qq.com");
        String port = EnvConfig.get(EnvConfig.MAIL_PORT, "465");
        String fromEmail = EnvConfig.get(EnvConfig.MAIL_USERNAME);
        String password = EnvConfig.get(EnvConfig.MAIL_PASSWORD);

        Properties props = new Properties();
        props.put("mail.smtp.auth", "true");
        props.put("mail.smtp.host", host);
        props.put("mail.smtp.port", port);
        props.put("mail.smtp.ssl.enable", "true");

        Session session = Session.getInstance(props, new Authenticator() {
            @Override
            protected PasswordAuthentication getPasswordAuthentication() {
                return new PasswordAuthentication(fromEmail, password);
            }
        });

        try {
            Message message = new MimeMessage(session);
            message.setFrom(new InternetAddress(fromEmail));
            message.setRecipients(Message.RecipientType.TO, InternetAddress.parse(email));
            message.setSubject("账号注册验证码");
            message.setText("您的注册验证码是：" + code + "，有效期5分钟，请妥善保管。");

            Transport.send(message);
            return "发送成功";
        } catch (MessagingException e) {
            System.err.println("Failed to send verification code: " + e.getMessage());
            return "验证码发送失败：" + e.getMessage();
        }
    }
    
    /**
     * 通过邮箱和验证码完成注册
     * 注意：当前已关闭邮件验证，验证码参数可传空或任意值
     */
    public String registerByEmail(User user, String code) throws SQLException {
        // 验证邮箱是否已被注册
        if (isEmailExists(user.getEmail())) {
            return "该邮箱已被注册";
        }
        
        // 验证用户名是否已存在
        if (isUsernameExists(user.getUname())) {
            return "该用户名已存在";
        }
        
        // 邮件验证已关闭，跳过验证码检查
        // 如需开启邮件验证，取消下面代码的注释
        /*
        // 验证验证码
        String storedCode = verificationCodeMap.get(user.getEmail());
        Long expireTime = codeExpireTimeMap.get(user.getEmail());
        
        if (storedCode == null || !storedCode.equals(code)) {
            return "验证码错误";
        }
        
        // 验证码过期检查（5分钟）
        if (expireTime == null || System.currentTimeMillis() - expireTime > 5 * 60 * 1000) {
            verificationCodeMap.remove(user.getEmail());
            codeExpireTimeMap.remove(user.getEmail());
            return "验证码已过期";
        }
        */
        
        // 执行注册
        String sql = "INSERT INTO users (uname, password, email) VALUES (?, ?, ?)";
        String hashedPassword = BCrypt.hashpw(user.getPassword(), BCrypt.gensalt());
        String result = mysqlHelper.executeSQL(sql, user.getUname(), hashedPassword, user.getEmail());
        
        if (result.isEmpty()) {
            verificationCodeMap.remove(user.getEmail());
            codeExpireTimeMap.remove(user.getEmail());
            return "注册成功";
        }
        
        return result;
    }
    
    /**
     * 直接注册（无需验证码）
     */
    public String registerDirect(User user) throws SQLException {
        // 1. 先验证用户名格式（必须先检查格式，再查数据库）
        if (user.getUname() == null || user.getUname().trim().isEmpty()) {
            return "用户名不能为空";
        }
        
        if (user.getUname().length() < 2 || user.getUname().length() > 20) {
            return "用户名长度应在2-20个字符之间";
        }
        
        // 2. 验证密码强度
        if (user.getPassword() == null || user.getPassword().length() < 6) {
            return "密码长度不能少于6位";
        }
        
        // 3. 验证用户名是否已存在
        if (isUsernameExists(user.getUname())) {
            return "该用户名已存在";
        }
        
        // 4. 验证邮箱是否已被注册（邮箱可选）
        if (user.getEmail() != null && !user.getEmail().isEmpty() && isEmailExists(user.getEmail())) {
            return "该邮箱已被注册";
        }
        
        // 执行注册
        String sql = "INSERT INTO users (uname, password, email) VALUES (?, ?, ?)";
        String hashedPassword = BCrypt.hashpw(user.getPassword(), BCrypt.gensalt());
        String email = (user.getEmail() != null && !user.getEmail().isEmpty()) ? user.getEmail() : null;
        String result = mysqlHelper.executeSQL(sql, user.getUname(), hashedPassword, email);
        
        if (result.isEmpty()) {
            return "注册成功";
        }
        
        return result;
    }
    
    /**
     * 生成6位随机验证码
     */
    private String generateRandomCode() {
        Random random = new Random();
        int code = 100000 + random.nextInt(900000);
        return String.valueOf(code);
    }
    
    /**
     * 检查邮箱是否已存在
     */
    private boolean isEmailExists(String email) throws SQLException {
        if (email == null || email.isBlank()) {
            return false;
        }
        String sql = "SELECT 1 FROM users WHERE email = ? LIMIT 1";
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql, email);
        return rows != null && !rows.isEmpty();
    }
    
    /**
     * 检查用户名是否已存在
     */
    private boolean isUsernameExists(String username) throws SQLException {
        if (username == null || username.isBlank()) {
            return false;
        }
        String sql = "SELECT 1 FROM users WHERE uname = ? LIMIT 1";
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql, username);
        return rows != null && !rows.isEmpty();
    }

    private static String getString(Object v) {
        return v == null ? null : String.valueOf(v);
    }
}
