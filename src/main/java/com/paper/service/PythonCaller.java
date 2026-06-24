package com.paper.service;

import java.io.BufferedReader;
import java.io.File;
import java.io.InputStreamReader;
import java.util.List;
import java.util.Map;

import com.fasterxml.jackson.databind.ObjectMapper;
import com.paper.model.Paper;

/**
 * Python脚本调用器
 * 用于实现Java与Python脚本的交互，执行数据分析任务
 */
public class PythonCaller {
    
    private static final String PYTHON_SCRIPT_PATH = "src/main/resources/python/data_analysis.py";
    private static final ObjectMapper objectMapper = new ObjectMapper();

    /**
     * 调用Python脚本进行论文数据分析
     * @param papers 论文数据列表
     * @return 分析结果（JSON格式的Map）
     */
    public Map<String, Object> analyzePapers(List<Paper> papers) throws Exception {
        String papersJson = objectMapper.writeValueAsString(papers);

        ProcessBuilder processBuilder = new ProcessBuilder(
                "python", PYTHON_SCRIPT_PATH, papersJson
        );

        processBuilder.directory(new File("."));
        processBuilder.redirectErrorStream(true);

        Process process = processBuilder.start();

        StringBuilder output = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line);
            }
        }

        int exitCode = process.waitFor();

        if (exitCode != 0) {
            throw new RuntimeException("Python脚本执行失败，退出码: " + exitCode + "，输出: " + output.toString());
        }

        return objectMapper.readValue(output.toString(), Map.class);
    }

    /**
     * 调用Python脚本的重载方法
     * @param pythonScriptPath Python脚本路径
     * @param inputJson 输入JSON数据
     * @return 脚本输出结果
     */
    public String callPythonScript(String pythonScriptPath, String inputJson) throws Exception {
        ProcessBuilder processBuilder = new ProcessBuilder(
                "python", pythonScriptPath, inputJson
        );

        processBuilder.directory(new File("."));
        processBuilder.redirectErrorStream(true);

        Process process = processBuilder.start();

        StringBuilder output = new StringBuilder();
        try (BufferedReader reader = new BufferedReader(
                new InputStreamReader(process.getInputStream(), "UTF-8"))) {
            String line;
            while ((line = reader.readLine()) != null) {
                output.append(line);
            }
        }

        int exitCode = process.waitFor();

        if (exitCode != 0) {
            throw new RuntimeException("Python脚本执行失败，退出码: " + exitCode + "，输出: " + output.toString());
        }

        return output.toString();
    }
}
