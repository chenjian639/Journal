package com.paper.service;

import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.paper.model.JournalMetrics;
import com.paper.model.JournalMetricsLike;
import com.paper.model.JournalRankingMetric;
import com.paper.model.UserSurvey;
import com.paper.repository.JournalMetricsRepository;
import com.paper.utils.AIClient;

/**
 * 期刊服务层 - 业务逻辑处理
 */
@Service
public class JournalService {
    private final JournalMetricsRepository repository;
    private final AIClient aiClient;
    private static final ObjectMapper objectMapper = new ObjectMapper();
    
    @Autowired
    public JournalService(JournalMetricsRepository repository, AIClient aiClient) {
        this.repository = repository;
        this.aiClient = aiClient;
    }
    
    // Repository访问方法
    public List<JournalMetrics> fetchJournals() {
        return repository.findAllLatestYears();
    }
    
    public List<JournalMetrics> fetchJournalRows(String journal) {
        return repository.findByJournalOrderByYearDesc(journal);
    }
    
    public List<String> fetchJournalNames() {
        return repository.findAllJournalNames();
    }
    
    public List<JournalMetrics> fetchLatestJournalRows() {
        return repository.findAllLatestYears();
    }

    public List<Integer> fetchAvailableYearsDesc() {
        return repository.findDistinctYearsDesc();
    }

    public List<String> fetchAvailableCategories() {
        return repository.findDistinctCategories();
    }

    public Page<JournalMetrics> fetchRankings(JournalRankingMetric metric, Integer yearOrNullForLatest,
                                             String categoryOrNull, String qOrNull, Pageable pageable) {
        final String metricId = (metric == null ? JournalRankingMetric.FRONTIER : metric).getId();
        if (yearOrNullForLatest == null) {
            return repository.findLatestRankings(metricId, categoryOrNull, qOrNull, pageable);
        }
        return repository.findYearRankings(metricId, yearOrNullForLatest, categoryOrNull, qOrNull, pageable);
    }
    
    public JournalMetrics fetchLatestRowForJournal(String journal) {
        return repository.findLatestByJournal(journal).orElse(null);
    }
    
    public Map<String, JournalMetrics> fetchLatestRowsForTwoJournals(String journalA, String journalB) {
        List<JournalMetrics> rows = repository.findLatestByTwoJournals(journalA, journalB);
        Map<String, JournalMetrics> result = new HashMap<>();
        for (JournalMetrics row : rows) {
            result.put(row.getJournal(), row);
        }
        return result;
    }
    
    /**
     * 构建雷达图数据
     */
    public Map<String, Object> buildRadarFromRow(JournalMetricsLike row) {
        if (row == null) {
            return new HashMap<>();
        }
        
        double disruption = toDouble(row.getDisruption());
        double novelty = toDouble(row.getNovelty());
        double interdisciplinary = toDouble(row.getInterdisciplinary());
        double themeConcentration = toDouble(row.getThemeConcentration());
        double topic = toDouble(row.getTopic());
        double hotResponse = toDouble(row.getHotResponse());
        
        Map<String, Object> radar = new HashMap<>();
        radar.put("labels", List.of("内容前沿性", "学科开放性", "主题集中度", "主题多样性", "热点响应度"));
        radar.put("values", List.of(
            disruption + novelty,
            interdisciplinary,
            themeConcentration,
            topic,
            hotResponse
        ));
        radar.put("max", 200);
        
        Map<String, Object> raw = new HashMap<>();
        raw.put("disruption", disruption);
        raw.put("novelty", novelty);
        raw.put("interdisciplinary", interdisciplinary);
        raw.put("theme_concentration", themeConcentration);
        raw.put("topic", topic);
        raw.put("hot_response", hotResponse);
        raw.put("paper_count", toDouble(row.getPaperCount()));
        radar.put("raw", raw);
        
        return radar;
    }
    
    /**
     * 构建规则评语
     */
    public Map<String, String> buildCommentsFromRow(JournalMetricsLike row) {
        if (row == null) {
            return new HashMap<>();
        }
        
        double disruption = toDouble(row.getDisruption());
        double novelty = toDouble(row.getNovelty());
        double interdisciplinary = toDouble(row.getInterdisciplinary());
        double themeConcentration = toDouble(row.getThemeConcentration());
        double topic = toDouble(row.getTopic());
        double hotResponse = toDouble(row.getHotResponse());
        
        Map<String, String> comments = new HashMap<>();
        
        // 1) 内容前沿性：新颖性 × 颠覆性
        comments.put("内容前沿性", pickQuadrantComment(
            isHigh(novelty), isHigh(disruption),
            "\"潮流引领者\"：专注于发布最新、最具突破性的研究。",
            "\"快速追踪者\"：紧密跟随热点，发表前沿但不一定是范式颠覆的工作。",
            "\"深度颠覆者\"：不追逐表面热点，但发表的文章可能从根本上改变某个经典领域的认知。（较少见）",
            "\"经典积淀者\"：专注于夯实基础、验证和完善现有理论。\""
        ));
        
        // 2) 学科开放性：跨学科性 × 主题多样性
        comments.put("学科开放性", pickQuadrantComment(
            isHigh(interdisciplinary), isHigh(topic),
            "\"开放枢纽\"：跨学科协作与多方向覆盖并重，适合作为综合交流平台。",
            "\"交叉聚焦者\"：方法/学科上开放，但议题相对聚焦，利于形成清晰的交叉主线。",
            "\"广谱专精者\"：主要在本学科内展开，但覆盖多个子方向，强调领域内的横向延展。",
            "\"窄域深耕者\"：学科边界与议题范围都较收敛，专注核心问题的深挖与迭代。\""
        ));
        
        // 3) 主题画像：主题集中度 × 主题多样性
        comments.put("主题画像", pickQuadrantComment(
            isHigh(themeConcentration), isHigh(topic),
            "\"多核聚集型\"：存在多个强势主题簇，既有聚合中心也保持一定方向广度。",
            "\"专题聚焦型\"：研究范围非常集中，深耕某一两个子领域。",
            "\"领域宽泛型\"：涵盖该学科下多个子方向，研究主题分布更分散。",
            "\"碎片探索型\"：既缺少显著主线、也未形成广覆盖，主题更偏零散尝试与过渡期特征。\""
        ));
        
        // 4) 热点响应度：热点响应度 × 颠覆性
        comments.put("热点响应度", pickQuadrantComment(
            isHigh(hotResponse), isHigh(disruption),
            "\"热点引爆者\"：既能迅速捕捉潮流，也更可能产出具有颠覆性的突破成果。",
            "\"热点追踪者\"：对热门方向反应快，但更多是增量式推进或应用扩展。",
            "\"逆势创新者\"：不依赖热门关键词驱动，但更可能在传统主题上做出颠覆性改写。",
            "\"稳态发展\"：核心关键词稳定、颠覆性相对温和，领域演进更偏渐进完善。\""
        ));
        
        return comments;
    }
    
    /**
     * 构建用户画像雷达图
     */
    public Map<String, Object> buildUserRadar(UserSurvey survey) {
        if (survey == null) {
            return new HashMap<>();
        }
        
        double disruption = toDouble(survey.getDisruption());
        double novelty = toDouble(survey.getNovelty());
        double interdisciplinary = toDouble(survey.getInterdisciplinary());
        double themeConcentration = toDouble(survey.getThemeConcentration());
        double topic = toDouble(survey.getTopic());
        double hotResponse = toDouble(survey.getHotResponse());
        
        Map<String, Object> radar = new HashMap<>();
        radar.put("labels", List.of("内容前沿性", "学科开放性", "主题集中度", "主题多样性", "热点响应度"));
        radar.put("values", List.of(
            disruption + novelty,
            interdisciplinary,
            themeConcentration,
            topic,
            hotResponse
        ));
        radar.put("max", 200);
        
        Map<String, Object> raw = new HashMap<>();
        raw.put("disruption", disruption);
        raw.put("novelty", novelty);
        raw.put("interdisciplinary", interdisciplinary);
        raw.put("theme_concentration", themeConcentration);
        raw.put("topic", topic);
        raw.put("hot_response", hotResponse);
        radar.put("raw", raw);
        
        return radar;
    }
    
    /**
     * 计算用户画像与期刊的相似度
     */
    public double computeSimilarity(Map<String, Object> userRadar, Map<String, Object> journalRadar) {
        @SuppressWarnings("unchecked")
        List<Double> uVals = (List<Double>) userRadar.get("values");
        @SuppressWarnings("unchecked")
        List<Double> jVals = (List<Double>) journalRadar.get("values");
        
        if (uVals == null || jVals == null || uVals.size() != 5 || jVals.size() != 5) {
            return 0.0;
        }
        
        double[] ranges = {200.0, 100.0, 100.0, 100.0, 100.0};
        double diffSum = 0.0;
        for (int i = 0; i < 5; i++) {
            double diff = Math.abs(uVals.get(i) - jVals.get(i)) / ranges[i];
            diffSum += diff;
        }
        
        double sim = 1.0 - (diffSum / 5.0);
        return Math.max(0.0, Math.min(1.0, sim));
    }
    
    /**
     * 解析用户输入的关键词
     */
    public List<String> parseUserKeywords(String raw) {
        if (raw == null || raw.trim().isEmpty()) {
            return new ArrayList<>();
        }
        
        String s = raw.trim();
        String[] separators = {"\n", "\r", "\t", ";", "；", ",", "，", "|", "/"};
        for (String sep : separators) {
            s = s.replace(sep, ",");
        }
        
        String[] parts = s.split(",");
        List<String> result = new ArrayList<>();
        for (String part : parts) {
            String trimmed = part.trim();
            if (!trimmed.isEmpty() && !result.contains(trimmed)) {
                result.add(trimmed);
                if (result.size() >= 20) {
                    break;
                }
            }
        }
        return result;
    }
    
    /**
     * 归一化关键词（小写、去除多余空格）
     */
    public String normalizeKeyword(String keyword) {
        if (keyword == null) return "";
        return String.join(" ", keyword.trim().toLowerCase().split("\\s+"));
    }
    
    /**
     * 从Likert量表（1-5）转换为分数（0-100）
     */
    public double scoresFromLikert(int value) {
        int v = Math.max(1, Math.min(5, value));
        return (v - 1) * 25.0;
    }
    
    /**
     * 选取指定年份的关键词
     */
    public List<String> pickKeywordsForYear(JournalMetricsLike latestRow, int year) {
        Map<Integer, List<String>> kwMap = pickTopKeywords(latestRow);
        if (kwMap.containsKey(year)) {
            return kwMap.get(year);
        }
        // 兜底：从当前年往前找最近非空
        for (int y = year; y >= 2021; y--) {
            List<String> arr = kwMap.get(y);
            if (arr != null && !arr.isEmpty()) {
                return arr;
            }
        }
        return new ArrayList<>();
    }
    
    /**
     * 从最新一行中提取各年份的top_keywords
     */
    public Map<Integer, List<String>> pickTopKeywords(JournalMetricsLike latestRow) {
        if (latestRow == null) {
            return new HashMap<>();
        }
        
        Map<Integer, List<String>> result = new HashMap<>();
        result.put(2021, parseKeywordsValue(latestRow.getTopKeywords2021()));
        result.put(2022, parseKeywordsValue(latestRow.getTopKeywords2022()));
        result.put(2023, parseKeywordsValue(latestRow.getTopKeywords2023()));
        result.put(2024, parseKeywordsValue(latestRow.getTopKeywords2024()));
        result.put(2025, parseKeywordsValue(latestRow.getTopKeywords2025()));
        return result;
    }
    
    /**
     * 解析关键词字段（支持JSON数组、Python字符串表示等）
     */
    private List<String> parseKeywordsValue(String value) {
        if (value == null || value.trim().isEmpty()) {
            return new ArrayList<>();
        }
        
        String s = value.trim();
        
        // 尝试JSON解析
        try {
            JsonNode node = objectMapper.readTree(s);
            if (node.isArray()) {
                List<String> result = new ArrayList<>();
                for (JsonNode item : node) {
                    String keyword = item.asText().trim();
                    if (!keyword.isEmpty()) {
                        result.add(keyword);
                    }
                }
                return result;
            } else if (node.isObject()) {
                // 如果是对象，按值（频次）降序排列
                List<String> result = new ArrayList<>();
                node.fields().forEachRemaining(entry -> {
                    result.add(entry.getKey());
                });
                return result;
            }
        } catch (Exception e) {
            // 不是有效JSON，继续尝试其他方式
        }
        
        // 兜底：按分隔符拆分
        String[] separators = {";", "；", ",", "，", "|", "/"};
        for (String sep : separators) {
            if (s.contains(sep)) {
                String[] parts = s.split(sep);
                List<String> result = new ArrayList<>();
                for (String part : parts) {
                    String trimmed = part.trim();
                    if (!trimmed.isEmpty()) {
                        result.add(trimmed);
                    }
                }
                return result;
            }
        }
        
        return List.of(s);
    }
    
    /**
     * 生成期刊AI分析
     */
    public String generateJournalAIAnalysis(JournalMetricsLike latestRow) 
            throws Exception {
        Map<Integer, List<String>> topKeywords = pickTopKeywords(latestRow);
        Map<String, Object> radar = buildRadarFromRow(latestRow);
        Map<String, String> comments = buildCommentsFromRow(latestRow);
        
        Map<String, Object> payload = new HashMap<>();
        payload.put("journal", latestRow.getJournal());
        payload.put("latest_year", latestRow.getYear());
        
        Map<String, Object> metrics = new HashMap<>();
        metrics.put("disruption", latestRow.getDisruption());
        metrics.put("novelty", latestRow.getNovelty());
        metrics.put("interdisciplinary", latestRow.getInterdisciplinary());
        metrics.put("theme_concentration", latestRow.getThemeConcentration());
        metrics.put("topic", latestRow.getTopic());
        metrics.put("hot_response", latestRow.getHotResponse());
        metrics.put("paper_count", latestRow.getPaperCount());
        metrics.put("category", latestRow.getCategory());
        payload.put("metrics", metrics);
        
        payload.put("radar", radar);
        payload.put("rule_based_comments", comments);
        payload.put("top_keywords_2021_2025", topKeywords);
        
        String systemPrompt = aiClient.loadJournalDetailPrompt();
        String userPrompt = "请基于下面 JSON 输入，对该期刊做一次投稿/定位分析。\n" +
            "注意：不得编造不存在的字段或数据。\n\n" +
            objectMapper.writeValueAsString(payload);
        
        return aiClient.callChatCompletion(systemPrompt, userPrompt);
    }
    
    // 辅助方法
    
    private double toDouble(Object value) {
        if (value == null) return 0.0;
        try {
            if (value instanceof Number) {
                return ((Number) value).doubleValue();
            }
            return Double.parseDouble(value.toString());
        } catch (Exception e) {
            return 0.0;
        }
    }
    
    private boolean isHigh(double value) {
        return value >= 50.0;
    }
    
    private String pickQuadrantComment(boolean aHigh, boolean bHigh, 
                                      String hh, String hl, String lh, String ll) {
        if (aHigh && bHigh) return hh;
        if (aHigh && !bHigh) return hl;
        if (!aHigh && bHigh) return lh;
        return ll;
    }
}
