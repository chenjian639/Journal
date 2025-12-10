package com.journal.entity;

import java.io.Serializable;
import java.time.LocalDate;
import java.time.LocalDateTime;

/**
 * 论文/文章实体类
 */
public class Article implements Serializable {
    private static final long serialVersionUID = 1L;

    private Long id;
    private Long journalId;             // 所属期刊ID
    private String title;               // 文章标题
    private String authors;             // 作者（逗号分隔）
    private String abstractText;        // 摘要
    private String keywords;            // 关键词
    private String doi;                 // DOI
    private LocalDate publishDate;      // 发表日期
    private Integer volume;             // 卷号
    private Integer issue;              // 期号
    private String pages;               // 页码
    private Integer citationCount;      // 被引次数
    private LocalDateTime createTime;   // 创建时间
    private LocalDateTime updateTime;   // 更新时间

    // 关联对象（非数据库字段）
    private Journal journal;

    public Article() {
    }

    // Getters and Setters
    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public Long getJournalId() {
        return journalId;
    }

    public void setJournalId(Long journalId) {
        this.journalId = journalId;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getAuthors() {
        return authors;
    }

    public void setAuthors(String authors) {
        this.authors = authors;
    }

    public String getAbstractText() {
        return abstractText;
    }

    public void setAbstractText(String abstractText) {
        this.abstractText = abstractText;
    }

    public String getKeywords() {
        return keywords;
    }

    public void setKeywords(String keywords) {
        this.keywords = keywords;
    }

    public String getDoi() {
        return doi;
    }

    public void setDoi(String doi) {
        this.doi = doi;
    }

    public LocalDate getPublishDate() {
        return publishDate;
    }

    public void setPublishDate(LocalDate publishDate) {
        this.publishDate = publishDate;
    }

    public Integer getVolume() {
        return volume;
    }

    public void setVolume(Integer volume) {
        this.volume = volume;
    }

    public Integer getIssue() {
        return issue;
    }

    public void setIssue(Integer issue) {
        this.issue = issue;
    }

    public String getPages() {
        return pages;
    }

    public void setPages(String pages) {
        this.pages = pages;
    }

    public Integer getCitationCount() {
        return citationCount;
    }

    public void setCitationCount(Integer citationCount) {
        this.citationCount = citationCount;
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

    public Journal getJournal() {
        return journal;
    }

    public void setJournal(Journal journal) {
        this.journal = journal;
    }

    @Override
    public String toString() {
        return "Article{" +
                "id=" + id +
                ", title='" + title + '\'' +
                ", authors='" + authors + '\'' +
                ", doi='" + doi + '\'' +
                '}';
    }
}
