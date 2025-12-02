package com.journal.dao;

import com.journal.entity.AnalysisReport;
import com.journal.util.DBUtil;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.*;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 分析报告数据访问层
 */
public class AnalysisReportDao {
    private static final Logger logger = LoggerFactory.getLogger(AnalysisReportDao.class);

    /**
     * 添加分析报告
     */
    public Long insert(AnalysisReport report) {
        String sql = "INSERT INTO analysis_reports (title, report_type, journal_id, journal_ids, " +
                "content, created_by, create_time, update_time) VALUES (?, ?, ?, ?, ?, ?, ?, ?)";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {
            
            LocalDateTime now = LocalDateTime.now();
            ps.setString(1, report.getTitle());
            ps.setString(2, report.getReportType());
            ps.setObject(3, report.getJournalId());
            ps.setString(4, report.getJournalIds());
            ps.setString(5, report.getContent());
            ps.setObject(6, report.getCreatedBy());
            ps.setTimestamp(7, Timestamp.valueOf(now));
            ps.setTimestamp(8, Timestamp.valueOf(now));
            
            ps.executeUpdate();
            
            try (ResultSet rs = ps.getGeneratedKeys()) {
                if (rs.next()) {
                    return rs.getLong(1);
                }
            }
        } catch (SQLException e) {
            logger.error("添加分析报告失败", e);
            throw new RuntimeException("添加分析报告失败", e);
        }
        return null;
    }

    /**
     * 根据ID查询分析报告
     */
    public AnalysisReport findById(Long id) {
        String sql = "SELECT * FROM analysis_reports WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, id);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return mapResultSetToReport(rs);
                }
            }
        } catch (SQLException e) {
            logger.error("查询分析报告失败", e);
            throw new RuntimeException("查询分析报告失败", e);
        }
        return null;
    }

    /**
     * 查询用户的分析报告列表
     */
    public List<AnalysisReport> findByUserId(Long userId) {
        String sql = "SELECT * FROM analysis_reports WHERE created_by=? ORDER BY create_time DESC";
        List<AnalysisReport> reports = new ArrayList<>();
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, userId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    reports.add(mapResultSetToReport(rs));
                }
            }
        } catch (SQLException e) {
            logger.error("查询用户分析报告列表失败", e);
            throw new RuntimeException("查询用户分析报告列表失败", e);
        }
        return reports;
    }

    /**
     * 查询所有分析报告
     */
    public List<AnalysisReport> findAll() {
        String sql = "SELECT * FROM analysis_reports ORDER BY create_time DESC";
        List<AnalysisReport> reports = new ArrayList<>();
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql);
             ResultSet rs = ps.executeQuery()) {
            
            while (rs.next()) {
                reports.add(mapResultSetToReport(rs));
            }
        } catch (SQLException e) {
            logger.error("查询分析报告列表失败", e);
            throw new RuntimeException("查询分析报告列表失败", e);
        }
        return reports;
    }

    /**
     * 删除分析报告
     */
    public boolean delete(Long id) {
        String sql = "DELETE FROM analysis_reports WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, id);
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            logger.error("删除分析报告失败", e);
            throw new RuntimeException("删除分析报告失败", e);
        }
    }

    /**
     * ResultSet映射到AnalysisReport对象
     */
    private AnalysisReport mapResultSetToReport(ResultSet rs) throws SQLException {
        AnalysisReport report = new AnalysisReport();
        report.setId(rs.getLong("id"));
        report.setTitle(rs.getString("title"));
        report.setReportType(rs.getString("report_type"));
        report.setJournalId(rs.getObject("journal_id") != null ? rs.getLong("journal_id") : null);
        report.setJournalIds(rs.getString("journal_ids"));
        report.setContent(rs.getString("content"));
        report.setCreatedBy(rs.getObject("created_by") != null ? rs.getLong("created_by") : null);
        
        Timestamp createTime = rs.getTimestamp("create_time");
        if (createTime != null) {
            report.setCreateTime(createTime.toLocalDateTime());
        }
        
        Timestamp updateTime = rs.getTimestamp("update_time");
        if (updateTime != null) {
            report.setUpdateTime(updateTime.toLocalDateTime());
        }
        
        return report;
    }
}
