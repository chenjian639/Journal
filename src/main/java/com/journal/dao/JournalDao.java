package com.journal.dao;

import com.journal.entity.Journal;
import com.journal.util.DBUtil;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.*;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 期刊数据访问层
 */
public class JournalDao {
    private static final Logger logger = LoggerFactory.getLogger(JournalDao.class);

    /**
     * 添加期刊
     */
    public Long insert(Journal journal) {
        String sql = "INSERT INTO journals (name, issn, publisher, country, language, category, " +
                "impact_factor, frequency, description, official_url, create_time, update_time) " +
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {
            
            LocalDateTime now = LocalDateTime.now();
            ps.setString(1, journal.getName());
            ps.setString(2, journal.getIssn());
            ps.setString(3, journal.getPublisher());
            ps.setString(4, journal.getCountry());
            ps.setString(5, journal.getLanguage());
            ps.setString(6, journal.getCategory());
            ps.setObject(7, journal.getImpactFactor());
            ps.setString(8, journal.getFrequency());
            ps.setString(9, journal.getDescription());
            ps.setString(10, journal.getOfficialUrl());
            ps.setTimestamp(11, Timestamp.valueOf(now));
            ps.setTimestamp(12, Timestamp.valueOf(now));
            
            ps.executeUpdate();
            
            try (ResultSet rs = ps.getGeneratedKeys()) {
                if (rs.next()) {
                    return rs.getLong(1);
                }
            }
        } catch (SQLException e) {
            logger.error("添加期刊失败", e);
            throw new RuntimeException("添加期刊失败", e);
        }
        return null;
    }

    /**
     * 更新期刊
     */
    public boolean update(Journal journal) {
        String sql = "UPDATE journals SET name=?, issn=?, publisher=?, country=?, language=?, " +
                "category=?, impact_factor=?, frequency=?, description=?, official_url=?, update_time=? " +
                "WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setString(1, journal.getName());
            ps.setString(2, journal.getIssn());
            ps.setString(3, journal.getPublisher());
            ps.setString(4, journal.getCountry());
            ps.setString(5, journal.getLanguage());
            ps.setString(6, journal.getCategory());
            ps.setObject(7, journal.getImpactFactor());
            ps.setString(8, journal.getFrequency());
            ps.setString(9, journal.getDescription());
            ps.setString(10, journal.getOfficialUrl());
            ps.setTimestamp(11, Timestamp.valueOf(LocalDateTime.now()));
            ps.setLong(12, journal.getId());
            
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            logger.error("更新期刊失败", e);
            throw new RuntimeException("更新期刊失败", e);
        }
    }

    /**
     * 删除期刊
     */
    public boolean delete(Long id) {
        String sql = "DELETE FROM journals WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, id);
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            logger.error("删除期刊失败", e);
            throw new RuntimeException("删除期刊失败", e);
        }
    }

    /**
     * 根据ID查询期刊
     */
    public Journal findById(Long id) {
        String sql = "SELECT * FROM journals WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, id);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return mapResultSetToJournal(rs);
                }
            }
        } catch (SQLException e) {
            logger.error("查询期刊失败", e);
            throw new RuntimeException("查询期刊失败", e);
        }
        return null;
    }

    /**
     * 查询所有期刊
     */
    public List<Journal> findAll() {
        String sql = "SELECT * FROM journals ORDER BY create_time DESC";
        List<Journal> journals = new ArrayList<>();
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql);
             ResultSet rs = ps.executeQuery()) {
            
            while (rs.next()) {
                journals.add(mapResultSetToJournal(rs));
            }
        } catch (SQLException e) {
            logger.error("查询期刊列表失败", e);
            throw new RuntimeException("查询期刊列表失败", e);
        }
        return journals;
    }

    /**
     * 分页查询期刊
     */
    public List<Journal> findByPage(int page, int pageSize) {
        String sql = "SELECT * FROM journals ORDER BY create_time DESC LIMIT ?, ?";
        List<Journal> journals = new ArrayList<>();
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setInt(1, (page - 1) * pageSize);
            ps.setInt(2, pageSize);
            
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    journals.add(mapResultSetToJournal(rs));
                }
            }
        } catch (SQLException e) {
            logger.error("分页查询期刊失败", e);
            throw new RuntimeException("分页查询期刊失败", e);
        }
        return journals;
    }

    /**
     * 根据条件搜索期刊
     */
    public List<Journal> search(String keyword, String country, String category) {
        StringBuilder sql = new StringBuilder("SELECT * FROM journals WHERE 1=1");
        List<Object> params = new ArrayList<>();
        
        if (keyword != null && !keyword.trim().isEmpty()) {
            sql.append(" AND (name LIKE ? OR issn LIKE ? OR publisher LIKE ?)");
            String likeKeyword = "%" + keyword.trim() + "%";
            params.add(likeKeyword);
            params.add(likeKeyword);
            params.add(likeKeyword);
        }
        if (country != null && !country.trim().isEmpty()) {
            sql.append(" AND country = ?");
            params.add(country);
        }
        if (category != null && !category.trim().isEmpty()) {
            sql.append(" AND category = ?");
            params.add(category);
        }
        
        sql.append(" ORDER BY impact_factor DESC");
        
        List<Journal> journals = new ArrayList<>();
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql.toString())) {
            
            for (int i = 0; i < params.size(); i++) {
                ps.setObject(i + 1, params.get(i));
            }
            
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    journals.add(mapResultSetToJournal(rs));
                }
            }
        } catch (SQLException e) {
            logger.error("搜索期刊失败", e);
            throw new RuntimeException("搜索期刊失败", e);
        }
        return journals;
    }

    /**
     * 统计期刊总数
     */
    public int count() {
        String sql = "SELECT COUNT(*) FROM journals";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql);
             ResultSet rs = ps.executeQuery()) {
            
            if (rs.next()) {
                return rs.getInt(1);
            }
        } catch (SQLException e) {
            logger.error("统计期刊数量失败", e);
            throw new RuntimeException("统计期刊数量失败", e);
        }
        return 0;
    }

    /**
     * 根据国家分组统计
     */
    public List<Object[]> countByCountry() {
        String sql = "SELECT country, COUNT(*) as cnt FROM journals GROUP BY country ORDER BY cnt DESC";
        List<Object[]> result = new ArrayList<>();
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql);
             ResultSet rs = ps.executeQuery()) {
            
            while (rs.next()) {
                result.add(new Object[]{rs.getString("country"), rs.getInt("cnt")});
            }
        } catch (SQLException e) {
            logger.error("按国家统计期刊失败", e);
            throw new RuntimeException("按国家统计期刊失败", e);
        }
        return result;
    }

    /**
     * ResultSet映射到Journal对象
     */
    private Journal mapResultSetToJournal(ResultSet rs) throws SQLException {
        Journal journal = new Journal();
        journal.setId(rs.getLong("id"));
        journal.setName(rs.getString("name"));
        journal.setIssn(rs.getString("issn"));
        journal.setPublisher(rs.getString("publisher"));
        journal.setCountry(rs.getString("country"));
        journal.setLanguage(rs.getString("language"));
        journal.setCategory(rs.getString("category"));
        journal.setImpactFactor(rs.getObject("impact_factor") != null ? rs.getDouble("impact_factor") : null);
        journal.setFrequency(rs.getString("frequency"));
        journal.setDescription(rs.getString("description"));
        journal.setOfficialUrl(rs.getString("official_url"));
        
        Timestamp createTime = rs.getTimestamp("create_time");
        if (createTime != null) {
            journal.setCreateTime(createTime.toLocalDateTime());
        }
        
        Timestamp updateTime = rs.getTimestamp("update_time");
        if (updateTime != null) {
            journal.setUpdateTime(updateTime.toLocalDateTime());
        }
        
        return journal;
    }
}
