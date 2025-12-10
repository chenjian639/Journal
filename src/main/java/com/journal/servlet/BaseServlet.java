package com.journal.servlet;

import com.journal.config.ThymeleafConfig;
import org.thymeleaf.TemplateEngine;
import org.thymeleaf.context.WebContext;
import org.thymeleaf.web.IWebExchange;
import org.thymeleaf.web.servlet.JavaxServletWebApplication;

import javax.servlet.http.HttpServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import java.io.IOException;

/**
 * Servlet基类
 * 提供Thymeleaf模板渲染的通用方法
 */
public abstract class BaseServlet extends HttpServlet {

    /**
     * 渲染Thymeleaf模板
     */
    protected void render(HttpServletRequest request, HttpServletResponse response, 
                          String templateName, WebContext context) throws IOException {
        response.setContentType("text/html;charset=UTF-8");
        TemplateEngine engine = ThymeleafConfig.getTemplateEngine();
        engine.process(templateName, context, response.getWriter());
    }

    /**
     * 创建WebContext
     */
    protected WebContext createWebContext(HttpServletRequest request, HttpServletResponse response) {
        JavaxServletWebApplication webApplication = ThymeleafConfig.getWebApplication();
        IWebExchange webExchange = webApplication.buildExchange(request, response);
        return new WebContext(webExchange);
    }

    /**
     * 重定向
     */
    protected void redirect(HttpServletResponse response, String url) throws IOException {
        response.sendRedirect(url);
    }

    /**
     * 返回JSON响应
     */
    protected void writeJson(HttpServletResponse response, String json) throws IOException {
        response.setContentType("application/json;charset=UTF-8");
        response.getWriter().write(json);
    }

    /**
     * 获取当前登录用户ID
     */
    protected Long getCurrentUserId(HttpServletRequest request) {
        Object userId = request.getSession().getAttribute("userId");
        return userId != null ? (Long) userId : null;
    }

    /**
     * 检查用户是否登录
     */
    protected boolean isLoggedIn(HttpServletRequest request) {
        return request.getSession().getAttribute("userId") != null;
    }

    /**
     * 检查用户是否是管理员
     */
    protected boolean isAdmin(HttpServletRequest request) {
        Object role = request.getSession().getAttribute("userRole");
        return "ADMIN".equals(role);
    }
}
