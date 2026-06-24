package com.paper.model;

import java.time.LocalDate;

/**
 * 论文实体类
 * 对应 papers 和 cleaned 表
 */
public class Paper {
    
    private Long id;
    private String doi;
    private String journal;
    private String keywords;
    private LocalDate publishDate;
    private String target;
    private String citations;      // 参考文献列表（TEXT）
    private String title;
    private String abstractText;
    private String category;
    private String citing;         // 引用该论文的文献列表
    
    // 以下为兼容旧代码的字段
    private String author;
    private String country;
    private int citationCount;     // 引用数量（整数）

    // Getter 和 Setter 方法

    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getDoi() {
        return doi;
    }

    public void setDoi(String doi) {
        this.doi = doi;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getAbstractText() {
        return abstractText;
    }

    public void setAbstractText(String abstractText) {
        this.abstractText = abstractText;
    }

    public LocalDate getPublishDate() {
        return publishDate;
    }

    public void setPublishDate(LocalDate publishDate) {
        this.publishDate = publishDate;
    }

    public String getJournal() {
        return journal;
    }

    public void setJournal(String journal) {
        this.journal = journal;
    }

    public String getKeywords() {
        return keywords;
    }

    public void setKeywords(String keywords) {
        this.keywords = keywords;
    }

    public String getTarget() {
        return target;
    }

    public void setTarget(String target) {
        this.target = target;
    }

    public String getCitations() {
        return citations;
    }

    public void setCitations(String citations) {
        this.citations = citations;
    }
    
    // 兼容旧代码的 int 版本
    public void setCitations(int count) {
        this.citationCount = count;
    }
    
    public int getCitationCount() {
        return citationCount;
    }

    public String getCategory() {
        return category;
    }

    public void setCategory(String category) {
        this.category = category;
    }

    public String getCiting() {
        return citing;
    }

    public void setCiting(String citing) {
        this.citing = citing;
    }

    // 兼容旧代码的方法
    public String getAuthor() {
        return author;
    }

    public void setAuthor(String author) {
        this.author = author;
    }

    public String getCountry() {
        return country;
    }

    public void setCountry(String country) {
        this.country = country;
    }

    // 兼容旧代码 - 保留但标记为过时
    @Deprecated
    public int getRefs() {
        return 0;
    }

    @Deprecated
    public void setRefs(int refs) {
        // 不再使用
    }
}
