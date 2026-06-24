package com.paper.config;

import org.springframework.boot.ApplicationArguments;
import org.springframework.boot.CommandLineRunner;
import org.springframework.stereotype.Component;

@Component
public class AIConfigProbeRunner implements CommandLineRunner {

    private final AIProperties aiProperties;
    private final ApplicationArguments applicationArguments;

    public AIConfigProbeRunner(AIProperties aiProperties, ApplicationArguments applicationArguments) {
        this.aiProperties = aiProperties;
        this.applicationArguments = applicationArguments;
    }

    @Override
    public void run(String... args) {
        boolean keyProvidedByArgs = applicationArguments.containsOption("ai.api.key");

        System.out.println("======================================");
        System.out.println("[AI Config] Effective configuration:");
        System.out.println("  ai.api.base-url = " + nullToEmpty(aiProperties.getBaseUrl()));
        System.out.println("  ai.api.model    = " + nullToEmpty(aiProperties.getModel()));
        System.out.println("  ai.api.timeout  = " + aiProperties.getTimeout());
        System.out.println("  ai.api.key      = " + maskKey(aiProperties.getKey()));
        System.out.println("  ai.api.key from command-line args? " + keyProvidedByArgs);
        System.out.println("======================================");
    }

    private static String maskKey(String key) {
        if (key == null || key.isBlank()) {
            return "(empty)";
        }

        String trimmed = key.trim();
        int len = trimmed.length();
        if (len <= 6) {
            return "*** (len=" + len + ")";
        }

        return trimmed.substring(0, 4) + "..." + trimmed.substring(len - 2) + " (len=" + len + ")";
    }

    private static String nullToEmpty(String value) {
        return value == null ? "" : value;
    }
}
