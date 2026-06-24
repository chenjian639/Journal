package com.paper.controller;

import java.io.ByteArrayOutputStream;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.FileVisitResult;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.nio.file.SimpleFileVisitor;
import java.nio.file.StandardCopyOption;
import java.nio.file.attribute.BasicFileAttributes;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.List;
import java.util.Map;
import java.util.zip.ZipEntry;
import java.util.zip.ZipOutputStream;

import org.springframework.http.HttpHeaders;
import org.springframework.http.MediaType;
import org.springframework.http.ResponseEntity;
import org.springframework.stereotype.Controller;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.RequestParam;

import com.paper.dao.AnalysisDAO;
import com.paper.dao.UserJournalMetricsDAO;
import com.paper.model.AnalysisRecord;
import com.paper.model.UserJournalMetricsRow;
import com.paper.service.UserAnalysisRankingService;
import com.paper.utils.ValidationUtils;

@Controller
public class ReportController {

    private final AnalysisDAO analysisDAO;
    private final UserJournalMetricsDAO userJournalMetricsDAO;
    private final UserAnalysisRankingService userAnalysisRankingService;

    public ReportController(
        AnalysisDAO analysisDAO,
        UserJournalMetricsDAO userJournalMetricsDAO,
        UserAnalysisRankingService userAnalysisRankingService
    ) {
        this.analysisDAO = analysisDAO;
        this.userJournalMetricsDAO = userJournalMetricsDAO;
        this.userAnalysisRankingService = userAnalysisRankingService;
    }

    private static final String UPLOAD_BASE_DIR = "uploads/";

    private Path getUserUploadDir(String username) {
        if (ValidationUtils.isBlank(username)) {
            return Paths.get(UPLOAD_BASE_DIR, "anonymous");
        }
        return Paths.get(UPLOAD_BASE_DIR, username);
    }

    @GetMapping("/report/download")
    public ResponseEntity<byte[]> downloadReport(
        @RequestParam String username,
        @RequestParam long analysisId
    ) {
        if (ValidationUtils.isBlank(username)) {
            return ResponseEntity.badRequest().build();
        }

        try {
            AnalysisRecord record = analysisDAO.getById(analysisId);
            if (record == null) {
                return ResponseEntity.notFound().build();
            }
            if (record.getUsername() == null || !username.equals(record.getUsername())) {
                return ResponseEntity.status(403).build();
            }

            // 1) 确保 user_journal_metrics 已落库（用于批量生成静态详情页）
            if (record.getAnalysisResult() != null && !record.getAnalysisResult().isBlank()) {
                try {
                    var dataset = userAnalysisRankingService.parseAnalysisResult(record.getAnalysisResult());
                    userJournalMetricsDAO.upsertAll(record.getId(), username, dataset.rows());
                } catch (Exception e) {
                    System.err.println("[WARN] Failed to upsert user journal metrics: " + e.getMessage());
                }
            }

            // 2) 选择数据来源：优先使用 reports/{analysisId} 归档；否则回退当前 outputs/data
            Path userDir = getUserUploadDir(username);
            Path archiveDir = userDir.resolve("reports").resolve(String.valueOf(analysisId));
            Path outputsDir = Files.exists(archiveDir) ? archiveDir.resolve("outputs") : userDir.resolve("outputs");
            Path dataDir = Files.exists(archiveDir) ? archiveDir.resolve("data") : userDir.resolve("data");

            ByteArrayOutputStream baos = new ByteArrayOutputStream();
            try (ZipOutputStream zos = new ZipOutputStream(baos, StandardCharsets.UTF_8)) {
                // 2.1 analysis_result.json：优先 archive 根目录；否则从 outputs；再否则从 DB
                Path archivedResult = archiveDir.resolve("analysis_result.json");
                Path outputsResult = outputsDir.resolve("analysis_result.json");
                if (Files.exists(archivedResult)) {
                    addFileToZip(zos, archivedResult, "analysis_result.json");
                } else if (Files.exists(outputsResult)) {
                    addFileToZip(zos, outputsResult, "analysis_result.json");
                } else if (record.getAnalysisResult() != null) {
                    addBytesToZip(zos, record.getAnalysisResult().getBytes(StandardCharsets.UTF_8), "analysis_result.json");
                }

                // 2.2 outputs/（与 /analysis/download 一致：根目录下放 disrupt/... 等）
                String[] metricDirs = {"disrupt", "interdisciplinary", "novelty", "theme", "topic", "keywords"};
                for (String dir : metricDirs) {
                    Path metricPath = outputsDir.resolve(dir);
                    if (Files.exists(metricPath) && Files.isDirectory(metricPath)) {
                        Files.walk(metricPath)
                            .filter(Files::isRegularFile)
                            .forEach(p -> {
                                try {
                                    String entryName = dir + "/" + p.getFileName().toString();
                                    addFileToZip(zos, p, entryName);
                                } catch (IOException e) {
                                    System.err.println("Failed to add file to zip: " + p);
                                }
                            });
                    }
                }

                // 2.3 data/*.csv
                if (Files.exists(dataDir) && Files.isDirectory(dataDir)) {
                    Files.list(dataDir)
                        .filter(Files::isRegularFile)
                        .filter(p -> p.toString().toLowerCase().endsWith(".csv"))
                        .forEach(p -> {
                            try {
                                addFileToZip(zos, p, "data/" + p.getFileName().toString());
                            } catch (IOException e) {
                                System.err.println("Failed to add data file to zip: " + p);
                            }
                        });
                }

                // 3) journal_details/*.html（不含 AI）
                addJournalDetailsHtml(zos, analysisId);
            }

            byte[] zipBytes = baos.toByteArray();
            String ts = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
            String zipFilename = "report_" + analysisId + "_" + ts + ".zip";

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.APPLICATION_OCTET_STREAM);
            headers.setContentDispositionFormData("attachment", zipFilename);
            headers.setContentLength(zipBytes.length);

            return ResponseEntity.ok().headers(headers).body(zipBytes);
        } catch (Exception e) {
            System.err.println("Report download failed: " + e.getMessage());
            e.printStackTrace();

            HttpHeaders headers = new HttpHeaders();
            headers.setContentType(MediaType.TEXT_PLAIN);
            String msg = "Report download failed: " + e.getMessage();
            return ResponseEntity.status(500).headers(headers).body(msg.getBytes(StandardCharsets.UTF_8));
        }
    }

    private void addJournalDetailsHtml(ZipOutputStream zos, long analysisId) throws IOException {
        List<String> journals = userJournalMetricsDAO.listJournalsByAnalysis(analysisId);
        if (journals == null || journals.isEmpty()) {
            // 没有明细也不报错：只是不附带期刊详情页
            return;
        }

        // 生成唯一、安全的文件名，防止同名/截断导致的重复 ZipEntry
        Map<String, String> safeNameMap = new java.util.LinkedHashMap<>(); // preserve order
        java.util.Set<String> used = new java.util.HashSet<>();
        for (String j : journals) {
            String base = toSafeFilename(j);
            String unique = toUniqueName(base, used);
            used.add(unique);
            safeNameMap.put(j, unique);
        }

        String indexHtml = buildJournalIndexHtml(safeNameMap);
        addBytesToZip(zos, indexHtml.getBytes(StandardCharsets.UTF_8), "journal_details/index.html");

        for (String journal : journals) {
            List<UserJournalMetricsRow> rows = userJournalMetricsDAO.findByAnalysisAndJournalOrderByYearDesc(analysisId, journal);
            if (rows == null || rows.isEmpty()) {
                continue;
            }

            String html = buildJournalDetailHtml(journal, rows);
            String safe = safeNameMap.get(journal);
            addBytesToZip(zos, html.getBytes(StandardCharsets.UTF_8), "journal_details/" + safe + ".html");
        }
    }

    private static String buildJournalIndexHtml(Map<String, String> journalToSafe) {
        StringBuilder sb = new StringBuilder();
        sb.append("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"/>");
        sb.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"/>");
        sb.append("<title>期刊详情页索引</title>");
        sb.append("<style>body{font-family:Arial,Helvetica,sans-serif;padding:18px;}a{color:#2563eb;text-decoration:none;}a:hover{text-decoration:underline;}li{margin:6px 0;} .muted{color:#6b7280;}</style>");
        sb.append("</head><body>");
        sb.append("<h1>期刊详情页（静态导出）</h1>");
        sb.append("<div class=\"muted\">说明：该目录下的详情页不包含 AI 分析部分，仅包含指标与关键词等结构化数据。</div>");
        sb.append("<ul>");
        for (Map.Entry<String, String> e : journalToSafe.entrySet()) {
            String j = e.getKey();
            String safe = e.getValue();
            sb.append("<li><a href=\"").append(safe).append(".html\">").append(escapeHtml(j)).append("</a></li>");
        }
        sb.append("</ul>");
        sb.append("</body></html>");
        return sb.toString();
    }

    private static String buildJournalDetailHtml(String journal, List<UserJournalMetricsRow> rows) {
        UserJournalMetricsRow head = rows.get(0);

        StringBuilder sb = new StringBuilder();
        sb.append("<!DOCTYPE html><html lang=\"zh-CN\"><head><meta charset=\"UTF-8\"/>");
        sb.append("<meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\"/>");
        sb.append("<title>期刊详情 - ").append(escapeHtml(journal)).append("</title>");
        sb.append("<style>");
        sb.append("body{font-family:Arial,Helvetica,sans-serif;padding:18px;line-height:1.55;}");
        sb.append("h1{margin:0 0 6px 0;} .muted{color:#6b7280;} .card{border:1px solid #e5e7eb;border-radius:10px;padding:14px;margin-top:12px;}");
        sb.append("table{border-collapse:collapse;width:100%;margin-top:10px;} th,td{border:1px solid #e5e7eb;padding:8px;text-align:left;font-size:14px;} th{background:#f9fafb;}");
        sb.append(".k{display:inline-block;background:#eef2ff;border:1px solid #e0e7ff;color:#1d4ed8;padding:2px 8px;border-radius:999px;margin:4px 6px 0 0;font-size:13px;}");
        sb.append("a{color:#2563eb;text-decoration:none;}a:hover{text-decoration:underline;}");
        sb.append("</style></head><body>");

        sb.append("<a href=\"index.html\">← 返回索引</a>");
        sb.append("<h1>").append(escapeHtml(journal)).append("</h1>");
        if (head.getCategory() != null && !head.getCategory().isBlank()) {
            sb.append("<div class=\"muted\">分类：").append(escapeHtml(head.getCategory())).append("</div>");
        }

        sb.append("<div class=\"card\"><h2 style=\"margin:0 0 8px 0;\">Top5 关键词（分年）</h2>");
        appendKeywordBlock(sb, "2021", head.getTopKeywords2021());
        appendKeywordBlock(sb, "2022", head.getTopKeywords2022());
        appendKeywordBlock(sb, "2023", head.getTopKeywords2023());
        appendKeywordBlock(sb, "2024", head.getTopKeywords2024());
        appendKeywordBlock(sb, "2025", head.getTopKeywords2025());
        sb.append("</div>");

        sb.append("<div class=\"card\"><h2 style=\"margin:0 0 8px 0;\">指标明细（按年）</h2>");
        sb.append("<table><thead><tr>");
        sb.append("<th>年份</th><th>论文数</th><th>Disruption</th><th>Interdisciplinary</th><th>Novelty</th><th>Topic</th><th>Theme</th><th>Hot Response</th>");
        sb.append("</tr></thead><tbody>");
        for (UserJournalMetricsRow r : rows) {
            sb.append("<tr>");
            sb.append("<td>").append(r.getYear() == null ? "" : r.getYear()).append("</td>");
            sb.append("<td>").append(r.getPaperCount() == null ? "" : r.getPaperCount()).append("</td>");
            sb.append("<td>").append(fmt(r.getDisruption())).append("</td>");
            sb.append("<td>").append(fmt(r.getInterdisciplinary())).append("</td>");
            sb.append("<td>").append(fmt(r.getNovelty())).append("</td>");
            sb.append("<td>").append(fmt(r.getTopic())).append("</td>");
            sb.append("<td>").append(fmt(r.getThemeConcentration())).append("</td>");
            sb.append("<td>").append(fmt(r.getHotResponse())).append("</td>");
            sb.append("</tr>");
        }
        sb.append("</tbody></table></div>");

        sb.append("</body></html>");
        return sb.toString();
    }

    private static void appendKeywordBlock(StringBuilder sb, String year, String keywords) {
        sb.append("<div style=\"margin-top:10px;\"><div class=\"muted\" style=\"margin-bottom:6px;\">"
            + escapeHtml(year) + "</div>");
        if (keywords == null || keywords.isBlank()) {
            sb.append("<div class=\"muted\">（无）</div></div>");
            return;
        }
        String[] parts = keywords.split(",");
        for (String p : parts) {
            String k = p == null ? "" : p.trim();
            if (!k.isEmpty()) {
                sb.append("<span class=\"k\">").append(escapeHtml(k)).append("</span>");
            }
        }
        sb.append("</div>");
    }

    private static String fmt(Double v) {
        if (v == null) return "";
        // 保持简洁，不做复杂格式化
        return String.valueOf(v);
    }

    private static String escapeHtml(String s) {
        if (s == null) return "";
        return s
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
            .replace("\"", "&quot;")
            .replace("'", "&#39;");
    }

    private static String toSafeFilename(String name) {
        if (name == null || name.isBlank()) {
            return "journal";
        }
        String safe = name.trim().replaceAll("[^a-zA-Z0-9\\u4e00-\\u9fa5]+", "_");
        safe = safe.replaceAll("_+", "_");
        if (safe.length() > 80) {
            safe = safe.substring(0, 80);
        }
        if (safe.isBlank()) safe = "journal";
        return safe;
    }

    private static String toUniqueName(String base, java.util.Set<String> used) {
        if (!used.contains(base)) return base;
        int i = 2;
        while (true) {
            String candidate = base + "_" + i;
            if (!used.contains(candidate)) {
                return candidate;
            }
            i++;
        }
    }

    private static void addFileToZip(ZipOutputStream zos, Path file, String entryName) throws IOException {
        ZipEntry entry = new ZipEntry(entryName);
        zos.putNextEntry(entry);
        Files.copy(file, zos);
        zos.closeEntry();
    }

    private static void addBytesToZip(ZipOutputStream zos, byte[] bytes, String entryName) throws IOException {
        ZipEntry entry = new ZipEntry(entryName);
        zos.putNextEntry(entry);
        zos.write(bytes);
        zos.closeEntry();
    }

    // 供 AnalysisController 复用：归档 outputs/data 到 reports/{analysisId}/
    static void archiveAnalysisSnapshot(Path userDir, long analysisId, String analysisJson) {
        if (userDir == null) return;
        try {
            Path archiveDir = userDir.resolve("reports").resolve(String.valueOf(analysisId));
            deleteDirectoryIfExists(archiveDir);
            Files.createDirectories(archiveDir);

            if (analysisJson != null && !analysisJson.isBlank()) {
                Files.writeString(archiveDir.resolve("analysis_result.json"), analysisJson, StandardCharsets.UTF_8);
            }

            Path outputsDir = userDir.resolve("outputs");
            if (Files.exists(outputsDir) && Files.isDirectory(outputsDir)) {
                copyDirectory(outputsDir, archiveDir.resolve("outputs"));
            }

            Path dataDir = userDir.resolve("data");
            if (Files.exists(dataDir) && Files.isDirectory(dataDir)) {
                copyDirectory(dataDir, archiveDir.resolve("data"));
            }
        } catch (Exception e) {
            System.err.println("[WARN] Failed to archive analysis snapshot: " + e.getMessage());
        }
    }

    private static void copyDirectory(Path src, Path dst) throws IOException {
        Files.walkFileTree(src, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult preVisitDirectory(Path dir, BasicFileAttributes attrs) throws IOException {
                Path target = dst.resolve(src.relativize(dir).toString());
                Files.createDirectories(target);
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                Path target = dst.resolve(src.relativize(file).toString());
                Files.copy(file, target, StandardCopyOption.REPLACE_EXISTING);
                return FileVisitResult.CONTINUE;
            }
        });
    }

    private static void deleteDirectoryIfExists(Path dir) throws IOException {
        if (dir == null || !Files.exists(dir)) return;
        Files.walkFileTree(dir, new SimpleFileVisitor<>() {
            @Override
            public FileVisitResult visitFile(Path file, BasicFileAttributes attrs) throws IOException {
                Files.deleteIfExists(file);
                return FileVisitResult.CONTINUE;
            }

            @Override
            public FileVisitResult postVisitDirectory(Path d, IOException exc) throws IOException {
                Files.deleteIfExists(d);
                return FileVisitResult.CONTINUE;
            }
        });
    }
}
