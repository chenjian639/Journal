package com.paper.controller;

import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Base64;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.stream.Collectors;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Controller;
import org.springframework.ui.Model;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PathVariable;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.ResponseBody;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.paper.dao.AnalysisDAO;
import com.paper.dao.UserJournalMetricsDAO;
import com.paper.model.AnalysisRecord;
import com.paper.model.JournalMetrics;
import com.paper.model.JournalMetricsLike;
import com.paper.model.JournalRankingMetric;
import com.paper.model.JournalRankingRow;
import com.paper.model.UserSurvey;
import com.paper.service.JournalService;
import com.paper.service.UserAnalysisRankingService;
import com.paper.utils.AIClient;

import jakarta.servlet.http.Cookie;
import jakarta.servlet.http.HttpServletRequest;
import jakarta.servlet.http.HttpServletResponse;

/**
 * 期刊控制器 - 处理期刊展示、推荐、对比等功能
 */
@Controller
@RequestMapping("/journal")
public class JournalController {
    
    private static final String SURVEY_COOKIE_NAME = "pm_survey";
    private static final ObjectMapper objectMapper = new ObjectMapper();
    
    private final JournalService service;
    private final AIClient aiClient;
    private final UserAnalysisRankingService userAnalysisRankingService;
    private final AnalysisDAO analysisDAO;
    private final UserJournalMetricsDAO userJournalMetricsDAO;
    
    @Autowired
    public JournalController(
        JournalService service,
        AIClient aiClient,
        UserAnalysisRankingService userAnalysisRankingService,
        AnalysisDAO analysisDAO,
        UserJournalMetricsDAO userJournalMetricsDAO
    ) {
        this.service = service;
        this.aiClient = aiClient;
        this.userAnalysisRankingService = userAnalysisRankingService;
        this.analysisDAO = analysisDAO;
        this.userJournalMetricsDAO = userJournalMetricsDAO;
    }
    
    /**
     * 期刊列表/入口页面（已升级为“期刊排名”页）
     */
    @GetMapping({"", "/", "/list"})
    public String journalsPage(Model model) {
        return "redirect:/journal/rankings";
    }

    /**
     * JCR风格期刊排名页
     *
     * 支持：指标切换、年份（0=最新）、类别过滤、关键词搜索、分页。
     */
    @GetMapping({"/rankings", "/ranking", "/jcr"})
    public String rankingsPage(
        @RequestParam(required = false) String metric,
        @RequestParam(required = false) String q,
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size,
        Model model
    ) {
        try {
            JournalRankingMetric selectedMetric = JournalRankingMetric.fromIdOrDefault(metric, JournalRankingMetric.FRONTIER);

            int safeSize = Math.max(5, Math.min(200, size));
            int safePage = Math.max(0, page);
            Pageable pageable = PageRequest.of(safePage, safeSize);

            // 总榜单：固定“最新口径”，不提供年份/类别筛选
            Page<JournalMetrics> pageResult = service.fetchRankings(
                selectedMetric,
                null,
                null,
                q,
                pageable
            );

            long total = pageResult.getTotalElements();
            int offset = pageResult.getNumber() * pageResult.getSize();
            List<JournalRankingRow> rows = new ArrayList<>();
            List<JournalMetrics> content = pageResult.getContent();
            for (int i = 0; i < content.size(); i++) {
                JournalMetrics row = content.get(i);
                int rank = offset + i + 1;
                int quartile = computeQuartile(rank, total);
                // paper_count 作为排序字段时，不再计算/展示“分值”，避免与“分数”概念混淆
                double metricValue = (selectedMetric == JournalRankingMetric.PAPER_COUNT) ? 0.0 : selectedMetric.computeValue(row);
                rows.add(new JournalRankingRow(rank, quartile, metricValue, row));
            }

            int totalPages = pageResult.getTotalPages();
            int cur = pageResult.getNumber();
            int startPage = Math.max(0, cur - 3);
            int endPage = Math.min(Math.max(0, totalPages - 1), cur + 3);
            // 尽量展示 7 个页码
            while (endPage - startPage < 6 && (startPage > 0 || endPage < totalPages - 1)) {
                if (startPage > 0) startPage--;
                else if (endPage < totalPages - 1) endPage++;
                else break;
            }

            model.addAttribute("metricOptions", JournalRankingMetric.all());
            model.addAttribute("selectedMetric", selectedMetric);
            model.addAttribute("q", q == null ? "" : q);

            model.addAttribute("rows", rows);
            model.addAttribute("page", pageResult);
            model.addAttribute("startPage", startPage);
            model.addAttribute("endPage", endPage);
            model.addAttribute("size", safeSize);

            return "journal/rankings";
        } catch (Exception e) {
            model.addAttribute("error", "加载期刊排名失败: " + e.getMessage());
            return "error";
        }
    }

    /**
     * 我的上传数据榜单（从 analysis_record.analysis_result 解析，不写入总库）
     */
    @GetMapping({"/my-rankings", "/user-rankings"})
    public String myRankingsPage(
        @RequestParam(required = false) String username,
        @RequestParam(required = false) Long analysisId,
        @RequestParam(required = false) String metric,
        @RequestParam(required = false) String q,
        @RequestParam(defaultValue = "0") int page,
        @RequestParam(defaultValue = "20") int size,
        Model model
    ) {
        try {
            String safeUsername = (username == null) ? "" : username.trim();
            JournalRankingMetric selectedMetric = JournalRankingMetric.fromIdOrDefault(metric, JournalRankingMetric.FRONTIER);

            int safeSize = Math.max(5, Math.min(200, size));
            int safePage = Math.max(0, page);
            Pageable pageable = PageRequest.of(safePage, safeSize);

            List<AnalysisRecord> analysisOptions = List.of();
            AnalysisRecord selectedAnalysisRecord = null;
            int datasetYear = 0;
            Page<JournalMetrics> pageResult = new org.springframework.data.domain.PageImpl<>(List.of(), pageable, 0);

            if (!safeUsername.isBlank()) {
                try {
                    analysisOptions = analysisDAO.getHistoryByUsername(safeUsername, 200);

                    if (analysisId != null) {
                        AnalysisRecord r = analysisDAO.getById(analysisId);
                        if (r != null && safeUsername.equals(r.getUsername())) {
                            selectedAnalysisRecord = r;
                        }
                    }
                } catch (Exception e) {
                    System.err.println("Failed to load analysis history: " + e.getMessage());
                }
            }

            if (selectedAnalysisRecord != null
                && selectedAnalysisRecord.getAnalysisResult() != null
                && !selectedAnalysisRecord.getAnalysisResult().isBlank()) {
                UserAnalysisRankingService.ParsedAnalysisDataset dataset =
                    userAnalysisRankingService.parseAnalysisResult(selectedAnalysisRecord.getAnalysisResult());
                datasetYear = dataset.yearMax();

                // 将本次分析的期刊“详情页所需字段”落库，便于复用 /journal/{journal} 详情页
                // 仅写入 user_journal_metrics（不污染总库 journal_metrics）
                try {
                    // 始终 upsert：
                    // - 允许同一个 analysisId 反复进入页面时修复/补齐字段（例如 top_keywords_2021~2025）
                    // - upsertAll 是幂等的（SQLite ON CONFLICT / MySQL ON DUPLICATE KEY UPDATE）
                    userJournalMetricsDAO.upsertAll(selectedAnalysisRecord.getId(), safeUsername, dataset.rows());
                } catch (Exception e) {
                    System.err.println("Failed to persist user journal metrics: " + e.getMessage());
                }

                pageResult = userAnalysisRankingService.buildRankingsPage(
                    dataset.rows(),
                    selectedMetric,
                    q,
                    pageable
                );
            }

            long total = pageResult.getTotalElements();
            int offset = pageResult.getNumber() * pageResult.getSize();
            List<JournalRankingRow> rows = new ArrayList<>();
            List<JournalMetrics> content = pageResult.getContent();
            for (int i = 0; i < content.size(); i++) {
                JournalMetrics row = content.get(i);
                int rank = offset + i + 1;
                int quartile = computeQuartile(rank, total);
                Integer pc = row == null ? null : row.getPaperCount();
                boolean smallSample = pc != null && pc > 0 && pc < 5;
                String note = smallSample ? ("论文数量过少（" + pc + "篇，不具有代表性）") : null;

                double metricValue;
                if (selectedMetric == JournalRankingMetric.PAPER_COUNT) {
                    metricValue = 0.0;
                } else if (smallSample) {
                    // 小样本：已在指标计算前剔除，不展示排序分值
                    metricValue = 0.0;
                } else {
                    metricValue = selectedMetric.computeValue(row);
                }
                rows.add(new JournalRankingRow(rank, quartile, metricValue, row, note));
            }

            int totalPages = pageResult.getTotalPages();
            int cur = pageResult.getNumber();
            int startPage = Math.max(0, cur - 3);
            int endPage = Math.min(Math.max(0, totalPages - 1), cur + 3);
            while (endPage - startPage < 6 && (startPage > 0 || endPage < totalPages - 1)) {
                if (startPage > 0) startPage--;
                else if (endPage < totalPages - 1) endPage++;
                else break;
            }

            model.addAttribute("metricOptions", JournalRankingMetric.all());
            model.addAttribute("selectedMetric", selectedMetric);
            model.addAttribute("q", q == null ? "" : q);
            model.addAttribute("size", safeSize);

            model.addAttribute("username", safeUsername);
            model.addAttribute("analysisOptions", analysisOptions);
            model.addAttribute("selectedAnalysisId", selectedAnalysisRecord == null ? null : selectedAnalysisRecord.getId());
            model.addAttribute("selectedAnalysisRecord", selectedAnalysisRecord);
            model.addAttribute("datasetYear", datasetYear);

            model.addAttribute("rows", rows);
            model.addAttribute("page", pageResult);
            model.addAttribute("startPage", startPage);
            model.addAttribute("endPage", endPage);

            return "journal/my_rankings";
        } catch (Exception e) {
            model.addAttribute("error", "加载我的榜单失败: " + e.getMessage());
            return "error";
        }
    }

    private int computeQuartile(int rank, long total) {
        if (total <= 0) {
            return 4;
        }
        int q = (int) Math.ceil(rank * 4.0 / (double) total);
        if (q < 1) return 1;
        if (q > 4) return 4;
        return q;
    }
    
    /**
     * 期刊详情页面
     */
    @GetMapping("/{journal}")
    public String journalDetailPage(
        @PathVariable String journal,
        @RequestParam(required = false) Long analysisId,
        @RequestParam(required = false) String username,
        Model model
    ) {
        try {
            List<? extends JournalMetricsLike> rows = List.of();

            // 如果带了 analysisId：优先从用户上传数据集读取（用于“我的上传榜单”期刊详情）
            if (analysisId != null && analysisId > 0) {
                boolean canUseUserDataset = true;
                // 轻量校验：若传入 username，则必须与该 analysis_record 归属用户一致
                if (username != null && !username.isBlank()) {
                    try {
                        AnalysisRecord r = analysisDAO.getById(analysisId);
                        if (r == null || r.getUsername() == null || !username.trim().equals(r.getUsername())) {
                            canUseUserDataset = false;
                        }
                    } catch (Exception ignored) {
                        // 校验失败不阻断（回退到总库）
                    }
                }

                if (canUseUserDataset) {
                    try {
                        rows = userJournalMetricsDAO.findByAnalysisAndJournalOrderByYearDesc(analysisId, journal);
                        if (!rows.isEmpty()) {
                            model.addAttribute("analysisId", analysisId);
                            model.addAttribute("datasetUsername", username);
                        }
                    } catch (Exception e) {
                        System.err.println("Failed to load user journal metrics: " + e.getMessage());
                    }
                }
            }

            // 回退：总数据集
            if (rows == null || rows.isEmpty()) {
                rows = service.fetchJournalRows(journal);
            }
            if (rows.isEmpty()) {
                model.addAttribute("error", "未找到该期刊");
                return "error";
            }
            
            JournalMetricsLike latestRow = rows.get(0);
            Map<Integer, List<String>> topKeywordsMap = service.pickTopKeywords(latestRow);
            
            // 转换为有序列表，便于Thymeleaf渲染
            List<Map<String, Object>> topKeywordsList = new ArrayList<>();
            for (int year = 2021; year <= 2025; year++) {
                Map<String, Object> yearData = new HashMap<>();
                yearData.put("year", year);
                yearData.put("keywords", topKeywordsMap.getOrDefault(year, new ArrayList<>()));
                topKeywordsList.add(yearData);
            }
            
            Map<String, Object> radar = service.buildRadarFromRow(latestRow);
            Map<String, String> comments = service.buildCommentsFromRow(latestRow);
            
            model.addAttribute("journal", journal);
            model.addAttribute("rows", rows);
            model.addAttribute("topKeywords", topKeywordsList);
            model.addAttribute("radarJson", objectMapper.writeValueAsString(radar));
            model.addAttribute("comments", comments);
            
            return "journal/journal_detail";
        } catch (Exception e) {
            model.addAttribute("error", "处理失败: " + e.getMessage());
            return "error";
        }
    }
    
    /**
     * 期刊AI分析（异步接口）
     */
    @PostMapping("/{journal}/ai-analysis")
    @ResponseBody
    public Map<String, Object> journalAIAnalysis(
        @PathVariable String journal,
        @RequestParam(required = false) Long analysisId,
        @RequestParam(required = false) String username
    ) {
        Map<String, Object> result = new HashMap<>();
        try {
            List<? extends JournalMetricsLike> rows = List.of();

            if (analysisId != null && analysisId > 0) {
                boolean canUseUserDataset = true;
                if (username != null && !username.isBlank()) {
                    try {
                        AnalysisRecord r = analysisDAO.getById(analysisId);
                        if (r == null || r.getUsername() == null || !username.trim().equals(r.getUsername())) {
                            canUseUserDataset = false;
                        }
                    } catch (Exception ignored) {
                    }
                }
                if (canUseUserDataset) {
                    try {
                        rows = userJournalMetricsDAO.findByAnalysisAndJournalOrderByYearDesc(analysisId, journal);
                    } catch (Exception e) {
                        System.err.println("Failed to load user journal metrics for AI: " + e.getMessage());
                    }
                }
            }

            if (rows == null || rows.isEmpty()) {
                rows = service.fetchJournalRows(journal);
            }
            if (rows.isEmpty()) {
                result.put("error", "未找到该期刊");
                return result;
            }
            
            JournalMetricsLike latestRow = rows.get(0);
            String analysis = service.generateJournalAIAnalysis(latestRow);
            
            result.put("journal", journal);
            result.put("year", latestRow.getYear());
            result.put("analysis", analysis);
            result.put("used_model", aiClient.getConfig().get("model"));
            if (analysisId != null && analysisId > 0) {
                result.put("analysisId", analysisId);
            }
            
        } catch (Exception e) {
            result.put("error", "AI 分析失败：" + e.getMessage());
        }
        return result;
    }
    
    /**
     * 问卷页面
     */
    @GetMapping("/survey")
    public String surveyPage(HttpServletRequest request, Model model) {
        UserSurvey survey = loadSurvey(request);
        model.addAttribute("survey", survey != null ? survey : new UserSurvey());
        return "journal/survey";
    }
    
    /**
     * 提交问卷
     */
    @PostMapping("/survey/analyze")
    public String surveyAnalyze(
            @RequestParam String keywords,
            @RequestParam int qNovelty,
            @RequestParam int qDisruption,
            @RequestParam int qInterdisciplinary,
            @RequestParam int qThemeConcentration,
            @RequestParam int qTopic,
            @RequestParam int qHotResponse,
            HttpServletResponse response) {
        
        List<String> kws = service.parseUserKeywords(keywords);
        if (kws.isEmpty()) {
            return "redirect:/journal/survey?error=keywords_required";
        }
        
        UserSurvey survey = new UserSurvey();
        survey.setKeywordsRaw(keywords.trim());
        survey.setKeywords(kws);
        survey.setNovelty(service.scoresFromLikert(qNovelty));
        survey.setDisruption(service.scoresFromLikert(qDisruption));
        survey.setInterdisciplinary(service.scoresFromLikert(qInterdisciplinary));
        survey.setThemeConcentration(service.scoresFromLikert(qThemeConcentration));
        survey.setTopic(service.scoresFromLikert(qTopic));
        survey.setHotResponse(service.scoresFromLikert(qHotResponse));
        survey.setCreatedAt(LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyy-MM-dd HH:mm:ss")));
        
        // 保存到Cookie
        try {
            String cookieValue = encodeSurvey(survey);
            Cookie cookie = new Cookie(SURVEY_COOKIE_NAME, cookieValue);
            cookie.setMaxAge(60 * 60 * 24 * 7); // 7天
            cookie.setHttpOnly(true);
            cookie.setPath("/");
            response.addCookie(cookie);
        } catch (Exception e) {
            System.err.println("Failed to save survey cookie: " + e.getMessage());
        }
        
        return "redirect:/journal/recommend";
    }
    
    /**
     * 推荐页面
     */
    @GetMapping("/recommend")
    public String recommendPage(HttpServletRequest request, Model model) {
        UserSurvey survey = loadSurvey(request);
        if (survey == null) {
            return "redirect:/journal/survey";
        }
        
        try {
            List<JournalMetrics> latestRows = service.fetchLatestJournalRows();
            Map<String, Object> userRadar = service.buildUserRadar(survey);
            Set<String> userNorm = survey.getKeywords().stream()
                .map(service::normalizeKeyword)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toSet());
            
            int targetYear = LocalDateTime.now().getYear();
            Map<String, List<String>> kwHits = new HashMap<>();
            for (String kw : survey.getKeywords()) {
                kwHits.put(kw, new ArrayList<>());
            }
            
            List<Map<String, Object>> recs = new ArrayList<>();
            
            for (JournalMetrics row : latestRows) {
                String jname = row.getJournal();
                if (jname == null || jname.trim().isEmpty()) {
                    continue;
                }
                
                List<String> journalKw = service.pickKeywordsForYear(row, targetYear);
                Map<String, String> jNormMap = new HashMap<>();
                for (String k : journalKw) {
                    String norm = service.normalizeKeyword(k);
                    if (!norm.isEmpty()) {
                        jNormMap.put(norm, k);
                    }
                }
                
                List<String> matchedNorm = userNorm.stream()
                    .filter(jNormMap::containsKey)
                    .collect(Collectors.toList());
                List<String> matchedDisplay = matchedNorm.stream()
                    .map(jNormMap::get)
                    .collect(Collectors.toList());
                
                // 记录每个用户关键词命中哪些期刊
                for (String uk : survey.getKeywords()) {
                    if (jNormMap.containsKey(service.normalizeKeyword(uk))) {
                        kwHits.get(uk).add(jname);
                    }
                }
                
                Map<String, Object> journalRadar = service.buildRadarFromRow(row);
                double sim = service.computeSimilarity(userRadar, journalRadar);
                double kwRatio = matchedDisplay.size() / (double) Math.max(1, userNorm.size());
                double score = kwRatio * 60.0 + sim * 40.0;
                
                Map<String, Object> rec = new HashMap<>();
                rec.put("journal", jname);
                rec.put("year", row.getYear());
                rec.put("category", row.getCategory());
                rec.put("matched_keywords", matchedDisplay);
                rec.put("kw_hit", matchedDisplay.size());
                rec.put("match_pct", (int) Math.round(sim * 100));
                rec.put("score", score);
                recs.add(rec);
            }
            
            // 排序并取前10
            recs.sort((a, b) -> {
                int scoreComp = Double.compare((Double) b.get("score"), (Double) a.get("score"));
                if (scoreComp != 0) return scoreComp;
                int kwComp = Integer.compare((Integer) b.get("kw_hit"), (Integer) a.get("kw_hit"));
                if (kwComp != 0) return kwComp;
                return Integer.compare((Integer) b.get("match_pct"), (Integer) a.get("match_pct"));
            });
            
            List<Map<String, Object>> topRecs = recs.stream().limit(10).collect(Collectors.toList());
            
            model.addAttribute("survey", survey);
            model.addAttribute("targetYear", targetYear);
            model.addAttribute("kwHits", kwHits);
            model.addAttribute("recs", topRecs);
            model.addAttribute("userRadarJson", objectMapper.writeValueAsString(userRadar));
            model.addAttribute("userComments", service.buildCommentsFromRow(
                convertSurveyToMetrics(survey)));
            
            return "journal/recommend";
        } catch (Exception e) {
            model.addAttribute("error", "生成推荐失败: " + e.getMessage());
            return "error";
        }
    }
    
    // 辅助方法：从Cookie加载问卷
    private UserSurvey loadSurvey(HttpServletRequest request) {
        Cookie[] cookies = request.getCookies();
        if (cookies == null) return null;
        
        for (Cookie cookie : cookies) {
            if (SURVEY_COOKIE_NAME.equals(cookie.getName())) {
                try {
                    return decodeSurvey(cookie.getValue());
                } catch (Exception e) {
                    System.err.println("Failed to parse survey cookie: " + e.getMessage());
                }
            }
        }
        return null;
    }
    
    // 辅助方法：编码问卷为Base64
    private String encodeSurvey(UserSurvey survey) throws Exception {
        Map<String, Object> data = new HashMap<>();
        data.put("keywords_raw", survey.getKeywordsRaw());
        data.put("keywords", survey.getKeywords());
        Map<String, Double> scores = new HashMap<>();
        scores.put("novelty", survey.getNovelty());
        scores.put("disruption", survey.getDisruption());
        scores.put("interdisciplinary", survey.getInterdisciplinary());
        scores.put("theme_concentration", survey.getThemeConcentration());
        scores.put("topic", survey.getTopic());
        scores.put("hot_response", survey.getHotResponse());
        data.put("scores", scores);
        data.put("created_at", survey.getCreatedAt());
        
        String json = objectMapper.writeValueAsString(data);
        return Base64.getUrlEncoder().withoutPadding()
            .encodeToString(json.getBytes(java.nio.charset.StandardCharsets.UTF_8));
    }
    
    // 辅助方法：从Base64解码问卷
    @SuppressWarnings("unchecked")
    private UserSurvey decodeSurvey(String token) throws Exception {
        byte[] decoded = Base64.getUrlDecoder().decode(token);
        String json = new String(decoded, java.nio.charset.StandardCharsets.UTF_8);
        Map<String, Object> data = objectMapper.readValue(json, Map.class);
        
        UserSurvey survey = new UserSurvey();
        survey.setKeywordsRaw((String) data.get("keywords_raw"));
        survey.setKeywords((List<String>) data.get("keywords"));
        
        Map<String, Object> scores = (Map<String, Object>) data.get("scores");
        survey.setNovelty(((Number) scores.get("novelty")).doubleValue());
        survey.setDisruption(((Number) scores.get("disruption")).doubleValue());
        survey.setInterdisciplinary(((Number) scores.get("interdisciplinary")).doubleValue());
        survey.setThemeConcentration(((Number) scores.get("theme_concentration")).doubleValue());
        survey.setTopic(((Number) scores.get("topic")).doubleValue());
        survey.setHotResponse(((Number) scores.get("hot_response")).doubleValue());
        survey.setCreatedAt((String) data.get("created_at"));
        
        return survey;
    }
    
    // 辅助方法：将Survey转换为Metrics格式以复用评语生成逻辑
    private JournalMetrics convertSurveyToMetrics(UserSurvey survey) {
        JournalMetrics metrics = new JournalMetrics();
        metrics.setNovelty(survey.getNovelty());
        metrics.setDisruption(survey.getDisruption());
        metrics.setInterdisciplinary(survey.getInterdisciplinary());
        metrics.setThemeConcentration(survey.getThemeConcentration());
        metrics.setTopic(survey.getTopic());
        metrics.setHotResponse(survey.getHotResponse());
        return metrics;
    }
    
    /**
     * 推荐详情页面
     */
    @GetMapping("/recommend/{journal}")
    public String recommendDetailPage(@PathVariable String journal, 
                                     HttpServletRequest request, Model model) {
        UserSurvey survey = loadSurvey(request);
        if (survey == null) {
            return "redirect:/journal/survey";
        }
        
        try {
            JournalMetrics row = service.fetchLatestRowForJournal(journal);
            if (row == null) {
                model.addAttribute("error", "未找到该期刊");
                return "error";
            }
            
            Map<String, Object> userRadar = service.buildUserRadar(survey);
            Map<String, Object> journalRadar = service.buildRadarFromRow(row);
            double sim = service.computeSimilarity(userRadar, journalRadar);
            
            // 构建叠加雷达图数据
            Map<String, Object> overlay = new HashMap<>();
            overlay.put("labels", userRadar.get("labels"));
            
            Map<String, Object> aData = new HashMap<>();
            aData.put("name", "你的画像");
            aData.put("values", userRadar.get("values"));
            overlay.put("a", aData);
            
            Map<String, Object> bData = new HashMap<>();
            bData.put("name", journal);
            bData.put("values", journalRadar.get("values"));
            overlay.put("b", bData);
            
            overlay.put("max", 200);
            
            // 关键词命中
            int targetYear = LocalDateTime.now().getYear();
            List<String> jKwYear = service.pickKeywordsForYear(row, targetYear);
            Set<String> jKwNorm = jKwYear.stream()
                .map(service::normalizeKeyword)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toSet());
            
            List<String> matchedUserKeywords = survey.getKeywords().stream()
                .filter(k -> jKwNorm.contains(service.normalizeKeyword(k)))
                .collect(Collectors.toList());
            
            // 维度差异
            @SuppressWarnings("unchecked")
            List<Double> uVals = (List<Double>) userRadar.get("values");
            @SuppressWarnings("unchecked")
            List<Double> jVals = (List<Double>) journalRadar.get("values");
            @SuppressWarnings("unchecked")
            List<String> labels = (List<String>) userRadar.get("labels");
            
            double[] ranges = {200.0, 100.0, 100.0, 100.0, 100.0};
            List<Map<String, Object>> diffs = new ArrayList<>();
            
            for (int i = 0; i < labels.size(); i++) {
                double uv = uVals.get(i);
                double jv = jVals.get(i);
                double gap = Math.abs(uv - jv);
                int dimMatch = (int) Math.round((1.0 - (gap / ranges[i])) * 100);
                dimMatch = Math.max(0, dimMatch);
                
                Map<String, Object> diff = new HashMap<>();
                diff.put("dim", labels.get(i));
                diff.put("user", uv);
                diff.put("journal", jv);
                diff.put("gap", gap);
                diff.put("match", dimMatch);
                diffs.add(diff);
            }
            
            model.addAttribute("survey", survey);
            model.addAttribute("journal", journal);
            model.addAttribute("row", row);
            model.addAttribute("targetYear", targetYear);
            model.addAttribute("matchedUserKeywords", matchedUserKeywords);
            model.addAttribute("overlayJson", objectMapper.writeValueAsString(overlay));
            model.addAttribute("userComments", service.buildCommentsFromRow(
                convertSurveyToMetrics(survey)));
            model.addAttribute("journalComments", service.buildCommentsFromRow(row));
            model.addAttribute("matchPct", (int) Math.round(sim * 100));
            model.addAttribute("diffs", diffs);
            
            return "journal/recommend_detail";
        } catch (Exception e) {
            model.addAttribute("error", "加载详情失败: " + e.getMessage());
            return "error";
        }
    }
    
    /**
     * 推荐详情AI分析（异步接口）
     */
    @PostMapping("/recommend/{journal}/ai-analysis")
    @ResponseBody
    public Map<String, Object> recommendAIAnalysis(@PathVariable String journal, 
                                                   HttpServletRequest request) {
        Map<String, Object> result = new HashMap<>();
        
        UserSurvey survey = loadSurvey(request);
        if (survey == null) {
            result.put("error", "未填写问卷，无法进行 AI 匹配分析");
            return result;
        }
        
        try {
            JournalMetrics row = service.fetchLatestRowForJournal(journal);
            if (row == null) {
                result.put("error", "未找到该期刊");
                return result;
            }
            
            Map<String, Object> userRadar = service.buildUserRadar(survey);
            Map<String, Object> journalRadar = service.buildRadarFromRow(row);
            double sim = service.computeSimilarity(userRadar, journalRadar);
            
            int targetYear = LocalDateTime.now().getYear();
            List<String> jKwYear = service.pickKeywordsForYear(row, targetYear);
            Set<String> jKwNorm = jKwYear.stream()
                .map(service::normalizeKeyword)
                .filter(s -> !s.isEmpty())
                .collect(Collectors.toSet());
            
            List<String> matchedUserKeywords = survey.getKeywords().stream()
                .filter(k -> jKwNorm.contains(service.normalizeKeyword(k)))
                .collect(Collectors.toList());
            
            // 构建维度差异
            @SuppressWarnings("unchecked")
            List<Double> uVals = (List<Double>) userRadar.get("values");
            @SuppressWarnings("unchecked")
            List<Double> jVals = (List<Double>) journalRadar.get("values");
            @SuppressWarnings("unchecked")
            List<String> labels = (List<String>) userRadar.get("labels");
            
            double[] ranges = {200.0, 100.0, 100.0, 100.0, 100.0};
            List<Map<String, Object>> diffs = new ArrayList<>();
            
            for (int i = 0; i < labels.size(); i++) {
                Map<String, Object> diff = new HashMap<>();
                diff.put("dim", labels.get(i));
                diff.put("user", uVals.get(i));
                diff.put("journal", jVals.get(i));
                diff.put("gap", Math.abs(uVals.get(i) - jVals.get(i)));
                int dimMatch = (int) Math.round((1.0 - (Math.abs(uVals.get(i) - jVals.get(i)) / ranges[i])) * 100);
                diff.put("match", Math.max(0, dimMatch));
                diffs.add(diff);
            }
            
            // 构建AI请求payload
            Map<String, Object> payload = new HashMap<>();
            
            Map<String, Object> surveyData = new HashMap<>();
            surveyData.put("keywords", survey.getKeywords());
            Map<String, Double> scores = new HashMap<>();
            scores.put("novelty", survey.getNovelty());
            scores.put("disruption", survey.getDisruption());
            scores.put("interdisciplinary", survey.getInterdisciplinary());
            scores.put("theme_concentration", survey.getThemeConcentration());
            scores.put("topic", survey.getTopic());
            scores.put("hot_response", survey.getHotResponse());
            surveyData.put("scores", scores);
            surveyData.put("created_at", survey.getCreatedAt());
            payload.put("survey", surveyData);
            
            Map<String, Object> authorProfile = new HashMap<>();
            authorProfile.put("radar", userRadar);
            authorProfile.put("rule_based_comments", service.buildCommentsFromRow(
                convertSurveyToMetrics(survey)));
            payload.put("author_profile", authorProfile);
            
            Map<String, Object> journalData = new HashMap<>();
            journalData.put("name", journal);
            journalData.put("latest_year", row.getYear());
            
            Map<String, Object> metrics = new HashMap<>();
            metrics.put("disruption", row.getDisruption());
            metrics.put("novelty", row.getNovelty());
            metrics.put("interdisciplinary", row.getInterdisciplinary());
            metrics.put("theme_concentration", row.getThemeConcentration());
            metrics.put("topic", row.getTopic());
            metrics.put("hot_response", row.getHotResponse());
            metrics.put("paper_count", row.getPaperCount());
            metrics.put("category", row.getCategory());
            journalData.put("metrics", metrics);
            
            journalData.put("radar", journalRadar);
            journalData.put("rule_based_comments", service.buildCommentsFromRow(row));
            journalData.put("top_keywords_2021_2025", service.pickTopKeywords(row));
            journalData.put("target_year", targetYear);
            journalData.put("target_year_keywords", jKwYear);
            payload.put("journal", journalData);
            
            Map<String, Object> match = new HashMap<>();
            match.put("overall_match_pct", (int) Math.round(sim * 100));
            match.put("matched_keywords", matchedUserKeywords);
            match.put("dimension_diffs", diffs);
            payload.put("match", match);
            
            String systemPrompt = aiClient.loadRecommendMatchPrompt();
            String userPrompt = "请基于下面 JSON 输入，对作者画像与该期刊的适配性做一次分析，并给出投稿建议。\n" +
                "注意：不得编造不存在的字段或数据。\n\n" +
                objectMapper.writeValueAsString(payload);
            
            String analysis = aiClient.callChatCompletion(systemPrompt, userPrompt);
            
            result.put("journal", journal);
            result.put("year", row.getYear());
            result.put("analysis", analysis);
            result.put("used_model", aiClient.getConfig().get("model"));
            result.put("match_pct", (int) Math.round(sim * 100));
            
        } catch (Exception e) {
            result.put("error", "AI 匹配分析失败：" + e.getMessage());
        }
        
        return result;
    }
    
    /**
     * 期刊对比页面
     */
    @GetMapping("/compare")
    public String comparePage(
            @RequestParam(required = false) String j1,
            @RequestParam(required = false) String j2,
            Model model) {
        
        try {
            List<String> allJournals = service.fetchJournalNames();
            model.addAttribute("journals", allJournals);
            model.addAttribute("j1", j1 != null ? j1 : "");
            model.addAttribute("j2", j2 != null ? j2 : "");
            
            if (j1 != null && j2 != null && !j1.isEmpty() && !j2.isEmpty()) {
                Map<String, JournalMetrics> rowMap = service.fetchLatestRowsForTwoJournals(j1, j2);
                
                JournalMetrics aRow = rowMap.get(j1);
                JournalMetrics bRow = rowMap.get(j2);
                
                if (aRow != null && bRow != null) {
                    Map<String, Object> aRadar = service.buildRadarFromRow(aRow);
                    Map<String, Object> bRadar = service.buildRadarFromRow(bRow);
                    
                    // 构建叠加雷达图
                    Map<String, Object> overlay = new HashMap<>();
                    overlay.put("labels", aRadar.get("labels"));
                    
                    Map<String, Object> aData = new HashMap<>();
                    aData.put("name", j1);
                    aData.put("values", aRadar.get("values"));
                    overlay.put("a", aData);
                    
                    Map<String, Object> bData = new HashMap<>();
                    bData.put("name", j2);
                    bData.put("values", bRadar.get("values"));
                    overlay.put("b", bData);
                    
                    overlay.put("max", 200);
                    
                    // 构建柱状图数据
                    String[] barLabels = {"paper_count", "novelty", "disruption", "interdisciplinary", 
                        "topic", "theme_concentration", "hot_response"};
                    Map<String, Object> bar = new HashMap<>();
                    bar.put("labels", List.of("论文数量", "新颖性", "颠覆性", "跨学科性", 
                        "主题多样性", "主题集中度", "热点响应度"));
                    
                    @SuppressWarnings("unchecked")
                    Map<String, Object> aRaw = (Map<String, Object>) aRadar.get("raw");
                    @SuppressWarnings("unchecked")
                    Map<String, Object> bRaw = (Map<String, Object>) bRadar.get("raw");
                    
                    List<Double> aValues = new ArrayList<>();
                    List<Double> bValues = new ArrayList<>();
                    for (String label : barLabels) {
                        aValues.add(((Number) aRaw.get(label)).doubleValue());
                        bValues.add(((Number) bRaw.get(label)).doubleValue());
                    }
                    
                    Map<String, Object> aBarData = new HashMap<>();
                    aBarData.put("name", j1);
                    aBarData.put("values", aValues);
                    bar.put("a", aBarData);
                    
                    Map<String, Object> bBarData = new HashMap<>();
                    bBarData.put("name", j2);
                    bBarData.put("values", bValues);
                    bar.put("b", bBarData);
                    
                    // 分析对比
                    @SuppressWarnings("unchecked")
                    List<String> dims = (List<String>) overlay.get("labels");
                    @SuppressWarnings("unchecked")
                    List<Double> aVals = (List<Double>) aData.get("values");
                    @SuppressWarnings("unchecked")
                    List<Double> bVals = (List<Double>) bData.get("values");
                    
                    List<String> analysisLines = new ArrayList<>();
                    for (int i = 0; i < dims.size(); i++) {
                        String dim = dims.get(i);
                        double av = aVals.get(i);
                        double bv = bVals.get(i);
                        
                        if (Math.abs(av - bv) < 0.01) {
                            analysisLines.add(String.format("%s：两者相当（%.2f）。", dim, av));
                        } else {
                            String win = av > bv ? j1 : j2;
                            double diff = Math.abs(av - bv);
                            analysisLines.add(String.format("%s：%s 更高（差值 %.2f）。", dim, win, diff));
                        }
                    }
                    
                    model.addAttribute("aRow", aRow);
                    model.addAttribute("bRow", bRow);
                    
                    // 转换Keywords为列表格式
                    Map<Integer, List<String>> aKwMap = service.pickTopKeywords(aRow);
                    Map<Integer, List<String>> bKwMap = service.pickTopKeywords(bRow);
                    
                    List<Map<String, Object>> aKwList = new ArrayList<>();
                    List<Map<String, Object>> bKwList = new ArrayList<>();
                    for (int year = 2021; year <= 2025; year++) {
                        Map<String, Object> aYearData = new HashMap<>();
                        aYearData.put("year", year);
                        aYearData.put("keywords", aKwMap.getOrDefault(year, new ArrayList<>()));
                        aKwList.add(aYearData);
                        
                        Map<String, Object> bYearData = new HashMap<>();
                        bYearData.put("year", year);
                        bYearData.put("keywords", bKwMap.getOrDefault(year, new ArrayList<>()));
                        bKwList.add(bYearData);
                    }
                    
                    model.addAttribute("aKeywords", aKwList);
                    model.addAttribute("bKeywords", bKwList);
                    model.addAttribute("aComments", service.buildCommentsFromRow(aRow));
                    model.addAttribute("bComments", service.buildCommentsFromRow(bRow));
                    model.addAttribute("overlayJson", objectMapper.writeValueAsString(overlay));
                    model.addAttribute("aRadarJson", objectMapper.writeValueAsString(aRadar));
                    model.addAttribute("bRadarJson", objectMapper.writeValueAsString(bRadar));
                    model.addAttribute("barJson", objectMapper.writeValueAsString(bar));
                    model.addAttribute("analysisLines", analysisLines);
                } else {
                    model.addAttribute("aRow", null);
                    model.addAttribute("bRow", null);
                }
            } else {
                model.addAttribute("aRow", null);
                model.addAttribute("bRow", null);
            }
            
            return "journal/compare";
        } catch (Exception e) {
            model.addAttribute("error", "加载对比页面失败: " + e.getMessage());
            return "error";
        }
    }
}
