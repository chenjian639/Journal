-- ====== 测试环境期刊数据库初始化脚本 (SQLite) ======
-- 创建journal_metrics表（SQLite版本）

CREATE TABLE IF NOT EXISTS journal_metrics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journal VARCHAR(255) NOT NULL,
    year INTEGER NOT NULL,
    disruption REAL,
    novelty REAL,
    interdisciplinary REAL,
    topic REAL,
    theme_concentration REAL,
    hot_response REAL,
    paper_count INTEGER,
    category VARCHAR(100),
    top_keywords_2021 TEXT,
    top_keywords_2022 TEXT,
    top_keywords_2023 TEXT,
    top_keywords_2024 TEXT,
    top_keywords_2025 TEXT,
    UNIQUE(journal, year)
);

-- 创建索引以提高查询性能
CREATE INDEX IF NOT EXISTS idx_journal ON journal_metrics(journal);
CREATE INDEX IF NOT EXISTS idx_year ON journal_metrics(year);
CREATE INDEX IF NOT EXISTS idx_journal_year ON journal_metrics(journal, year);

-- 插入测试数据示例
INSERT OR IGNORE INTO journal_metrics (
    journal, year, disruption, novelty, interdisciplinary, topic, 
    theme_concentration, hot_response, paper_count, category,
    top_keywords_2021, top_keywords_2022, top_keywords_2023
) VALUES 
    ('Nature', 2023, 0.85, 0.90, 0.75, 0.80, 0.70, 0.88, 1500, 'Multidisciplinary',
     '["artificial intelligence", "machine learning", "climate change"]',
     '["quantum computing", "gene editing", "renewable energy"]',
     '["large language models", "carbon capture", "biodiversity"]'),
     
    ('Science', 2023, 0.82, 0.87, 0.73, 0.78, 0.68, 0.85, 1400, 'Multidisciplinary',
     '["covid-19", "vaccines", "genomics"]',
     '["crispr", "materials science", "neuroscience"]',
     '["ai ethics", "fusion energy", "microbiome"]'),
     
    ('Cell', 2023, 0.78, 0.83, 0.65, 0.70, 0.75, 0.80, 800, 'Biology',
     '["immunotherapy", "stem cells", "cancer"]',
     '["cell biology", "protein structure", "aging"]',
     '["mrna", "organoids", "single-cell"]');

-- 测试数据统计
SELECT 
    COUNT(*) as total_records,
    COUNT(DISTINCT journal) as unique_journals,
    MIN(year) as earliest_year,
    MAX(year) as latest_year
FROM journal_metrics;
