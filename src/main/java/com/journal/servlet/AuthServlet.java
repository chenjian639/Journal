package com.journal.servlet;

import com.journal.entity.User;
import com.journal.service.UserService;
import com.journal.util.StringUtil;
import org.thymeleaf.context.WebContext;

import javax.servlet.annotation.WebServlet;
import javax.servlet.http.HttpServletRequest;
import javax.servlet.http.HttpServletResponse;
import javax.servlet.http.HttpSession;
import java.io.IOException;

/**
 * 用户认证Servlet（登录、注册、登出）
 */
@WebServlet(name = "AuthServlet", urlPatterns = {"/login", "/register", "/logout"})
public class AuthServlet extends BaseServlet {
    private UserService userService = new UserService();

    @Override
    protected void doGet(HttpServletRequest request, HttpServletResponse response) throws IOException {
        String path = request.getServletPath();
        WebContext context = createWebContext(request, response);
        
        switch (path) {
            case "/login":
                if (isLoggedIn(request)) {
                    redirect(response, request.getContextPath() + "/");
                    return;
                }
                render(request, response, "login", context);
                break;
            case "/register":
                if (isLoggedIn(request)) {
                    redirect(response, request.getContextPath() + "/");
                    return;
                }
                render(request, response, "register", context);
                break;
            case "/logout":
                request.getSession().invalidate();
                redirect(response, request.getContextPath() + "/login");
                break;
            default:
                response.sendError(HttpServletResponse.SC_NOT_FOUND);
        }
    }

    @Override
    protected void doPost(HttpServletRequest request, HttpServletResponse response) throws IOException {
        request.setCharacterEncoding("UTF-8");
        String path = request.getServletPath();
        WebContext context = createWebContext(request, response);
        
        switch (path) {
            case "/login":
                handleLogin(request, response, context);
                break;
            case "/register":
                handleRegister(request, response, context);
                break;
            default:
                response.sendError(HttpServletResponse.SC_NOT_FOUND);
        }
    }

    /**
     * 处理登录请求
     */
    private void handleLogin(HttpServletRequest request, HttpServletResponse response, 
                             WebContext context) throws IOException {
        String username = request.getParameter("username");
        String password = request.getParameter("password");
        
        if (StringUtil.isEmpty(username) || StringUtil.isEmpty(password)) {
            context.setVariable("error", "用户名和密码不能为空");
            render(request, response, "login", context);
            return;
        }
        
        try {
            User user = userService.login(username, password);
            
            // 设置Session
            HttpSession session = request.getSession();
            session.setAttribute("userId", user.getId());
            session.setAttribute("username", user.getUsername());
            session.setAttribute("userRole", user.getRole());
            session.setAttribute("user", user);
            
            redirect(response, request.getContextPath() + "/");
        } catch (Exception e) {
            context.setVariable("error", e.getMessage());
            context.setVariable("username", username);
            render(request, response, "login", context);
        }
    }

    /**
     * 处理注册请求
     */
    private void handleRegister(HttpServletRequest request, HttpServletResponse response, 
                                WebContext context) throws IOException {
        String username = request.getParameter("username");
        String password = request.getParameter("password");
        String confirmPassword = request.getParameter("confirmPassword");
        String email = request.getParameter("email");
        String realName = request.getParameter("realName");
        
        // 验证输入
        if (StringUtil.isEmpty(username) || StringUtil.isEmpty(password)) {
            context.setVariable("error", "用户名和密码不能为空");
            render(request, response, "register", context);
            return;
        }
        
        if (!password.equals(confirmPassword)) {
            context.setVariable("error", "两次输入的密码不一致");
            context.setVariable("username", username);
            context.setVariable("email", email);
            context.setVariable("realName", realName);
            render(request, response, "register", context);
            return;
        }
        
        try {
            userService.register(username, password, email, realName);
            context.setVariable("success", "注册成功，请登录");
            render(request, response, "login", context);
        } catch (Exception e) {
            context.setVariable("error", e.getMessage());
            context.setVariable("username", username);
            context.setVariable("email", email);
            context.setVariable("realName", realName);
            render(request, response, "register", context);
        }
    }
}
