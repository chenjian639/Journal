package com.journal.servlet;

import com.google.gson.Gson;
import com.journal.entity.AnalysisReport;
import com.journal.entity.Journal;
import com.journal.service.AnalysisService;
import com.journal.service.JournalService;
import org.thymeleaf.context.WebContext;

import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.ArrayList;
import java.util.List;
import java.util.Map;

/**
 * 分析功能Servlet
 */
@WebServlet(name = "AnalysisServlet", urlPatterns = {"/analysis", "/analysis/*"})
public class AnalysisServlet extends BaseServlet {
    private AnalysisService analysisService = new AnalysisService();
    private JournalService journalService = new JournalService();
    private Gson gson = new Gson();

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String pathInfo = request.getPathInfo();
        WebContext context = createWebContext(request, response);
        
        // 设置通用变量
        context.setVariable("isLoggedIn", isLoggedIn(request));
        context.setVariable("username", request.getSession().getAttribute("username"));
        
        if (pathInfo == null || pathInfo.equals("/")) {
            // 分析首页
            List<Journal> journals = journalService.getAllJournals();
            context.setVariable("journals", journals);
            render(request, response, "analysis", context);
        } else if (pathInfo.equals("/single")) {
            // 单期刊分析页面
            List<Journal> journals = journalService.getAllJournals();
            context.setVariable("journals", journals);
            render(request, response, "analysis-single", context);
        } else if (pathInfo.equals("/compare")) {
            // 期刊比较页面
            List<Journal> journals = journalService.getAllJournals();
            context.setVariable("journals", journals);
            render(request, response, "analysis-compare", context);
        } else if (pathInfo.equals("/reports")) {
            // 分析报告列表
            handleReportList(request, response, context);
        } else if (pathInfo.matches("/report/\\d+")) {
            // 报告详情
            Long reportId = Long.parseLong(pathInfo.substring(8));
            handleReportDetail(request, response, context, reportId);
        } else {
            response.sendError(HttpServletResponse.SC_NOT_FOUND);
        }
    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response) throws IOException {
        request.setCharacterEncoding("UTF-8");
        String pathInfo = request.getPathInfo();
        
        if (!isLoggedIn(request)) {
            response.sendError(HttpServletResponse.SC_UNAUTHORIZED);
            return;
        }
        
        if (pathInfo == null) {
            response.sendError(HttpServletResponse.SC_BAD_REQUEST);
            return;
        }
        
        switch (pathInfo) {
            case "/single":
                handleSingleAnalysis(request, response);
                break;
            case "/compare":
                handleCompareAnalysis(request, response);
                break;
            case "/save-report":
                handleSaveReport(request, response);
                break;
            default:
                response.sendError(HttpServletResponse.SC_NOT_FOUND);
        }
    }

    /**
     * 处理单期刊分析请求
     */
    private void handleSingleAnalysis(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String journalIdStr = request.getParameter("journalId");
        if (journalIdStr == null) {
            response.sendError(HttpServletResponse.SC_BAD_REQUEST, "请选择期刊");
            return;
        }
        
        try {
            Long journalId = Long.parseLong(journalIdStr);
            Map<String, Object> result = analysisService.analyzeJournal(journalId);
            writeJson(response, gson.toJson(result));
        } catch (Exception e) {
            response.sendError(HttpServletResponse.SC_INTERNAL_SERVER_ERROR, e.getMessage());
        }
    }

    /**
     * 处理期刊比较分析请求
     */
    private void handleCompareAnalysis(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String[] journalIdStrs = request.getParameterValues("journalIds");
        if (journalIdStrs == null || journalIdStrs.length < 2) {
            response.sendError(HttpServletResponse.SC_BAD_REQUEST, "请至少选择两个期刊");
            return;
        }
        
        try {
            List<Long> journalIds = new ArrayList<>();
            for (String idStr : journalIdStrs) {
                journalIds.add(Long.parseLong(idStr));
            }
            
            Map<String, Object> result = analysisService.compareJournals(journalIds);
            writeJson(response, gson.toJson(result));
        } catch (Exception e) {
            response.sendError(HttpServletResponse.SC_INTERNAL_SERVER_ERROR, e.getMessage());
        }
    }

    /**
     * 保存分析报告
     */
    private void handleSaveReport(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String title = request.getParameter("title");
        String reportType = request.getParameter("reportType");
        String journalIdStr = request.getParameter("journalId");
        String journalIds = request.getParameter("journalIds");
        String content = request.getParameter("content");
        Long userId = getCurrentUserId(request);
        
        Long journalId = null;
        if (journalIdStr != null && !journalIdStr.isEmpty()) {
            journalId = Long.parseLong(journalIdStr);
        }
        
        Long reportId = analysisService.generateReport(title, reportType, journalId, journalIds, content, userId);
        writeJson(response, "{\"success\": true, \"reportId\": " + reportId + "}");
    }

    /**
     * 处理报告列表
     */
    private void handleReportList(HttpServletRequest request, HttpServletResponse response, 
                                  WebContext context) throws IOException {
        List<AnalysisReport> reports;
        if (isAdmin(request)) {
            reports = analysisService.getAllReports();
        } else if (isLoggedIn(request)) {
            reports = analysisService.getUserReports(getCurrentUserId(request));
        } else {
            reports = new ArrayList<>();
        }
        
        context.setVariable("reports", reports);
        render(request, response, "analysis-reports", context);
    }

    /**
     * 处理报告详情
     */
    private void handleReportDetail(HttpServletRequest request, HttpServletResponse response, 
                                    WebContext context, Long reportId) throws IOException {
        AnalysisReport report = analysisService.getReportById(reportId);
        if (report == null) {
            response.sendError(HttpServletResponse.SC_NOT_FOUND, "报告不存在");
            return;
        }
        
        context.setVariable("report", report);
        render(request, response, "analysis-report-detail", context);
    }
}
