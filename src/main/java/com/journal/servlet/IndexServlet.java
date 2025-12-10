package com.journal.servlet;

import com.journal.entity.Journal;
import com.journal.service.AnalysisService;
import com.journal.service.JournalService;
import org.thymeleaf.context.WebContext;

import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;
import java.util.Map;

/**
 * 首页Servlet
 */
@WebServlet(name = "IndexServlet", urlPatterns = {"", "/index"})
public class IndexServlet extends BaseServlet {
    private JournalService journalService = new JournalService();
    private AnalysisService analysisService = new AnalysisService();

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws IOException {
        WebContext context = createWebContext(request, response);
        
        // 获取最新期刊列表
        List<Journal> latestJournals = journalService.getJournalsByPage(1, 6);
        context.setVariable("latestJournals", latestJournals);
        
        // 获取统计数据
        Map<String, Object> stats = analysisService.getSystemStats();
        context.setVariable("stats", stats);
        
        // 检查用户登录状态
        context.setVariable("isLoggedIn", isLoggedIn(request));
        context.setVariable("username", request.getSession().getAttribute("username"));
        
        render(request, response, "index", context);
    }
}
