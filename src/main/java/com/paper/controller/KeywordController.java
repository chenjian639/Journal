package com.paper.controller;

import java.util.HashMap;
import java.util.List;
import java.util.Map;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.web.bind.annotation.GetMapping;
import org.springframework.web.bind.annotation.PostMapping;
import org.springframework.web.bind.annotation.RequestMapping;
import org.springframework.web.bind.annotation.RequestParam;
import org.springframework.web.bind.annotation.RestController;

import com.paper.service.KeywordAnalysisService;
import com.paper.utils.ResponseUtils;

@RestController
@RequestMapping("/keyword")
public class KeywordController {

    private final KeywordAnalysisService keywordService;

    @Autowired
    public KeywordController(KeywordAnalysisService keywordService) {
        this.keywordService = keywordService;
    }

    @GetMapping("/status")
    public Map<String, Object> status(@RequestParam(name = "username", required = false) String username,
                                      @RequestParam(name = "filename", required = false) String filename) {
        Map<String, Object> data = new HashMap<>();
        data.put("status", keywordService.getStatus(username, filename));
        return ResponseUtils.success("ok", data);
    }

    @PostMapping("/build-index")
    public Map<String, Object> buildIndex(@RequestParam(name = "force", required = false, defaultValue = "false") boolean force,
                                          @RequestParam(name = "username", required = false) String username,
                                          @RequestParam(name = "filename", required = false) String filename) {
        Map<String, Object> data = new HashMap<>();
        data.put("result", keywordService.buildIndexAsync(force, username, filename));
        data.put("status", keywordService.getStatus(username, filename));
        return ResponseUtils.success("accepted", data);
    }

    @GetMapping("/analyze")
    public Map<String, Object> analyze(@RequestParam("keyword") String keyword,
                                       @RequestParam(name = "page", required = false, defaultValue = "1") int page,
                                       @RequestParam(name = "size", required = false, defaultValue = "20") int size,
                                       @RequestParam(name = "username", required = false) String username,
                                       @RequestParam(name = "filename", required = false) String filename) {
        Map<String, Object> analysis = keywordService.analyzeKeyword(keyword, page, size, username, filename);
        if (analysis.containsKey("error")) {
            return ResponseUtils.error(String.valueOf(analysis.get("error")));
        }
        Map<String, Object> data = new HashMap<>();
        data.put("analysis", analysis);
        return ResponseUtils.success("ok", data);
    }

    @GetMapping("/top")
    public Map<String, Object> top(@RequestParam(name = "limit", required = false, defaultValue = "30") int limit,
                                   @RequestParam(name = "username", required = false) String username,
                                   @RequestParam(name = "filename", required = false) String filename) {
        List<Map<String, Object>> rows = keywordService.topKeywords(limit, username, filename);
        Map<String, Object> data = new HashMap<>();
        data.put("rows", rows);
        return ResponseUtils.success("ok", data);
    }
}
