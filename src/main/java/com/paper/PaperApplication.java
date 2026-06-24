package com.paper;

import java.io.PrintStream;
import java.nio.charset.StandardCharsets;

import org.springframework.boot.SpringApplication;
import org.springframework.boot.autoconfigure.SpringBootApplication;

/**
 * 学术论文管理系统 - 启动类
 * 
 * 包结构说明：
 * - com.paper.controller: HTTP请求控制器
 * - com.paper.service: 业务逻辑层
 * - com.paper.dao: 数据访问层
 * - com.paper.model: 数据模型/实体类
 * - com.paper.utils: 工具类（数据库配置、初始化等）
 */
@SpringBootApplication
public class PaperApplication {

    public static void main(String[] args) {
        // 设置控制台输出编码为 UTF-8，解决中文乱码
        try {
            System.setOut(new PrintStream(System.out, true, StandardCharsets.UTF_8));
            System.setErr(new PrintStream(System.err, true, StandardCharsets.UTF_8));
        } catch (Exception e) {
            // 忽略编码设置失败
        }
        
        SpringApplication.run(PaperApplication.class, args);
    }

}
