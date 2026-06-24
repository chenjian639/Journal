package com.paper.model;

import java.util.List;

/**
 * 用户问卷调查实体类
 */
public class UserSurvey {
    private String keywordsRaw;          // 原始关键词字符串
    private List<String> keywords;       // 关键词列表
    private Double novelty;              // 新颖性偏好
    private Double disruption;           // 颠覆性偏好
    private Double interdisciplinary;    // 跨学科性偏好
    private Double themeConcentration;   // 主题集中度偏好
    private Double topic;                // 主题多样性偏好
    private Double hotResponse;          // 热点响应度偏好
    private String createdAt;            // 创建时间

    public UserSurvey() {
    }

    public UserSurvey(List<String> keywords, Double novelty, Double disruption, Double interdisciplinary,
                      Double themeConcentration, Double topic, Double hotResponse) {
        this.keywords = keywords;
        this.novelty = novelty;
        this.disruption = disruption;
        this.interdisciplinary = interdisciplinary;
        this.themeConcentration = themeConcentration;
        this.topic = topic;
        this.hotResponse = hotResponse;
    }

    // Getters and Setters
    public String getKeywordsRaw() {
        return keywordsRaw;
    }

    public void setKeywordsRaw(String keywordsRaw) {
        this.keywordsRaw = keywordsRaw;
    }

    public List<String> getKeywords() {
        return keywords;
    }

    public void setKeywords(List<String> keywords) {
        this.keywords = keywords;
    }

    public Double getNovelty() {
        return novelty;
    }

    public void setNovelty(Double novelty) {
        this.novelty = novelty;
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

    public Double getThemeConcentration() {
        return themeConcentration;
    }

    public void setThemeConcentration(Double themeConcentration) {
        this.themeConcentration = themeConcentration;
    }

    public Double getTopic() {
        return topic;
    }

    public void setTopic(Double topic) {
        this.topic = topic;
    }

    public Double getHotResponse() {
        return hotResponse;
    }

    public void setHotResponse(Double hotResponse) {
        this.hotResponse = hotResponse;
    }

    public String getCreatedAt() {
        return createdAt;
    }

    public void setCreatedAt(String createdAt) {
        this.createdAt = createdAt;
    }

    @Override
    public String toString() {
        return "UserSurvey{" +
                "keywords=" + keywords +
                ", novelty=" + novelty +
                ", disruption=" + disruption +
                ", interdisciplinary=" + interdisciplinary +
                ", themeConcentration=" + themeConcentration +
                ", topic=" + topic +
                ", hotResponse=" + hotResponse +
                ", createdAt='" + createdAt + '\'' +
                '}';
    }
}
