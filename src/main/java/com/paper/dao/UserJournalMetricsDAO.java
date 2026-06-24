package com.paper.dao;

import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.List;

import javax.sql.DataSource;

import org.springframework.stereotype.Repository;

import com.paper.model.JournalMetricsLike;
import com.paper.model.UserJournalMetricsRow;

/**
 * 用户上传数据集的期刊指标明细（用于复用既有期刊详情页）。
 *
 * 设计目标：
 * - 以 analysis_record.id 作为数据集主键（analysis_id），把每个期刊的“详情页所需字段”落库
 * - 不污染总库 journal_metrics
 */
@Repository
public class UserJournalMetricsDAO {

    private final DataSource dataSource;

    public UserJournalMetricsDAO(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    public boolean hasAnyForAnalysis(long analysisId) {
        String sql = "SELECT 1 FROM user_journal_metrics WHERE analysis_id = ? LIMIT 1";
        try (var conn = dataSource.getConnection(); PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, analysisId);
            try (ResultSet rs = ps.executeQuery()) {
                return rs != null && rs.next();
            }
        } catch (SQLException e) {
            return false;
        }
    }

    public void upsertAll(long analysisId, String username, List<? extends JournalMetricsLike> rows) throws SQLException {
        if (rows == null || rows.isEmpty()) {
            return;
        }

        try (var conn = dataSource.getConnection()) {
            boolean isSQLite = isSQLite(conn.getMetaData().getDatabaseProductName());

            String sql;
            if (isSQLite) {
                sql = """
                INSERT INTO user_journal_metrics (
                    analysis_id, username, journal, year,
                    disruption, interdisciplinary, novelty, topic, theme_concentration, hot_response,
                    top_keywords_2021, top_keywords_2022, top_keywords_2023, top_keywords_2024, top_keywords_2025,
                    paper_count, category
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON CONFLICT(analysis_id, journal, year) DO UPDATE SET
                    username = excluded.username,
                    disruption = excluded.disruption,
                    interdisciplinary = excluded.interdisciplinary,
                    novelty = excluded.novelty,
                    topic = excluded.topic,
                    theme_concentration = excluded.theme_concentration,
                    hot_response = excluded.hot_response,
                    top_keywords_2021 = excluded.top_keywords_2021,
                    top_keywords_2022 = excluded.top_keywords_2022,
                    top_keywords_2023 = excluded.top_keywords_2023,
                    top_keywords_2024 = excluded.top_keywords_2024,
                    top_keywords_2025 = excluded.top_keywords_2025,
                    paper_count = excluded.paper_count,
                    category = excluded.category
            """;
            } else {
                sql = """
                INSERT INTO user_journal_metrics (
                    analysis_id, username, journal, year,
                    disruption, interdisciplinary, novelty, topic, theme_concentration, hot_response,
                    top_keywords_2021, top_keywords_2022, top_keywords_2023, top_keywords_2024, top_keywords_2025,
                    paper_count, category
                ) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                ON DUPLICATE KEY UPDATE
                    username = VALUES(username),
                    disruption = VALUES(disruption),
                    interdisciplinary = VALUES(interdisciplinary),
                    novelty = VALUES(novelty),
                    topic = VALUES(topic),
                    theme_concentration = VALUES(theme_concentration),
                    hot_response = VALUES(hot_response),
                    top_keywords_2021 = VALUES(top_keywords_2021),
                    top_keywords_2022 = VALUES(top_keywords_2022),
                    top_keywords_2023 = VALUES(top_keywords_2023),
                    top_keywords_2024 = VALUES(top_keywords_2024),
                    top_keywords_2025 = VALUES(top_keywords_2025),
                    paper_count = VALUES(paper_count),
                    category = VALUES(category)
            """;
            }

            boolean prevAutoCommit = conn.getAutoCommit();
            conn.setAutoCommit(false);

            try (PreparedStatement ps = conn.prepareStatement(sql)) {
                int i = 0;
                for (JournalMetricsLike row : rows) {
                    ps.setLong(1, analysisId);
                    ps.setString(2, username);
                    ps.setString(3, row.getJournal());
                    ps.setObject(4, row.getYear());

                    ps.setObject(5, row.getDisruption());
                    ps.setObject(6, row.getInterdisciplinary());
                    ps.setObject(7, row.getNovelty());
                    ps.setObject(8, row.getTopic());
                    ps.setObject(9, row.getThemeConcentration());
                    ps.setObject(10, row.getHotResponse());

                    ps.setObject(11, row.getTopKeywords2021());
                    ps.setObject(12, row.getTopKeywords2022());
                    ps.setObject(13, row.getTopKeywords2023());
                    ps.setObject(14, row.getTopKeywords2024());
                    ps.setObject(15, row.getTopKeywords2025());

                    ps.setObject(16, row.getPaperCount());
                    ps.setObject(17, row.getCategory());

                    ps.addBatch();
                    i++;

                    if (i % 500 == 0) {
                        ps.executeBatch();
                    }
                }

                ps.executeBatch();
                conn.commit();
            } catch (SQLException e) {
                try {
                    conn.rollback();
                } catch (SQLException ignored) {
                }
                throw e;
            } finally {
                conn.setAutoCommit(prevAutoCommit);
            }
        }
    }

    public List<UserJournalMetricsRow> findByAnalysisAndJournalOrderByYearDesc(long analysisId, String journal) {
        String sql = """
            SELECT
                journal, year,
                disruption, interdisciplinary, novelty, topic, theme_concentration, hot_response,
                top_keywords_2021, top_keywords_2022, top_keywords_2023, top_keywords_2024, top_keywords_2025,
                paper_count, category
            FROM user_journal_metrics
            WHERE analysis_id = ? AND journal = ?
            ORDER BY year DESC
        """;

        List<UserJournalMetricsRow> rows = new ArrayList<>();
        try (var conn = dataSource.getConnection(); PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, analysisId);
            ps.setString(2, journal);

            try (ResultSet rs = ps.executeQuery()) {
                while (rs != null && rs.next()) {
                    UserJournalMetricsRow jm = new UserJournalMetricsRow();
                    jm.setId(0L);
                    jm.setJournal(rs.getString("journal"));
                    jm.setYear(rs.getInt("year"));

                    jm.setDisruption((Double) rs.getObject("disruption"));
                    jm.setInterdisciplinary((Double) rs.getObject("interdisciplinary"));
                    jm.setNovelty((Double) rs.getObject("novelty"));
                    jm.setTopic((Double) rs.getObject("topic"));
                    jm.setThemeConcentration((Double) rs.getObject("theme_concentration"));
                    jm.setHotResponse((Double) rs.getObject("hot_response"));

                    jm.setTopKeywords2021((String) rs.getObject("top_keywords_2021"));
                    jm.setTopKeywords2022((String) rs.getObject("top_keywords_2022"));
                    jm.setTopKeywords2023((String) rs.getObject("top_keywords_2023"));
                    jm.setTopKeywords2024((String) rs.getObject("top_keywords_2024"));
                    jm.setTopKeywords2025((String) rs.getObject("top_keywords_2025"));

                    Object pc = rs.getObject("paper_count");
                    jm.setPaperCount(pc == null ? null : ((Number) pc).intValue());
                    jm.setCategory((String) rs.getObject("category"));

                    rows.add(jm);
                }
            }
        } catch (SQLException e) {
            return List.of();
        }

        return rows;
    }

    public List<String> listJournalsByAnalysis(long analysisId) {
        String sql = "SELECT DISTINCT journal FROM user_journal_metrics WHERE analysis_id = ? ORDER BY journal";
        List<String> journals = new ArrayList<>();
        try (var conn = dataSource.getConnection(); PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setLong(1, analysisId);
            try (ResultSet rs = ps.executeQuery()) {
                while (rs != null && rs.next()) {
                    String j = rs.getString(1);
                    if (j != null && !j.isBlank()) {
                        journals.add(j);
                    }
                }
            }
        } catch (SQLException e) {
            return List.of();
        }
        return journals;
    }

    private static boolean isSQLite(String productName) {
        if (productName == null) return false;
        return productName.toLowerCase().contains("sqlite");
    }
}
