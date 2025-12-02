package com.journal.entity;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 期刊实体类
 */
public class Journal implements Serializable {
    private static final long serialVersionUID = 1L;

    private Long id;
    private String name;                // 期刊名称
    private String issn;                // ISSN号
    private String publisher;           // 出版商
    private String country;             // 国家/地区
    private String language;            // 语言
    private String category;            // 学科分类
    private Double impactFactor;        // 影响因子
    private String frequency;           // 出版频率
    private String description;         // 期刊描述
    private String officialUrl;         // 官方网站
    private LocalDateTime createTime;   // 创建时间
    private LocalDateTime updateTime;   // 更新时间

    public Journal() {
    }

    public Journal(String name, String issn) {
        this.name = name;
        this.issn = issn;
    }

    // Getters and Setters
    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getName() {
        return name;
    }

    public void setName(String name) {
        this.name = name;
    }

    public String getIssn() {
        return issn;
    }

    public void setIssn(String issn) {
        this.issn = issn;
    }

    public String getPublisher() {
        return publisher;
    }

    public void setPublisher(String publisher) {
        this.publisher = publisher;
    }

    public String getCountry() {
        return country;
    }

    public void setCountry(String country) {
        this.country = country;
    }

    public String getLanguage() {
        return language;
    }

    public void setLanguage(String language) {
        this.language = language;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public Double getImpactFactor() {
        return impactFactor;
    }

    public void setImpactFactor(Double impactFactor) {
        this.impactFactor = impactFactor;
    }

    public String getFrequency() {
        return frequency;
    }

    public void setFrequency(String frequency) {
        this.frequency = frequency;
    }

    public String getDescription() {
        return description;
    }

    public void setDescription(String description) {
        this.description = description;
    }

    public String getOfficialUrl() {
        return officialUrl;
    }

    public void setOfficialUrl(String officialUrl) {
        this.officialUrl = officialUrl;
    }

    public LocalDateTime getCreateTime() {
        return createTime;
    }

    public void setCreateTime(LocalDateTime createTime) {
        this.createTime = createTime;
    }

    public LocalDateTime getUpdateTime() {
        return updateTime;
    }

    public void setUpdateTime(LocalDateTime updateTime) {
        this.updateTime = updateTime;
    }

    @Override
    public String toString() {
        return "Journal{" +
                "id=" + id +
                ", name='" + name + '\'' +
                ", issn='" + issn + '\'' +
                ", publisher='" + publisher + '\'' +
                ", country='" + country + '\'' +
                ", impactFactor=" + impactFactor +
                '}';
    }
}
