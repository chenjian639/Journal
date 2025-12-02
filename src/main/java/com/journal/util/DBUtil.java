package com.journal.util;

import com.zaxxer.hikari.HikariConfig;
import com.zaxxer.hikari.HikariDataSource;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.sql.Connection;
import java.sql.SQLException;
import java.sql.Statement;
import java.util.Properties;

/**
 * 数据库连接工具类
 * 使用HikariCP连接池管理数据库连接
 * 支持 MySQL 和 SQLite（测试环境）
 */
public class DBUtil {
    private static final Logger logger = LoggerFactory.getLogger(DBUtil.class);
    private static HikariDataSource dataSource;
    private static boolean isSQLite = false;

    static {
        try {
            initDataSource();
        } catch (Exception e) {
            logger.error("初始化数据库连接池失败", e);
            throw new RuntimeException("初始化数据库连接池失败", e);
        }
    }

    private static void initDataSource() throws IOException {
        Properties props = new Properties();
        
        // 优先加载 SQLite 配置（测试环境），如果不存在则加载 MySQL 配置
        String configFile = "db-sqlite.properties";
        InputStream is = DBUtil.class.getClassLoader().getResourceAsStream(configFile);
        
        if (is == null) {
            configFile = "db.properties";
            is = DBUtil.class.getClassLoader().getResourceAsStream(configFile);
        }
        
        if (is == null) {
            throw new IOException("找不到数据库配置文件");
        }
        
        try (InputStream inputStream = is) {
            props.load(inputStream);
        }
        
        String jdbcUrl = props.getProperty("db.url");
        isSQLite = jdbcUrl != null && jdbcUrl.startsWith("jdbc:sqlite");
        
        logger.info("使用数据库配置文件: {}, isSQLite: {}", configFile, isSQLite);

        HikariConfig config = new HikariConfig();
        config.setJdbcUrl(jdbcUrl);
        
        // SQLite 不需要用户名密码
        if (!isSQLite) {
            config.setUsername(props.getProperty("db.username"));
            config.setPassword(props.getProperty("db.password"));
        }
        
        config.setDriverClassName(props.getProperty("db.driver"));

        // 连接池配置
        config.setMaximumPoolSize(Integer.parseInt(props.getProperty("db.pool.maxSize", "10")));
        config.setMinimumIdle(Integer.parseInt(props.getProperty("db.pool.minIdle", "5")));
        config.setConnectionTimeout(Long.parseLong(props.getProperty("db.pool.connectionTimeout", "30000")));

        // 其他优化配置（仅 MySQL）
        if (!isSQLite) {
            config.addDataSourceProperty("cachePrepStmts", "true");
            config.addDataSourceProperty("prepStmtCacheSize", "250");
            config.addDataSourceProperty("prepStmtCacheSqlLimit", "2048");
        }

        dataSource = new HikariDataSource(config);
        logger.info("数据库连接池初始化成功");
        
        // 如果是 SQLite，自动初始化数据库表
        if (isSQLite) {
            initSQLiteDatabase();
        }
    }
    
    /**
     * 初始化 SQLite 数据库表结构
     */
    private static void initSQLiteDatabase() {
        String initScript = "sql/init-sqlite.sql";
        try (InputStream is = DBUtil.class.getClassLoader().getResourceAsStream(initScript)) {
            if (is == null) {
                logger.warn("找不到SQLite初始化脚本: {}", initScript);
                return;
            }
            
            StringBuilder sql = new StringBuilder();
            try (BufferedReader reader = new BufferedReader(new InputStreamReader(is, StandardCharsets.UTF_8))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    // 跳过注释行
                    String trimmedLine = line.trim();
                    if (trimmedLine.startsWith("--") || trimmedLine.isEmpty()) {
                        continue;
                    }
                    sql.append(line).append("\n");
                }
            }
            
            // 执行 SQL 语句
            try (Connection conn = dataSource.getConnection();
                 Statement stmt = conn.createStatement()) {
                
                // 按分号分割 SQL 语句
                String[] statements = sql.toString().split(";");
                for (String statement : statements) {
                    String trimmed = statement.trim();
                    if (!trimmed.isEmpty()) {
                        try {
                            stmt.execute(trimmed);
                        } catch (SQLException e) {
                            // 忽略已存在的表或约束错误
                            if (!e.getMessage().contains("already exists") && 
                                !e.getMessage().contains("UNIQUE constraint")) {
                                logger.warn("执行SQL语句失败: {}", trimmed, e);
                            }
                        }
                    }
                }
            }
            
            logger.info("SQLite数据库初始化完成");
        } catch (Exception e) {
            logger.error("初始化SQLite数据库失败", e);
        }
    }
    
    /**
     * 判断是否使用 SQLite 数据库
     */
    public static boolean isSQLite() {
        return isSQLite;
    }

    /**
     * 获取数据库连接
     */
    public static Connection getConnection() throws SQLException {
        return dataSource.getConnection();
    }

    /**
     * 关闭连接（归还到连接池）
     */
    public static void closeConnection(Connection conn) {
        if (conn != null) {
            try {
                conn.close();
            } catch (SQLException e) {
                logger.error("关闭数据库连接失败", e);
            }
        }
    }

    /**
     * 关闭数据源
     */
    public static void closeDataSource() {
        if (dataSource != null && !dataSource.isClosed()) {
            dataSource.close();
            logger.info("数据库连接池已关闭");
        }
    }
}
