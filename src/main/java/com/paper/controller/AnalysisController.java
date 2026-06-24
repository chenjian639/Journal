package com.paper.controller;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.net.URLEncoder;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.attribute.FileTime;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;
import java.util.stream.Stream;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestBody;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;
import org.springframework.web.multipart.MultipartFile;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.paper.dao.AnalysisDAO;
import com.paper.model.AnalysisRecord;
import com.paper.service.AnalysisService;
import com.paper.service.UserUploadCsvNormalizer;
import com.paper.utils.ResponseUtils;
import com.paper.utils.ValidationUtils;

/**
 * 期刊分析控制器
 */
@Controller
@RequestMapping("/analysis")
public class AnalysisController {

    private final AnalysisService analysisService;
    private final UserUploadCsvNormalizer csvNormalizer;
    private final AnalysisDAO analysisDAO;

    public AnalysisController(AnalysisService analysisService, UserUploadCsvNormalizer csvNormalizer, AnalysisDAO analysisDAO) {
        this.analysisService = analysisService;
        this.csvNormalizer = csvNormalizer;
        this.analysisDAO = analysisDAO;
    }

    // 用户上传文件存储目录：uploads/{username}/
    private static final String UPLOAD_BASE_DIR = "uploads/";
    private static final List<String> ALLOWED_EXTENSIONS = List.of(".json", ".csv");
    private static final long MAX_FILE_SIZE = 1000 * 1024 * 1024; // 100MB
    private static final ObjectMapper objectMapper = new ObjectMapper();

    public record OutputFileItem(String path, long size, String lastModified) {}

    /**
     * 获取用户上传目录
     */
    private Path getUserUploadDir(String username) {
        if (ValidationUtils.isBlank(username)) {
            return Paths.get(UPLOAD_BASE_DIR, "anonymous");
        }
        return Paths.get(UPLOAD_BASE_DIR, username);
    }

    /**
     * 上传数据文件（需要用户名）
     */
    @PostMapping("/upload")
    @ResponseBody
    public Map<String, Object> uploadFile(
            @RequestParam("file") MultipartFile file,
            @RequestParam(required = false) String username) {
        
        if (file.isEmpty()) {
            return ResponseUtils.error("请选择要上传的文件");
        }
        
        if (file.getSize() > MAX_FILE_SIZE) {
            return ResponseUtils.error("文件大小不能超过1000MB");
        }
        
        String originalFilename = file.getOriginalFilename();
        String extension = getFileExtension(originalFilename);
        if (!ALLOWED_EXTENSIONS.contains(extension.toLowerCase())) {
            return ResponseUtils.error("仅支持JSON和CSV格式文件");
        }
        
        try {
            // 使用用户专属目录
            Path uploadPath = getUserUploadDir(username);
            if (!Files.exists(uploadPath)) {
                Files.createDirectories(uploadPath);
            }
            
            // 清理用户目录下的旧数据文件（只保留一份）
            cleanUserDataFiles(uploadPath);
            
            String uniqueFilename = UUID.randomUUID().toString() + extension;
            Path filePath = uploadPath.resolve(uniqueFilename);
            Files.copy(file.getInputStream(), filePath);

            // 对用户上传 CSV 做一次“表头/分隔符”规范化，避免期刊列（journal）无法识别
            Map<String, Object> normalizeInfo = null;
            if (".csv".equalsIgnoreCase(extension)) {
                try {
                    var report = csvNormalizer.normalizeInPlace(filePath);
                    normalizeInfo = new HashMap<>();
                    normalizeInfo.put("changed", report.changed());
                    normalizeInfo.put("encoding", report.encoding());
                    normalizeInfo.put("detectedDelimiter", String.valueOf(report.detectedDelimiter()));
                    normalizeInfo.put("renamedHeaders", report.renamedHeaders());
                    normalizeInfo.put("warnings", report.warnings());
                } catch (Exception e) {
                    normalizeInfo = new HashMap<>();
                    normalizeInfo.put("changed", false);
                    normalizeInfo.put("error", "CSV 规范化失败: " + e.getMessage());
                }
            }
            
            // 保存到数据库
            if (ValidationUtils.isNotBlank(username)) {
                try {
                    analysisDAO.saveUploadRecord(username, uniqueFilename, originalFilename, file.getSize());
                } catch (Exception e) {
                    System.err.println("Failed to save upload record: " + e.getMessage());
                }
            }
            
            Map<String, Object> data = new HashMap<>();
            data.put("filename", uniqueFilename);
            data.put("originalName", originalFilename);
            data.put("size", file.getSize());
            data.put("userDir", uploadPath.toString());
            if (normalizeInfo != null) {
                data.put("csvNormalize", normalizeInfo);
            }
            return ResponseUtils.success("文件上传成功", data);
            
        } catch (IOException e) {
            return ResponseUtils.error("文件上传失败: " + e.getMessage());
        }
    }

    /**
     * 运行数据分析（保存结果到数据库）
     */
    @PostMapping("/run")
    @ResponseBody
    public Map<String, Object> runAnalysis(
            @RequestParam(required = false) String filename,
            @RequestParam(required = false) String username) {
        try {
            Map<String, Object> result;
            String analysisFilename = filename;
            
            if (ValidationUtils.isNotBlank(filename)) {
                if (!ValidationUtils.isSafeFilename(filename)) {
                    return ResponseUtils.error("无效的文件名");
                }
                // 使用用户专属目录
                Path userDir = getUserUploadDir(username);
                result = analysisService.analyzeFile(userDir.resolve(filename).toString());
            } else if (ValidationUtils.isNotBlank(username)) {
                // 分析用户目录下的所有文件
                Path userDir = getUserUploadDir(username);
                result = analysisService.analyzeUserDirectory(userDir.toString());
                // 为用户目录分析生成一个唯一文件名标识
                analysisFilename = "user_analysis_" + System.currentTimeMillis() + ".json";
            } else {
                result = analysisService.analyzeAllData();
                analysisFilename = "db_analysis_" + System.currentTimeMillis() + ".json";
            }
            
            // 保存分析结果到数据库
            if (Boolean.TRUE.equals(result.get("success")) && ValidationUtils.isNotBlank(username)) {
                try {
                    Object analysisObj = result.get("analysis");
                    String analysisJson = analysisObj != null ? objectMapper.writeValueAsString(analysisObj) : "{}";
                    
                    // 如果是新分析，先创建记录
                    if (analysisFilename != null && analysisFilename.startsWith("user_analysis_")) {
                        analysisDAO.saveAnalysisRecord(username, analysisFilename, "用户数据分析", analysisJson);
                    } else if (analysisFilename != null) {
                        analysisDAO.updateAnalysisResult(analysisFilename, analysisJson);
                    }

                    // 归档本次分析产物（outputs/data + analysis_result.json），用于后续按 analysisId 下载报告
                    try {
                        AnalysisRecord saved = analysisDAO.getByFilename(analysisFilename);
                        if (saved != null && saved.getId() != null) {
                            Path userDir = getUserUploadDir(username);
                            ReportController.archiveAnalysisSnapshot(userDir, saved.getId(), analysisJson);
                        }
                    } catch (Exception e) {
                        System.err.println("[WARN] Failed to archive analysis snapshot: " + e.getMessage());
                    }
                    
                    // 在返回结果中添加分析记录ID
                    result.put("analysisId", analysisFilename);
                } catch (Exception e) {
                    System.err.println("Failed to save analysis result: " + e.getMessage());
                    e.printStackTrace();
                }
            }
            
            return result;
            
        } catch (Exception e) {
            return ResponseUtils.error("数据分析失败: " + e.getMessage());
        }
    }

    /**
     * AI对话接口（包含分析上下文）
     */
    @PostMapping("/chat")
    @ResponseBody
    public Map<String, Object> chat(@RequestBody Map<String, String> request) {
        String message = request.get("message");
        String context = request.get("context");
        String username = request.get("username");
        
        if (ValidationUtils.isBlank(message)) {
            return ResponseUtils.error("请输入消息");
        }
        
        if (message.length() > 1000) {
            return ResponseUtils.error("消息内容过长");
        }
        
        try {
            // 如果没有传入 context，尝试获取用户最近的分析结果
            if (ValidationUtils.isBlank(context) && ValidationUtils.isNotBlank(username)) {
                try {
                    AnalysisRecord record = analysisDAO.getLatestByUsername(username);
                    if (record != null && record.getAnalysisResult() != null) {
                        context = record.getAnalysisResult();
                    }
                } catch (Exception e) {
                    System.err.println("Failed to get analysis context: " + e.getMessage());
                }
            }
            
            String reply = analysisService.chat(message.trim(), context);
            
            Map<String, Object> data = new HashMap<>();
            data.put("reply", reply);
            return ResponseUtils.success("success", data);
            
        } catch (Exception e) {
            return ResponseUtils.error("AI对话失败: " + e.getMessage());
        }
    }

    /**
     * 获取用户的分析历史
     */
    @GetMapping("/history")
    @ResponseBody
    public Map<String, Object> getHistory(@RequestParam String username) {
        if (ValidationUtils.isBlank(username)) {
            return ResponseUtils.error("请提供用户名");
        }
        
        try {
            List<AnalysisRecord> records = analysisDAO.getHistoryByUsername(username, 10);
            
            List<Map<String, Object>> historyList = new ArrayList<>();
            for (AnalysisRecord record : records) {
                Map<String, Object> item = new HashMap<>();
                item.put("id", record.getId());
                item.put("filename", record.getFilename());
                item.put("originalName", record.getOriginalName());
                item.put("fileSize", record.getFileSize());
                item.put("createdAt", record.getCreatedAt() != null ? record.getCreatedAt().toString() : null);
                
                // 解析分析结果摘要
                if (record.getAnalysisResult() != null) {
                    try {
                        Map<String, Object> analysis = objectMapper.readValue(record.getAnalysisResult(), Map.class);
                        // 兼容多种字段名
                        Object totalPapers = analysis.get("total_records");
                        if (totalPapers == null) {
                            totalPapers = analysis.get("total_papers");
                        }
                        item.put("totalPapers", totalPapers != null ? totalPapers : 0);
                        item.put("journalCount", analysis.get("journal_count"));
                    } catch (Exception e) {
                        item.put("totalPapers", 0);
                    }
                }
                historyList.add(item);
            }
            
            Map<String, Object> data = new HashMap<>();
            data.put("history", historyList);
            return ResponseUtils.success("success", data);
            
        } catch (Exception e) {
            return ResponseUtils.error("获取历史记录失败: " + e.getMessage());
        }
    }

    /**
     * 获取特定分析记录详情
     */
    @GetMapping("/detail")
    @ResponseBody
    public Map<String, Object> getDetail(@RequestParam String filename) {
        if (ValidationUtils.isBlank(filename) || !ValidationUtils.isSafeFilename(filename)) {
            return ResponseUtils.error("无效的文件名");
        }
        
        try {
            AnalysisRecord record = analysisDAO.getByFilename(filename);
            
            if (record == null) {
                return ResponseUtils.error("记录不存在");
            }
            
            Map<String, Object> data = new HashMap<>();
            data.put("filename", record.getFilename());
            data.put("originalName", record.getOriginalName());
            data.put("createdAt", record.getCreatedAt() != null ? record.getCreatedAt().toString() : null);
            
            if (record.getAnalysisResult() != null) {
                data.put("analysis", objectMapper.readValue(record.getAnalysisResult(), Map.class));
            }
            
            return ResponseUtils.success("success", data);
            
        } catch (Exception e) {
            return ResponseUtils.error("获取详情失败: " + e.getMessage());
        }
    }

    /**
     * 获取 AI 配置状态
     */
    @GetMapping("/ai-status")
    @ResponseBody
    public Map<String, Object> getAIStatus() {
        Map<String, Object> data = new HashMap<>();
        
        boolean isConfigured = com.paper.config.EnvConfig.hasValidDeepSeekKey();
        
        data.put("configured", isConfigured);
        data.put("provider", "deepseek");
        data.put("model", com.paper.config.EnvConfig.get(
            com.paper.config.EnvConfig.DEEPSEEK_MODEL, "deepseek-chat"));
        
        if (!isConfigured) {
            data.put("message", "AI 功能未启用。请在 .env 文件中配置 DEEPSEEK_API_KEY");
        }
        
        return ResponseUtils.success("success", data);
    }

    /**
     * 获取已上传的文件列表（用户专属）
     */
    @GetMapping("/files")
    @ResponseBody
    public Map<String, Object> listFiles(@RequestParam(required = false) String username) {
        try {
            Path uploadPath = getUserUploadDir(username);
            List<String> fileList = new ArrayList<>();
            
            if (Files.exists(uploadPath) && Files.isDirectory(uploadPath)) {
                Files.list(uploadPath)
                     .filter(Files::isRegularFile)
                     .forEach(path -> fileList.add(path.getFileName().toString()));
            }
            
            Map<String, Object> data = new HashMap<>();
            data.put("files", fileList);
            data.put("userDir", uploadPath.toString());
            return ResponseUtils.success("success", data);
            
        } catch (IOException e) {
            return ResponseUtils.error("获取文件列表失败: " + e.getMessage());
        }
    }

    /**
     * 删除已上传的文件
     */
    @PostMapping("/delete")
    @ResponseBody
    public Map<String, Object> deleteFile(
            @RequestParam String filename,
            @RequestParam(required = false) String username) {
        if (!ValidationUtils.isSafeFilename(filename)) {
            return ResponseUtils.error("无效的文件名");
        }
        
        try {
            // 删除数据库记录
            try {
                analysisDAO.deleteByFilename(filename);
            } catch (Exception e) {
                System.err.println("Failed to delete DB record: " + e.getMessage());
            }
            
            // 删除文件（从用户目录）
            Path filePath = getUserUploadDir(username).resolve(filename);
            if (Files.exists(filePath)) {
                Files.delete(filePath);
                return ResponseUtils.success("文件删除成功");
            } else {
                return ResponseUtils.error("文件不存在");
            }
        } catch (IOException e) {
            return ResponseUtils.error("文件删除失败: " + e.getMessage());
        }
    }

    private String getFileExtension(String filename) {
        if (filename == null || !filename.contains(".")) {
            return "";
        }
        return filename.substring(filename.lastIndexOf("."));
    }

    /**
     * 一键打包下载分析结果
     */
    @GetMapping("/download")
    public ResponseEntity<byte[]> downloadResults(@RequestParam(required = false) String username) {
        try {
            Path userDir = getUserUploadDir(username);
            Path outputsDir = userDir.resolve("outputs");
            
            if (!Files.exists(outputsDir)) {
                return ResponseEntity.notFound().build();
            }
            
            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            try (ZipOutputStream zos = new ZipOutputStream(baos)) {
                // 添加主分析结果
                Path resultFile = outputsDir.resolve("analysis_result.json");
                if (Files.exists(resultFile)) {
                    addToZip(zos, resultFile, "analysis_result.json");
                }
                
                // 添加各指标详细结果
                String[] metricDirs = {"disrupt", "interdisciplinary", "novelty", "theme", "topic", "keywords"};
                for (String dir : metricDirs) {
                    Path metricPath = outputsDir.resolve(dir);
                    if (Files.exists(metricPath) && Files.isDirectory(metricPath)) {
                        Files.walk(metricPath)
                            .filter(Files::isRegularFile)
                            .forEach(file -> {
                                try {
                                    String entryName = dir + "/" + file.getFileName().toString();
                                    addToZip(zos, file, entryName);
                                } catch (IOException e) {
                                    System.err.println("Failed to add file to zip: " + file);
                                }
                            });
                    }
                }
                
                // 添加清洗后的数据文件
                Path dataDir = userDir.resolve("data");
                if (Files.exists(dataDir) && Files.isDirectory(dataDir)) {
                    Files.list(dataDir)
                        .filter(Files::isRegularFile)
                        .filter(p -> p.toString().endsWith(".csv"))
                        .forEach(file -> {
                            try {
                                String entryName = "data/" + file.getFileName().toString();
                                addToZip(zos, file, entryName);
                            } catch (IOException e) {
                                System.err.println("Failed to add data file to zip: " + file);
                            }
                        });
                }
            }
            
            byte[] zipBytes = baos.toByteArray();
            
            String zipFilename = "analysis_results_" + System.currentTimeMillis() + ".zip";
            
            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_OCTET_STREAM);
            headers.setContentDispositionFormData("attachment", zipFilename);
            headers.setContentLength(zipBytes.length);
            
            return ResponseEntity.ok()
                    .headers(headers)
                    .body(zipBytes);
                    
        } catch (IOException e) {
            System.err.println("Download failed: " + e.getMessage());
            return ResponseEntity.internalServerError().build();
        }
    }

    /**
     * 在线查看用户 outputs 目录（全量 CSV/JSON 列表 + 可点开下载）
     */
    @GetMapping("/outputs")
    public String outputsPage(@RequestParam(required = false) String username, Model model) {
        try {
            if (ValidationUtils.isBlank(username)) {
                model.addAttribute("error", "请提供 username");
                return "error";
            }

            Path userDir = getUserUploadDir(username);
            Path outputsDir = userDir.resolve("outputs");
            if (!Files.exists(outputsDir) || !Files.isDirectory(outputsDir)) {
                model.addAttribute("error", "未找到 outputs 目录（请先运行一次分析）");
                return "error";
            }

            List<OutputFileItem> items = new ArrayList<>();
            try (Stream<Path> s = Files.walk(outputsDir)) {
                s.filter(Files::isRegularFile)
                    .forEach(p -> {
                        try {
                            String rel = outputsDir.relativize(p).toString().replace('\\', '/');
                            String ext = getFileExtension(rel).toLowerCase();
                            if (!ALLOWED_EXTENSIONS.contains(ext)) {
                                return;
                            }
                            long size = Files.size(p);
                            FileTime ft = Files.getLastModifiedTime(p);
                            String lm = ft == null ? "" : String.valueOf(ft);
                            items.add(new OutputFileItem(rel, size, lm));
                        } catch (Exception ignored) {
                        }
                    });
            }

            items.sort((a, b) -> a.path().compareToIgnoreCase(b.path()));

            model.addAttribute("username", username);
            model.addAttribute("items", items);
            model.addAttribute("zipUrl", "/analysis/download?username=" + URLEncoder.encode(username, StandardCharsets.UTF_8));
            model.addAttribute("resultUrl", "/analysis/outputs/file?username=" + URLEncoder.encode(username, StandardCharsets.UTF_8)
                + "&path=" + URLEncoder.encode("analysis_result.json", StandardCharsets.UTF_8));
            return "analysis/outputs";
        } catch (Exception e) {
            model.addAttribute("error", "加载 outputs 失败: " + e.getMessage());
            return "error";
        }
    }

    /**
     * 下载/查看 outputs 下的单个文件（CSV/JSON）。
     * 通过 outputsDir + 相对路径访问，避免路径穿越。
     */
    @GetMapping("/outputs/file")
    public ResponseEntity<byte[]> downloadOutputFile(
        @RequestParam String username,
        @RequestParam String path
    ) {
        try {
            if (ValidationUtils.isBlank(username) || ValidationUtils.isBlank(path)) {
                return ResponseEntity.badRequest().build();
            }

            String rel = path.replace('\\', '/').trim();
            if (rel.startsWith("/") || rel.contains("..")) {
                return ResponseEntity.badRequest().build();
            }

            String ext = getFileExtension(rel).toLowerCase();
            if (!ALLOWED_EXTENSIONS.contains(ext)) {
                return ResponseEntity.status(403).build();
            }

            Path userDir = getUserUploadDir(username);
            Path outputsDir = userDir.resolve("outputs").normalize();
            Path target = outputsDir.resolve(rel).normalize();
            if (!target.startsWith(outputsDir)) {
                return ResponseEntity.status(403).build();
            }
            if (!Files.exists(target) || !Files.isRegularFile(target)) {
                return ResponseEntity.notFound().build();
            }

            byte[] bytes = Files.readAllBytes(target);
            String filename = target.getFileName().toString();

            MediaType mt = ".json".equals(ext)
                ? MediaType.APPLICATION_JSON
                : new MediaType("text", "csv", StandardCharsets.UTF_8);

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(mt);
            headers.setContentDispositionFormData("attachment", filename);
            headers.setContentLength(bytes.length);

            return ResponseEntity.ok().headers(headers).body(bytes);
        } catch (Exception e) {
            return ResponseEntity.internalServerError().build();
        }
    }
    
    /**
     * 添加文件到ZIP
     */
    private void addToZip(ZipOutputStream zos, Path file, String entryName) throws IOException {
        ZipEntry entry = new ZipEntry(entryName);
        zos.putNextEntry(entry);
        Files.copy(file, zos);
        zos.closeEntry();
    }
    
    /**
     * 清理用户目录下的旧数据文件（CSV/JSON），只保留一份
     */
    private void cleanUserDataFiles(Path userDir) {
        if (!Files.exists(userDir) || !Files.isDirectory(userDir)) {
            return;
        }
        
        try {
            Files.list(userDir)
                .filter(Files::isRegularFile)
                .filter(path -> {
                    String name = path.getFileName().toString().toLowerCase();
                    return name.endsWith(".csv") || name.endsWith(".json");
                })
                .forEach(path -> {
                    try {
                        Files.delete(path);
                        System.out.println("<=Deleted old file: " + path.getFileName());
                    } catch (IOException e) {
                        System.err.println("Failed to delete old file: " + path.getFileName() + " - " + e.getMessage());
                    }
                });

            // 同步清理 raw 备份（避免多次上传导致占用过大）
            Path rawDir = userDir.resolve("raw");
            if (Files.exists(rawDir) && Files.isDirectory(rawDir)) {
                Files.list(rawDir)
                    .filter(Files::isRegularFile)
                    .forEach(path -> {
                        try {
                            Files.delete(path);
                        } catch (IOException e) {
                            System.err.println("Failed to delete raw backup: " + path.getFileName() + " - " + e.getMessage());
                        }
                    });
            }
        } catch (IOException e) {
            System.err.println("Failed to clean user dir: " + e.getMessage());
        }
    }
}
