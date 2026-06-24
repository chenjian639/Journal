package com.paper.utils;

import java.io.BufferedReader;
import java.io.IOException;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.io.OutputStream;
import java.net.HttpURLConnection;
import java.net.URI;
import java.net.URL;
import java.nio.charset.StandardCharsets;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.stereotype.Component;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.paper.config.AIPromptProperties;
import com.paper.config.AIProperties;

/**
 * AI客户端工具类 - 使用Spring配置注入
 * 调用DeepSeek或其他OpenAI兼容的API
 */
@Component
public class AIClient {
    
    private static final ObjectMapper objectMapper = new ObjectMapper();

    // Upstream API error: "Input length ... exceeds the maximum length 98304"
    // The limit is typically enforced on request content length; use a safety margin for JSON overhead.
    private static final int MAX_INPUT_BYTES = 98_304;
    private static final int INPUT_SAFETY_BYTES = 4_096;
    private static final int MAX_MESSAGE_CONTENT_BYTES = MAX_INPUT_BYTES - INPUT_SAFETY_BYTES;
    private static final String TRUNCATION_NOTE = "\n\n[内容过长，已截断]\n";
    
    private final AIProperties aiProperties;
    private final AIPromptProperties promptProperties;
    private final ResourceLoader resourceLoader;
    
    @Autowired
    public AIClient(AIProperties aiProperties, 
                    AIPromptProperties promptProperties,
                    ResourceLoader resourceLoader) {
        this.aiProperties = aiProperties;
        this.promptProperties = promptProperties;
        this.resourceLoader = resourceLoader;
    }
    
    /**
     * 调用OpenAI兼容的Chat Completions API
     */
    public String callChatCompletion(String systemPrompt, String userPrompt) 
            throws IOException {
        return callChatCompletion(systemPrompt, userPrompt, aiProperties.getTimeout());
    }
    
    /**
     * 调用OpenAI兼容的Chat Completions API（带超时）
     */
    public String callChatCompletion(String systemPrompt, String userPrompt, 
                                   double timeoutSeconds) throws IOException {
        String baseUrl = aiProperties.getBaseUrl();
        String apiKey = aiProperties.getKey();
        String model = aiProperties.getModel();

        if (baseUrl != null) baseUrl = baseUrl.trim();
        if (apiKey != null) apiKey = apiKey.trim();
        if (model != null) model = model.trim();
        
        if (baseUrl == null || baseUrl.isEmpty()) {
            throw new RuntimeException("未配置 ai.api.base-url");
        }
        if (apiKey == null || apiKey.isEmpty()) {
            throw new RuntimeException("未配置 ai.api.key");
        }
        if (model == null || model.isEmpty()) {
            throw new RuntimeException("未配置 ai.api.model");
        }
        
        String endpoint = baseUrl.replaceAll("/$", "") + "/chat/completions";

        // Guardrail: prevent 400 due to oversized input.
        String safeSystemPrompt = systemPrompt;
        String safeUserPrompt = userPrompt;
        if (safeUserPrompt == null) safeUserPrompt = "";
        if (safeSystemPrompt == null) safeSystemPrompt = "";

        int userBytes = safeUserPrompt.getBytes(StandardCharsets.UTF_8).length;
        int systemBytes = safeSystemPrompt.getBytes(StandardCharsets.UTF_8).length;
        if (systemBytes + userBytes > MAX_MESSAGE_CONTENT_BYTES) {
            // Keep user prompt as much as possible, truncate system prompt first.
            int remainingForSystem = Math.max(0, MAX_MESSAGE_CONTENT_BYTES - userBytes);
            safeSystemPrompt = truncateUtf8(safeSystemPrompt, remainingForSystem, TRUNCATION_NOTE);

            // If still too large (e.g., user prompt itself is huge), truncate user prompt too.
            systemBytes = safeSystemPrompt.getBytes(StandardCharsets.UTF_8).length;
            userBytes = safeUserPrompt.getBytes(StandardCharsets.UTF_8).length;
            if (systemBytes + userBytes > MAX_MESSAGE_CONTENT_BYTES) {
                int remainingForUser = Math.max(0, MAX_MESSAGE_CONTENT_BYTES - systemBytes);
                safeUserPrompt = truncateUtf8(safeUserPrompt, remainingForUser, TRUNCATION_NOTE);
            }
        }

        // Second guardrail: some providers enforce the limit on the request "input" length
        // after JSON escaping/serialization. So we ensure the final JSON payload bytes are within MAX_INPUT_BYTES.
        String jsonPayload = buildPayloadJson(model, safeSystemPrompt, safeUserPrompt);
        if (jsonPayload.getBytes(StandardCharsets.UTF_8).length > MAX_INPUT_BYTES) {
            // Prefer trimming system prompt first (context is usually there).
            safeSystemPrompt = shrinkToFitPayload(model, safeSystemPrompt, safeUserPrompt, true);
            jsonPayload = buildPayloadJson(model, safeSystemPrompt, safeUserPrompt);

            // If still too large, trim user prompt as well.
            if (jsonPayload.getBytes(StandardCharsets.UTF_8).length > MAX_INPUT_BYTES) {
                safeUserPrompt = shrinkToFitPayload(model, safeSystemPrompt, safeUserPrompt, false);
                jsonPayload = buildPayloadJson(model, safeSystemPrompt, safeUserPrompt);
            }
        }
        
        // 发送HTTP POST请求
        URL url = URI.create(endpoint).toURL();
        HttpURLConnection conn = (HttpURLConnection) url.openConnection();
        conn.setRequestMethod("POST");
        conn.setRequestProperty("Authorization", "Bearer " + apiKey);
        conn.setRequestProperty("Content-Type", "application/json");
        conn.setDoOutput(true);
        conn.setConnectTimeout((int) (timeoutSeconds * 1000));
        conn.setReadTimeout((int) (timeoutSeconds * 1000));
        
        // 发送请求体
        try (OutputStream os = conn.getOutputStream()) {
            byte[] input = jsonPayload.getBytes(StandardCharsets.UTF_8);
            os.write(input, 0, input.length);
        }
        
        // 读取响应
        int responseCode = conn.getResponseCode();
        if (responseCode != 200) {
            try (BufferedReader br = new BufferedReader(
                    new InputStreamReader(conn.getErrorStream(), StandardCharsets.UTF_8))) {
                StringBuilder response = new StringBuilder();
                String line;
                while ((line = br.readLine()) != null) {
                    response.append(line);
                }
                throw new IOException("API调用失败，响应码: " + responseCode + 
                    ", 错误信息: " + response.toString());
            }
        }
        
        try (BufferedReader br = new BufferedReader(
                new InputStreamReader(conn.getInputStream(), StandardCharsets.UTF_8))) {
            StringBuilder response = new StringBuilder();
            String line;
            while ((line = br.readLine()) != null) {
                response.append(line);
            }
            
            // 解析响应
            var root = objectMapper.readTree(response.toString());
            try {
                return root.get("choices").get(0).get("message").get("content").asText().strip();
            } catch (Exception e) {
                // 兜底：返回原始响应
                return response.toString();
            }
        }
    }
    
    /**
     * 加载期刊详情系统提示词
     */
    public String loadJournalDetailPrompt() {
        return loadPrompt(promptProperties.getJournalDetail());
    }
    
    /**
     * 加载推荐匹配系统提示词
     */
    public String loadRecommendMatchPrompt() {
        return loadPrompt(promptProperties.getRecommendMatch());
    }
    
    /**
     * 加载系统提示词
     */
    private String loadPrompt(String path) {
        if (path == null || path.isEmpty()) {
            return "";
        }
        
        try {
            Resource resource = resourceLoader.getResource(path);
            if (resource.exists()) {
                try (InputStream is = resource.getInputStream()) {
                    return new String(is.readAllBytes(), StandardCharsets.UTF_8).strip();
                }
            }
        } catch (IOException e) {
            System.err.println("Failed to load prompt file: " + path + ", " + e.getMessage());
        }
        return "";
    }
    
    /**
     * 获取当前配置信息
     */
    public Map<String, String> getConfig() {
        Map<String, String> config = new HashMap<>();
        config.put("baseUrl", aiProperties.getBaseUrl());
        config.put("model", aiProperties.getModel());
        config.put("apiKeySet", 
            aiProperties.getKey() != null && !aiProperties.getKey().isEmpty() ? "true" : "false");
        return config;
    }

    private static String truncateUtf8(String text, int maxBytes, String truncationNote) {
        if (text == null) return "";
        if (maxBytes <= 0) return "";

        byte[] bytes = text.getBytes(StandardCharsets.UTF_8);
        if (bytes.length <= maxBytes) return text;

        String note = truncationNote == null ? "" : truncationNote;
        int noteBytes = note.getBytes(StandardCharsets.UTF_8).length;
        int targetBytes = Math.max(0, maxBytes - noteBytes);

        // Binary search the max prefix length that fits in targetBytes.
        int lo = 0;
        int hi = text.length();
        while (lo < hi) {
            int mid = (lo + hi + 1) >>> 1;
            int midBytes = text.substring(0, mid).getBytes(StandardCharsets.UTF_8).length;
            if (midBytes <= targetBytes) {
                lo = mid;
            } else {
                hi = mid - 1;
            }
        }

        String prefix = text.substring(0, lo);
        String result = prefix + note;

        // Final clamp (in case note pushed it over due to edge cases)
        byte[] finalBytes = result.getBytes(StandardCharsets.UTF_8);
        if (finalBytes.length <= maxBytes) return result;
        return prefix;
    }

    private static String buildPayloadJson(String model, String systemPrompt, String userPrompt) throws IOException {
        Map<String, Object> payload = new HashMap<>();
        payload.put("model", model);
        payload.put("temperature", 0.2);

        List<Map<String, String>> messages = new ArrayList<>();
        if (systemPrompt != null && !systemPrompt.isEmpty()) {
            messages.add(Map.of("role", "system", "content", systemPrompt));
        }
        messages.add(Map.of("role", "user", "content", userPrompt == null ? "" : userPrompt));
        payload.put("messages", messages);
        return objectMapper.writeValueAsString(payload);
    }

    private static String shrinkToFitPayload(String model, String systemPrompt, String userPrompt, boolean shrinkSystem) throws IOException {
        String original = shrinkSystem ? (systemPrompt == null ? "" : systemPrompt) : (userPrompt == null ? "" : userPrompt);
        if (original.isEmpty()) return original;

        // Binary search the maximum prefix length that fits after JSON serialization.
        int lo = 0;
        int hi = original.length();
        while (lo < hi) {
            int mid = (lo + hi + 1) >>> 1;
            String candidate = original.substring(0, mid) + TRUNCATION_NOTE;
            String json = shrinkSystem
                    ? buildPayloadJson(model, candidate, userPrompt)
                    : buildPayloadJson(model, systemPrompt, candidate);
            int bytes = json.getBytes(StandardCharsets.UTF_8).length;
            if (bytes <= MAX_INPUT_BYTES) {
                lo = mid;
            } else {
                hi = mid - 1;
            }
        }

        if (lo <= 0) {
            // Even the note might not fit; return empty to avoid 400.
            return "";
        }
        String result = original.substring(0, lo) + TRUNCATION_NOTE;

        // Final clamp by bytes just in case.
        String json = shrinkSystem
                ? buildPayloadJson(model, result, userPrompt)
                : buildPayloadJson(model, systemPrompt, result);
        if (json.getBytes(StandardCharsets.UTF_8).length <= MAX_INPUT_BYTES) {
            return result;
        }

        // Fall back to byte-based truncation if needed.
        int keepBytes = Math.max(0, (MAX_INPUT_BYTES / 2));
        return truncateUtf8(original, keepBytes, TRUNCATION_NOTE);
    }
}
