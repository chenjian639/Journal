package com.journal.listener;

import com.journal.config.ThymeleafConfig;
import com.journal.util.DBUtil;
import org.slf4j.Logger;
import org.slf4j.LoggerFactory;

import javax.servlet.ServletContext;
import javax.servlet.ServletContextEvent;
import javax.servlet.ServletContextListener;
import javax.servlet.annotation.WebListener;

/**
 * 应用启动监听器
 */
@WebListener
public class AppInitListener implements ServletContextListener {
    private static final Logger logger = LoggerFactory.getLogger(AppInitListener.class);

    @Override
    public void contextInitialized(ServletContextEvent sce) {
        logger.info("期刊分析系统启动中...");
        
        ServletContext servletContext = sce.getServletContext();
        
        // 初始化Thymeleaf
        ThymeleafConfig.init(servletContext);
        logger.info("Thymeleaf模板引擎初始化完成");
        
        // 设置应用上下文路径
        servletContext.setAttribute("ctx", servletContext.getContextPath());
        
        logger.info("期刊分析系统启动完成！");
    }

    @Override
    public void contextDestroyed(ServletContextEvent sce) {
        logger.info("期刊分析系统关闭中...");
        
        // 关闭数据库连接池
        DBUtil.closeDataSource();
        
        logger.info("期刊分析系统已关闭");
    }
}
