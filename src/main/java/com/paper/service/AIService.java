package com.paper.service;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.JsonNode;
import com.fasterxml.jackson.databind.ObjectMapper;
import com.paper.config.EnvConfig;

/**
 * AI 服务类
 * 调用 DeepSeek API 进行智能对话
 */
public class AIService {
    
    private static final ObjectMapper objectMapper = new ObjectMapper();
    private static final int CONNECT_TIMEOUT = 30000;
    private static final int READ_TIMEOUT = 60000;
    
    /**
     * 发送消息给 AI 并获取回复
     */
    public String chat(String message) throws IOException {
        return chat(message, null);
    }
    
    /**
     * 发送消息给 AI 并获取回复（带系统提示）
     */
    public String chat(String message, String systemPrompt) throws IOException {
        String apiKey = EnvConfig.get(EnvConfig.DEEPSEEK_API_KEY);
        
        // 检查 API Key 是否配置
        if (apiKey == null || apiKey.isEmpty() || apiKey.startsWith("your-")) {
            return "错误：DeepSeek API Key 未配置。请在 .env 文件中设置 DEEPSEEK_API_KEY";
        }
        
        String apiBase = EnvConfig.get(EnvConfig.DEEPSEEK_API_BASE, "https://api.deepseek.com/v1");
        String model = EnvConfig.get(EnvConfig.DEEPSEEK_MODEL, "deepseek-chat");
        
        URL url = new URL(apiBase + "/chat/completions");
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        
        try {
            conn.setRequestMethod("POST");
            conn.setRequestProperty("Content-Type", "application/json");
            conn.setRequestProperty("Authorization", "Bearer " + apiKey);
            conn.setDoOutput(true);
            conn.setConnectTimeout(CONNECT_TIMEOUT);
            conn.setReadTimeout(READ_TIMEOUT);
            
            // 构建消息列表
            List<Map<String, String>> messages = new ArrayList<>();
            
            if (systemPrompt != null && !systemPrompt.isEmpty()) {
                Map<String, String> systemMsg = new HashMap<>();
                systemMsg.put("role", "system");
                systemMsg.put("content", systemPrompt);
                messages.add(systemMsg);
            }
            
            Map<String, String> userMsg = new HashMap<>();
            userMsg.put("role", "user");
            userMsg.put("content", message);
            messages.add(userMsg);
            
            // 构建请求体
            Map<String, Object> requestBody = new HashMap<>();
            requestBody.put("model", model);
            requestBody.put("messages", messages);
            requestBody.put("max_tokens", 2000);
            
            String jsonRequest = objectMapper.writeValueAsString(requestBody);
            
            try (OutputStream os = conn.getOutputStream()) {
                os.write(jsonRequest.getBytes(StandardCharsets.UTF_8));
            }
            
            int responseCode = conn.getResponseCode();
            
            if (responseCode == HttpURLConnection.HTTP_OK) {
                return parseResponse(conn);
            } else {
                return parseError(conn, responseCode);
            }
        } finally {
            conn.disconnect();
        }
    }
    
    private String parseResponse(HttpURLConnection conn) throws IOException {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
            StringBuilder response = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                response.append(line);
            }
            JsonNode jsonResponse = objectMapper.readTree(response.toString());
            return jsonResponse.path("choices").path(0).path("message").path("content").asText();
        }
    }
    
    private String parseError(HttpURLConnection conn, int responseCode) throws IOException {
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(conn.getErrorStream(), StandardCharsets.UTF_8))) {
            StringBuilder error = new StringBuilder();
            String line;
            while ((line = reader.readLine()) != null) {
                error.append(line);
            }
            return "API 调用失败 (" + responseCode + "): " + error;
        }
    }
}
