package com.paper.repository;

import java.util.List;
import java.util.Optional;

import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.data.jpa.repository.JpaRepository;
import org.springframework.data.jpa.repository.Query;
import org.springframework.data.repository.query.Param;
import org.springframework.stereotype.Repository;

import com.paper.model.JournalMetrics;

/**
 * 期刊指标Repository - 使用JPA进行数据访问
 * 安全、高效，避免SQL注入风险
 */
@Repository
public interface JournalMetricsRepository extends JpaRepository<JournalMetrics, Long> {
    
    /**
     * 查询所有期刊的最新年份数据
     */
    @Query("""
        SELECT j FROM JournalMetrics j
        WHERE j.year = (
            SELECT MAX(j2.year) FROM JournalMetrics j2
            WHERE j2.journal = j.journal
        )
        ORDER BY j.journal
        """)
    List<JournalMetrics> findAllLatestYears();
    
    /**
     * 根据期刊名称查询所有年份数据
     */
    List<JournalMetrics> findByJournalOrderByYearDesc(String journal);
    
    /**
     * 查询所有不同的期刊名称
     */
    @Query("SELECT DISTINCT j.journal FROM JournalMetrics j ORDER BY j.journal")
    List<String> findAllJournalNames();
    
    /**
     * 查询指定期刊的最新年份数据
     */
    @Query("""
        SELECT j FROM JournalMetrics j
        WHERE j.journal = :journal
        AND j.year = (
            SELECT MAX(j2.year) FROM JournalMetrics j2
            WHERE j2.journal = :journal
        )
        """)
    Optional<JournalMetrics> findLatestByJournal(@Param("journal") String journal);
    
    /**
     * 查询两个期刊的最新年份数据
     */
    @Query("""
        SELECT j FROM JournalMetrics j
        WHERE j.journal IN (:journal1, :journal2)
        AND j.year = (
            SELECT MAX(j2.year) FROM JournalMetrics j2
            WHERE j2.journal = j.journal
        )
        """)
    List<JournalMetrics> findLatestByTwoJournals(
        @Param("journal1") String journal1,
        @Param("journal2") String journal2
    );
    
    /**
     * 检查期刊是否存在
     */
    boolean existsByJournal(String journal);
    
    /**
     * 统计总期刊数量
     */
    @Query("SELECT COUNT(DISTINCT j.journal) FROM JournalMetrics j")
    long countDistinctJournals();

        /**
         * 查询所有年份（降序）
         */
        @Query("SELECT DISTINCT j.year FROM JournalMetrics j ORDER BY j.year DESC")
        List<Integer> findDistinctYearsDesc();

        /**
         * 查询所有学科/类别（升序；SQLite 下常见为空字符串）
         */
        @Query("SELECT DISTINCT COALESCE(j.category, '') FROM JournalMetrics j ORDER BY COALESCE(j.category, '')")
        List<String> findDistinctCategories();

        /**
         * 指定年份的期刊排名（支持按指标排序、按类别/关键词过滤、分页）。
         *
         * 注意：指标参数 metric 通过 CASE 分支白名单控制，避免 SQL 注入。
         */
        @Query(
                value = """
                        SELECT j.*
                        FROM journal_metrics j
                        WHERE j.year = :year
                            AND (:category IS NULL OR COALESCE(j.category, '') = :category)
                            AND (:q IS NULL OR :q = '' OR LOWER(j.journal) LIKE '%' || LOWER(:q) || '%')
                        ORDER BY
                            CASE
                                WHEN :metric = 'frontier' THEN COALESCE(j.disruption, 0) + COALESCE(j.novelty, 0)
                                WHEN :metric = 'disruption' THEN COALESCE(j.disruption, -1.0e18)
                                WHEN :metric = 'novelty' THEN COALESCE(j.novelty, -1.0e18)
                                WHEN :metric = 'interdisciplinary' THEN COALESCE(j.interdisciplinary, -1.0e18)
                                WHEN :metric = 'topic' THEN COALESCE(j.topic, -1.0e18)
                                WHEN :metric = 'theme_concentration' THEN COALESCE(j.theme_concentration, -1.0e18)
                                WHEN :metric = 'hot_response' THEN COALESCE(j.hot_response, -1.0e18)
                                WHEN :metric = 'paper_count' THEN COALESCE(j.paper_count, -1.0e18)
                                ELSE COALESCE(j.disruption, 0) + COALESCE(j.novelty, 0)
                            END DESC,
                            j.journal ASC
                        """,
                countQuery = """
                        SELECT COUNT(*)
                        FROM journal_metrics j
                        WHERE j.year = :year
                            AND (:category IS NULL OR COALESCE(j.category, '') = :category)
                            AND (:q IS NULL OR :q = '' OR LOWER(j.journal) LIKE '%' || LOWER(:q) || '%')
                        """,
                nativeQuery = true
        )
        Page<JournalMetrics> findYearRankings(
                @Param("metric") String metric,
                @Param("year") int year,
                @Param("category") String category,
                @Param("q") String q,
                Pageable pageable
        );

        /**
         * 最新年份（每本期刊取自身最新一年）的期刊排名（支持按指标排序、按类别/关键词过滤、分页）。
         */
        @Query(
                value = """
                        SELECT j.*
                        FROM journal_metrics j
                        WHERE j.year = (
                                SELECT MAX(j2.year)
                                FROM journal_metrics j2
                                WHERE j2.journal = j.journal
                        )
                            AND (:category IS NULL OR COALESCE(j.category, '') = :category)
                            AND (:q IS NULL OR :q = '' OR LOWER(j.journal) LIKE '%' || LOWER(:q) || '%')
                        ORDER BY
                            CASE
                                WHEN :metric = 'frontier' THEN COALESCE(j.disruption, 0) + COALESCE(j.novelty, 0)
                                WHEN :metric = 'disruption' THEN COALESCE(j.disruption, -1.0e18)
                                WHEN :metric = 'novelty' THEN COALESCE(j.novelty, -1.0e18)
                                WHEN :metric = 'interdisciplinary' THEN COALESCE(j.interdisciplinary, -1.0e18)
                                WHEN :metric = 'topic' THEN COALESCE(j.topic, -1.0e18)
                                WHEN :metric = 'theme_concentration' THEN COALESCE(j.theme_concentration, -1.0e18)
                                WHEN :metric = 'hot_response' THEN COALESCE(j.hot_response, -1.0e18)
                                WHEN :metric = 'paper_count' THEN COALESCE(j.paper_count, -1.0e18)
                                ELSE COALESCE(j.disruption, 0) + COALESCE(j.novelty, 0)
                            END DESC,
                            j.journal ASC
                        """,
                countQuery = """
                        SELECT COUNT(*)
                        FROM journal_metrics j
                        WHERE j.year = (
                                SELECT MAX(j2.year)
                                FROM journal_metrics j2
                                WHERE j2.journal = j.journal
                        )
                            AND (:category IS NULL OR COALESCE(j.category, '') = :category)
                            AND (:q IS NULL OR :q = '' OR LOWER(j.journal) LIKE '%' || LOWER(:q) || '%')
                        """,
                nativeQuery = true
        )
        Page<JournalMetrics> findLatestRankings(
                @Param("metric") String metric,
                @Param("category") String category,
                @Param("q") String q,
                Pageable pageable
        );
}
