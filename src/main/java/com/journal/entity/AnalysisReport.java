package com.journal.entity;

import java.io.Serializable;
import java.time.LocalDateTime;

/**
 * 分析报告实体类
 */
public class AnalysisReport implements Serializable {
    private static final long serialVersionUID = 1L;

    private Long id;
    private String title;               // 报告标题
    private String reportType;          // 报告类型：SINGLE, COMPARE
    private Long journalId;             // 单期刊分析时使用
    private String journalIds;          // 多期刊比较时使用（逗号分隔）
    private String content;             // 报告内容（JSON格式）
    private Long createdBy;             // 创建者ID
    private LocalDateTime createTime;   // 创建时间
    private LocalDateTime updateTime;   // 更新时间

    // 关联对象
    private Journal journal;
    private User creator;

    public AnalysisReport() {
    }

    // Getters and Setters
    public Long getId() {
        return id;
    }

    public void setId(Long id) {
        this.id = id;
    }

    public String getTitle() {
        return title;
    }

    public void setTitle(String title) {
        this.title = title;
    }

    public String getReportType() {
        return reportType;
    }

    public void setReportType(String reportType) {
        this.reportType = reportType;
    }

    public Long getJournalId() {
        return journalId;
    }

    public void setJournalId(Long journalId) {
        this.journalId = journalId;
    }

    public String getJournalIds() {
        return journalIds;
    }

    public void setJournalIds(String journalIds) {
        this.journalIds = journalIds;
    }

    public String getContent() {
        return content;
    }

    public void setContent(String content) {
        this.content = content;
    }

    public Long getCreatedBy() {
        return createdBy;
    }

    public void setCreatedBy(Long createdBy) {
        this.createdBy = createdBy;
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

    public User getCreator() {
        return creator;
    }

    public void setCreator(User creator) {
        this.creator = creator;
    }

    @Override
    public String toString() {
        return "AnalysisReport{" +
                "id=" + id +
                ", title='" + title + '\'' +
                ", reportType='" + reportType + '\'' +
                '}';
    }
}
