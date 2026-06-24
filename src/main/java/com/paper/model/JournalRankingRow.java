package com.paper.model;

/**
 * 排名页展示用行模型（不落库）。
 */
public class JournalRankingRow {
    private final int rank;
    private final int quartile;
    private final double metricValue;
    private final JournalMetrics row;
    private final String note;

    public JournalRankingRow(int rank, int quartile, double metricValue, JournalMetrics row) {
        this.rank = rank;
        this.quartile = quartile;
        this.metricValue = metricValue;
        this.row = row;
        this.note = null;
    }

    public JournalRankingRow(int rank, int quartile, double metricValue, JournalMetrics row, String note) {
        this.rank = rank;
        this.quartile = quartile;
        this.metricValue = metricValue;
        this.row = row;
        this.note = (note == null || note.isBlank()) ? null : note;
    }

    public int getRank() {
        return rank;
    }

    public int getQuartile() {
        return quartile;
    }

    public double getMetricValue() {
        return metricValue;
    }

    public JournalMetrics getRow() {
        return row;
    }

    public String getNote() {
        return note;
    }
}
