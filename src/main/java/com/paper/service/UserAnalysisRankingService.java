package com.paper.service;

import java.io.BufferedReader;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageImpl;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.paper.model.JournalMetrics;
import com.paper.model.JournalRankingMetric;

@Service
public class UserAnalysisRankingService {

    private final ObjectMapper objectMapper;

    public UserAnalysisRankingService(ObjectMapper objectMapper) {
        this.objectMapper = objectMapper;
    }

    public record ParsedAnalysisDataset(int yearMax, List<JournalMetrics> rows) {}

    public ParsedAnalysisDataset parseAnalysisResult(String analysisJson) {
        if (analysisJson == null || analysisJson.isBlank()) {
            return new ParsedAnalysisDataset(0, List.of());
        }

        try {
            JsonNode root = objectMapper.readTree(analysisJson);
            int yearMax = root.path("year_range").path("max").asInt(0);

            Map<String, MutableMetrics> acc = new HashMap<>();

            // 先把“小样本期刊”种到列表里：这些期刊会在 Python 计算指标前被剔除，但仍需要在最终期刊列表里显示并备注
            // 兼容两种来源：analysis_result.json 内嵌 small_sample_journals 或 outputs/small_sample_journals.csv
            seedSmallSampleJournals(acc, root);

            // 优先从 outputs/*.csv 加载完整榜单（analysis_result.json 里通常只有 TopN）
            // 关键修复：逐项回退（避免“部分 CSV 读取失败 => 该指标全是空值”）

            Path disruptCsv = resolvePathFromAnalysis(root, "disruption_file");
            if (!mergePercentMetricFromCsv(acc, disruptCsv, "disruption", "percent_score", "n_papers")) {
                // 兜底：旧/异常输出可能没有 percent_score，但有 percent_score_raw
                if (!mergePercentMetricFromCsv(acc, disruptCsv, "disruption", "percent_score_raw", "n_papers")) {
                    mergePercentMetric(acc, root.path("disruption"), "disruption", "percent_score", "n_papers");
                }
            }

            Path noveltyCsv = resolvePathFromAnalysis(root, "novelty_file");
            if (!mergePercentMetricFromCsv(acc, noveltyCsv, "novelty", "percent_score", "paper_count")) {
                // 兜底：如果 percent_score 解析失败，至少用 percent_score_raw 或 novelty_score 填充（避免整列空）
                if (!mergePercentMetricFromCsv(acc, noveltyCsv, "novelty", "percent_score_raw", "paper_count")) {
                    if (!mergePercentMetricFromCsv(acc, noveltyCsv, "novelty", "novelty_score", "paper_count")) {
                        mergePercentMetric(acc, root.path("novelty"), "novelty", "percent_score", "paper_count");
                    }
                }
            }

            Path interCsv = resolvePathFromAnalysis(root, "interdisciplinary_file");
            if (!mergePercentMetricFromCsv(acc, interCsv, "interdisciplinary", "percent_score", "paper_count")) {
                mergePercentMetric(acc, root.path("interdisciplinary"), "interdisciplinary", "percent_score", "paper_count");
            }

            Path topicCsv = resolvePathFromAnalysis(root, "topic_file");
            if (!mergePercentMetricFromCsv(acc, topicCsv, "topic", "percent_score", "paper_count")) {
                mergePercentMetric(acc, root.path("topic"), "topic", "percent_score", "paper_count");
            }

            Path themeCsv = resolvePathFromAnalysis(root, "theme_file");
            if (!mergeThemeFromCsv(acc, themeCsv)) {
                mergeTheme(acc, root.path("theme"));
            }

            List<JournalMetrics> rows = new ArrayList<>(acc.size());
            for (MutableMetrics m : acc.values()) {
                JournalMetrics jm = new JournalMetrics();
                jm.setId(0L);
                jm.setJournal(m.journal);
                jm.setYear(yearMax);
                if (m.smallSample) {
                    // 小样本：按需求在指标计算前剔除，因此这里不展示任何指标分值（保留 null）
                    jm.setDisruption(null);
                    jm.setNovelty(null);
                    jm.setInterdisciplinary(null);
                    jm.setTopic(null);
                    jm.setThemeConcentration(null);
                    jm.setHotResponse(null);
                } else {
                    // 非小样本：避免“缺失值整列显示为空”，统一把缺失视为 0 分
                    jm.setDisruption(m.disruption != null ? m.disruption : 0.0);
                    jm.setNovelty(m.novelty != null ? m.novelty : 0.0);
                    jm.setInterdisciplinary(m.interdisciplinary != null ? m.interdisciplinary : 0.0);
                    jm.setTopic(m.topic != null ? m.topic : 0.0);
                    jm.setThemeConcentration(m.themeConcentration != null ? m.themeConcentration : 0.0);
                    jm.setHotResponse(m.hotResponse != null ? m.hotResponse : 0.0);
                }
                jm.setPaperCount(m.paperCount);
                jm.setCategory(null);
                jm.setTopKeywords2021(m.topKeywords2021);
                jm.setTopKeywords2022(m.topKeywords2022);
                jm.setTopKeywords2023(m.topKeywords2023);
                jm.setTopKeywords2024(m.topKeywords2024);
                jm.setTopKeywords2025(m.topKeywords2025);
                rows.add(jm);
            }

            return new ParsedAnalysisDataset(yearMax, rows);
        } catch (Exception e) {
            System.err.println("Failed to parse analysis_result JSON: " + e.getMessage());
            return new ParsedAnalysisDataset(0, List.of());
        }
    }

    private void seedSmallSampleJournals(Map<String, MutableMetrics> acc, JsonNode root) {
        if (acc == null || root == null) {
            return;
        }

        // 1) JSON 内嵌列表
        JsonNode arr = root.path("small_sample_journals");
        if (arr != null && arr.isArray()) {
            for (JsonNode item : arr) {
                String journal = item.path("journal").asText(null);
                if (journal == null || journal.isBlank()) {
                    continue;
                }
                Integer cnt = item.path("paper_count").isNumber() ? item.path("paper_count").intValue() : null;
                MutableMetrics m = acc.computeIfAbsent(journal, MutableMetrics::new);
                m.smallSample = true;
                if (cnt != null) {
                    m.paperCount = (m.paperCount == null) ? cnt : Math.max(m.paperCount, cnt);
                }
            }
            // 若有内嵌列表，直接返回（避免重复读 CSV）
            if (acc.size() > 0) {
                return;
            }
        }

        // 2) outputs/small_sample_journals.csv
        Path csvPath = resolvePathFromAnalysis(root, "small_sample_file");
        if (csvPath == null || !Files.exists(csvPath) || !Files.isRegularFile(csvPath)) {
            return;
        }

        CSVFormat format = CSVFormat.DEFAULT.builder()
            .setHeader()
            .setSkipHeaderRecord(true)
            .setIgnoreEmptyLines(true)
            .setQuote('"')
            .build();

        try (BufferedReader reader = Files.newBufferedReader(csvPath, StandardCharsets.UTF_8);
             CSVParser parser = new CSVParser(reader, format)) {

            Map<String, String> headerLowerToActual = new HashMap<>();
            for (String h : parser.getHeaderMap().keySet()) {
                if (h == null) continue;
                String key = normalizeHeaderKey(h);
                if (!key.isBlank()) headerLowerToActual.put(key, h);
            }

            for (CSVRecord record : parser) {
                String journal = getColumn(record, headerLowerToActual, "journal", "Journal");
                if (journal == null || journal.isBlank()) continue;
                Integer cnt = parseInt(getColumn(record, headerLowerToActual, "paper_count"));
                MutableMetrics m = acc.computeIfAbsent(journal, MutableMetrics::new);
                m.smallSample = true;
                if (cnt != null) {
                    m.paperCount = (m.paperCount == null) ? cnt : Math.max(m.paperCount, cnt);
                }
            }
        } catch (Exception e) {
            System.err.println("Failed to read small_sample CSV: " + csvPath + " - " + e.getMessage());
        }
    }

    private Path resolvePathFromAnalysis(JsonNode root, String fieldName) {
        if (root == null || fieldName == null) {
            return null;
        }
        String raw = root.path(fieldName).asText(null);
        if (raw == null || raw.isBlank()) {
            return null;
        }
        // 兼容 Windows/Unix 分隔符
        String normalized = raw.replace('\\', '/');
        Path p;
        try {
            p = Paths.get(normalized);
        } catch (Exception e) {
            return null;
        }
        if (!p.isAbsolute()) {
            Path base = Paths.get("").toAbsolutePath().normalize();
            p = base.resolve(p).normalize();
            // 兜底：如果工作目录不是项目根目录（bootRun/部署环境常见），尝试向上查找包含 uploads/ 的目录
            if (!Files.exists(p)) {
                Path probe = base;
                for (int i = 0; i < 8 && probe != null; i++) {
                    if (Files.isDirectory(probe.resolve("uploads"))) {
                        Path candidate = probe.resolve(normalized).normalize();
                        if (Files.exists(candidate)) {
                            p = candidate;
                            break;
                        }
                    }
                    probe = probe.getParent();
                }
            }
        }
        return p;
    }

    private boolean mergePercentMetricFromCsv(
        Map<String, MutableMetrics> acc,
        Path csvPath,
        String metricKey,
        String percentField,
        String countField
    ) {
        if (csvPath == null || !Files.exists(csvPath) || !Files.isRegularFile(csvPath)) {
            return false;
        }

        CSVFormat format = CSVFormat.DEFAULT.builder()
            .setHeader()
            .setSkipHeaderRecord(true)
            .setIgnoreEmptyLines(true)
            .setQuote('"')
            .build();

        try (BufferedReader reader = Files.newBufferedReader(csvPath, StandardCharsets.UTF_8);
             CSVParser parser = new CSVParser(reader, format)) {

            Map<String, String> headerLowerToActual = new HashMap<>();
            for (String h : parser.getHeaderMap().keySet()) {
                if (h == null) {
                    continue;
                }
                String key = normalizeHeaderKey(h);
                if (!key.isBlank()) {
                    headerLowerToActual.put(key, h);
                }
            }

            for (CSVRecord record : parser) {
                String journal = getColumn(record, headerLowerToActual, "journal", "Journal");
                if (journal == null || journal.isBlank()) {
                    continue;
                }
                MutableMetrics m = acc.computeIfAbsent(journal, MutableMetrics::new);

                Double val = parseDouble(getColumn(record, headerLowerToActual, percentField));
                Integer count = parseInt(getColumn(record, headerLowerToActual, countField, "paper_count", "n_papers"));
                if (count != null) {
                    m.paperCount = (m.paperCount == null) ? count : Math.max(m.paperCount, count);
                }

                switch (metricKey) {
                    case "disruption" -> m.disruption = val;
                    case "novelty" -> m.novelty = val;
                    case "interdisciplinary" -> m.interdisciplinary = val;
                    case "topic" -> m.topic = val;
                    default -> {
                    }
                }
            }

            return true;
        } catch (Exception e) {
            System.err.println("Failed to read metric CSV: " + csvPath + " - " + e.getMessage());
            return false;
        }
    }

    private boolean mergeThemeFromCsv(Map<String, MutableMetrics> acc, Path csvPath) {
        if (csvPath == null || !Files.exists(csvPath) || !Files.isRegularFile(csvPath)) {
            return false;
        }

        CSVFormat format = CSVFormat.DEFAULT.builder()
            .setHeader()
            .setSkipHeaderRecord(true)
            .setIgnoreEmptyLines(true)
            .setQuote('"')
            .build();

        try (BufferedReader reader = Files.newBufferedReader(csvPath, StandardCharsets.UTF_8);
             CSVParser parser = new CSVParser(reader, format)) {

            Map<String, String> headerLowerToActual = new HashMap<>();
            for (String h : parser.getHeaderMap().keySet()) {
                if (h == null) {
                    continue;
                }
                String key = normalizeHeaderKey(h);
                if (!key.isBlank()) {
                    headerLowerToActual.put(key, h);
                }
            }

            for (CSVRecord record : parser) {
                String journal = getColumn(record, headerLowerToActual, "journal", "Journal");
                if (journal == null || journal.isBlank()) {
                    continue;
                }
                MutableMetrics m = acc.computeIfAbsent(journal, MutableMetrics::new);

                // 兼容：部分历史/异常输出可能只有 *_raw，没有最终百分位字段
                Double themeConcentration = parseDouble(getColumn(record, headerLowerToActual, "theme_concentration"));
                if (themeConcentration == null) {
                    themeConcentration = parseDouble(getColumn(record, headerLowerToActual, "theme_concentration_raw"));
                }
                Double hotResponse = parseDouble(getColumn(record, headerLowerToActual, "hot_response"));
                if (hotResponse == null) {
                    hotResponse = parseDouble(getColumn(record, headerLowerToActual, "hot_response_raw"));
                }
                m.themeConcentration = themeConcentration;
                m.hotResponse = hotResponse;

                m.topKeywords2021 = normalizeKeywordListString(getColumn(record, headerLowerToActual, "top_keywords_2021"));
                m.topKeywords2022 = normalizeKeywordListString(getColumn(record, headerLowerToActual, "top_keywords_2022"));
                m.topKeywords2023 = normalizeKeywordListString(getColumn(record, headerLowerToActual, "top_keywords_2023"));
                m.topKeywords2024 = normalizeKeywordListString(getColumn(record, headerLowerToActual, "top_keywords_2024"));
                m.topKeywords2025 = normalizeKeywordListString(getColumn(record, headerLowerToActual, "top_keywords_2025"));
            }

            return true;
        } catch (Exception e) {
            System.err.println("Failed to read theme CSV: " + csvPath + " - " + e.getMessage());
            return false;
        }
    }

    private String normalizeHeaderKey(String header) {
        if (header == null) {
            return "";
        }
        String h = header.trim();
        // 兼容 UTF-8 BOM（Python to_csv(encoding="utf-8-sig") 会在首列 header 前写 BOM）
        if (!h.isEmpty() && h.charAt(0) == '\uFEFF') {
            h = h.substring(1);
        }
        return h.trim().toLowerCase(Locale.ROOT);
    }

    private String getColumn(CSVRecord record, Map<String, String> headerLowerToActual, String... candidates) {
        if (record == null || headerLowerToActual == null || candidates == null) {
            return null;
        }
        for (String c : candidates) {
            if (c == null || c.isBlank()) continue;
            String actual = headerLowerToActual.get(normalizeHeaderKey(c));
            if (actual == null) continue;
            try {
                return record.get(actual);
            } catch (Exception ignored) {
            }
        }
        return null;
    }

    private Double parseDouble(String s) {
        if (s == null) return null;
        String t = s.trim();
        if (t.isEmpty()) return null;
        try {
            return Double.parseDouble(t);
        } catch (Exception e) {
            return null;
        }
    }

    private Integer parseInt(String s) {
        if (s == null) return null;
        String t = s.trim();
        if (t.isEmpty()) return null;
        try {
            return Integer.parseInt(t);
        } catch (Exception e) {
            return null;
        }
    }

    private String normalizeKeywordListString(String raw) {
        if (raw == null) return null;
        String s = raw.trim();
        if (s.isEmpty() || "[]".equals(s)) return null;
        // 兼容 Python 列表字符串：['a', 'b']
        if (s.startsWith("[") && s.endsWith("]")) {
            s = s.substring(1, s.length() - 1).trim();
            if (s.isEmpty()) return null;
            String[] parts = s.split(",");
            StringBuilder sb = new StringBuilder();
            for (String p : parts) {
                String x = p.trim();
                if (x.startsWith("'") && x.endsWith("'") && x.length() >= 2) {
                    x = x.substring(1, x.length() - 1);
                }
                if (x.startsWith("\"") && x.endsWith("\"") && x.length() >= 2) {
                    x = x.substring(1, x.length() - 1);
                }
                x = x.trim();
                if (x.isEmpty()) continue;
                if (sb.length() > 0) sb.append(", ");
                sb.append(x);
            }
            return sb.length() == 0 ? null : sb.toString();
        }
        return s;
    }

    public Page<JournalMetrics> buildRankingsPage(
        List<JournalMetrics> allRows,
        JournalRankingMetric metric,
        String q,
        Pageable pageable
    ) {
        if (allRows == null || allRows.isEmpty()) {
            return new PageImpl<>(List.of(), pageable, 0);
        }
        JournalRankingMetric safeMetric = metric == null ? JournalRankingMetric.FRONTIER : metric;

        String query = (q == null) ? "" : q.trim();
        final String queryLower = query.toLowerCase(Locale.ROOT);

        List<JournalMetrics> filtered = new ArrayList<>(allRows.size());
        for (JournalMetrics row : allRows) {
            if (row == null || row.getJournal() == null) continue;
            if (!queryLower.isEmpty() && !row.getJournal().toLowerCase(Locale.ROOT).contains(queryLower)) {
                continue;
            }
            filtered.add(row);
        }

        filtered.sort((a, b) -> {
            double va = safeMetric.computeValue(a);
            double vb = safeMetric.computeValue(b);
            int cmp = Double.compare(vb, va); // desc
            if (cmp != 0) return cmp;
            String ja = a.getJournal() == null ? "" : a.getJournal();
            String jb = b.getJournal() == null ? "" : b.getJournal();
            return ja.compareToIgnoreCase(jb);
        });

        int start = (int) pageable.getOffset();
        int end = Math.min(start + pageable.getPageSize(), filtered.size());
        if (start >= filtered.size()) {
            return new PageImpl<>(List.of(), pageable, filtered.size());
        }

        return new PageImpl<>(filtered.subList(start, end), pageable, filtered.size());
    }

    private void mergePercentMetric(
        Map<String, MutableMetrics> acc,
        JsonNode arrayNode,
        String metricKey,
        String percentField,
        String countField
    ) {
        if (arrayNode == null || !arrayNode.isArray()) {
            return;
        }

        for (JsonNode item : arrayNode) {
            String journal = item.path("journal").asText(null);
            if (journal == null || journal.isBlank()) {
                continue;
            }
            MutableMetrics m = acc.computeIfAbsent(journal, MutableMetrics::new);

            Double val = item.path(percentField).isNumber() ? item.path(percentField).asDouble() : null;
            Integer count = null;
            JsonNode c = item.get(countField);
            if (c != null && c.isNumber()) {
                count = c.intValue();
            }
            if (count != null) {
                m.paperCount = (m.paperCount == null) ? count : Math.max(m.paperCount, count);
            }

            switch (metricKey) {
                case "disruption" -> m.disruption = val;
                case "novelty" -> m.novelty = val;
                case "interdisciplinary" -> m.interdisciplinary = val;
                case "topic" -> m.topic = val;
                default -> {
                }
            }
        }
    }

    private void mergeTheme(Map<String, MutableMetrics> acc, JsonNode arrayNode) {
        if (arrayNode == null || !arrayNode.isArray()) {
            return;
        }

        for (JsonNode item : arrayNode) {
            String journal = item.path("journal").asText(null);
            if (journal == null || journal.isBlank()) {
                continue;
            }
            MutableMetrics m = acc.computeIfAbsent(journal, MutableMetrics::new);

            Double themeConcentration = item.path("theme_concentration").isNumber() ? item.path("theme_concentration").asDouble() : null;
            if (themeConcentration == null && item.path("theme_concentration_raw").isNumber()) {
                themeConcentration = item.path("theme_concentration_raw").asDouble();
            }
            Double hotResponse = item.path("hot_response").isNumber() ? item.path("hot_response").asDouble() : null;
            if (hotResponse == null && item.path("hot_response_raw").isNumber()) {
                hotResponse = item.path("hot_response_raw").asDouble();
            }
            m.themeConcentration = themeConcentration;
            m.hotResponse = hotResponse;

            m.topKeywords2021 = joinStringArray(item.path("top_keywords_2021"));
            m.topKeywords2022 = joinStringArray(item.path("top_keywords_2022"));
            m.topKeywords2023 = joinStringArray(item.path("top_keywords_2023"));
            m.topKeywords2024 = joinStringArray(item.path("top_keywords_2024"));
            m.topKeywords2025 = joinStringArray(item.path("top_keywords_2025"));
        }
    }

    private String joinStringArray(JsonNode n) {
        if (n == null || !n.isArray() || n.isEmpty()) {
            return null;
        }
        StringBuilder sb = new StringBuilder();
        for (JsonNode v : n) {
            String s = v.asText(null);
            if (s == null || s.isBlank()) continue;
            if (sb.length() > 0) sb.append(", ");
            sb.append(s.trim());
        }
        return sb.length() == 0 ? null : sb.toString();
    }

    private static final class MutableMetrics {
        private final String journal;

        private boolean smallSample;

        private Double disruption;
        private Double novelty;
        private Double interdisciplinary;
        private Double topic;
        private Double themeConcentration;
        private Double hotResponse;
        private Integer paperCount;

        private String topKeywords2021;
        private String topKeywords2022;
        private String topKeywords2023;
        private String topKeywords2024;
        private String topKeywords2025;

        private MutableMetrics(String journal) {
            this.journal = journal;
        }
    }
}
