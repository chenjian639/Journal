package com.journal.servlet;

import com.journal.entity.Journal;
import com.journal.service.JournalService;
import com.journal.util.StringUtil;
import org.thymeleaf.context.WebContext;

import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;
import java.util.List;

/**
 * 期刊管理Servlet
 */
@WebServlet(name = "JournalServlet", urlPatterns = {"/journals", "/journal/*"})
public class JournalServlet extends BaseServlet {
    private JournalService journalService = new JournalService();

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String path = request.getServletPath();
        String pathInfo = request.getPathInfo();
        WebContext context = createWebContext(request, response);
        
        // 设置通用变量
        context.setVariable("isLoggedIn", isLoggedIn(request));
        context.setVariable("username", request.getSession().getAttribute("username"));
        context.setVariable("isAdmin", isAdmin(request));
        
        if ("/journals".equals(path)) {
            handleList(request, response, context);
        } else if ("/journal".equals(path) && pathInfo != null) {
            if (pathInfo.equals("/add")) {
                if (!isLoggedIn(request)) {
                    redirect(response, request.getContextPath() + "/login");
                    return;
                }
                render(request, response, "journal-form", context);
            } else if (pathInfo.matches("/\\d+")) {
                Long id = Long.parseLong(pathInfo.substring(1));
                handleDetail(request, response, context, id);
            } else if (pathInfo.matches("/edit/\\d+")) {
                if (!isAdmin(request)) {
                    redirect(response, request.getContextPath() + "/journals");
                    return;
                }
                Long id = Long.parseLong(pathInfo.substring(6));
                handleEdit(request, response, context, id);
            } else {
                response.sendError(HttpServletResponse.SC_NOT_FOUND);
            }
        } else {
            response.sendError(HttpServletResponse.SC_NOT_FOUND);
        }
    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response) throws IOException {
        request.setCharacterEncoding("UTF-8");
        String pathInfo = request.getPathInfo();
        
        if (!isLoggedIn(request)) {
            redirect(response, request.getContextPath() + "/login");
            return;
        }
        
        if (pathInfo == null || pathInfo.equals("/add")) {
            handleSave(request, response);
        } else if (pathInfo.matches("/edit/\\d+")) {
            handleUpdate(request, response);
        } else if (pathInfo.matches("/delete/\\d+")) {
            if (!isAdmin(request)) {
                response.sendError(HttpServletResponse.SC_FORBIDDEN);
                return;
            }
            Long id = Long.parseLong(pathInfo.substring(8));
            journalService.deleteJournal(id);
            redirect(response, request.getContextPath() + "/journals");
        } else {
            response.sendError(HttpServletResponse.SC_NOT_FOUND);
        }
    }

    /**
     * 处理期刊列表
     */
    private void handleList(HttpServletRequest request, HttpServletResponse response, 
                            WebContext context) throws IOException {
        String keyword = request.getParameter("keyword");
        String country = request.getParameter("country");
        String category = request.getParameter("category");
        String pageStr = request.getParameter("page");
        
        int page = 1;
        int pageSize = 10;
        
        if (pageStr != null) {
            try {
                page = Integer.parseInt(pageStr);
            } catch (NumberFormatException ignored) {}
        }
        
        List<Journal> journals;
        if (StringUtil.isNotEmpty(keyword) || StringUtil.isNotEmpty(country) || StringUtil.isNotEmpty(category)) {
            journals = journalService.searchJournals(keyword, country, category);
            context.setVariable("keyword", keyword);
            context.setVariable("country", country);
            context.setVariable("category", category);
        } else {
            journals = journalService.getJournalsByPage(page, pageSize);
        }
        
        int totalCount = journalService.getJournalCount();
        int totalPages = (int) Math.ceil((double) totalCount / pageSize);
        
        context.setVariable("journals", journals);
        context.setVariable("currentPage", page);
        context.setVariable("totalPages", totalPages);
        context.setVariable("totalCount", totalCount);
        
        render(request, response, "journal-list", context);
    }

    /**
     * 处理期刊详情
     */
    private void handleDetail(HttpServletRequest request, HttpServletResponse response, 
                              WebContext context, Long id) throws IOException {
        Journal journal = journalService.getJournalById(id);
        if (journal == null) {
            response.sendError(HttpServletResponse.SC_NOT_FOUND, "期刊不存在");
            return;
        }
        
        context.setVariable("journal", journal);
        render(request, response, "journal-detail", context);
    }

    /**
     * 处理编辑页面
     */
    private void handleEdit(HttpServletRequest request, HttpServletResponse response, 
                            WebContext context, Long id) throws IOException {
        Journal journal = journalService.getJournalById(id);
        if (journal == null) {
            response.sendError(HttpServletResponse.SC_NOT_FOUND, "期刊不存在");
            return;
        }
        
        context.setVariable("journal", journal);
        context.setVariable("isEdit", true);
        render(request, response, "journal-form", context);
    }

    /**
     * 处理保存期刊
     */
    private void handleSave(HttpServletRequest request, HttpServletResponse response) throws IOException {
        Journal journal = buildJournalFromRequest(request);
        Long id = journalService.addJournal(journal);
        redirect(response, request.getContextPath() + "/journal/" + id);
    }

    /**
     * 处理更新期刊
     */
    private void handleUpdate(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String pathInfo = request.getPathInfo();
        Long id = Long.parseLong(pathInfo.substring(6));
        
        Journal journal = buildJournalFromRequest(request);
        journal.setId(id);
        journalService.updateJournal(journal);
        
        redirect(response, request.getContextPath() + "/journal/" + id);
    }

    /**
     * 从请求构建期刊对象
     */
    private Journal buildJournalFromRequest(HttpServletRequest request) {
        Journal journal = new Journal();
        journal.setName(request.getParameter("name"));
        journal.setIssn(request.getParameter("issn"));
        journal.setPublisher(request.getParameter("publisher"));
        journal.setCountry(request.getParameter("country"));
        journal.setLanguage(request.getParameter("language"));
        journal.setCategory(request.getParameter("category"));
        journal.setFrequency(request.getParameter("frequency"));
        journal.setDescription(request.getParameter("description"));
        journal.setOfficialUrl(request.getParameter("officialUrl"));
        
        String impactFactor = request.getParameter("impactFactor");
        if (StringUtil.isNotEmpty(impactFactor)) {
            try {
                journal.setImpactFactor(Double.parseDouble(impactFactor));
            } catch (NumberFormatException ignored) {}
        }
        
        return journal;
    }
}
