package com.paper.model;

import jakarta.persistence.Column;
import jakarta.persistence.Entity;
import jakarta.persistence.GeneratedValue;
import jakarta.persistence.GenerationType;
import jakarta.persistence.Id;
import jakarta.persistence.Index;
import jakarta.persistence.Table;

/**
 * 期刊指标实体类
 */
@Entity
@Table(name = "journal_metrics", indexes = {
    @Index(name = "idx_journal", columnList = "journal"),
    @Index(name = "idx_year", columnList = "year")
})
public class JournalMetrics implements JournalMetricsLike {
    
    @Id
    @GeneratedValue(strategy = GenerationType.IDENTITY)
    private Long id;
    
    @Column(nullable = false)
    private String journal;              // 期刊名称
    
    @Column(nullable = false)
    private Integer year;                // 年份
    
    private Double disruption;           // 颠覆性
    private Double interdisciplinary;    // 跨学科性
    private Double novelty;              // 新颖性
    private Double topic;                // 主题多样性
    
    @Column(name = "theme_concentration")
    private Double themeConcentration;   // 主题集中度
    
    @Column(name = "hot_response")
    private Double hotResponse;          // 热点响应度
    
    @Column(name = "paper_count")
    private Integer paperCount;          // 论文数量
    
    private String category;             // 学科/类别
    
    @Column(name = "top_keywords_2021", columnDefinition = "TEXT")
    private String topKeywords2021;      // 2021年热门关键词
    
    @Column(name = "top_keywords_2022", columnDefinition = "TEXT")
    private String topKeywords2022;      // 2022年热门关键词
    
    @Column(name = "top_keywords_2023", columnDefinition = "TEXT")
    private String topKeywords2023;      // 2023年热门关键词
    
    @Column(name = "top_keywords_2024", columnDefinition = "TEXT")
    private String topKeywords2024;      // 2024年热门关键词
    
    @Column(name = "top_keywords_2025", columnDefinition = "TEXT")
    private String topKeywords2025;      // 2025年热门关键词

    // 默认构造函数
    public JournalMetrics() {
    }

    // 完整构造函数
    public JournalMetrics(String journal, Integer year, Double disruption, Double interdisciplinary,
                          Double novelty, Double topic, Double themeConcentration, Double hotResponse,
                          Integer paperCount, String category) {
        this.journal = journal;
        this.year = year;
        this.disruption = disruption;
        this.interdisciplinary = interdisciplinary;
        this.novelty = novelty;
        this.topic = topic;
        this.themeConcentration = themeConcentration;
        this.hotResponse = hotResponse;
        this.paperCount = paperCount;
        this.category = category;
    }

    // Getters and Setters
    public Long getId() {
        return id;
    }
    
    public void setId(Long id) {
        this.id = id;
    }
    
    public String getJournal() {
        return journal;
    }

    public void setJournal(String journal) {
        this.journal = journal;
    }

    public Integer getYear() {
        return year;
    }

    public void setYear(Integer year) {
        this.year = year;
    }

    public Double getDisruption() {
        return disruption;
    }

    public void setDisruption(Double disruption) {
        this.disruption = disruption;
    }

    public Double getInterdisciplinary() {
        return interdisciplinary;
    }

    public void setInterdisciplinary(Double interdisciplinary) {
        this.interdisciplinary = interdisciplinary;
    }

    public Double getNovelty() {
        return novelty;
    }

    public void setNovelty(Double novelty) {
        this.novelty = novelty;
    }

    public Double getTopic() {
        return topic;
    }

    public void setTopic(Double topic) {
        this.topic = topic;
    }

    public Double getThemeConcentration() {
        return themeConcentration;
    }

    public void setThemeConcentration(Double themeConcentration) {
        this.themeConcentration = themeConcentration;
    }

    public Double getHotResponse() {
        return hotResponse;
    }

    public void setHotResponse(Double hotResponse) {
        this.hotResponse = hotResponse;
    }

    public Integer getPaperCount() {
        return paperCount;
    }

    public void setPaperCount(Integer paperCount) {
        this.paperCount = paperCount;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getTopKeywords2021() {
        return topKeywords2021;
    }

    public void setTopKeywords2021(String topKeywords2021) {
        this.topKeywords2021 = topKeywords2021;
    }

    public String getTopKeywords2022() {
        return topKeywords2022;
    }

    public void setTopKeywords2022(String topKeywords2022) {
        this.topKeywords2022 = topKeywords2022;
    }

    public String getTopKeywords2023() {
        return topKeywords2023;
    }

    public void setTopKeywords2023(String topKeywords2023) {
        this.topKeywords2023 = topKeywords2023;
    }

    public String getTopKeywords2024() {
        return topKeywords2024;
    }

    public void setTopKeywords2024(String topKeywords2024) {
        this.topKeywords2024 = topKeywords2024;
    }

    public String getTopKeywords2025() {
        return topKeywords2025;
    }

    public void setTopKeywords2025(String topKeywords2025) {
        this.topKeywords2025 = topKeywords2025;
    }

    @Override
    public String toString() {
        return "JournalMetrics{" +
                "journal='" + journal + '\'' +
                ", year=" + year +
                ", disruption=" + disruption +
                ", interdisciplinary=" + interdisciplinary +
                ", novelty=" + novelty +
                ", topic=" + topic +
                ", themeConcentration=" + themeConcentration +
                ", hotResponse=" + hotResponse +
                ", paperCount=" + paperCount +
                ", category='" + category + '\'' +
                '}';
    }
}
