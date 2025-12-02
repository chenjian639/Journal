package com.journal.filter;

import javax.servlet.*;
import javax.servlet.annotation.WebFilter;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;
import java.io.IOException;
import java.util.Arrays;
import java.util.List;

/**
 * 登录认证过滤器
 */
@WebFilter(filterName = "AuthFilter", urlPatterns = "/*")
public class AuthFilter implements Filter {
    
    // 不需要登录即可访问的路径
    private static final List<String> PUBLIC_PATHS = Arrays.asList(
            "/", "/index", "/login", "/register", "/journals", "/journal/",
            "/static/", "/css/", "/js/", "/images/"
    );

    @Override
    public void init(FilterConfig filterConfig) throws ServletException {
    }

    @Override
    public void doFilter(ServletRequest request, ServletResponse response, FilterChain chain)
            throws IOException, ServletException {
        HttpServletRequest httpRequest = (HttpServletRequest) request;
        HttpServletResponse httpResponse = (HttpServletResponse) response;
        
        String path = httpRequest.getServletPath();
        String pathInfo = httpRequest.getPathInfo();
        String fullPath = path + (pathInfo != null ? pathInfo : "");
        
        // 检查是否是公开路径
        if (isPublicPath(fullPath)) {
            chain.doFilter(request, response);
            return;
        }
        
        // 检查用户是否登录
        HttpSession session = httpRequest.getSession(false);
        if (session != null && session.getAttribute("userId") != null) {
            chain.doFilter(request, response);
            return;
        }
        
        // 未登录，重定向到登录页
        httpResponse.sendRedirect(httpRequest.getContextPath() + "/login");
    }

    private boolean isPublicPath(String path) {
        for (String publicPath : PUBLIC_PATHS) {
            if (path.equals(publicPath) || path.startsWith(publicPath)) {
                return true;
            }
        }
        // 允许查看期刊详情
        if (path.matches("/journal/\\d+")) {
            return true;
        }
        return false;
    }

    @Override
    public void destroy() {
    }
}
