package com.paper.service;

import java.io.BufferedReader;
import java.io.IOException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.Paths;
import java.sql.Connection;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.time.Instant;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.concurrent.ExecutorService;
import java.util.concurrent.Executors;
import java.util.concurrent.atomic.AtomicBoolean;
import java.util.concurrent.atomic.AtomicInteger;
import java.util.concurrent.atomic.AtomicLong;

import javax.sql.DataSource;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;
import org.springframework.stereotype.Service;

import com.paper.utils.KeywordParser;
import com.paper.utils.ValidationUtils;

@Service
public class KeywordAnalysisService {

    private final DataSource dataSource;

    private final ExecutorService executor = Executors.newSingleThreadExecutor(r -> {
        Thread t = new Thread(r, "keyword-index-builder");
        t.setDaemon(true);
        return t;
    });

    private final AtomicBoolean building = new AtomicBoolean(false);
    private final AtomicInteger totalPapers = new AtomicInteger(0);
    private final AtomicInteger processedPapers = new AtomicInteger(0);
    private final AtomicLong insertedRows = new AtomicLong(0);
    private volatile String lastError = null;
    private volatile Instant startedAt = null;
    private volatile Instant finishedAt = null;

    public KeywordAnalysisService(DataSource dataSource) {
        this.dataSource = dataSource;
    }

    public Map<String, Object> getStatus(String username, String filename) {
        ensureIndexTablesExistQuietly();

        boolean datasetMode = isDatasetMode(username, filename);
        String datasetKey = datasetMode ? datasetKey(username, filename) : null;

        Map<String, Object> status = new HashMap<>();
        status.put("building", building.get());
        status.put("totalPapers", totalPapers.get());
        status.put("processedPapers", processedPapers.get());
        status.put("insertedRows", insertedRows.get());
        status.put("startedAt", startedAt == null ? null : startedAt.toString());
        status.put("finishedAt", finishedAt == null ? null : finishedAt.toString());
        status.put("lastError", lastError);
        status.put("scope", datasetMode ? "dataset" : "global");
        status.put("username", datasetMode ? username : null);
        status.put("filename", datasetMode ? filename : null);

        long occ = 0;
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(datasetMode
                 ? "SELECT COUNT(*) FROM user_keyword_occurrence WHERE dataset_key = ?"
                 : "SELECT COUNT(*) FROM keyword_occurrence")) {

            if (datasetMode) {
                ps.setString(1, datasetKey);
            }

            try (ResultSet rs = ps.executeQuery()) {
            if (rs.next()) {
                occ = rs.getLong(1);
            }
            }
        } catch (SQLException e) {
            // ignore: table may not exist yet
        }
        status.put("occurrenceRows", occ);
        status.put("built", occ > 0);
        return status;
    }

    public Map<String, Object> buildIndexAsync(boolean forceRebuild, String username, String filename) {
        ensureIndexTablesExistQuietly();

        boolean datasetMode = isDatasetMode(username, filename);
        if (datasetMode) {
            if (!ValidationUtils.isSafeFilename(filename)) {
                return Map.of("accepted", false, "reason", "invalid filename");
            }
        }

        Map<String, Object> result = new HashMap<>();
        if (!building.compareAndSet(false, true)) {
            result.put("accepted", false);
            result.put("reason", "building");
            return result;
        }

        lastError = null;
        startedAt = Instant.now();
        finishedAt = null;
        totalPapers.set(0);
        processedPapers.set(0);
        insertedRows.set(0);

        executor.submit(() -> {
            try {
                if (datasetMode) {
                    buildUserDatasetIndexInternal(username, filename, forceRebuild);
                } else {
                    buildIndexInternal(forceRebuild);
                }
            } catch (Exception e) {
                lastError = e.getMessage();
            } finally {
                finishedAt = Instant.now();
                building.set(false);
            }
        });

        result.put("accepted", true);
        result.put("forceRebuild", forceRebuild);
        result.put("scope", datasetMode ? "dataset" : "global");
        if (datasetMode) {
            result.put("username", username);
            result.put("filename", filename);
        }
        return result;
    }

    public Map<String, Object> analyzeKeyword(String keyword, int page, int size, String username, String filename) {
        ensureIndexTablesExistQuietly();

        boolean datasetMode = isDatasetMode(username, filename);
        String datasetKey = datasetMode ? datasetKey(username, filename) : null;

        if (keyword == null || keyword.trim().isEmpty()) {
            return Map.of("error", "keyword required");
        }

        String normalized = normalizeSingleKeyword(keyword);
        if (normalized.isEmpty()) {
            return Map.of("error", "keyword required");
        }

        if (!isBuilt(datasetKey)) {
            return Map.of("error", "keyword index not built");
        }

        int safeSize = Math.max(1, Math.min(size, 100));
        int safePage = Math.max(1, page);
        int offset = (safePage - 1) * safeSize;

        Map<String, Object> out = new HashMap<>();
        out.put("keyword", normalized);
        out.put("page", safePage);
        out.put("size", safeSize);
        out.put("scope", datasetMode ? "dataset" : "global");
        if (datasetMode) {
            out.put("username", username);
            out.put("filename", filename);
        }

        try (Connection conn = dataSource.getConnection()) {
            if (datasetMode) {
                out.put("totalPapers", queryLong(conn,
                    "SELECT COUNT(DISTINCT paper_key) FROM user_keyword_occurrence WHERE dataset_key = ? AND keyword = ?",
                    datasetKey, normalized));
                out.put("totalJournals", queryLong(conn,
                    "SELECT COUNT(DISTINCT journal) FROM user_keyword_occurrence WHERE dataset_key = ? AND keyword = ? AND journal IS NOT NULL AND TRIM(journal) <> ''",
                    datasetKey, normalized));

                Map<String, Object> earliest = querySingleRow(conn,
                    "SELECT paper_key AS paperId, MAX(title) AS title, MAX(journal) AS journal, MAX(publish_date) AS publishDate, MAX(doi) AS doi " +
                        "FROM user_keyword_occurrence " +
                        "WHERE dataset_key = ? AND keyword = ? " +
                        "GROUP BY paper_key " +
                        "ORDER BY (MAX(publish_date) IS NULL) ASC, MAX(publish_date) ASC, paper_key ASC LIMIT 1",
                    datasetKey, normalized);
                out.put("earliest", earliest);

                Map<String, Object> topJournal = querySingleRow(conn,
                    "SELECT journal, COUNT(DISTINCT paper_key) AS cnt FROM user_keyword_occurrence " +
                        "WHERE dataset_key = ? AND keyword = ? AND journal IS NOT NULL AND TRIM(journal) <> '' " +
                        "GROUP BY journal ORDER BY cnt DESC, journal ASC LIMIT 1",
                    datasetKey, normalized);
                out.put("topJournal", topJournal);

                List<Map<String, Object>> journals = queryRows(conn,
                    "SELECT journal, COUNT(DISTINCT paper_key) AS cnt FROM user_keyword_occurrence " +
                        "WHERE dataset_key = ? AND keyword = ? AND journal IS NOT NULL AND TRIM(journal) <> '' " +
                        "GROUP BY journal ORDER BY cnt DESC, journal ASC LIMIT 20",
                    datasetKey, normalized);
                out.put("journals", journals);

                List<Map<String, Object>> papers = queryRows(conn,
                    "SELECT paper_key AS paperId, MAX(title) AS title, MAX(journal) AS journal, MAX(publish_date) AS publishDate, MAX(doi) AS doi " +
                        "FROM user_keyword_occurrence " +
                        "WHERE dataset_key = ? AND keyword = ? " +
                        "GROUP BY paper_key " +
                        "ORDER BY (MAX(publish_date) IS NULL) ASC, MAX(publish_date) DESC, paper_key DESC " +
                        "LIMIT ? OFFSET ?",
                    datasetKey, normalized, safeSize, offset);
                out.put("papers", papers);
            } else {
                out.put("totalPapers", queryLong(conn, "SELECT COUNT(*) FROM keyword_occurrence WHERE keyword = ?", normalized));
                out.put("totalJournals", queryLong(conn,
                    "SELECT COUNT(DISTINCT journal) FROM keyword_occurrence WHERE keyword = ? AND journal IS NOT NULL AND TRIM(journal) <> ''",
                    normalized));

                Map<String, Object> earliest = querySingleRow(conn,
                    "SELECT p.id AS paperId, p.title AS title, p.journal AS journal, p.publish_date AS publishDate, p.doi AS doi " +
                        "FROM keyword_occurrence ko JOIN papers p ON p.id = ko.paper_id " +
                        "WHERE ko.keyword = ? " +
                        "ORDER BY (p.publish_date IS NULL) ASC, p.publish_date ASC, p.id ASC LIMIT 1",
                    normalized);
                out.put("earliest", earliest);

                Map<String, Object> topJournal = querySingleRow(conn,
                    "SELECT journal, COUNT(*) AS cnt FROM keyword_occurrence " +
                        "WHERE keyword = ? AND journal IS NOT NULL AND TRIM(journal) <> '' " +
                        "GROUP BY journal ORDER BY cnt DESC, journal ASC LIMIT 1",
                    normalized);
                out.put("topJournal", topJournal);

                List<Map<String, Object>> journals = queryRows(conn,
                    "SELECT journal, COUNT(*) AS cnt FROM keyword_occurrence " +
                        "WHERE keyword = ? AND journal IS NOT NULL AND TRIM(journal) <> '' " +
                        "GROUP BY journal ORDER BY cnt DESC, journal ASC LIMIT 20",
                    normalized);
                out.put("journals", journals);

                List<Map<String, Object>> papers = queryRows(conn,
                    "SELECT p.id AS paperId, p.title AS title, p.journal AS journal, p.publish_date AS publishDate, p.doi AS doi " +
                        "FROM keyword_occurrence ko JOIN papers p ON p.id = ko.paper_id " +
                        "WHERE ko.keyword = ? " +
                        "ORDER BY (p.publish_date IS NULL) ASC, p.publish_date DESC, p.id DESC " +
                        "LIMIT ? OFFSET ?",
                    normalized, safeSize, offset);
                out.put("papers", papers);
            }

        } catch (SQLException e) {
            return Map.of("error", e.getMessage());
        }

        return out;
    }

    public List<Map<String, Object>> topKeywords(int limit, String username, String filename) {
        ensureIndexTablesExistQuietly();

        boolean datasetMode = isDatasetMode(username, filename);
        String datasetKey = datasetMode ? datasetKey(username, filename) : null;
        if (!isBuilt(datasetKey)) {
            return List.of();
        }

        int safeLimit = Math.max(1, Math.min(limit, 200));
        try (Connection conn = dataSource.getConnection()) {
            if (datasetMode) {
                return queryRows(conn,
                    "SELECT keyword, COUNT(DISTINCT paper_key) AS cnt FROM user_keyword_occurrence WHERE dataset_key = ? GROUP BY keyword ORDER BY cnt DESC, keyword ASC LIMIT ?",
                    datasetKey, safeLimit);
            }
            return queryRows(conn,
                "SELECT keyword, COUNT(*) AS cnt FROM keyword_occurrence GROUP BY keyword ORDER BY cnt DESC, keyword ASC LIMIT ?",
                safeLimit);
        } catch (SQLException e) {
            return List.of();
        }
    }

    private boolean isBuilt(String datasetKey) {
        try (Connection conn = dataSource.getConnection();
             PreparedStatement ps = conn.prepareStatement(datasetKey == null
                 ? "SELECT COUNT(*) FROM keyword_occurrence"
                 : "SELECT COUNT(*) FROM user_keyword_occurrence WHERE dataset_key = ?")) {

            if (datasetKey != null) {
                ps.setString(1, datasetKey);
            }
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() && rs.getLong(1) > 0;
            }
        } catch (SQLException e) {
            return false;
        }
    }

    private void buildUserDatasetIndexInternal(String username, String filename, boolean forceRebuild) throws Exception {
        ensureIndexTablesExist();

        String datasetKey = datasetKey(username, filename);
        Path file = resolveUserUploadFile(username, filename);

        try (Connection conn = dataSource.getConnection()) {
            conn.setAutoCommit(false);
            boolean isSQLite = isSQLite(conn.getMetaData().getDatabaseProductName());

            if (forceRebuild) {
                try (PreparedStatement clear = conn.prepareStatement("DELETE FROM user_keyword_occurrence WHERE dataset_key = ?")) {
                    clear.setString(1, datasetKey);
                    clear.executeUpdate();
                }
                conn.commit();
            }

            totalPapers.set(0);
            processedPapers.set(0);
            insertedRows.set(0);

            String insertSql = isSQLite
                ? "INSERT OR IGNORE INTO user_keyword_occurrence (dataset_key, keyword, paper_key, title, journal, publish_date, doi) VALUES (?,?,?,?,?,?,?)"
                : "INSERT IGNORE INTO user_keyword_occurrence (dataset_key, keyword, paper_key, title, journal, publish_date, doi) VALUES (?,?,?,?,?,?,?)";

            try (PreparedStatement insert = conn.prepareStatement(insertSql)) {
                String name = file.getFileName().toString().toLowerCase();
                if (name.endsWith(".csv")) {
                    buildUserDatasetIndexFromCsv(conn, insert, datasetKey, file);
                } else if (name.endsWith(".json")) {
                    buildUserDatasetIndexFromJson(conn, insert, datasetKey, file);
                } else {
                    throw new IllegalArgumentException("unsupported file: " + name);
                }
            } catch (Exception e) {
                conn.rollback();
                throw e;
            } finally {
                conn.setAutoCommit(true);
            }
        }
    }

    private void buildUserDatasetIndexFromCsv(Connection conn, PreparedStatement insert, String datasetKey, Path file) throws Exception {
        try (BufferedReader reader = Files.newBufferedReader(file, StandardCharsets.UTF_8);
             CSVParser parser = CSVFormat.DEFAULT
                 .builder()
                 .setHeader()
                 .setSkipHeaderRecord(true)
                 .setIgnoreHeaderCase(true)
                 .setTrim(true)
                 .build()
                 .parse(reader)) {

            Map<String, Integer> headerMap = parser.getHeaderMap();
            String colKeywords = pickHeader(headerMap, List.of("keywords", "author_keywords", "keyword", "keywords_alt1"));
            String colTitle = pickHeader(headerMap, List.of("title", "paper_title"));
            String colJournal = pickHeader(headerMap, List.of("journal", "source", "source_title"));
            String colPublishDate = pickHeader(headerMap, List.of("publish_date", "publication_date", "date", "year"));
            String colDoi = pickHeader(headerMap, List.of("doi"));

            if (colKeywords == null) {
                throw new IllegalArgumentException("CSV 缺少关键词列（keywords）");
            }

            int batch = 0;
            int rowNo = 0;
            for (CSVRecord r : parser) {
                rowNo++;
                String rawKeywords = getCsvValue(r, colKeywords);
                if (rawKeywords == null || rawKeywords.trim().isEmpty()) {
                    processedPapers.incrementAndGet();
                    continue;
                }

                String title = getCsvValue(r, colTitle);
                String journal = getCsvValue(r, colJournal);
                String publishDate = getCsvValue(r, colPublishDate);
                String doi = getCsvValue(r, colDoi);

                String paperKey = buildPaperKey(rowNo, title, doi);
                Set<String> keys = KeywordParser.parseNormalizedKeywords(rawKeywords);
                for (String k : keys) {
                    insert.setString(1, datasetKey);
                    insert.setString(2, k);
                    insert.setString(3, paperKey);
                    insert.setString(4, title);
                    insert.setString(5, journal);
                    insert.setString(6, publishDate);
                    insert.setString(7, doi);
                    insert.addBatch();
                    batch++;
                }

                processedPapers.incrementAndGet();

                if (batch >= 4000) {
                    int[] affected = insert.executeBatch();
                    conn.commit();
                    insertedRows.addAndGet(sumAffected(affected));
                    batch = 0;
                }
            }

            if (batch > 0) {
                int[] affected = insert.executeBatch();
                conn.commit();
                insertedRows.addAndGet(sumAffected(affected));
            }
        }
    }

    private void buildUserDatasetIndexFromJson(Connection conn, PreparedStatement insert, String datasetKey, Path file) throws Exception {
        // 兼容：JSON 可能是数组，或 {data:[...]} 形式。这里使用 jackson 读取整棵树（对超大 JSON 可能较慢）。
        // 若后续遇到大文件压力，可改为流式 JsonParser。
        var mapper = new com.fasterxml.jackson.databind.ObjectMapper();
        var root = mapper.readTree(file.toFile());

        com.fasterxml.jackson.databind.JsonNode arr = root;
        if (root != null && root.isObject() && root.has("data") && root.get("data").isArray()) {
            arr = root.get("data");
        }
        if (arr == null || !arr.isArray()) {
            throw new IllegalArgumentException("JSON 需要是数组或包含 data 数组");
        }

        int batch = 0;
        int rowNo = 0;
        for (var node : arr) {
            rowNo++;
            String rawKeywords = getJsonText(node, List.of("keywords", "author_keywords", "keyword", "keywords_alt1"));
            if (rawKeywords == null || rawKeywords.trim().isEmpty()) {
                processedPapers.incrementAndGet();
                continue;
            }

            String title = getJsonText(node, List.of("title", "paper_title"));
            String journal = getJsonText(node, List.of("journal", "source", "source_title"));
            String publishDate = getJsonText(node, List.of("publish_date", "publication_date", "date", "year"));
            String doi = getJsonText(node, List.of("doi"));

            String paperKey = buildPaperKey(rowNo, title, doi);
            Set<String> keys = KeywordParser.parseNormalizedKeywords(rawKeywords);
            for (String k : keys) {
                insert.setString(1, datasetKey);
                insert.setString(2, k);
                insert.setString(3, paperKey);
                insert.setString(4, title);
                insert.setString(5, journal);
                insert.setString(6, publishDate);
                insert.setString(7, doi);
                insert.addBatch();
                batch++;
            }

            processedPapers.incrementAndGet();

            if (batch >= 4000) {
                int[] affected = insert.executeBatch();
                conn.commit();
                insertedRows.addAndGet(sumAffected(affected));
                batch = 0;
            }
        }

        if (batch > 0) {
            int[] affected = insert.executeBatch();
            conn.commit();
            insertedRows.addAndGet(sumAffected(affected));
        }
    }

    private void buildIndexInternal(boolean forceRebuild) throws SQLException {
        ensureIndexTablesExist();

        try (Connection conn = dataSource.getConnection()) {
            conn.setAutoCommit(false);

            boolean isSQLite = isSQLite(conn.getMetaData().getDatabaseProductName());

            if (forceRebuild) {
                try (PreparedStatement clear = conn.prepareStatement("DELETE FROM keyword_occurrence")) {
                    clear.executeUpdate();
                }
            }

            int total;
            try (PreparedStatement ps = conn.prepareStatement("SELECT COUNT(*) FROM papers");
                 ResultSet rs = ps.executeQuery()) {
                total = rs.next() ? rs.getInt(1) : 0;
            }
            totalPapers.set(total);

            String selectSql = "SELECT id, journal, publish_date, keywords FROM papers";
            String insertSql = isSQLite
                ? "INSERT OR IGNORE INTO keyword_occurrence (keyword, paper_id, journal, publish_date) VALUES (?,?,?,?)"
                : "INSERT IGNORE INTO keyword_occurrence (keyword, paper_id, journal, publish_date) VALUES (?,?,?,?)";

            try (PreparedStatement select = conn.prepareStatement(selectSql);
                 PreparedStatement insert = conn.prepareStatement(insertSql);
                 ResultSet rs = select.executeQuery()) {

                int batch = 0;
                while (rs.next()) {
                    long paperId = rs.getLong("id");
                    String journal = rs.getString("journal");
                    String publishDate = rs.getString("publish_date");
                    String rawKeywords = rs.getString("keywords");

                    Set<String> keys = KeywordParser.parseNormalizedKeywords(rawKeywords);
                    for (String k : keys) {
                        insert.setString(1, k);
                        insert.setLong(2, paperId);
                        insert.setString(3, journal);
                        insert.setString(4, publishDate);
                        insert.addBatch();
                        batch++;
                    }

                    processedPapers.incrementAndGet();

                    if (batch >= 5000) {
                        int[] affected = insert.executeBatch();
                        conn.commit();
                        insertedRows.addAndGet(sumAffected(affected));
                        batch = 0;
                    }
                }

                if (batch > 0) {
                    int[] affected = insert.executeBatch();
                    conn.commit();
                    insertedRows.addAndGet(sumAffected(affected));
                }
            } catch (SQLException e) {
                conn.rollback();
                throw e;
            } finally {
                conn.setAutoCommit(true);
            }
        }
    }

    private static long sumAffected(int[] affected) {
        long sum = 0;
        if (affected == null) {
            return 0;
        }
        for (int a : affected) {
            if (a > 0) {
                sum += a;
            }
        }
        return sum;
    }

    private void ensureIndexTablesExistQuietly() {
        try {
            ensureIndexTablesExist();
        } catch (SQLException ignore) {
            // ignore
        }
    }

    private void ensureIndexTablesExist() throws SQLException {
        try (Connection conn = dataSource.getConnection()) {
            boolean isSQLite = isSQLite(conn.getMetaData().getDatabaseProductName());

            String createTableSql = isSQLite
                ? "CREATE TABLE IF NOT EXISTS keyword_occurrence (" +
                    "keyword TEXT NOT NULL, " +
                    "paper_id INTEGER NOT NULL, " +
                    "journal TEXT, " +
                    "publish_date DATE, " +
                    "PRIMARY KEY(keyword, paper_id)" +
                    ")"
                : "CREATE TABLE IF NOT EXISTS keyword_occurrence (" +
                    "keyword VARCHAR(255) NOT NULL, " +
                    "paper_id BIGINT NOT NULL, " +
                    "journal VARCHAR(512), " +
                    "publish_date DATE, " +
                    "PRIMARY KEY(keyword, paper_id)" +
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4";

            try (PreparedStatement ps1 = conn.prepareStatement(createTableSql)) {
                ps1.executeUpdate();
            }

            String createUserTableSql = isSQLite
                ? "CREATE TABLE IF NOT EXISTS user_keyword_occurrence (" +
                    "dataset_key TEXT NOT NULL, " +
                    "keyword TEXT NOT NULL, " +
                    "paper_key TEXT NOT NULL, " +
                    "title TEXT, " +
                    "journal TEXT, " +
                    "publish_date TEXT, " +
                    "doi TEXT, " +
                    "PRIMARY KEY(dataset_key, keyword, paper_key)" +
                    ")"
                : "CREATE TABLE IF NOT EXISTS user_keyword_occurrence (" +
                    "dataset_key VARCHAR(255) NOT NULL, " +
                    "keyword VARCHAR(255) NOT NULL, " +
                    "paper_key VARCHAR(512) NOT NULL, " +
                    "title TEXT, " +
                    "journal VARCHAR(512), " +
                    "publish_date VARCHAR(32), " +
                    "doi VARCHAR(255), " +
                    "PRIMARY KEY(dataset_key, keyword, paper_key)" +
                    ") ENGINE=InnoDB DEFAULT CHARSET=utf8mb4";

            try (PreparedStatement ps2 = conn.prepareStatement(createUserTableSql)) {
                ps2.executeUpdate();
            }

            createIndexIfMissing(conn, "keyword_occurrence", "idx_keyword_occurrence_keyword", "CREATE INDEX idx_keyword_occurrence_keyword ON keyword_occurrence(keyword)");
            createIndexIfMissing(conn, "keyword_occurrence", "idx_keyword_occurrence_journal", "CREATE INDEX idx_keyword_occurrence_journal ON keyword_occurrence(journal)");
            createIndexIfMissing(conn, "keyword_occurrence", "idx_keyword_occurrence_publish_date", "CREATE INDEX idx_keyword_occurrence_publish_date ON keyword_occurrence(publish_date)");

            createIndexIfMissing(conn, "user_keyword_occurrence", "idx_user_keyword_occurrence_dataset", "CREATE INDEX idx_user_keyword_occurrence_dataset ON user_keyword_occurrence(dataset_key)");
            createIndexIfMissing(conn, "user_keyword_occurrence", "idx_user_keyword_occurrence_keyword", "CREATE INDEX idx_user_keyword_occurrence_keyword ON user_keyword_occurrence(keyword)");
            createIndexIfMissing(conn, "user_keyword_occurrence", "idx_user_keyword_occurrence_dataset_keyword", "CREATE INDEX idx_user_keyword_occurrence_dataset_keyword ON user_keyword_occurrence(dataset_key, keyword)");
            createIndexIfMissing(conn, "user_keyword_occurrence", "idx_user_keyword_occurrence_journal", "CREATE INDEX idx_user_keyword_occurrence_journal ON user_keyword_occurrence(journal)");
            createIndexIfMissing(conn, "user_keyword_occurrence", "idx_user_keyword_occurrence_publish_date", "CREATE INDEX idx_user_keyword_occurrence_publish_date ON user_keyword_occurrence(publish_date)");
        }
    }

    private static boolean isSQLite(String productName) {
        if (productName == null) return false;
        return productName.toLowerCase().contains("sqlite");
    }

    private static boolean indexExists(Connection conn, String tableName, String indexName) {
        try {
            var md = conn.getMetaData();
            try (var rs = md.getIndexInfo(conn.getCatalog(), null, tableName, false, false)) {
                while (rs != null && rs.next()) {
                    String name = rs.getString("INDEX_NAME");
                    if (name != null && name.equalsIgnoreCase(indexName)) {
                        return true;
                    }
                }
            }
        } catch (SQLException ignored) {
        }
        return false;
    }

    private static void createIndexIfMissing(Connection conn, String tableName, String indexName, String createSql) throws SQLException {
        if (indexExists(conn, tableName, indexName)) {
            return;
        }
        try (PreparedStatement ps = conn.prepareStatement(createSql)) {
            ps.executeUpdate();
        } catch (SQLException e) {
            // 并发/重复创建时允许忽略
        }
    }

    private static String normalizeSingleKeyword(String input) {
        Set<String> keys = KeywordParser.parseNormalizedKeywords(input);
        if (keys.isEmpty()) {
            return "";
        }
        // If user pasted multiple, take the first.
        return keys.iterator().next();
    }

    private static boolean isDatasetMode(String username, String filename) {
        return ValidationUtils.isNotBlank(username) && ValidationUtils.isNotBlank(filename);
    }

    private static String datasetKey(String username, String filename) {
        return username + ":" + filename;
    }

    private static Path resolveUserUploadFile(String username, String filename) throws IOException {
        if (ValidationUtils.isBlank(username)) {
            throw new IllegalArgumentException("username required");
        }
        if (ValidationUtils.isBlank(filename) || !ValidationUtils.isSafeFilename(filename)) {
            throw new IllegalArgumentException("invalid filename");
        }
        Path p = Paths.get("uploads", username, filename).normalize();
        if (!Files.exists(p)) {
            throw new IOException("file not found: " + p);
        }
        return p;
    }

    private static String pickHeader(Map<String, Integer> headerMap, List<String> candidates) {
        if (headerMap == null || headerMap.isEmpty()) return null;
        for (String c : candidates) {
            for (String key : headerMap.keySet()) {
                if (key != null && key.trim().equalsIgnoreCase(c)) {
                    return key;
                }
            }
        }
        // fallback: contains
        for (String c : candidates) {
            for (String key : headerMap.keySet()) {
                if (key != null && key.toLowerCase().contains(c.toLowerCase())) {
                    return key;
                }
            }
        }
        return null;
    }

    private static String getCsvValue(CSVRecord r, String col) {
        if (col == null) return null;
        try {
            String v = r.get(col);
            return v == null ? null : v.trim();
        } catch (Exception e) {
            return null;
        }
    }

    private static String getJsonText(com.fasterxml.jackson.databind.JsonNode node, List<String> keys) {
        if (node == null || !node.isObject()) {
            return null;
        }
        for (String k : keys) {
            var v = node.get(k);
            if (v != null && !v.isNull()) {
                if (v.isTextual()) return v.asText().trim();
                if (v.isNumber()) return v.asText();
                if (v.isArray()) {
                    // keywords 可能是数组，拼接
                    List<String> parts = new ArrayList<>();
                    for (var it : v) {
                        if (it != null && it.isTextual()) parts.add(it.asText());
                    }
                    return String.join("; ", parts).trim();
                }
            }
        }
        return null;
    }

    private static String buildPaperKey(int rowNo, String title, String doi) {
        String d = doi == null ? "" : doi.trim();
        if (!d.isEmpty()) {
            return "doi:" + d.toLowerCase();
        }
        String t = title == null ? "" : title.trim();
        if (!t.isEmpty()) {
            return "title:" + t.toLowerCase();
        }
        return "row:" + rowNo;
    }

    private static long queryLong(Connection conn, String sql, Object... params) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            for (int i = 0; i < params.length; i++) {
                ps.setObject(i + 1, params[i]);
            }
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next() ? rs.getLong(1) : 0;
            }
        }
    }

    private static Map<String, Object> querySingleRow(Connection conn, String sql, Object... params) throws SQLException {
        List<Map<String, Object>> rows = queryRows(conn, sql, params);
        if (rows.isEmpty()) {
            return null;
        }
        return rows.get(0);
    }

    private static List<Map<String, Object>> queryRows(Connection conn, String sql, Object... params) throws SQLException {
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            for (int i = 0; i < params.length; i++) {
                ps.setObject(i + 1, params[i]);
            }
            try (ResultSet rs = ps.executeQuery()) {
                List<Map<String, Object>> out = new ArrayList<>();
                int colCount = rs.getMetaData().getColumnCount();
                while (rs.next()) {
                    Map<String, Object> row = new HashMap<>();
                    for (int i = 1; i <= colCount; i++) {
                        String name = rs.getMetaData().getColumnLabel(i);
                        row.put(name, rs.getObject(i));
                    }
                    out.add(row);
                }
                return out;
            }
        }
    }
}
