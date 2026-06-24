package com.paper.model;

/**
 * 期刊指标的“只读视图”接口。
 *
 * 用途：
 * - 让 JPA Entity（journal_metrics）与用户数据集明细表（user_journal_metrics）的 DTO
 *   共享同一套 getter 形状，避免 DAO 返回 Entity 造成语义混淆。
 */
public interface JournalMetricsLike {

    Long getId();

    String getJournal();

    Integer getYear();

    Double getDisruption();

    Double getInterdisciplinary();

    Double getNovelty();

    Double getTopic();

    Double getThemeConcentration();

    Double getHotResponse();

    Integer getPaperCount();

    String getCategory();

    String getTopKeywords2021();

    String getTopKeywords2022();

    String getTopKeywords2023();

    String getTopKeywords2024();

    String getTopKeywords2025();
}
