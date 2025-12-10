package com.journal.dao;

import com.journal.entity.User;
import com.journal.util.DBUtil;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.*;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 用户数据访问层
 */
public class UserDao {
    private static final Logger logger = LoggerFactory.getLogger(UserDao.class);

    /**
     * 添加用户
     */
    public Long insert(User user) {
        String sql = "INSERT INTO users (username, password, email, real_name, role, status, create_time, update_time) " +
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {
            
            LocalDateTime now = LocalDateTime.now();
            ps.setString(1, user.getUsername());
            ps.setString(2, user.getPassword());
            ps.setString(3, user.getEmail());
            ps.setString(4, user.getRealName());
            ps.setString(5, user.getRole() != null ? user.getRole() : "USER");
            ps.setInt(6, user.getStatus() != null ? user.getStatus() : 1);
            ps.setTimestamp(7, Timestamp.valueOf(now));
            ps.setTimestamp(8, Timestamp.valueOf(now));
            
            ps.executeUpdate();
            
            try (ResultSet rs = ps.getGeneratedKeys()) {
                if (rs.next()) {
                    return rs.getLong(1);
                }
            }
        } catch (SQLException e) {
            logger.error("添加用户失败", e);
            throw new RuntimeException("添加用户失败", e);
        }
        return null;
    }

    /**
     * 更新用户
     */
    public boolean update(User user) {
        String sql = "UPDATE users SET email=?, real_name=?, role=?, status=?, update_time=? WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setString(1, user.getEmail());
            ps.setString(2, user.getRealName());
            ps.setString(3, user.getRole());
            ps.setInt(4, user.getStatus());
            ps.setTimestamp(5, Timestamp.valueOf(LocalDateTime.now()));
            ps.setLong(6, user.getId());
            
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            logger.error("更新用户失败", e);
            throw new RuntimeException("更新用户失败", e);
        }
    }

    /**
     * 更新密码
     */
    public boolean updatePassword(Long userId, String newPassword) {
        String sql = "UPDATE users SET password=?, update_time=? WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setString(1, newPassword);
            ps.setTimestamp(2, Timestamp.valueOf(LocalDateTime.now()));
            ps.setLong(3, userId);
            
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            logger.error("更新密码失败", e);
            throw new RuntimeException("更新密码失败", e);
        }
    }

    /**
     * 更新最后登录时间
     */
    public boolean updateLastLoginTime(Long userId) {
        String sql = "UPDATE users SET last_login_time=? WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setTimestamp(1, Timestamp.valueOf(LocalDateTime.now()));
            ps.setLong(2, userId);
            
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            logger.error("更新最后登录时间失败", e);
            throw new RuntimeException("更新最后登录时间失败", e);
        }
    }

    /**
     * 删除用户
     */
    public boolean delete(Long id) {
        String sql = "DELETE FROM users WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, id);
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            logger.error("删除用户失败", e);
            throw new RuntimeException("删除用户失败", e);
        }
    }

    /**
     * 根据ID查询用户
     */
    public User findById(Long id) {
        String sql = "SELECT * FROM users WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, id);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return mapResultSetToUser(rs);
                }
            }
        } catch (SQLException e) {
            logger.error("查询用户失败", e);
            throw new RuntimeException("查询用户失败", e);
        }
        return null;
    }

    /**
     * 根据用户名查询用户
     */
    public User findByUsername(String username) {
        String sql = "SELECT * FROM users WHERE username=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setString(1, username);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return mapResultSetToUser(rs);
                }
            }
        } catch (SQLException e) {
            logger.error("根据用户名查询用户失败", e);
            throw new RuntimeException("根据用户名查询用户失败", e);
        }
        return null;
    }

    /**
     * 查询所有用户
     */
    public List<User> findAll() {
        String sql = "SELECT * FROM users ORDER BY create_time DESC";
        List<User> users = new ArrayList<>();
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql);
             ResultSet rs = ps.executeQuery()) {
            
            while (rs.next()) {
                users.add(mapResultSetToUser(rs));
            }
        } catch (SQLException e) {
            logger.error("查询用户列表失败", e);
            throw new RuntimeException("查询用户列表失败", e);
        }
        return users;
    }

    /**
     * 检查用户名是否存在
     */
    public boolean existsByUsername(String username) {
        String sql = "SELECT COUNT(*) FROM users WHERE username=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setString(1, username);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return rs.getInt(1) > 0;
                }
            }
        } catch (SQLException e) {
            logger.error("检查用户名是否存在失败", e);
            throw new RuntimeException("检查用户名是否存在失败", e);
        }
        return false;
    }

    /**
     * ResultSet映射到User对象
     */
    private User mapResultSetToUser(ResultSet rs) throws SQLException {
        User user = new User();
        user.setId(rs.getLong("id"));
        user.setUsername(rs.getString("username"));
        user.setPassword(rs.getString("password"));
        user.setEmail(rs.getString("email"));
        user.setRealName(rs.getString("real_name"));
        user.setRole(rs.getString("role"));
        user.setStatus(rs.getInt("status"));
        
        Timestamp createTime = rs.getTimestamp("create_time");
        if (createTime != null) {
            user.setCreateTime(createTime.toLocalDateTime());
        }
        
        Timestamp updateTime = rs.getTimestamp("update_time");
        if (updateTime != null) {
            user.setUpdateTime(updateTime.toLocalDateTime());
        }
        
        Timestamp lastLoginTime = rs.getTimestamp("last_login_time");
        if (lastLoginTime != null) {
            user.setLastLoginTime(lastLoginTime.toLocalDateTime());
        }
        
        return user;
    }
}
