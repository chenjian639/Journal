package com.journal.config;

import org.thymeleaf.TemplateEngine;
import org.thymeleaf.templatemode.TemplateMode;
import org.thymeleaf.web.servlet.JavaxServletWebApplication;
import org.thymeleaf.templateresolver.WebApplicationTemplateResolver;

import javax.servlet.ServletContext;

/**
 * Thymeleaf配置类
 */
public class ThymeleafConfig {
    private static TemplateEngine templateEngine;
    private static JavaxServletWebApplication webApplication;

    /**
     * 初始化Thymeleaf模板引擎
     */
    public static void init(ServletContext servletContext) {
        // 创建Web应用程序包装
        webApplication = JavaxServletWebApplication.buildApplication(servletContext);
        
        // 创建模板解析器
        WebApplicationTemplateResolver templateResolver = new WebApplicationTemplateResolver(webApplication);
        templateResolver.setTemplateMode(TemplateMode.HTML);
        templateResolver.setPrefix("/WEB-INF/templates/");
        templateResolver.setSuffix(".html");
        templateResolver.setCharacterEncoding("UTF-8");
        templateResolver.setCacheable(false); // 开发环境关闭缓存

        // 创建模板引擎
        templateEngine = new TemplateEngine();
        templateEngine.setTemplateResolver(templateResolver);
    }

    /**
     * 获取模板引擎
     */
    public static TemplateEngine getTemplateEngine() {
        return templateEngine;
    }

    /**
     * 获取Web应用程序包装
     */
    public static JavaxServletWebApplication getWebApplication() {
        return webApplication;
    }
}
