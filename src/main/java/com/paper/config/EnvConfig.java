package com.paper.config;

import java.io.BufferedReader;
import java.io.File;
import java.io.FileReader;
import java.io.IOException;
import java.util.HashMap;
import java.util.Map;

/**
 * 环境配置管理
 * 从 .env 文件和系统环境变量读取配置
 */
public class EnvConfig {
    
    private static final Map<String, String> config = new HashMap<>();
    private static boolean initialized = false;
    
    // ====== 配置键常量 ======
    
    // 数据库
    public static final String DB_MODE = "DB_MODE";
    public static final String MYSQL_HOST = "MYSQL_HOST";
    public static final String MYSQL_PORT = "MYSQL_PORT";
    public static final String MYSQL_DATABASE = "MYSQL_DATABASE";
    public static final String MYSQL_USER = "MYSQL_USER";
    public static final String MYSQL_PASSWORD = "MYSQL_PASSWORD";
    
    // 邮件
    public static final String MAIL_ENABLED = "MAIL_ENABLED";
    public static final String MAIL_HOST = "MAIL_HOST";
    public static final String MAIL_PORT = "MAIL_PORT";
    public static final String MAIL_USERNAME = "MAIL_USERNAME";
    public static final String MAIL_PASSWORD = "MAIL_PASSWORD";
    
    // DeepSeek AI
    public static final String DEEPSEEK_API_KEY = "DEEPSEEK_API_KEY";
    public static final String DEEPSEEK_API_BASE = "DEEPSEEK_API_BASE";
    public static final String DEEPSEEK_MODEL = "DEEPSEEK_MODEL";

    // 兼容旧配置键（历史版本可能使用这些）
    private static final String LEGACY_AI_API_KEY = "AI_API_KEY";
    private static final String LEGACY_AI_API_BASE = "AI_API_BASE";
    private static final String LEGACY_AI_MODEL = "AI_MODEL";
    
    // 服务器
    public static final String SERVER_HOST = "SERVER_HOST";
    public static final String SERVER_PORT = "SERVER_PORT";
    
    // 日志
    public static final String LOG_LEVEL = "LOG_LEVEL";
    
    static {
        initialize();
    }
    
    private static synchronized void initialize() {
        if (initialized) return;
        
        loadEnvFile();
        loadSystemEnv();
        applyLegacyAliases();
        setDefaults();
        
        initialized = true;
        System.out.println("[EnvConfig] Config loaded, total " + config.size() + " items");
    }

    private static void applyLegacyAliases() {
        // 兼容：如果用户只配置了 AI_API_KEY，则映射到 DEEPSEEK_API_KEY
        if (!config.containsKey(DEEPSEEK_API_KEY) && config.containsKey(LEGACY_AI_API_KEY)) {
            config.put(DEEPSEEK_API_KEY, config.get(LEGACY_AI_API_KEY));
        }
        if (!config.containsKey(DEEPSEEK_API_BASE) && config.containsKey(LEGACY_AI_API_BASE)) {
            config.put(DEEPSEEK_API_BASE, config.get(LEGACY_AI_API_BASE));
        }
        if (!config.containsKey(DEEPSEEK_MODEL) && config.containsKey(LEGACY_AI_MODEL)) {
            config.put(DEEPSEEK_MODEL, config.get(LEGACY_AI_MODEL));
        }
    }
    
    private static void loadEnvFile() {
        String[] paths = { ".env", "../.env", System.getProperty("user.dir") + "/.env" };
        
        for (String path : paths) {
            File envFile = new File(path);
            if (envFile.exists() && envFile.isFile()) {
                try (BufferedReader reader = new BufferedReader(new FileReader(envFile))) {
                    String line;
                    while ((line = reader.readLine()) != null) {
                        line = line.trim();
                        if (line.isEmpty() || line.startsWith("#")) continue;
                        
                        int eq = line.indexOf('=');
                        if (eq > 0) {
                            String key = line.substring(0, eq).trim();
                            String value = line.substring(eq + 1).trim();
                            // 移除引号
                            if ((value.startsWith("\"") && value.endsWith("\"")) ||
                                (value.startsWith("'") && value.endsWith("'"))) {
                                value = value.substring(1, value.length() - 1);
                            }
                            config.put(key, value);
                        }
                    }
                    System.out.println("[EnvConfig] Loaded: " + envFile.getAbsolutePath());
                    return;
                } catch (IOException e) {
                    System.err.println("[EnvConfig] Read failed: " + e.getMessage());
                }
            }
        }
    }
    
    private static void loadSystemEnv() {
        for (Map.Entry<String, String> entry : System.getenv().entrySet()) {
            String key = entry.getKey();
            if (key.startsWith("DB_") || key.startsWith("MYSQL_") || 
                key.startsWith("MAIL_") || key.startsWith("DEEPSEEK_") ||
                key.startsWith("SERVER_") || key.startsWith("LOG_")) {
                config.put(key, entry.getValue());
            }
        }
    }
    
    private static void setDefaults() {
        config.putIfAbsent(DB_MODE, "sqlite");
        config.putIfAbsent(MYSQL_HOST, "localhost");
        config.putIfAbsent(MYSQL_PORT, "3306");
        config.putIfAbsent(MYSQL_DATABASE, "paper_sys");
        config.putIfAbsent(MYSQL_USER, "root");
        
        config.putIfAbsent(MAIL_ENABLED, "false");
        config.putIfAbsent(MAIL_HOST, "smtp.qq.com");
        config.putIfAbsent(MAIL_PORT, "465");
        
        config.putIfAbsent(DEEPSEEK_API_BASE, "https://api.deepseek.com/v1");
        config.putIfAbsent(DEEPSEEK_MODEL, "deepseek-chat");
        
        config.putIfAbsent(SERVER_HOST, "0.0.0.0");
        config.putIfAbsent(SERVER_PORT, "5000");
        config.putIfAbsent(LOG_LEVEL, "INFO");
    }
    
    // ====== 公共方法 ======
    
    public static String get(String key) {
        return config.get(key);
    }
    
    public static String get(String key, String defaultValue) {
        return config.getOrDefault(key, defaultValue);
    }
    
    public static int getInt(String key, int defaultValue) {
        String value = config.get(key);
        if (value == null) return defaultValue;
        try {
            return Integer.parseInt(value);
        } catch (NumberFormatException e) {
            return defaultValue;
        }
    }
    
    public static boolean getBoolean(String key, boolean defaultValue) {
        String value = config.get(key);
        if (value == null) return defaultValue;
        return "true".equalsIgnoreCase(value) || "1".equals(value);
    }
    
    // ====== 便捷方法 ======
    
    public static boolean isSQLiteMode() {
        return "sqlite".equalsIgnoreCase(get(DB_MODE, "sqlite"));
    }
    
    public static boolean isMailEnabled() {
        String password = get(MAIL_PASSWORD);
        return getBoolean(MAIL_ENABLED, false) && 
               password != null && !password.isEmpty() && !password.startsWith("your");
    }
    
    public static boolean hasValidDeepSeekKey() {
        String key = get(DEEPSEEK_API_KEY);
        return key != null && !key.isEmpty() && !key.startsWith("your-");
    }
    
    public static String getMySQLUrl() {
        return String.format("jdbc:mysql://%s:%s/%s?useSSL=false&serverTimezone=UTC&allowPublicKeyRetrieval=true",
                get(MYSQL_HOST), get(MYSQL_PORT), get(MYSQL_DATABASE));
    }
}
