package com.paper.model;

import java.util.Arrays;
import java.util.List;
import java.util.Locale;

/**
 * 期刊排名指标（页面与查询层统一使用的白名单）。
 *
 * 注意：id 会直接传给 Repository 的 native query，并通过 CASE 分支选择排序字段，
 * 因此必须严格受控，避免任何拼接式 ORDER BY 带来的注入风险。
 */
public enum JournalRankingMetric {
    FRONTIER("frontier", "内容前沿性", "颠覆性 + 新颖性（综合）"),
    DISRUPTION("disruption", "颠覆性", "颠覆性指标"),
    NOVELTY("novelty", "新颖性", "新颖性指标"),
    INTERDISCIPLINARY("interdisciplinary", "跨学科性", "跨学科性指标"),
    TOPIC("topic", "主题多样性", "主题多样性/复杂度"),
    THEME_CONCENTRATION("theme_concentration", "主题集中度", "主题集中度"),
    HOT_RESPONSE("hot_response", "热点响应度", "热点响应度"),
    PAPER_COUNT("paper_count", "论文数量", "该年论文数量"),
    ;

    private final String id;
    private final String label;
    private final String description;

    JournalRankingMetric(String id, String label, String description) {
        this.id = id;
        this.label = label;
        this.description = description;
    }

    public String getId() {
        return id;
    }

    public String getLabel() {
        return label;
    }

    public String getDescription() {
        return description;
    }

    public static List<JournalRankingMetric> all() {
        return List.of(values());
    }

    public static JournalRankingMetric fromIdOrDefault(String id, JournalRankingMetric fallback) {
        if (id == null || id.isBlank()) {
            return fallback;
        }
        final String norm = id.trim().toLowerCase(Locale.ROOT);
        return Arrays.stream(values())
            .filter(m -> m.id.equals(norm))
            .findFirst()
            .orElse(fallback);
    }

    /**
     * 计算某条记录在该指标上的展示值（用于页面显示“本次排序分值”）。
     */
    public double computeValue(JournalMetrics row) {
        if (row == null) {
            return 0.0;
        }

        return switch (this) {
            case FRONTIER -> nz(row.getDisruption()) + nz(row.getNovelty());
            case DISRUPTION -> nz(row.getDisruption());
            case NOVELTY -> nz(row.getNovelty());
            case INTERDISCIPLINARY -> nz(row.getInterdisciplinary());
            case TOPIC -> nz(row.getTopic());
            case THEME_CONCENTRATION -> nz(row.getThemeConcentration());
            case HOT_RESPONSE -> nz(row.getHotResponse());
            case PAPER_COUNT -> row.getPaperCount() == null ? 0.0 : row.getPaperCount().doubleValue();
        };
    }

    private static double nz(Double v) {
        return v == null ? 0.0 : v;
    }
}
