package com.paper.utils;

import java.util.ArrayList;
import java.util.LinkedHashSet;
import java.util.List;
import java.util.Locale;
import java.util.Set;

import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;

public final class KeywordParser {
    private static final ObjectMapper OBJECT_MAPPER = new ObjectMapper();

    private KeywordParser() {
    }

    public static Set<String> parseNormalizedKeywords(String rawKeywords) {
        if (rawKeywords == null) {
            return Set.of();
        }

        String s = rawKeywords.trim();
        if (s.isEmpty()) {
            return Set.of();
        }

        LinkedHashSet<String> out = new LinkedHashSet<>();

        // Common formats observed:
        // - JSON array: ["a","b"]
        // - Python-like list: ['a','b']
        // - Delimited: a; b, c | d
        if (s.startsWith("[") && s.endsWith("]")) {
            List<String> parsed = tryParseArrayLike(s);
            if (parsed != null) {
                for (String k : parsed) {
                    addNormalized(out, k);
                }
                return out;
            }
        }

        // Fallback: treat as delimited text
        for (String part : splitBySeparators(s)) {
            addNormalized(out, part);
        }

        return out;
    }

    private static List<String> tryParseArrayLike(String s) {
        // First try strict JSON
        try {
            return OBJECT_MAPPER.readValue(s, new TypeReference<List<String>>() {
            });
        } catch (Exception ignore) {
            // ignore
        }

        // Heuristic: python-like single-quoted list without embedded double-quotes
        if (s.indexOf('"') < 0 && s.indexOf('\'') >= 0) {
            String maybeJson = s.replace('\'', '"');
            try {
                return OBJECT_MAPPER.readValue(maybeJson, new TypeReference<List<String>>() {
                });
            } catch (Exception ignore) {
                // ignore
            }
        }

        return null;
    }

    private static List<String> splitBySeparators(String s) {
        String normalized = s;
        String[] seps = { "\n", "\r", "\t", ";", "；", ",", "，", "|", "/" };
        for (String sep : seps) {
            normalized = normalized.replace(sep, ",");
        }

        String[] parts = normalized.split(",");
        List<String> out = new ArrayList<>();
        for (String p : parts) {
            String t = p.trim();
            if (!t.isEmpty()) {
                out.add(t);
            }
        }
        return out;
    }

    private static void addNormalized(Set<String> out, String keyword) {
        if (keyword == null) {
            return;
        }

        String t = keyword.trim();
        if (t.isEmpty()) {
            return;
        }

        // Strip surrounding quotes
        if ((t.startsWith("\"") && t.endsWith("\"")) || (t.startsWith("'") && t.endsWith("'"))) {
            if (t.length() >= 2) {
                t = t.substring(1, t.length() - 1).trim();
            }
        }

        t = t.replaceAll("\\s+", " ");
        if (t.isEmpty()) {
            return;
        }

        // Normalize key for stable matching
        String normalizedKey = t.toLowerCase(Locale.ROOT);
        if (normalizedKey.length() > 100) {
            normalizedKey = normalizedKey.substring(0, 100);
        }
        out.add(normalizedKey);
    }
}
