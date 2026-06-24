package com.paper.service;

import java.io.BufferedReader;
import java.io.File;
import java.io.IOException;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.sql.SQLException;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Value;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.paper.dao.MySQLHelper;
import com.paper.model.Paper;
import com.paper.utils.AIClient;

/**
 * 期刊分析服务类
 * <p>负责数据分析、AI对话等业务逻辑</p>
 * 
 * <h3>功能说明：</h3>
 * <ul>
 *   <li>分析上传的JSON/CSV文件</li>
 *   <li>分析数据库中的论文数据</li>
 *   <li>提供AI对话功能（简化实现）</li>
 * </ul>
 * 
 * @author PaperMaster Team
 * @version 1.0
 * @since 2024-12-18
 */
@Service
public class AnalysisService {

    /** Python分析主脚本路径 */
    private static final String PYTHON_MAIN_SCRIPT = "src/main/resources/python/main.py";
    
    /** JSON对象映射器 */
    private static final ObjectMapper objectMapper = new ObjectMapper();
    
    private final AIClient aiClient;
    private final UserUploadCsvNormalizer csvNormalizer;

    private final MySQLHelper mysqlHelper;

    /**
     * 关键词翻译模式：off | glossary | baidu
     * - off: 不翻译（保持原文，可能是中文）
     * - glossary: 仅用 keyword_glossary_clean.json 查表翻译（离线、快）
     * - baidu: 词表未命中时调用百度翻译（联网、慢）
     */
    @Value("${papermaster.keywordTranslateMode:glossary}")
    private String keywordTranslateMode;

    /**
     * 构造函数，初始化数据库连接
     * 
     * @throws ClassNotFoundException 数据库驱动未找到
     * @throws SQLException 数据库连接失败
     */
    public AnalysisService(AIClient aiClient, UserUploadCsvNormalizer csvNormalizer, MySQLHelper mysqlHelper) {
        this.aiClient = aiClient;
        this.csvNormalizer = csvNormalizer;
        this.mysqlHelper = mysqlHelper;
    }

    /**
     * 分析上传的文件
     * <p>支持JSON和CSV格式的论文数据文件</p>
     * <p>直接调用Python脚本分析文件所在目录</p>
     * 
     * @param filePath 文件路径
     * @return 分析结果，包含统计信息
     * @throws Exception 文件读取或解析失败
     */
    public Map<String, Object> analyzeFile(String filePath) throws Exception {
        Map<String, Object> response = new HashMap<>();
        
        File file = new File(filePath);
        if (!file.exists()) {
            response.put("success", false);
            response.put("message", "文件不存在");
            return response;
        }
        
        // 验证文件类型
        String filename = file.getName().toLowerCase();
        if (!filename.endsWith(".json") && !filename.endsWith(".csv")) {
            response.put("success", false);
            response.put("message", "不支持的文件格式，请上传JSON或CSV文件");
            return response;
        }
        
        // 直接使用文件所在目录调用Python分析
        // 这样可以保留原始CSV/JSON格式，让Python脚本直接处理
        String userDirPath = file.getParent();
        return runPythonAnalysis(userDirPath);
    }

    /**
     * 分析数据库中的所有数据
     * <p>从数据库获取论文数据并进行统计分析</p>
     * 
     * @return 分析结果
     * @throws Exception 数据库查询或分析失败
     */
    public Map<String, Object> analyzeAllData() throws Exception {
        Map<String, Object> response = new HashMap<>();
        
        // 从数据库获取所有论文数据
        List<Paper> papers = getAllPapers();
        
        if (papers.isEmpty()) {
            response.put("success", true);
            response.put("message", "数据库中暂无数据");
            response.put("analysis", new HashMap<>());
            return response;
        }
        
        return analyzePapersData(papers);
    }

    /**
     * 分析用户目录下的所有CSV/JSON文件
     * <p>调用Python脚本进行完整的指标分析</p>
     * 
     * @param userDirPath 用户目录路径
     * @return 分析结果
     * @throws Exception 文件读取或分析失败
     */
    public Map<String, Object> analyzeUserDirectory(String userDirPath) throws Exception {
        Map<String, Object> response = new HashMap<>();
        
        File userDir = new File(userDirPath);
        if (!userDir.exists() || !userDir.isDirectory()) {
            response.put("success", false);
            response.put("message", "用户目录不存在，请先上传文件");
            return response;
        }
        
        // 获取目录下所有CSV和JSON文件
        File[] dataFiles = userDir.listFiles((dir, name) -> {
            String lower = name.toLowerCase();
            return lower.endsWith(".csv") || lower.endsWith(".json");
        });
        
        if (dataFiles == null || dataFiles.length == 0) {
            response.put("success", false);
            response.put("message", "目录下没有数据文件，请先上传CSV或JSON文件");
            return response;
        }
        
        // 调用 Python main.py --user-dir 模式进行分析
        return runPythonAnalysis(userDirPath);
    }
    
    /**
     * 调用Python脚本分析用户数据
     * Python 脚本会将结果保存到 outputs/analysis_result.json 文件
     * 
     * @param userDirPath 用户目录路径
     * @return 分析结果
     */
    private Map<String, Object> runPythonAnalysis(String userDirPath) throws Exception {
        Map<String, Object> response = new HashMap<>();

        // 修复：如果 CSV 在上传规范化阶段误判编码导致中文变成“�”，尝试从 raw 备份恢复并重新规范化
        try {
            repairGarbledCsvFromRaw(Path.of(userDirPath));
        } catch (Exception e) {
            System.err.println("[WARN] Failed to repair garbled CSV: " + e.getMessage());
        }
        
        // 删除旧的结果文件，确保读取的是新结果
        File oldResultFile = new File(userDirPath, "outputs/analysis_result.json");
        if (oldResultFile.exists()) {
            oldResultFile.delete();
            System.out.println("[Debug] Deleted old result file: " + oldResultFile.getAbsolutePath());
        }
        
        ProcessBuilder processBuilder = new ProcessBuilder(
                "python", "-u", PYTHON_MAIN_SCRIPT, 
                "--user-dir", userDirPath,
                "--json"  // 启用JSON模式（日志输出到stderr）
        );
        processBuilder.directory(new File("."));
        processBuilder.redirectErrorStream(false);  // 分离错误输出
        
        // 设置 Python 环境变量，强制使用 UTF-8 编码
        Map<String, String> env = processBuilder.environment();
        env.put("PYTHONIOENCODING", "utf-8");
        env.put("PYTHONUTF8", "1");

        // 将 Spring 配置注入到 Python 进程环境变量中（用于控制关键词是否翻译成英文）
        String mode = (keywordTranslateMode == null) ? "" : keywordTranslateMode.trim().toLowerCase();
        if (!mode.isEmpty() && !"off".equals(mode)) {
            env.put("PM_KEYWORD_TRANSLATE_MODE", mode);
        }
        
        System.out.println("[Debug] Starting Python analysis process...");
        Process process = processBuilder.start();
        
        // 使用多线程同时读取stdout和stderr，避免缓冲区满导致的死锁
        StringBuilder output = new StringBuilder();
        StringBuilder errorOutput = new StringBuilder();
        
        // 异步读取stderr（日志信息）
        Thread stderrThread = new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getErrorStream(), "UTF-8"))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    errorOutput.append(line).append("\n");
                    System.err.println("[Python] " + line);
                }
            } catch (Exception e) {
                System.err.println("[Error] Failed to read stderr: " + e.getMessage());
            }
        });
        stderrThread.start();
        
        // 主线程读取stdout
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line);
            }
        }
        
        // 等待stderr线程完成
        stderrThread.join();
        
        int exitCode = process.waitFor();
        System.out.println("[Debug] Python process exit code: " + exitCode);
        
        if (exitCode != 0) {
            response.put("success", false);
            response.put("message", "Python分析脚本执行失败");
            response.put("error", errorOutput.toString());
            return response;
        }
        
        // 从文件读取分析结果
        File resultFile = new File(userDirPath, "outputs/analysis_result.json");
        if (!resultFile.exists()) {
            response.put("success", false);
            response.put("message", "分析结果文件不存在: " + resultFile.getAbsolutePath());
            return response;
        }
        
        try {
            System.out.println("[Debug] Reading result file: " + resultFile.getAbsolutePath());
            
            @SuppressWarnings("unchecked")
            Map<String, Object> analysisResult = objectMapper.readValue(resultFile, Map.class);
            
            // 检查Python返回的结果
            if (analysisResult.containsKey("success") && Boolean.FALSE.equals(analysisResult.get("success"))) {
                response.put("success", false);
                response.put("message", analysisResult.get("message"));
                return response;
            }
            
            response.put("success", true);
            response.put("message", "分析完成");
            response.put("analysis", analysisResult);
            response.put("totalPapers", analysisResult.get("total_records"));
            
            return response;
            
        } catch (Exception e) {
            response.put("success", false);
            response.put("message", "解析分析结果文件失败: " + e.getMessage());
            return response;
        }
    }

    private void repairGarbledCsvFromRaw(Path userDir) throws IOException {
        if (userDir == null || !Files.exists(userDir) || !Files.isDirectory(userDir)) {
            return;
        }

        Path rawDir = userDir.resolve("raw");
        if (!Files.exists(rawDir) || !Files.isDirectory(rawDir)) {
            return;
        }

        try (var stream = Files.list(userDir)) {
            stream
                .filter(Files::isRegularFile)
                .filter(p -> p.getFileName().toString().toLowerCase().endsWith(".csv"))
                .forEach(csv -> {
                    try {
                        if (!looksGarbledUtf8(csv)) {
                            return;
                        }

                        String base = csv.getFileName().toString();
                        String stem = base.replaceAll("(?i)\\.csv$", "");

                        Path bestRaw = findLatestRawForStem(rawDir, stem);
                        if (bestRaw == null) {
                            return;
                        }

                        System.out.println("[Repair] Detected garbled CSV, restoring from raw: " + bestRaw.getFileName());
                        Files.copy(bestRaw, csv, StandardCopyOption.REPLACE_EXISTING);

                        // 重新规范化（会自动写回 UTF-8-BOM + 逗号分隔）
                        csvNormalizer.normalizeInPlace(csv);
                    } catch (Exception e) {
                        System.err.println("[WARN] Failed to repair CSV: " + csv.getFileName() + " - " + e.getMessage());
                    }
                });
        }
    }

    private boolean looksGarbledUtf8(Path csv) {
        // 只抽样前若干行，出现替换字符“�”即可判定已不可逆乱码
        try (BufferedReader r = Files.newBufferedReader(csv, StandardCharsets.UTF_8)) {
            String line;
            int i = 0;
            while ((line = r.readLine()) != null && i < 200) {
                if (line.indexOf('�') >= 0) {
                    return true;
                }
                i++;
            }
        } catch (Exception ignored) {
        }
        return false;
    }

    private Path findLatestRawForStem(Path rawDir, String stem) {
        if (rawDir == null || stem == null || stem.isBlank()) {
            return null;
        }

        Path best = null;
        try (var stream = Files.list(rawDir)) {
            for (Path p : stream.toList()) {
                if (!Files.isRegularFile(p)) continue;
                String name = p.getFileName().toString();
                if (!name.startsWith(stem + ".")) continue;
                if (!name.toLowerCase().endsWith(".raw.csv")) continue;
                if (best == null) {
                    best = p;
                    continue;
                }
                try {
                    if (Files.getLastModifiedTime(p).compareTo(Files.getLastModifiedTime(best)) > 0) {
                        best = p;
                    }
                } catch (Exception ignored) {
                }
            }
        } catch (Exception ignored) {
        }
        return best;
    }

    /**
     * 调用Python脚本分析论文数据（JSON格式）
     * 这个方法用于分析单个文件或数据库的论文数据
     */
    private Map<String, Object> analyzePapersData(List<Paper> papers) throws Exception {
        Map<String, Object> response = new HashMap<>();
        
        // 将论文数据写入临时文件
        File tempFile = File.createTempFile("papers_", ".json");
        tempFile.deleteOnExit();
        objectMapper.writeValue(tempFile, papers);
        
        ProcessBuilder processBuilder = new ProcessBuilder(
                "python", "-u", PYTHON_MAIN_SCRIPT, 
                "--user-dir", tempFile.getParent(),
                "--json"
        );
        processBuilder.directory(new File("."));
        processBuilder.redirectErrorStream(false);  // 分离错误输出，避免日志混入 JSON
        
        // 设置 Python 环境变量，强制使用 UTF-8 编码
        Map<String, String> env = processBuilder.environment();
        env.put("PYTHONIOENCODING", "utf-8");
        env.put("PYTHONUTF8", "1");

        // 将 Spring 配置注入到 Python 进程环境变量中（用于控制关键词是否翻译成英文）
        String mode = (keywordTranslateMode == null) ? "" : keywordTranslateMode.trim().toLowerCase();
        if (!mode.isEmpty() && !"off".equals(mode)) {
            env.put("PM_KEYWORD_TRANSLATE_MODE", mode);
        }
        
        Process process = processBuilder.start();
        
        // 使用多线程同时读取stdout和stderr，避免缓冲区满导致的死锁
        StringBuilder output = new StringBuilder();
        
        // 异步读取stderr（日志信息）
        Thread stderrThread = new Thread(() -> {
            try (BufferedReader reader = new BufferedReader(
                    new InputStreamReader(process.getErrorStream(), "UTF-8"))) {
                String line;
                while ((line = reader.readLine()) != null) {
                    System.err.println("[Python] " + line);
                }
            } catch (Exception e) {
                System.err.println("[Error] Failed to read stderr: " + e.getMessage());
            }
        });
        stderrThread.start();
        
        // 主线程读取stdout（JSON）
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line);
            }
        }
        
        // 等待stderr线程完成
        stderrThread.join();
        
        int exitCode = process.waitFor();
        
        // 清理临时文件
        tempFile.delete();
        
        if (exitCode != 0) {
            response.put("success", false);
            response.put("message", "Python分析脚本执行失败");
            response.put("error", output.toString());
            return response;
        }
        
        @SuppressWarnings("unchecked")
        Map<String, Object> analysisResult = objectMapper.readValue(output.toString(), Map.class);
        
        response.put("success", true);
        response.put("message", "分析完成");
        response.put("analysis", analysisResult);
        response.put("totalPapers", papers.size());
        
        return response;
    }

    /**
     * AI对话功能
     */
    public String chat(String message, String context) {
        Map<String, String> cfg = aiClient.getConfig();
        boolean aiEnabled = "true".equalsIgnoreCase(cfg.get("apiKeySet"))
                && cfg.get("baseUrl") != null && !cfg.get("baseUrl").isBlank()
                && cfg.get("model") != null && !cfg.get("model").isBlank();

        if (!aiEnabled) {
            return fallbackChat(message, context);
        }

        try {
            String systemPrompt = "你是一个学术论文分析助手，帮助用户理解和分析学术论文数据。用中文回答。";
            
            if (context != null && !context.isEmpty()) {
                systemPrompt += "\n\n当前分析结果：" + context;
            }
            
            return aiClient.callChatCompletion(systemPrompt, message);
        } catch (Exception e) {
            System.err.println("AI call failed: " + e.getMessage());
            return fallbackChat(message, context);
        }
    }
    
    /**
     * 简单关键词匹配回复（未配置 API 时使用）
     */
    private String fallbackChat(String message, String context) {
        String msg = message.toLowerCase();
        
        if (msg.contains("论文") || msg.contains("paper")) {
            return "您可以上传论文数据文件（JSON/CSV），然后点击\"运行数据分析\"获取统计结果。";
        }
        if (msg.contains("引用") || msg.contains("citation")) {
            return "系统会统计平均引用数、最高被引论文等信息。";
        }
        if (msg.contains("分析") || msg.contains("analysis")) {
            return "支持：论文数量统计、引用分析、领域分布、国家分布等。";
        }
        if (msg.contains("帮助") || msg.contains("help")) {
            return "主要功能：1.上传数据 2.运行分析 3.AI助手\n\n配置 ai.api.base-url / ai.api.key / ai.api.model 可获得智能对话。";
        }
        if (context != null && !context.isEmpty()) {
            return "当前分析结果：" + context;
        }
        return "我是论文分析助手。请在 application.properties 中配置 ai.api.base-url / ai.api.key / ai.api.model 以启用智能对话。";
    }

    /**
     * 从数据库获取所有论文
     * 使用 papers 表（按文档定义的字段结构）
     */
    private List<Paper> getAllPapers() throws SQLException {
        List<Paper> papers = new ArrayList<>();
        String sql = "SELECT * FROM papers";

        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql);
        if (rows == null || rows.isEmpty()) {
            return papers;
        }

        for (Map<String, Object> row : rows) {
            Paper paper = new Paper();
            paper.setTitle(getString(row.get("title")));
            paper.setDoi(getString(row.get("doi")));
            paper.setJournal(getString(row.get("journal")));
            paper.setKeywords(getString(row.get("keywords")));

            Integer publishYear = getInt(row.get("publish_date"));
            if (publishYear != null && publishYear > 0) {
                paper.setPublishDate(java.time.LocalDate.of(publishYear, 1, 1));
            }

            paper.setTarget(getString(row.get("target")));
            paper.setAbstractText(getString(row.get("abstract")));
            paper.setCategory(getString(row.get("category")));

            String citationsText = getString(row.get("citations"));
            if (citationsText != null && !citationsText.isBlank()) {
                paper.setCitations(citationsText.split(";").length);
            }
            papers.add(paper);
        }
        
        return papers;
    }

    private static String getString(Object v) {
        return v == null ? null : String.valueOf(v);
    }

    private static Integer getInt(Object v) {
        if (v == null) return null;
        if (v instanceof Number n) return n.intValue();
        try {
            return Integer.parseInt(String.valueOf(v));
        } catch (Exception e) {
            return null;
        }
    }
}
