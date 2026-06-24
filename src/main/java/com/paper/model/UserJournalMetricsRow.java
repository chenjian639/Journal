package com.paper.model;

/**
 * user_journal_metrics 表的查询结果 DTO。
 *
 * 注意：
 * - 这不是 JPA Entity，不参与持久化。
 * - 通过实现 JournalMetricsLike 来复用现有详情页/AI 分析等逻辑（只依赖 getters）。
 */
public class UserJournalMetricsRow implements JournalMetricsLike {

    private Long id;
    private String journal;
    private Integer year;

    private Double disruption;
    private Double interdisciplinary;
    private Double novelty;
    private Double topic;
    private Double themeConcentration;
    private Double hotResponse;

    private Integer paperCount;
    private String category;

    private String topKeywords2021;
    private String topKeywords2022;
    private String topKeywords2023;
    private String topKeywords2024;
    private String topKeywords2025;

    @Override
    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    @Override
    public String getJournal() {
        return journal;
    }

    public void setJournal(String journal) {
        this.journal = journal;
    }

    @Override
    public Integer getYear() {
        return year;
    }

    public void setYear(Integer year) {
        this.year = year;
    }

    @Override
    public Double getDisruption() {
        return disruption;
    }

    public void setDisruption(Double disruption) {
        this.disruption = disruption;
    }

    @Override
    public Double getInterdisciplinary() {
        return interdisciplinary;
    }

    public void setInterdisciplinary(Double interdisciplinary) {
        this.interdisciplinary = interdisciplinary;
    }

    @Override
    public Double getNovelty() {
        return novelty;
    }

    public void setNovelty(Double novelty) {
        this.novelty = novelty;
    }

    @Override
    public Double getTopic() {
        return topic;
    }

    public void setTopic(Double topic) {
        this.topic = topic;
    }

    @Override
    public Double getThemeConcentration() {
        return themeConcentration;
    }

    public void setThemeConcentration(Double themeConcentration) {
        this.themeConcentration = themeConcentration;
    }

    @Override
    public Double getHotResponse() {
        return hotResponse;
    }

    public void setHotResponse(Double hotResponse) {
        this.hotResponse = hotResponse;
    }

    @Override
    public Integer getPaperCount() {
        return paperCount;
    }

    public void setPaperCount(Integer paperCount) {
        this.paperCount = paperCount;
    }

    @Override
    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    @Override
    public String getTopKeywords2021() {
        return topKeywords2021;
    }

    public void setTopKeywords2021(String topKeywords2021) {
        this.topKeywords2021 = topKeywords2021;
    }

    @Override
    public String getTopKeywords2022() {
        return topKeywords2022;
    }

    public void setTopKeywords2022(String topKeywords2022) {
        this.topKeywords2022 = topKeywords2022;
    }

    @Override
    public String getTopKeywords2023() {
        return topKeywords2023;
    }

    public void setTopKeywords2023(String topKeywords2023) {
        this.topKeywords2023 = topKeywords2023;
    }

    @Override
    public String getTopKeywords2024() {
        return topKeywords2024;
    }

    public void setTopKeywords2024(String topKeywords2024) {
        this.topKeywords2024 = topKeywords2024;
    }

    @Override
    public String getTopKeywords2025() {
        return topKeywords2025;
    }

    public void setTopKeywords2025(String topKeywords2025) {
        this.topKeywords2025 = topKeywords2025;
    }
}
