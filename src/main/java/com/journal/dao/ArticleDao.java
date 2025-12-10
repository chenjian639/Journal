package com.journal.dao;

import com.journal.entity.Article;
import com.journal.util.DBUtil;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.sql.*;
import java.time.LocalDateTime;
import java.util.ArrayList;
import java.util.List;

/**
 * 论文数据访问层
 */
public class ArticleDao {
    private static final Logger logger = LoggerFactory.getLogger(ArticleDao.class);

    /**
     * 添加论文
     */
    public Long insert(Article article) {
        String sql = "INSERT INTO articles (journal_id, title, authors, abstract_text, keywords, " +
                "doi, publish_date, volume, issue, pages, citation_count, create_time, update_time) " +
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql, Statement.RETURN_GENERATED_KEYS)) {
            
            LocalDateTime now = LocalDateTime.now();
            ps.setLong(1, article.getJournalId());
            ps.setString(2, article.getTitle());
            ps.setString(3, article.getAuthors());
            ps.setString(4, article.getAbstractText());
            ps.setString(5, article.getKeywords());
            ps.setString(6, article.getDoi());
            ps.setObject(7, article.getPublishDate());
            ps.setObject(8, article.getVolume());
            ps.setObject(9, article.getIssue());
            ps.setString(10, article.getPages());
            ps.setObject(11, article.getCitationCount());
            ps.setTimestamp(12, Timestamp.valueOf(now));
            ps.setTimestamp(13, Timestamp.valueOf(now));
            
            ps.executeUpdate();
            
            try (ResultSet rs = ps.getGeneratedKeys()) {
                if (rs.next()) {
                    return rs.getLong(1);
                }
            }
        } catch (SQLException e) {
            logger.error("添加论文失败", e);
            throw new RuntimeException("添加论文失败", e);
        }
        return null;
    }

    /**
     * 根据ID查询论文
     */
    public Article findById(Long id) {
        String sql = "SELECT * FROM articles WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, id);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return mapResultSetToArticle(rs);
                }
            }
        } catch (SQLException e) {
            logger.error("查询论文失败", e);
            throw new RuntimeException("查询论文失败", e);
        }
        return null;
    }

    /**
     * 根据期刊ID查询论文列表
     */
    public List<Article> findByJournalId(Long journalId) {
        String sql = "SELECT * FROM articles WHERE journal_id=? ORDER BY publish_date DESC";
        List<Article> articles = new ArrayList<>();
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, journalId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    articles.add(mapResultSetToArticle(rs));
                }
            }
        } catch (SQLException e) {
            logger.error("查询期刊论文列表失败", e);
            throw new RuntimeException("查询期刊论文列表失败", e);
        }
        return articles;
    }

    /**
     * 搜索论文
     */
    public List<Article> search(String keyword) {
        String sql = "SELECT * FROM articles WHERE title LIKE ? OR authors LIKE ? OR keywords LIKE ? " +
                "ORDER BY publish_date DESC LIMIT 100";
        List<Article> articles = new ArrayList<>();
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            String likeKeyword = "%" + keyword + "%";
            ps.setString(1, likeKeyword);
            ps.setString(2, likeKeyword);
            ps.setString(3, likeKeyword);
            
            try (ResultSet rs = ps.executeQuery()) {
                while (rs.next()) {
                    articles.add(mapResultSetToArticle(rs));
                }
            }
        } catch (SQLException e) {
            logger.error("搜索论文失败", e);
            throw new RuntimeException("搜索论文失败", e);
        }
        return articles;
    }

    /**
     * 统计期刊论文数量
     */
    public int countByJournalId(Long journalId) {
        String sql = "SELECT COUNT(*) FROM articles WHERE journal_id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, journalId);
            try (ResultSet rs = ps.executeQuery()) {
                if (rs.next()) {
                    return rs.getInt(1);
                }
            }
        } catch (SQLException e) {
            logger.error("统计期刊论文数量失败", e);
            throw new RuntimeException("统计期刊论文数量失败", e);
        }
        return 0;
    }

    /**
     * 删除论文
     */
    public boolean delete(Long id) {
        String sql = "DELETE FROM articles WHERE id=?";
        
        try (Connection conn = DBUtil.getConnection();
             PreparedStatement ps = conn.prepareStatement(sql)) {
            
            ps.setLong(1, id);
            return ps.executeUpdate() > 0;
        } catch (SQLException e) {
            logger.error("删除论文失败", e);
            throw new RuntimeException("删除论文失败", e);
        }
    }

    /**
     * ResultSet映射到Article对象
     */
    private Article mapResultSetToArticle(ResultSet rs) throws SQLException {
        Article article = new Article();
        article.setId(rs.getLong("id"));
        article.setJournalId(rs.getLong("journal_id"));
        article.setTitle(rs.getString("title"));
        article.setAuthors(rs.getString("authors"));
        article.setAbstractText(rs.getString("abstract_text"));
        article.setKeywords(rs.getString("keywords"));
        article.setDoi(rs.getString("doi"));
        
        Date publishDate = rs.getDate("publish_date");
        if (publishDate != null) {
            article.setPublishDate(publishDate.toLocalDate());
        }
        
        article.setVolume(rs.getObject("volume") != null ? rs.getInt("volume") : null);
        article.setIssue(rs.getObject("issue") != null ? rs.getInt("issue") : null);
        article.setPages(rs.getString("pages"));
        article.setCitationCount(rs.getObject("citation_count") != null ? rs.getInt("citation_count") : null);
        
        Timestamp createTime = rs.getTimestamp("create_time");
        if (createTime != null) {
            article.setCreateTime(createTime.toLocalDateTime());
        }
        
        Timestamp updateTime = rs.getTimestamp("update_time");
        if (updateTime != null) {
            article.setUpdateTime(updateTime.toLocalDateTime());
        }
        
        return article;
    }
}
