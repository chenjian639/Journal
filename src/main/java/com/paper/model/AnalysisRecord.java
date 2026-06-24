package com.paper.model;

import java.time.LocalDateTime;

/**
 * 分析记录模型
 * 存储用户的文件上传和分析结果
 */
public class AnalysisRecord {
    
    private Long id;
    private String username;           // 用户名
    private String filename;           // 保存的文件名（UUID）
    private String originalName;       // 原始文件名
    private Long fileSize;             // 文件大小（字节）
    private String analysisResult;     // 分析结果（JSON格式）
    private LocalDateTime createdAt;   // 创建时间
    
    public AnalysisRecord() {}
    
    public AnalysisRecord(String username, String filename, String originalName, Long fileSize) {
        this.username = username;
        this.filename = filename;
        this.originalName = originalName;
        this.fileSize = fileSize;
    }

    // Getters and Setters
    public Long getId() { return id; }
    public void setId(Long id) { this.id = id; }

    public String getUsername() { return username; }
    public void setUsername(String username) { this.username = username; }

    public String getFilename() { return filename; }
    public void setFilename(String filename) { this.filename = filename; }

    public String getOriginalName() { return originalName; }
    public void setOriginalName(String originalName) { this.originalName = originalName; }

    public Long getFileSize() { return fileSize; }
    public void setFileSize(Long fileSize) { this.fileSize = fileSize; }

    public String getAnalysisResult() { return analysisResult; }
    public void setAnalysisResult(String analysisResult) { this.analysisResult = analysisResult; }

    public LocalDateTime getCreatedAt() { return createdAt; }
    public void setCreatedAt(LocalDateTime createdAt) { this.createdAt = createdAt; }
}
