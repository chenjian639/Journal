package com.paper.dao;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;

import javax.sql.DataSource;

import org.springframework.dao.DataAccessException;
import org.springframework.stereotype.Component;

/**
 * 数据库帮助类
 * 使用 Spring Boot DataSource（可通过 profile 在 SQLite/MySQL 间切换）
 */
@Component
public class MySQLHelper {

    private final DataSource dataSource;

    public MySQLHelper(DataSource dataSource) {
        this.dataSource = dataSource;
    }
    
    /**
     * 执行更新类SQL（INSERT, UPDATE, DELETE）
     * @param sql SQL语句
     * @param params 参数
     * @return 错误信息（空字符串表示成功）
     */
    public String executeSQL(String sql, Object... params) {
        String errorString = "";
        try (var conn = dataSource.getConnection(); PreparedStatement pstmt = conn.prepareStatement(sql)) {
            setParameters(pstmt, params);
            int affectedRows = pstmt.executeUpdate();
            if (affectedRows == 0) {
                errorString = "SQL执行成功，但未影响任何数据（可能参数不匹配）";
            }
        } catch (SQLException | NumberFormatException | DataAccessException ex) {
            errorString = "SQL执行异常：" + ex.getMessage();
        }
        return errorString;
    }
    
    /**
     * 执行查询类SQL（SELECT）
     * @param sql SQL语句
     * @param params 参数
     * @return 包含 "result" (ResultSet) 和 "error" (String) 的Map
     */
    public List<Map<String, Object>> executeSQLWithSelect(String sql, Object... params) {
        try (var conn = dataSource.getConnection(); PreparedStatement pstmt = conn.prepareStatement(sql)) {
            setParameters(pstmt, params);
            try (ResultSet rs = pstmt.executeQuery()) {
                List<Map<String, Object>> out = new ArrayList<>();
                int colCount = rs.getMetaData().getColumnCount();
                while (rs.next()) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (int i = 1; i <= colCount; i++) {
                        String name = rs.getMetaData().getColumnLabel(i);
                        row.put(name, rs.getObject(i));
                    }
                    out.add(row);
                }
                return out;
            }
        } catch (SQLException | NumberFormatException | DataAccessException e) {
            return List.of();
        }
    }
    
    /**
     * 设置PreparedStatement的参数
     */
    private void setParameters(PreparedStatement pstmt, Object... params) throws SQLException {
        if (params != null && params.length > 0) {
            for (int i = 0; i < params.length; i++) {
                pstmt.setObject(i + 1, params[i]);
            }
        }
    }
    
    /**
     * 关闭数据库连接
     */
    public void close() {
        // 由 Spring 管理 DataSource/连接池，这里无需手动关闭
    }
}
