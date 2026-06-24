package com.paper.utils;

import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import javax.sql.DataSource;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.ApplicationRunner;
import org.springframework.stereotype.Component;

/**
 * 数据库初始化工具类
 * 自动创建必要的表结构
 */
@Component
public class DatabaseInitializer implements ApplicationRunner {

    private final DataSource dataSource;

    public DatabaseInitializer(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    @Override
    public void run(ApplicationArguments args) {
        initialize();
    }
    
    /**
     * 初始化数据库（创建表）
     */
    public void initialize() {
        System.out.println("======================================");
        System.out.println("[DB Init] Starting database initialization...");
        System.out.println("======================================");
        
        try {
            try (Connection conn = dataSource.getConnection()) {
                String product = null;
                try {
                    product = conn.getMetaData().getDatabaseProductName();
                    String url = conn.getMetaData().getURL();
                    System.out.println("[DB Init] Product: " + product);
                    System.out.println("[DB Init] URL: " + url);
                } catch (Exception ignored) {
                }

                boolean isSQLite = isSQLite(product);
                
                // 创建用户表
                createUserTable(conn, isSQLite);

                // 创建/修复默认管理员账户（可通过环境变量关闭或自定义）
                try {
                    ensureDefaultAdminUser(conn, isSQLite);
                } catch (Exception e) {
                    System.err.println("[DB Init] Failed to ensure default admin user: " + e.getMessage());
                }
                
                // 创建论文表
                createPaperTable(conn, isSQLite);
                
                // 创建作者表
                createAuthorTable(conn, isSQLite);
                
                // 创建关键词表
                createKeywordTable(conn, isSQLite);

                // 创建关键词出现索引表（用于关键词分析）
                createKeywordOccurrenceTable(conn, isSQLite);
                
                // 创建期刊指标表
                createJournalMetricsTable(conn, isSQLite);
                
                // 创建分析记录表
                createAnalysisRecordTable(conn, isSQLite);

                // 创建用户上传数据集的期刊指标表（用于复用期刊详情页）
                createUserJournalMetricsTable(conn, isSQLite);
                
                System.out.println("[DB Init] Database initialization completed!");
                
            }
        } catch (SQLException e) {
            System.err.println("Database initialization failed: " + e.getMessage());
        }
    }

    private static void executeSql(Connection conn, String sql) throws SQLException {
        try (PreparedStatement pstmt = conn.prepareStatement(sql)) {
            pstmt.executeUpdate();
        }
    }

    private static boolean isSQLite(String productName) {
        if (productName == null) return false;
        return productName.toLowerCase().contains("sqlite");
    }

    private static boolean indexExists(Connection conn, String tableName, String indexName) {
        try {
            var md = conn.getMetaData();
            try (var rs = md.getIndexInfo(conn.getCatalog(), null, tableName, false, false)) {
                while (rs != null && rs.next()) {
                    String name = rs.getString("INDEX_NAME");
                    if (name != null && name.equalsIgnoreCase(indexName)) {
                        return true;
                    }
                }
            }
        } catch (SQLException ignored) {
        }
        return false;
    }

    private static void createIndexIfMissing(Connection conn, String tableName, String indexName, String createSql) throws SQLException {
        if (indexExists(conn, tableName, indexName)) {
            return;
        }
        try {
            executeSql(conn, createSql);
        } catch (SQLException e) {
            // 允许并发/重复创建时失败
        }
    }

    private static String getConfig(String key, String defaultValue) {
        // 优先 Java system property，其次环境变量
        String v = System.getProperty(key);
        if (v == null || v.isBlank()) {
            v = System.getenv(key);
        }
        if (v == null || v.isBlank()) {
            return defaultValue;
        }
        return v.trim();
    }

    private static Set<String> getExistingColumnsLower(Connection conn, String tableName) {
        Set<String> cols = new HashSet<>();
        try {
            var md = conn.getMetaData();
            try (ResultSet rs = md.getColumns(conn.getCatalog(), null, tableName, null)) {
                while (rs != null && rs.next()) {
                    String name = rs.getString("COLUMN_NAME");
                    if (name != null && !name.isBlank()) {
                        cols.add(name.toLowerCase(Locale.ROOT));
                    }
                }
            }
        } catch (SQLException ignored) {
        }
        return cols;
    }

    private static void ensureColumnsExist(Connection conn, String tableName, Map<String, String> columnNameToSqlType) {
        Set<String> existing = getExistingColumnsLower(conn, tableName);
        for (var e : columnNameToSqlType.entrySet()) {
            String col = e.getKey();
            String type = e.getValue();
            if (existing.contains(col.toLowerCase(Locale.ROOT))) {
                continue;
            }
            try {
                executeSql(conn, "ALTER TABLE " + tableName + " ADD COLUMN " + col + " " + type);
                System.out.println("  [OK] Added missing column: " + tableName + "." + col);
            } catch (SQLException ex) {
                // 并发/重复补列或方言差异时允许失败
            }
        }
    }
    
    /**
     * 创建用户表
     */
    private static void createUserTable(Connection conn, boolean isSQLite) throws SQLException {
        String sql;
        if (isSQLite) {
            sql = """
                CREATE TABLE IF NOT EXISTS users (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    uname VARCHAR(50) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    email VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """;
        } else {
            sql = """
                CREATE TABLE IF NOT EXISTS users (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    uname VARCHAR(50) NOT NULL UNIQUE,
                    password VARCHAR(255) NOT NULL,
                    email VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """;
        }
        executeSql(conn, sql);

        // 兼容旧库：补齐 is_admin 字段
        Map<String, String> missingCols = new LinkedHashMap<>();
        missingCols.put("is_admin", isSQLite ? "INTEGER DEFAULT 0" : "TINYINT(1) DEFAULT 0");
        ensureColumnsExist(conn, "users", missingCols);

        System.out.println("  [OK] Table 'users' created");
    }

    private static void ensureDefaultAdminUser(Connection conn, boolean isSQLite) throws SQLException {
        // 通过 PM_ADMIN_ENABLED 控制是否创建默认管理员
        String enabled = getConfig("PM_ADMIN_ENABLED", "true").toLowerCase(Locale.ROOT);
        if ("false".equals(enabled) || "0".equals(enabled) || "off".equals(enabled)) {
            System.out.println("[DB Init] Default admin user creation is disabled (PM_ADMIN_ENABLED=false)");
            return;
        }

        String uname = getConfig("PM_ADMIN_USERNAME", "admin");
        String rawPassword = getConfig("PM_ADMIN_PASSWORD", "admin123456");
        String email = getConfig("PM_ADMIN_EMAIL", "");

        // 若用户已存在：确保标记为管理员
        if (userExists(conn, uname)) {
            try (PreparedStatement ps = conn.prepareStatement("UPDATE users SET is_admin = 1 WHERE uname = ?")) {
                ps.setString(1, uname);
                ps.executeUpdate();
            }
            System.out.println("[DB Init] Default admin user already exists: " + uname);
            return;
        }

        // 创建用户（BCrypt hash）
        String hashed = org.mindrot.jbcrypt.BCrypt.hashpw(rawPassword, org.mindrot.jbcrypt.BCrypt.gensalt());
        String sql = "INSERT INTO users (uname, password, email, is_admin) VALUES (?, ?, ?, 1)";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, uname);
            ps.setString(2, hashed);
            ps.setString(3, (email == null || email.isBlank()) ? null : email);
            ps.executeUpdate();
        }

        System.out.println("[DB Init] Created default admin user: " + uname);
        System.out.println("[DB Init] NOTE: Change PM_ADMIN_PASSWORD in production.");
    }

    private static boolean userExists(Connection conn, String uname) throws SQLException {
        if (uname == null || uname.isBlank()) return false;
        try (PreparedStatement ps = conn.prepareStatement("SELECT 1 FROM users WHERE uname = ? LIMIT 1")) {
            ps.setString(1, uname);
            try (ResultSet rs = ps.executeQuery()) {
                return rs != null && rs.next();
            }
        }
    }
    
    /**
     * 创建论文表
     */
    private static void createPaperTable(Connection conn, boolean isSQLite) throws SQLException {
        String sql;
        if (isSQLite) {
            sql = """
                CREATE TABLE IF NOT EXISTS papers (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    wos_id VARCHAR(50) UNIQUE,
                    title TEXT NOT NULL,
                    abstract_text TEXT,
                    publish_date DATE,
                    journal VARCHAR(255),
                    volume INT,
                    issue INT,
                    pages INT,
                    doi VARCHAR(100),
                    country VARCHAR(100),
                    author TEXT,
                    target TEXT,
                    conference VARCHAR(255),
                    citations INT DEFAULT 0,
                    refs INT DEFAULT 0,
                    keywords TEXT
                )
            """;
        } else {
            sql = """
                CREATE TABLE IF NOT EXISTS papers (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    wos_id VARCHAR(50) UNIQUE,
                    title TEXT NOT NULL,
                    abstract_text TEXT,
                    publish_date DATE,
                    journal VARCHAR(255),
                    volume INT,
                    issue INT,
                    pages INT,
                    doi VARCHAR(100),
                    country VARCHAR(100),
                    author TEXT,
                    target TEXT,
                    conference VARCHAR(255),
                    citations INT DEFAULT 0,
                    refs INT DEFAULT 0,
                    keywords TEXT
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """;
        }
        executeSql(conn, sql);
        System.out.println("  [OK] Table 'papers' created");
    }
    
    /**
     * 创建作者表
     */
    private static void createAuthorTable(Connection conn, boolean isSQLite) throws SQLException {
        String sql;
        if (isSQLite) {
            sql = """
                CREATE TABLE IF NOT EXISTS authors (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name VARCHAR(100) NOT NULL,
                    affiliation VARCHAR(255),
                    email VARCHAR(100)
                )
            """;
        } else {
            sql = """
                CREATE TABLE IF NOT EXISTS authors (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    name VARCHAR(100) NOT NULL,
                    affiliation VARCHAR(255),
                    email VARCHAR(100)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """;
        }
        executeSql(conn, sql);
        System.out.println("  [OK] Table 'authors' created");
    }
    
    /**
     * 创建关键词表
     */
    private static void createKeywordTable(Connection conn, boolean isSQLite) throws SQLException {
        String sql;
        if (isSQLite) {
            sql = """
                CREATE TABLE IF NOT EXISTS keywords (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    keyword VARCHAR(100) NOT NULL UNIQUE
                )
            """;
        } else {
            sql = """
                CREATE TABLE IF NOT EXISTS keywords (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    keyword VARCHAR(100) NOT NULL UNIQUE
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """;
        }
        executeSql(conn, sql);
        System.out.println("  [OK] Table 'keywords' created");
    }

    /**
     * 创建关键词出现索引表
     * 用于快速查询：关键词 -> 论文 -> 期刊
     */
    private static void createKeywordOccurrenceTable(Connection conn, boolean isSQLite) throws SQLException {
        String sql;
        if (isSQLite) {
            sql = """
                CREATE TABLE IF NOT EXISTS keyword_occurrence (
                    keyword TEXT NOT NULL,
                    paper_id INTEGER NOT NULL,
                    journal TEXT,
                    publish_date DATE,
                    PRIMARY KEY(keyword, paper_id)
                )
            """;
        } else {
            // MySQL: 使用复合主键
            sql = """
                CREATE TABLE IF NOT EXISTS keyword_occurrence (
                    keyword VARCHAR(255) NOT NULL,
                    paper_id BIGINT NOT NULL,
                    journal VARCHAR(512),
                    publish_date DATE,
                    PRIMARY KEY(keyword, paper_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """;
        }
        executeSql(conn, sql);

        if (isSQLite) {
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_keyword_occurrence_keyword ON keyword_occurrence(keyword)");
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_keyword_occurrence_journal ON keyword_occurrence(journal)");
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_keyword_occurrence_publish_date ON keyword_occurrence(publish_date)");
        } else {
            createIndexIfMissing(conn, "keyword_occurrence", "idx_keyword_occurrence_keyword",
                "CREATE INDEX idx_keyword_occurrence_keyword ON keyword_occurrence(keyword)");
            createIndexIfMissing(conn, "keyword_occurrence", "idx_keyword_occurrence_journal",
                "CREATE INDEX idx_keyword_occurrence_journal ON keyword_occurrence(journal)");
            createIndexIfMissing(conn, "keyword_occurrence", "idx_keyword_occurrence_publish_date",
                "CREATE INDEX idx_keyword_occurrence_publish_date ON keyword_occurrence(publish_date)");
        }
        System.out.println("  [OK] Table 'keyword_occurrence' created");
    }
    
    /**
     * 创建期刊指标表
     */
    private static void createJournalMetricsTable(Connection conn, boolean isSQLite) throws SQLException {
        String sql;
        if (isSQLite) {
            sql = """
                CREATE TABLE IF NOT EXISTS journal_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
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
                    UNIQUE(journal, year)
                )
            """;
        } else {
            sql = """
                CREATE TABLE IF NOT EXISTS journal_metrics (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    journal VARCHAR(512) NOT NULL,
                    year INT NOT NULL,
                    disruption DOUBLE,
                    interdisciplinary DOUBLE,
                    novelty DOUBLE,
                    topic DOUBLE,
                    theme_concentration DOUBLE,
                    hot_response DOUBLE,
                    top_keywords_2021 TEXT,
                    top_keywords_2022 TEXT,
                    top_keywords_2023 TEXT,
                    top_keywords_2024 TEXT,
                    top_keywords_2025 TEXT,
                    paper_count INT,
                    category VARCHAR(100),
                    UNIQUE KEY idx_journal_year (journal, year)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """;
        }
        executeSql(conn, sql);

        if (isSQLite) {
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_journal_metrics_journal ON journal_metrics(journal)");
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_journal_metrics_year ON journal_metrics(year)");
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_journal_metrics_category ON journal_metrics(category)");
        } else {
            createIndexIfMissing(conn, "journal_metrics", "idx_journal_metrics_journal",
                "CREATE INDEX idx_journal_metrics_journal ON journal_metrics(journal)");
            createIndexIfMissing(conn, "journal_metrics", "idx_journal_metrics_year",
                "CREATE INDEX idx_journal_metrics_year ON journal_metrics(year)");
            createIndexIfMissing(conn, "journal_metrics", "idx_journal_metrics_category",
                "CREATE INDEX idx_journal_metrics_category ON journal_metrics(category)");
        }
        System.out.println("  [OK] Table 'journal_metrics' created");
    }
    
    /**
     * 创建分析记录表
     */
    private static void createAnalysisRecordTable(Connection conn, boolean isSQLite) throws SQLException {
        String sql;
        if (isSQLite) {
            sql = """
                CREATE TABLE IF NOT EXISTS analysis_record (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    username VARCHAR(50) NOT NULL,
                    filename VARCHAR(100) NOT NULL UNIQUE,
                    original_name VARCHAR(255),
                    file_size BIGINT,
                    analysis_result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """;
        } else {
            sql = """
                CREATE TABLE IF NOT EXISTS analysis_record (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    username VARCHAR(50) NOT NULL,
                    filename VARCHAR(100) NOT NULL UNIQUE,
                    original_name VARCHAR(255),
                    file_size BIGINT,
                    analysis_result TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    INDEX idx_analysis_username (username),
                    INDEX idx_analysis_created (created_at)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """;
        }
        executeSql(conn, sql);

        if (isSQLite) {
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_analysis_username ON analysis_record(username)");
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_analysis_created ON analysis_record(created_at)");
        } else {
            createIndexIfMissing(conn, "analysis_record", "idx_analysis_username",
                "CREATE INDEX idx_analysis_username ON analysis_record(username)");
            createIndexIfMissing(conn, "analysis_record", "idx_analysis_created",
                "CREATE INDEX idx_analysis_created ON analysis_record(created_at)");
        }
        System.out.println("  [OK] Table 'analysis_record' created");
    }

    /**
     * 创建用户上传数据集的期刊指标表
     * 用于：在“我的上传榜单”中为每个期刊提供详情页所需字段。
     */
    private static void createUserJournalMetricsTable(Connection conn, boolean isSQLite) throws SQLException {
        String sql;
        if (isSQLite) {
            sql = """
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
                )
            """;
        } else {
            sql = """
                CREATE TABLE IF NOT EXISTS user_journal_metrics (
                    id INT PRIMARY KEY AUTO_INCREMENT,
                    analysis_id INT NOT NULL,
                    username VARCHAR(50) NOT NULL,
                    journal VARCHAR(512) NOT NULL,
                    year INT NOT NULL,
                    disruption DOUBLE,
                    interdisciplinary DOUBLE,
                    novelty DOUBLE,
                    topic DOUBLE,
                    theme_concentration DOUBLE,
                    hot_response DOUBLE,
                    top_keywords_2021 TEXT,
                    top_keywords_2022 TEXT,
                    top_keywords_2023 TEXT,
                    top_keywords_2024 TEXT,
                    top_keywords_2025 TEXT,
                    paper_count INT,
                    category VARCHAR(100),
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    UNIQUE KEY idx_user_journal_analysis (analysis_id, journal, year),
                    INDEX idx_user_journal_analysis_id (analysis_id),
                    INDEX idx_user_journal_username (username),
                    INDEX idx_user_journal_journal (journal)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """;
        }
        executeSql(conn, sql);

        // 兼容旧库：表已存在但缺少 top_keywords_2021~2025 列时自动补齐
        Map<String, String> missingCols = new LinkedHashMap<>();
        missingCols.put("top_keywords_2021", "TEXT");
        missingCols.put("top_keywords_2022", "TEXT");
        missingCols.put("top_keywords_2023", "TEXT");
        missingCols.put("top_keywords_2024", "TEXT");
        missingCols.put("top_keywords_2025", "TEXT");
        ensureColumnsExist(conn, "user_journal_metrics", missingCols);

        if (isSQLite) {
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_user_journal_analysis_id ON user_journal_metrics(analysis_id)");
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_user_journal_username ON user_journal_metrics(username)");
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_user_journal_journal ON user_journal_metrics(journal)");
            executeSql(conn, "CREATE INDEX IF NOT EXISTS idx_user_journal_year ON user_journal_metrics(year)");
        } else {
            createIndexIfMissing(conn, "user_journal_metrics", "idx_user_journal_analysis_id",
                "CREATE INDEX idx_user_journal_analysis_id ON user_journal_metrics(analysis_id)");
            createIndexIfMissing(conn, "user_journal_metrics", "idx_user_journal_username",
                "CREATE INDEX idx_user_journal_username ON user_journal_metrics(username)");
            createIndexIfMissing(conn, "user_journal_metrics", "idx_user_journal_journal",
                "CREATE INDEX idx_user_journal_journal ON user_journal_metrics(journal)");
            createIndexIfMissing(conn, "user_journal_metrics", "idx_user_journal_year",
                "CREATE INDEX idx_user_journal_year ON user_journal_metrics(year)");
        }

        System.out.println("  [OK] Table 'user_journal_metrics' created");
    }
}
