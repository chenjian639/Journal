package com.paper.dao;

import java.sql.Connection;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

import javax.sql.DataSource;

import org.springframework.stereotype.Repository;

import com.paper.model.AnalysisRecord;

/**
 * 分析记录数据访问对象
 */
@Repository
public class AnalysisDAO {
    
    private final MySQLHelper mysqlHelper;
    private final DataSource dataSource;
    private volatile Boolean sqliteCached;
    
    public AnalysisDAO(MySQLHelper mysqlHelper, DataSource dataSource) {
        this.mysqlHelper = mysqlHelper;
        this.dataSource = dataSource;
    }
    
    /**
     * 保存文件上传记录
     */
    public String saveUploadRecord(String username, String filename, String originalName, Long fileSize) {
        String sql = "INSERT INTO analysis_record (username, filename, original_name, file_size) VALUES (?, ?, ?, ?)";
        return mysqlHelper.executeSQL(sql, username, filename, originalName, fileSize);
    }
    
    /**
     * 保存分析记录（包含分析结果）
     */
    public String saveAnalysisRecord(String username, String filename, String originalName, String analysisResult) {
        String sql = "INSERT INTO analysis_record (username, filename, original_name, analysis_result) VALUES (?, ?, ?, ?)";
        return mysqlHelper.executeSQL(sql, username, filename, originalName, analysisResult);
    }
    
    /**
     * 更新分析结果
     */
    public String updateAnalysisResult(String filename, String analysisResult) {
        String sql = "UPDATE analysis_record SET analysis_result = ? WHERE filename = ?";
        return mysqlHelper.executeSQL(sql, analysisResult, filename);
    }
    
    /**
     * 根据文件名获取记录
     */
    public AnalysisRecord getByFilename(String filename) {
        String sql = selectAnalysisRecordSql("WHERE filename = ?", "");
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql, filename);
        if (rows == null || rows.isEmpty()) {
            return null;
        }
        try {
            return mapRowToRecord(rows.get(0));
        } catch (Exception e) {
            System.err.println("Failed to map analysis record: " + e.getMessage());
        }
        return null;
    }

    /**
     * 根据ID获取记录
     */
    public AnalysisRecord getById(long id) {
        String sql = selectAnalysisRecordSql("WHERE id = ?", "");
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql, id);
        if (rows == null || rows.isEmpty()) {
            return null;
        }
        try {
            return mapRowToRecord(rows.get(0));
        } catch (Exception e) {
            System.err.println("Failed to map analysis record by id: " + e.getMessage());
        }
        return null;
    }
    
    /**
     * 获取用户的分析历史
     */
    public List<AnalysisRecord> getHistoryByUsername(String username, int limit) {
        String sql = selectAnalysisRecordSql(
            "WHERE username = ? AND analysis_result IS NOT NULL",
            "ORDER BY created_at DESC LIMIT ?"
        );
        List<AnalysisRecord> records = new ArrayList<>();
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql, username, limit);
        if (rows == null || rows.isEmpty()) {
            return records;
        }
        for (Map<String, Object> row : rows) {
            try {
                records.add(mapRowToRecord(row));
            } catch (Exception ignored) {
            }
        }
        return records;
    }
    
    /**
     * 获取用户最近一次分析结果
     */
    public AnalysisRecord getLatestByUsername(String username) {
        String sql = selectAnalysisRecordSql(
            "WHERE username = ? AND analysis_result IS NOT NULL",
            "ORDER BY created_at DESC LIMIT 1"
        );
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql, username);
        if (rows == null || rows.isEmpty()) {
            return null;
        }
        try {
            return mapRowToRecord(rows.get(0));
        } catch (Exception e) {
            System.err.println("Failed to map latest analysis record: " + e.getMessage());
        }
        return null;
    }
    
    /**
     * 删除分析记录
     */
    public String deleteByFilename(String filename) {
        String sql = "DELETE FROM analysis_record WHERE filename = ?";
        return mysqlHelper.executeSQL(sql, filename);
    }
    
    /**
     * 将 ResultSet 映射为 AnalysisRecord
     */
    private AnalysisRecord mapRowToRecord(Map<String, Object> row) {
        AnalysisRecord record = new AnalysisRecord();
        record.setId(getLong(row.get("id")));
        record.setUsername(getString(row.get("username")));
        record.setFilename(getString(row.get("filename")));
        record.setOriginalName(getString(row.get("original_name")));
        record.setFileSize(getLong(row.get("file_size")));
        record.setAnalysisResult(getString(row.get("analysis_result")));
        
        String createdAt = getString(row.get("created_at"));
        if (createdAt != null) {
            try {
                record.setCreatedAt(LocalDateTime.parse(createdAt.replace(" ", "T")));
            } catch (Exception e) {
                record.setCreatedAt(LocalDateTime.now());
            }
        }
        return record;
    }

    private boolean isSQLite() {
        Boolean cached = sqliteCached;
        if (cached != null) return cached;
        boolean isSqlite = false;
        try (Connection conn = dataSource.getConnection()) {
            String product = conn.getMetaData().getDatabaseProductName();
            isSqlite = product != null && product.toLowerCase().contains("sqlite");
        } catch (Exception ignored) {
        }
        sqliteCached = isSqlite;
        return isSqlite;
    }

    /**
     * 统一构造查询 SQL：
     * - SQLite 的 CURRENT_TIMESTAMP 默认是 UTC；这里用 datetime(created_at,'localtime') 转成本地时间再返回给前端展示。
     * - MySQL 保持原样。
     */
    private String selectAnalysisRecordSql(String whereClause, String tail) {
        String baseCols;
        if (isSQLite()) {
            baseCols = "id, username, filename, original_name, file_size, analysis_result, datetime(created_at, 'localtime') AS created_at";
        } else {
            baseCols = "id, username, filename, original_name, file_size, analysis_result, created_at";
        }
        String w = (whereClause == null || whereClause.isBlank()) ? "" : (" " + whereClause.trim());
        String t = (tail == null || tail.isBlank()) ? "" : (" " + tail.trim());
        return "SELECT " + baseCols + " FROM analysis_record" + w + t;
    }

    private static String getString(Object v) {
        return v == null ? null : String.valueOf(v);
    }

    private static Long getLong(Object v) {
        if (v == null) return null;
        if (v instanceof Number n) return n.longValue();
        try {
            return Long.parseLong(String.valueOf(v));
        } catch (Exception e) {
            return null;
        }
    }
}
