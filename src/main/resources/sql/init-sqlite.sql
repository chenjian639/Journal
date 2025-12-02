-- ============================================
-- 期刊分析系统数据库初始化脚本 (SQLite版本)
-- Journal Analysis System Database Schema
-- ============================================

-- ============================================
-- 用户表
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL,
    email TEXT,
    real_name TEXT,
    role TEXT DEFAULT 'USER',
    status INTEGER DEFAULT 1,
    create_time TEXT DEFAULT (datetime('now', 'localtime')),
    update_time TEXT DEFAULT (datetime('now', 'localtime')),
    last_login_time TEXT
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- ============================================
-- 期刊表
-- ============================================
CREATE TABLE IF NOT EXISTS journals (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    issn TEXT,
    publisher TEXT,
    country TEXT,
    language TEXT,
    category TEXT,
    impact_factor REAL,
    frequency TEXT,
    description TEXT,
    official_url TEXT,
    create_time TEXT DEFAULT (datetime('now', 'localtime')),
    update_time TEXT DEFAULT (datetime('now', 'localtime'))
);

CREATE INDEX IF NOT EXISTS idx_journals_name ON journals(name);
CREATE INDEX IF NOT EXISTS idx_journals_issn ON journals(issn);
CREATE INDEX IF NOT EXISTS idx_journals_country ON journals(country);
CREATE INDEX IF NOT EXISTS idx_journals_category ON journals(category);
CREATE INDEX IF NOT EXISTS idx_journals_impact_factor ON journals(impact_factor);

-- ============================================
-- 论文/文章表
-- ============================================
CREATE TABLE IF NOT EXISTS articles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    journal_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    authors TEXT,
    abstract_text TEXT,
    keywords TEXT,
    doi TEXT,
    publish_date TEXT,
    volume INTEGER,
    issue INTEGER,
    pages TEXT,
    citation_count INTEGER DEFAULT 0,
    create_time TEXT DEFAULT (datetime('now', 'localtime')),
    update_time TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (journal_id) REFERENCES journals(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_articles_journal_id ON articles(journal_id);
CREATE INDEX IF NOT EXISTS idx_articles_title ON articles(title);
CREATE INDEX IF NOT EXISTS idx_articles_doi ON articles(doi);
CREATE INDEX IF NOT EXISTS idx_articles_publish_date ON articles(publish_date);

-- ============================================
-- 分析报告表
-- ============================================
CREATE TABLE IF NOT EXISTS analysis_reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    title TEXT NOT NULL,
    report_type TEXT NOT NULL,
    journal_id INTEGER,
    journal_ids TEXT,
    content TEXT,
    created_by INTEGER,
    create_time TEXT DEFAULT (datetime('now', 'localtime')),
    update_time TEXT DEFAULT (datetime('now', 'localtime')),
    FOREIGN KEY (journal_id) REFERENCES journals(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_reports_type ON analysis_reports(report_type);
CREATE INDEX IF NOT EXISTS idx_reports_created_by ON analysis_reports(created_by);
CREATE INDEX IF NOT EXISTS idx_reports_create_time ON analysis_reports(create_time);

-- ============================================
-- 插入初始数据
-- ============================================

-- 插入管理员用户（密码：admin123，使用SHA-256加密）
INSERT OR IGNORE INTO users (username, password, email, real_name, role, status) VALUES 
('admin', '240be518fabd2724ddb6f04eeb9d6d8b55c7cd8e79f7c99e5df5e7c3c12e7d01', 'admin@example.com', '系统管理员', 'ADMIN', 1);

-- 插入示例期刊数据
INSERT OR IGNORE INTO journals (name, issn, publisher, country, language, category, impact_factor, frequency, description, official_url) VALUES 
('Nature', '0028-0836', 'Springer Nature', '英国', '英文', '综合', 69.504, '周刊', 'Nature是世界上最具影响力的科学期刊之一，发表各学科领域的原创研究论文。', 'https://www.nature.com'),
('Science', '0036-8075', 'AAAS', '美国', '英文', '综合', 63.714, '周刊', 'Science是美国科学促进会出版的学术期刊，涵盖所有科学领域。', 'https://www.science.org'),
('Cell', '0092-8674', 'Elsevier', '美国', '英文', '生物学', 66.850, '双周刊', 'Cell是生命科学领域的顶级期刊，主要发表细胞生物学相关研究。', 'https://www.cell.com'),
('中国科学', '1674-7291', '科学出版社', '中国', '中英双语', '综合', 2.879, '月刊', '《中国科学》是中国科学院主办的综合性科学期刊。', 'https://www.scichina.com'),
('计算机学报', '0254-4164', '科学出版社', '中国', '中文', '计算机科学', 3.546, '月刊', '《计算机学报》是中国计算机领域的权威学术期刊。', 'http://cjc.ict.ac.cn'),
('IEEE Transactions on Pattern Analysis and Machine Intelligence', '0162-8828', 'IEEE', '美国', '英文', '计算机科学', 24.314, '月刊', 'TPAMI是人工智能和模式识别领域的顶级期刊。', 'https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34'),
('The Lancet', '0140-6736', 'Elsevier', '英国', '英文', '医学', 202.731, '周刊', 'The Lancet是世界上最古老和最具影响力的医学期刊之一。', 'https://www.thelancet.com'),
('中华医学杂志', '0376-2491', '中华医学会', '中国', '中文', '医学', 2.154, '周刊', '《中华医学杂志》是中国医学领域的权威综合性学术期刊。', 'http://www.nmjc.net.cn');

-- 插入示例论文数据
INSERT OR IGNORE INTO articles (journal_id, title, authors, abstract_text, keywords, doi, publish_date, volume, issue, pages, citation_count) VALUES
(1, 'A revolutionary approach to quantum computing', 'John Smith, Jane Doe', 'This paper presents a groundbreaking methodology for quantum computing...', 'quantum computing, algorithms, optimization', '10.1038/s41586-023-00001-1', '2023-06-15', 618, 7965, '245-251', 156),
(1, 'Climate change impact on global ecosystems', 'Alice Johnson, Bob Wilson', 'We analyze the effects of climate change on biodiversity...', 'climate change, ecosystems, biodiversity', '10.1038/s41586-023-00002-2', '2023-07-20', 619, 7970, '112-118', 89),
(4, '人工智能在医疗诊断中的应用研究', '张三, 李四, 王五', '本文探讨了人工智能技术在医疗影像诊断中的创新应用...', '人工智能, 医疗诊断, 深度学习', '10.1360/SSC-2023-0001', '2023-05-10', 53, 5, '678-690', 45),
(5, '基于深度学习的图像识别算法研究', '刘一, 陈二', '提出了一种新型的深度学习图像识别算法...', '深度学习, 图像识别, 卷积神经网络', '10.11897/SP.J.1016.2023.00001', '2023-08-01', 46, 8, '1567-1580', 32);

-- ============================================
-- 结束
-- ============================================
