-- ============================================
-- 期刊分析系统数据库初始化脚本
-- Journal Analysis System Database Schema
-- ============================================

-- 创建数据库
CREATE DATABASE IF NOT EXISTS journal_analysis 
    DEFAULT CHARACTER SET utf8mb4 
    DEFAULT COLLATE utf8mb4_unicode_ci;

USE journal_analysis;

-- ============================================
-- 用户表
-- ============================================
CREATE TABLE IF NOT EXISTS users (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '用户ID',
    username VARCHAR(50) NOT NULL UNIQUE COMMENT '用户名',
    password VARCHAR(255) NOT NULL COMMENT '密码（加密）',
    email VARCHAR(100) COMMENT '邮箱',
    real_name VARCHAR(50) COMMENT '真实姓名',
    role VARCHAR(20) DEFAULT 'USER' COMMENT '角色：ADMIN, USER',
    status TINYINT DEFAULT 1 COMMENT '状态：0-禁用，1-启用',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    last_login_time DATETIME COMMENT '最后登录时间',
    INDEX idx_username (username),
    INDEX idx_email (email)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户表';

-- ============================================
-- 期刊表
-- ============================================
CREATE TABLE IF NOT EXISTS journals (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '期刊ID',
    name VARCHAR(255) NOT NULL COMMENT '期刊名称',
    issn VARCHAR(20) COMMENT 'ISSN号',
    publisher VARCHAR(255) COMMENT '出版商',
    country VARCHAR(50) COMMENT '国家/地区',
    language VARCHAR(50) COMMENT '语言',
    category VARCHAR(100) COMMENT '学科分类',
    impact_factor DECIMAL(10, 3) COMMENT '影响因子',
    frequency VARCHAR(50) COMMENT '出版频率',
    description TEXT COMMENT '期刊描述',
    official_url VARCHAR(500) COMMENT '官方网站',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_name (name),
    INDEX idx_issn (issn),
    INDEX idx_country (country),
    INDEX idx_category (category),
    INDEX idx_impact_factor (impact_factor)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='期刊表';

-- ============================================
-- 论文/文章表
-- ============================================
CREATE TABLE IF NOT EXISTS articles (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '论文ID',
    journal_id BIGINT NOT NULL COMMENT '所属期刊ID',
    title VARCHAR(500) NOT NULL COMMENT '论文标题',
    authors TEXT COMMENT '作者（逗号分隔）',
    abstract_text TEXT COMMENT '摘要',
    keywords VARCHAR(500) COMMENT '关键词',
    doi VARCHAR(100) COMMENT 'DOI',
    publish_date DATE COMMENT '发表日期',
    volume INT COMMENT '卷号',
    issue INT COMMENT '期号',
    pages VARCHAR(50) COMMENT '页码',
    citation_count INT DEFAULT 0 COMMENT '被引次数',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_journal_id (journal_id),
    INDEX idx_title (title(100)),
    INDEX idx_doi (doi),
    INDEX idx_publish_date (publish_date),
    FOREIGN KEY (journal_id) REFERENCES journals(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='论文表';

-- ============================================
-- 分析报告表
-- ============================================
CREATE TABLE IF NOT EXISTS analysis_reports (
    id BIGINT PRIMARY KEY AUTO_INCREMENT COMMENT '报告ID',
    title VARCHAR(255) NOT NULL COMMENT '报告标题',
    report_type VARCHAR(20) NOT NULL COMMENT '报告类型：SINGLE, COMPARE',
    journal_id BIGINT COMMENT '单期刊分析时使用',
    journal_ids VARCHAR(500) COMMENT '多期刊比较时使用（逗号分隔）',
    content LONGTEXT COMMENT '报告内容（JSON格式）',
    created_by BIGINT COMMENT '创建者ID',
    create_time DATETIME DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    update_time DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    INDEX idx_report_type (report_type),
    INDEX idx_created_by (created_by),
    INDEX idx_create_time (create_time),
    FOREIGN KEY (journal_id) REFERENCES journals(id) ON DELETE SET NULL,
    FOREIGN KEY (created_by) REFERENCES users(id) ON DELETE SET NULL
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='分析报告表';

-- ============================================
-- 插入初始数据
-- ============================================

-- 插入管理员用户（密码：admin123，使用SHA-256加密）
INSERT INTO users (username, password, email, real_name, role, status) VALUES 
('admin', '240be518fabd2724ddb6f04eeb9d6d8b55c7cd8e79f7c99e5df5e7c3c12e7d01', 'admin@example.com', '系统管理员', 'ADMIN', 1);

-- 插入示例期刊数据
INSERT INTO journals (name, issn, publisher, country, language, category, impact_factor, frequency, description, official_url) VALUES 
('Nature', '0028-0836', 'Springer Nature', '英国', '英文', '综合', 69.504, '周刊', 'Nature是世界上最具影响力的科学期刊之一，发表各学科领域的原创研究论文。', 'https://www.nature.com'),
('Science', '0036-8075', 'AAAS', '美国', '英文', '综合', 63.714, '周刊', 'Science是美国科学促进会出版的学术期刊，涵盖所有科学领域。', 'https://www.science.org'),
('Cell', '0092-8674', 'Elsevier', '美国', '英文', '生物学', 66.850, '双周刊', 'Cell是生命科学领域的顶级期刊，主要发表细胞生物学相关研究。', 'https://www.cell.com'),
('中国科学', '1674-7291', '科学出版社', '中国', '中英双语', '综合', 2.879, '月刊', '《中国科学》是中国科学院主办的综合性科学期刊。', 'https://www.scichina.com'),
('计算机学报', '0254-4164', '科学出版社', '中国', '中文', '计算机科学', 3.546, '月刊', '《计算机学报》是中国计算机领域的权威学术期刊。', 'http://cjc.ict.ac.cn'),
('IEEE Transactions on Pattern Analysis and Machine Intelligence', '0162-8828', 'IEEE', '美国', '英文', '计算机科学', 24.314, '月刊', 'TPAMI是人工智能和模式识别领域的顶级期刊。', 'https://ieeexplore.ieee.org/xpl/RecentIssue.jsp?punumber=34'),
('The Lancet', '0140-6736', 'Elsevier', '英国', '英文', '医学', 202.731, '周刊', 'The Lancet是世界上最古老和最具影响力的医学期刊之一。', 'https://www.thelancet.com'),
('中华医学杂志', '0376-2491', '中华医学会', '中国', '中文', '医学', 2.154, '周刊', '《中华医学杂志》是中国医学领域的权威综合性学术期刊。', 'http://www.nmjc.net.cn');

-- 插入示例论文数据
INSERT INTO articles (journal_id, title, authors, abstract_text, keywords, doi, publish_date, volume, issue, pages, citation_count) VALUES
(1, 'A revolutionary approach to quantum computing', 'John Smith, Jane Doe', 'This paper presents a groundbreaking methodology for quantum computing...', 'quantum computing, algorithms, optimization', '10.1038/s41586-023-00001-1', '2023-06-15', 618, 7965, '245-251', 156),
(1, 'Climate change impact on global ecosystems', 'Alice Johnson, Bob Wilson', 'We analyze the effects of climate change on biodiversity...', 'climate change, ecosystems, biodiversity', '10.1038/s41586-023-00002-2', '2023-07-20', 619, 7970, '112-118', 89),
(4, '人工智能在医疗诊断中的应用研究', '张三, 李四, 王五', '本文探讨了人工智能技术在医疗影像诊断中的创新应用...', '人工智能, 医疗诊断, 深度学习', '10.1360/SSC-2023-0001', '2023-05-10', 53, 5, '678-690', 45),
(5, '基于深度学习的图像识别算法研究', '刘一, 陈二', '提出了一种新型的深度学习图像识别算法...', '深度学习, 图像识别, 卷积神经网络', '10.11897/SP.J.1016.2023.00001', '2023-08-01', 46, 8, '1567-1580', 32);

-- ============================================
-- 结束
-- ============================================
SELECT '数据库初始化完成！' AS message;
