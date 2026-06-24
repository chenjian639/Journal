-- ============================================
-- 学术论文管理系统 - SQLite 数据库初始化脚本
-- ============================================
-- 使用方法: sqlite3 paper_system.db < init_sqlite.sql
-- 数据库文件位置: 项目根目录/data/paper_system.db
-- ============================================

-- ============================================
-- 用户表
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    uname VARCHAR(50) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL,
    email VARCHAR(100),
    is_admin INTEGER DEFAULT 0,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_uname ON users(uname);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================
-- 原始论文数据表 (papers)
-- 用于存储从外部源采集的未经清洗的论文信息
-- ============================================
CREATE TABLE IF NOT EXISTS papers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doi VARCHAR(255),
    journal VARCHAR(255),
    keywords TEXT,
    publish_date INTEGER,  -- 发表年份
    target VARCHAR(255),
    citations TEXT,        -- 参考文献列表
    title TEXT,
    abstract TEXT,
    category VARCHAR(100),
    citing TEXT            -- 引用该论文的文献列表
);

CREATE INDEX IF NOT EXISTS idx_papers_doi ON papers(doi);
CREATE INDEX IF NOT EXISTS idx_papers_journal ON papers(journal);
CREATE INDEX IF NOT EXISTS idx_papers_publish_date ON papers(publish_date);
CREATE INDEX IF NOT EXISTS idx_papers_category ON papers(category);

-- ============================================
-- 清洗后的论文数据表 (cleaned)
-- 结构与 papers 相同，用于存储经过数据清洗、规范化和预处理后的论文信息
-- ============================================
CREATE TABLE IF NOT EXISTS cleaned (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    doi VARCHAR(255),
    journal VARCHAR(255),
    keywords TEXT,
    publish_date INTEGER,  -- 发表年份
    target VARCHAR(255),
    citations TEXT,        -- 参考文献列表
    title TEXT,
    abstract TEXT,
    category VARCHAR(100),
    citing TEXT            -- 引用该论文的文献列表
);

CREATE INDEX IF NOT EXISTS idx_cleaned_doi ON cleaned(doi);
CREATE INDEX IF NOT EXISTS idx_cleaned_journal ON cleaned(journal);
CREATE INDEX IF NOT EXISTS idx_cleaned_publish_date ON cleaned(publish_date);
CREATE INDEX IF NOT EXISTS idx_cleaned_category ON cleaned(category);

-- ============================================
-- 期刊指标表 (journal_metrics)
-- 用于存储期刊在不同年份的各项学术计量指标
-- ============================================
CREATE TABLE IF NOT EXISTS journal_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journal VARCHAR(512) NOT NULL,
    year INTEGER NOT NULL,
    disruption REAL,           -- 颠覆性指标
    interdisciplinary REAL,    -- 跨学科性指标
    novelty REAL,              -- 新颖性指标
    topic REAL,                -- 主题相关性指标
    theme_concentration REAL,  -- 主题集中度指标
    hot_response REAL,         -- 热点响应指标
    top_keywords_2021 TEXT,    -- 2021年顶级关键词
    top_keywords_2022 TEXT,    -- 2022年顶级关键词
    top_keywords_2023 TEXT,    -- 2023年顶级关键词
    top_keywords_2024 TEXT,    -- 2024年顶级关键词
    top_keywords_2025 TEXT,    -- 2025年顶级关键词
    paper_count INTEGER,       -- 论文总数
    category VARCHAR(100),     -- 期刊分类
    UNIQUE(journal, year)
);

CREATE INDEX IF NOT EXISTS idx_journal_metrics_journal ON journal_metrics(journal);
CREATE INDEX IF NOT EXISTS idx_journal_metrics_year ON journal_metrics(year);
CREATE INDEX IF NOT EXISTS idx_journal_metrics_category ON journal_metrics(category);

-- ============================================
-- 分析记录表 (analysis_record)
-- 用于存储用户上传文件和分析结果
-- ============================================
CREATE TABLE IF NOT EXISTS analysis_record (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) NOT NULL,
    filename VARCHAR(100) NOT NULL UNIQUE,
    original_name VARCHAR(255),
    file_size BIGINT,
    analysis_result TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_analysis_username ON analysis_record(username);
CREATE INDEX IF NOT EXISTS idx_analysis_created ON analysis_record(created_at);

-- ============================================
-- 用户上传数据集的期刊指标表 (user_journal_metrics)
-- 用于存储用户单次分析（analysis_record.id）下每本期刊的详情页指标
-- 目的：复用既有 /journal/{journal} 详情页逻辑，而不污染总库 journal_metrics
-- ============================================
CREATE TABLE IF NOT EXISTS user_journal_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    analysis_id INTEGER NOT NULL,
    username VARCHAR(50) NOT NULL,
    journal VARCHAR(512) NOT NULL,
    year INTEGER NOT NULL,
    disruption REAL,
    interdisciplinary REAL,
    novelty REAL,
    topic REAL,
    theme_concentration REAL,
    hot_response REAL,
    top_keywords_2021 TEXT,
    top_keywords_2022 TEXT,
    top_keywords_2023 TEXT,
    top_keywords_2024 TEXT,
    top_keywords_2025 TEXT,
    paper_count INTEGER,
    category VARCHAR(100),
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(analysis_id, journal, year)
);

CREATE INDEX IF NOT EXISTS idx_user_journal_analysis_id ON user_journal_metrics(analysis_id);
CREATE INDEX IF NOT EXISTS idx_user_journal_username ON user_journal_metrics(username);
CREATE INDEX IF NOT EXISTS idx_user_journal_journal ON user_journal_metrics(journal);
CREATE INDEX IF NOT EXISTS idx_user_journal_year ON user_journal_metrics(year);

-- ============================================
-- 验证数据库初始化
-- ============================================
SELECT '数据库初始化完成！' AS message;
