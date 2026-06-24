package com.paper.config;

import org.springframework.boot.context.properties.ConfigurationProperties;
import org.springframework.context.annotation.Configuration;

/**
 * AI提示词配置类
 */
@Configuration
@ConfigurationProperties(prefix = "ai.prompt")
public class AIPromptProperties {
    
    private String journalDetail;
    private String recommendMatch;
    
    // Getters and Setters
    public String getJournalDetail() {
        return journalDetail;
    }
    
    public void setJournalDetail(String journalDetail) {
        this.journalDetail = journalDetail;
    }
    
    public String getRecommendMatch() {
        return recommendMatch;
    }
    
    public void setRecommendMatch(String recommendMatch) {
        this.recommendMatch = recommendMatch;
    }
}
