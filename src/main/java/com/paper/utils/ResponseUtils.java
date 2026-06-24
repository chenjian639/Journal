package com.paper.utils;

import java.util.HashMap;
import java.util.Map;

/**
 * API响应工具类
 * 统一API响应格式
 */
public class ResponseUtils {

    /**
     * 创建成功响应
     * 
     * @param message 成功消息
     * @return 响应Map
     */
    public static Map<String, Object> success(String message) {
        Map<String, Object> response = new HashMap<>();
        response.put("success", true);
        response.put("message", message);
        return response;
    }

    /**
     * 创建成功响应（带数据）
     * 
     * @param message 成功消息
     * @param data 响应数据
     * @return 响应Map
     */
    public static Map<String, Object> success(String message, Map<String, Object> data) {
        Map<String, Object> response = new HashMap<>(data);
        response.put("success", true);
        response.put("message", message);
        return response;
    }

    /**
     * 创建失败响应
     * 
     * @param message 错误消息
     * @return 响应Map
     */
    public static Map<String, Object> error(String message) {
        Map<String, Object> response = new HashMap<>();
        response.put("success", false);
        response.put("message", message);
        return response;
    }
}
