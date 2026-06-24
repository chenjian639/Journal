package com.paper.service;

import java.io.BufferedReader;
import java.io.InputStream;
import java.io.InputStreamReader;
import java.nio.charset.StandardCharsets;
import java.security.SecureRandom;
import java.sql.Connection;
import java.sql.DatabaseMetaData;
import java.sql.PreparedStatement;
import java.sql.ResultSet;
import java.sql.SQLException;
import java.sql.Types;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashSet;
import java.util.HashMap;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Map;
import java.util.Set;
import java.util.regex.Pattern;

import org.mindrot.jbcrypt.BCrypt;
import org.springframework.web.multipart.MultipartFile;
import org.springframework.stereotype.Service;

import com.paper.dao.MySQLHelper;
import com.fasterxml.jackson.core.type.TypeReference;
import com.fasterxml.jackson.databind.ObjectMapper;
import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVRecord;

import javax.sql.DataSource;

@Service
public class AdminService {

    private final MySQLHelper mysqlHelper;
    private final DataSource dataSource;
    private final ObjectMapper objectMapper;
    private final SecureRandom random = new SecureRandom();

    public AdminService(MySQLHelper mysqlHelper, DataSource dataSource, ObjectMapper objectMapper) {
        this.mysqlHelper = mysqlHelper;
        this.dataSource = dataSource;
        this.objectMapper = objectMapper;
    }

    public boolean isAdmin(String uname) throws SQLException {
        String sql = "SELECT is_admin FROM users WHERE uname = ?";
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql, uname);
        if (rows == null || rows.isEmpty()) {
            return false;
        }
        Object v = rows.get(0).get("is_admin");
        if (v == null) {
            return false;
        }
        if (v instanceof Number n) {
            return n.intValue() == 1;
        }
        try {
            return Integer.parseInt(String.valueOf(v)) == 1;
        } catch (NumberFormatException e) {
            return false;
        }
    }

    public Map<String, Object> getSystemStats() {
        Map<String, Object> out = new HashMap<>();
        out.put("userCount", count("SELECT COUNT(*) c FROM users"));
        out.put("paperCount", count("SELECT COUNT(*) c FROM papers"));
        out.put("analysisCount", count("SELECT COUNT(*) c FROM analysis_record"));
        out.put("userJournalMetricsRows", count("SELECT COUNT(*) c FROM user_journal_metrics"));
        out.put("userKeywordOccurrenceRows", count("SELECT COUNT(*) c FROM user_keyword_occurrence"));
        out.put("journalMetricsRows", count("SELECT COUNT(*) c FROM journal_metrics"));
        return out;
    }

    public List<Map<String, Object>> listUsers() {
        String sql = "SELECT uname, email, is_admin, created_at FROM users ORDER BY created_at DESC";
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql);
        List<Map<String, Object>> out = new ArrayList<>();
        for (Map<String, Object> r : rows) {
            Map<String, Object> m = new HashMap<>();
            String uname = r.get("uname") == null ? "" : String.valueOf(r.get("uname"));
            m.put("uname", uname);
            m.put("email", r.get("email") == null ? "" : String.valueOf(r.get("email")));

            Object ia = r.get("is_admin");
            boolean isAdmin = false;
            if (ia instanceof Number n) isAdmin = n.intValue() == 1;
            else if (ia != null) {
                try { isAdmin = Integer.parseInt(String.valueOf(ia)) == 1; } catch (NumberFormatException ignored) {}
            }
            m.put("isAdmin", isAdmin);
            m.put("createdAt", r.get("created_at") == null ? "" : String.valueOf(r.get("created_at")));
            out.add(m);
        }
        return out;
    }

    public void deleteUserCascade(String targetUname) {
        if (!userExists(targetUname)) {
            throw new IllegalStateException("用户不存在: " + targetUname);
        }

        // 保护：不允许删除最后一个管理员
        if (isAdminNoThrow(targetUname) && countAdmins() <= 1) {
            throw new IllegalStateException("不能删除最后一个管理员账号");
        }

        // 先删依赖表（顺序避免外键/约束问题；当前库可能没有 FK，但保持一致）
        mysqlHelper.executeSQL("DELETE FROM analysis_record WHERE username = ?", targetUname);
        mysqlHelper.executeSQL("DELETE FROM user_journal_metrics WHERE username = ?", targetUname);
        // user_keyword_occurrence 通过 dataset_key=\"{username}:{filename}\" 归属用户
        mysqlHelper.executeSQL("DELETE FROM user_keyword_occurrence WHERE dataset_key LIKE ?", targetUname + ":%");

        String err = mysqlHelper.executeSQL("DELETE FROM users WHERE uname = ?", targetUname);
        if (err != null && !err.isEmpty()) {
            throw new IllegalStateException("删除用户失败: " + err);
        }
    }

    public String resetUserPassword(String targetUname, String newPasswordOrBlank) {
        if (!userExists(targetUname)) {
            throw new IllegalStateException("用户不存在: " + targetUname);
        }

        String pwd = (newPasswordOrBlank == null) ? "" : newPasswordOrBlank.trim();
        if (pwd.isBlank()) {
            pwd = generatePassword(12);
        }

        String hashed = BCrypt.hashpw(pwd, BCrypt.gensalt());
        String err = mysqlHelper.executeSQL("UPDATE users SET password = ? WHERE uname = ?", hashed, targetUname);
        if (err != null && !err.isEmpty()) {
            throw new IllegalStateException("重置密码失败: " + err);
        }
        return pwd;
    }

    private boolean userExists(String uname) {
        if (uname == null || uname.isBlank()) return false;
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(
            "SELECT 1 FROM users WHERE uname = ? LIMIT 1",
            uname
        );
        return rows != null && !rows.isEmpty();
    }

    private long count(String sql) {
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql);
        if (rows == null || rows.isEmpty()) return 0;
        Object v = rows.get(0).values().stream().findFirst().orElse(0);
        if (v instanceof Number n) return n.longValue();
        try { return Long.parseLong(String.valueOf(v)); } catch (NumberFormatException e) { return 0; }
    }

    private int countAdmins() {
        long c = count("SELECT COUNT(*) c FROM users WHERE is_admin = 1");
        if (c > Integer.MAX_VALUE) return Integer.MAX_VALUE;
        return (int) c;
    }

    private boolean isAdminNoThrow(String uname) {
        try {
            return isAdmin(uname);
        } catch (SQLException e) {
            return false;
        }
    }

    private String generatePassword(int len) {
        final String chars = "ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz23456789";
        StringBuilder sb = new StringBuilder();
        for (int i = 0; i < len; i++) {
            sb.append(chars.charAt(random.nextInt(chars.length())));
        }
        return sb.toString();
    }

    // =========================
    // Papers: import + search
    // =========================

    private static final int PREVIEW_ROWS = 8;
    private static final Pattern DOI_PREFIX = Pattern.compile("^(https?://(dx\\.)?doi\\.org/|doi:)\\s*", Pattern.CASE_INSENSITIVE);

    public Map<String, Object> previewPapers(MultipartFile file, String format) throws Exception {
        if (file == null || file.isEmpty()) {
            return Map.of(
                "columns", List.of(),
                "sample", List.of(),
                "rowCount", 0
            );
        }

        String fmt = (format == null) ? "csv" : format.trim().toLowerCase();
        if (fmt.isBlank()) fmt = "csv";

        if ("json".equals(fmt)) {
            List<Map<String, Object>> rows = parseJsonRows(file.getInputStream());
            List<Map<String, Object>> sample = rows.subList(0, Math.min(PREVIEW_ROWS, rows.size()));
            List<String> cols = collectColumnsFromRows(sample);
            Map<String, Object> out = new HashMap<>();
            out.put("columns", cols);
            out.put("sample", sample);
            out.put("rowCount", rows.size());
            return out;
        }

        CsvParseResult csv = parseCsvRows(file.getInputStream());
        List<Map<String, Object>> sample = csv.rows.subList(0, Math.min(PREVIEW_ROWS, csv.rows.size()));
        Map<String, Object> out = new HashMap<>();
        out.put("columns", csv.headers);
        out.put("sample", sample);
        out.put("rowCount", csv.rows.size());
        return out;
    }

    public Map<String, Object> importPapers(
        MultipartFile file,
        String format,
        Map<String, String> mapping,
        Integer minYear,
        Integer maxYear,
        boolean requireTitle
    ) throws Exception {
        if (file == null || file.isEmpty()) {
            return Map.of(
                "inserted", 0,
                "skipped", 0,
                "duplicates", 0,
                "total", 0
            );
        }

        PaperTableSchema schema = detectPaperSchema();
        if (!schema.hasColumn("title")) {
            throw new IllegalStateException("papers 表缺少 title 字段，无法导入");
        }

        String fmt = (format == null) ? "csv" : format.trim().toLowerCase();
        if (fmt.isBlank()) fmt = "csv";

        List<Map<String, Object>> rows;
        if ("json".equals(fmt)) {
            rows = parseJsonRows(file.getInputStream());
        } else {
            rows = parseCsvRows(file.getInputStream()).rows;
        }

        int total = rows.size();
        if (total == 0) {
            return Map.of(
                "inserted", 0,
                "skipped", 0,
                "duplicates", 0,
                "total", 0
            );
        }

        String colTitle = pick(mapping, "title");
        String colDoi = pick(mapping, "doi");
        String colJournal = pick(mapping, "journal");
        String colKeywords = pick(mapping, "keywords");
        String colPublish = pick(mapping, "publish_date");
        String colAbstract = pick(mapping, "abstract");
        String colTarget = pick(mapping, "target");

        // 允许只映射 title（最小可导入）
        if (colTitle == null || colTitle.isBlank()) {
            // 常见兜底
            colTitle = findFirstExistingColumn(rows, List.of("title", "Title", "TI", "paper_title"));
        }

        int inserted = 0;
        int skipped = 0;
        int duplicates = 0;

        String insertSql = buildInsertSql(schema);
        try (Connection conn = dataSource.getConnection()) {
            conn.setAutoCommit(false);

            try (PreparedStatement insert = conn.prepareStatement(insertSql)) {
                int batch = 0;
                for (Map<String, Object> r : rows) {
                    String title = normText(getMapped(r, colTitle));
                    if (requireTitle && (title == null || title.isBlank())) {
                        skipped++;
                        continue;
                    }

                    String doi = normDoi(getMapped(r, colDoi));
                    String doiKey = (doi == null) ? "" : doi;

                    Integer year = parseYear(getMapped(r, colPublish));
                    if (year != null) {
                        if (minYear != null && year < minYear) {
                            skipped++;
                            continue;
                        }
                        if (maxYear != null && year > maxYear) {
                            skipped++;
                            continue;
                        }
                    }

                    boolean exists;
                    if (doiKey != null && !doiKey.isBlank() && schema.hasColumn("doi")) {
                        exists = existsByDoi(conn, schema, doiKey);
                    } else {
                        // DOI 为空：按标题去重
                        if (title == null || title.isBlank()) {
                            skipped++;
                            continue;
                        }
                        exists = existsByTitle(conn, schema, title);
                    }

                    if (exists) {
                        duplicates++;
                        continue;
                    }

                    Map<String, Object> values = new LinkedHashMap<>();
                    values.put("title", title);
                    if (schema.hasColumn("doi")) values.put("doi", doiKey.isBlank() ? null : doiKey);
                    if (schema.hasColumn("journal")) values.put("journal", normText(getMapped(r, colJournal)));
                    if (schema.hasColumn("keywords")) values.put("keywords", normText(getMapped(r, colKeywords)));
                    if (schema.hasColumn(schema.abstractColumn)) values.put(schema.abstractColumn, normText(getMapped(r, colAbstract)));
                    if (schema.hasColumn("target")) values.put("target", normText(getMapped(r, colTarget)));

                    if (schema.hasColumn("publish_date")) {
                        Object publishValue = null;
                        if (year != null && year > 0) {
                            publishValue = schema.publishDateIsInteger ? year : String.format("%04d-01-01", year);
                        } else {
                            // 若不是年份，尝试原始字符串
                            String raw = normText(getMapped(r, colPublish));
                            if (raw != null && !raw.isBlank()) {
                                publishValue = raw;
                            }
                        }
                        values.put("publish_date", publishValue);
                    }

                    bindInsert(insert, schema, values);
                    insert.addBatch();
                    batch++;

                    if (batch >= 800) {
                        int[] affected = insert.executeBatch();
                        conn.commit();
                        inserted += sumAffected(affected);
                        batch = 0;
                    }
                }

                if (batch > 0) {
                    int[] affected = insert.executeBatch();
                    conn.commit();
                    inserted += sumAffected(affected);
                }
            } catch (Exception e) {
                conn.rollback();
                throw e;
            } finally {
                conn.setAutoCommit(true);
            }
        }

        Map<String, Object> out = new HashMap<>();
        out.put("inserted", inserted);
        out.put("skipped", skipped);
        out.put("duplicates", duplicates);
        out.put("total", total);
        out.put("schema", schema.toPublicMap());
        return out;
    }

    public Map<String, Object> searchPapers(String q, int limit, int offset) {
        int lim = Math.max(1, Math.min(limit, 200));
        int off = Math.max(0, offset);

        PaperTableSchema schema;
        try {
            schema = detectPaperSchema();
        } catch (SQLException e) {
            schema = new PaperTableSchema();
        }

        String query = (q == null) ? "" : q.trim();

        String cols = selectColumnsForSearch(schema);
        String base = " FROM papers";
        List<Object> params = new ArrayList<>();

        String where = "";
        if (!query.isBlank()) {
            String like = "%" + query + "%";
            List<String> parts = new ArrayList<>();
            if (schema.hasColumn("title")) {
                parts.add("title LIKE ?");
                params.add(like);
            }
            if (schema.hasColumn("doi")) {
                parts.add("doi LIKE ?");
                params.add(like);
            }
            if (schema.hasColumn("journal")) {
                parts.add("journal LIKE ?");
                params.add(like);
            }
            if (schema.hasColumn("keywords")) {
                parts.add("keywords LIKE ?");
                params.add(like);
            }
            if (schema.hasColumn("target")) {
                parts.add("target LIKE ?");
                params.add(like);
            }
            if (!parts.isEmpty()) {
                where = " WHERE (" + String.join(" OR ", parts) + ")";
            }
        }

        long total = 0;
        try {
            String countSql = "SELECT COUNT(*) c" + base + where;
            List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(countSql, params.toArray());
            if (rows != null && !rows.isEmpty()) {
                Object v = rows.get(0).values().stream().findFirst().orElse(0);
                if (v instanceof Number n) total = n.longValue();
                else {
                    try { total = Long.parseLong(String.valueOf(v)); } catch (NumberFormatException ignored) {}
                }
            }
        } catch (Exception ignored) {
        }

        String sql = "SELECT " + cols + base + where + " ORDER BY id DESC LIMIT " + lim + " OFFSET " + off;
        List<Map<String, Object>> items = mysqlHelper.executeSQLWithSelect(sql, params.toArray());

        Map<String, Object> out = new HashMap<>();
        out.put("total", total);
        out.put("limit", lim);
        out.put("offset", off);
        out.put("items", items == null ? List.of() : items);
        return out;
    }

    public Map<String, Object> getPaperDetail(long id) {
        PaperTableSchema schema;
        try {
            schema = detectPaperSchema();
        } catch (SQLException e) {
            schema = new PaperTableSchema();
        }

        String cols = selectColumnsForDetail(schema);
        String sql = "SELECT " + cols + " FROM papers WHERE id = ?";
        List<Map<String, Object>> rows = mysqlHelper.executeSQLWithSelect(sql, id);
        if (rows == null || rows.isEmpty()) {
            return Map.of();
        }
        return rows.get(0);
    }

    private static int sumAffected(int[] affected) {
        if (affected == null) return 0;
        int sum = 0;
        for (int a : affected) {
            if (a > 0) sum += a;
        }
        return sum;
    }

    private static String pick(Map<String, String> mapping, String key) {
        if (mapping == null) return null;
        String v = mapping.get(key);
        return v == null ? null : v.trim();
    }

    private static String getMapped(Map<String, Object> row, String col) {
        if (row == null || col == null || col.isBlank()) return null;
        Object v = row.get(col);
        if (v == null) {
            // 容错：尝试大小写不同
            v = row.get(col.toLowerCase());
            if (v == null) v = row.get(col.toUpperCase());
        }
        return v == null ? null : String.valueOf(v);
    }

    private static String normText(String s) {
        if (s == null) return null;
        String t = s.trim();
        return t.isBlank() ? null : t;
    }

    private static String normDoi(String s) {
        String t = normText(s);
        if (t == null) return null;
        t = DOI_PREFIX.matcher(t).replaceAll("");
        t = t.trim();
        return t.isBlank() ? null : t.toLowerCase();
    }

    private static String normTitleKey(String title) {
        String t = normText(title);
        if (t == null) return null;
        return t.toLowerCase().replaceAll("\\s+", " ").trim();
    }

    private static Integer parseYear(String s) {
        if (s == null) return null;
        String t = s.trim();
        if (t.isBlank()) return null;
        // 允许 YYYY 或 YYYY-MM-DD
        if (t.length() >= 4) {
            String y = t.substring(0, 4);
            try {
                int year = Integer.parseInt(y);
                if (year > 0) return year;
            } catch (NumberFormatException ignored) {
            }
        }
        return null;
    }

    private static String findFirstExistingColumn(List<Map<String, Object>> rows, List<String> candidates) {
        if (rows == null || rows.isEmpty() || candidates == null) return null;
        Map<String, Object> first = rows.get(0);
        if (first == null) return null;
        for (String c : candidates) {
            if (first.containsKey(c)) return c;
        }
        return null;
    }

    private static List<String> collectColumnsFromRows(List<Map<String, Object>> rows) {
        if (rows == null || rows.isEmpty()) return List.of();
        Set<String> cols = new HashSet<>();
        for (Map<String, Object> r : rows) {
            if (r != null) cols.addAll(r.keySet());
        }
        List<String> out = new ArrayList<>(cols);
        Collections.sort(out);
        return out;
    }

    private CsvParseResult parseCsvRows(InputStream in) throws Exception {
        try (BufferedReader reader = new BufferedReader(new InputStreamReader(in, StandardCharsets.UTF_8))) {
            CSVFormat fmt = CSVFormat.DEFAULT
                .builder()
                .setHeader()
                .setSkipHeaderRecord(true)
                .setIgnoreEmptyLines(true)
                .setTrim(true)
                .build();

            try (CSVParser parser = new CSVParser(reader, fmt)) {
                List<String> headers = new ArrayList<>(parser.getHeaderMap().keySet());
                List<Map<String, Object>> rows = new ArrayList<>();
                for (CSVRecord rec : parser) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (String h : headers) {
                        row.put(h, rec.isMapped(h) ? rec.get(h) : "");
                    }
                    rows.add(row);
                }
                return new CsvParseResult(headers, rows);
            }
        }
    }

    private List<Map<String, Object>> parseJsonRows(InputStream in) throws Exception {
        Object v = objectMapper.readValue(in, Object.class);
        if (v instanceof List<?> list) {
            List<Map<String, Object>> out = new ArrayList<>();
            for (Object o : list) {
                if (o instanceof Map<?, ?> m) {
                    Map<String, Object> row = new LinkedHashMap<>();
                    for (Map.Entry<?, ?> e : m.entrySet()) {
                        String k = (e.getKey() == null) ? "" : String.valueOf(e.getKey());
                        row.put(k, e.getValue());
                    }
                    out.add(row);
                }
            }
            return out;
        }
        if (v instanceof Map<?, ?> map) {
            // 允许 {"data":[...]} 或单对象
            Object data = map.get("data");
            if (data instanceof List<?>) {
                return objectMapper.convertValue(data, new TypeReference<List<Map<String, Object>>>() {});
            }
            Map<String, Object> row = new LinkedHashMap<>();
            for (Map.Entry<?, ?> e : map.entrySet()) {
                String k = (e.getKey() == null) ? "" : String.valueOf(e.getKey());
                row.put(k, e.getValue());
            }
            return List.of(row);
        }
        return List.of();
    }

    private PaperTableSchema detectPaperSchema() throws SQLException {
        PaperTableSchema schema = new PaperTableSchema();
        try (Connection conn = dataSource.getConnection()) {
            DatabaseMetaData meta = conn.getMetaData();
            String catalog = conn.getCatalog();
            try (ResultSet rs = meta.getColumns(catalog, null, "papers", null)) {
                while (rs.next()) {
                    String name = rs.getString("COLUMN_NAME");
                    String typeName = rs.getString("TYPE_NAME");
                    int dataType = rs.getInt("DATA_TYPE");
                    if (name == null) continue;
                    schema.columns.add(name.toLowerCase());
                    if ("publish_date".equalsIgnoreCase(name)) {
                        schema.publishDateIsInteger = (dataType == Types.INTEGER || dataType == Types.BIGINT || dataType == Types.SMALLINT)
                            || (typeName != null && typeName.toUpperCase().contains("INT"));
                    }
                }
            }
        }

        if (schema.hasColumn("abstract")) schema.abstractColumn = "abstract";
        else if (schema.hasColumn("abstract_text")) schema.abstractColumn = "abstract_text";
        else schema.abstractColumn = "abstract";

        // publish_date：如果列存在但未判断出来，默认为 integer（与旧 SQLite 初始化一致）
        if (schema.hasColumn("publish_date") && schema.publishDateIsInteger == null) {
            schema.publishDateIsInteger = true;
        }
        if (schema.publishDateIsInteger == null) schema.publishDateIsInteger = true;

        return schema;
    }

    private boolean existsByDoi(Connection conn, PaperTableSchema schema, String doiNorm) throws SQLException {
        if (!schema.hasColumn("doi")) return false;
        String sql;
        if (schema.hasColumn("doi")) {
            // 尽量大小写不敏感
            sql = "SELECT 1 FROM papers WHERE lower(doi) = ? LIMIT 1";
        } else {
            return false;
        }
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, doiNorm.toLowerCase());
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next();
            }
        }
    }

    private boolean existsByTitle(Connection conn, PaperTableSchema schema, String title) throws SQLException {
        if (!schema.hasColumn("title")) return false;
        String key = normTitleKey(title);
        if (key == null) return false;
        String sql = "SELECT 1 FROM papers WHERE lower(title) = ? LIMIT 1";
        try (PreparedStatement ps = conn.prepareStatement(sql)) {
            ps.setString(1, key);
            try (ResultSet rs = ps.executeQuery()) {
                return rs.next();
            }
        }
    }

    private String buildInsertSql(PaperTableSchema schema) {
        List<String> cols = new ArrayList<>();
        cols.add("title");

        if (schema.hasColumn("doi")) cols.add("doi");
        if (schema.hasColumn("journal")) cols.add("journal");
        if (schema.hasColumn("keywords")) cols.add("keywords");
        if (schema.hasColumn(schema.abstractColumn)) cols.add(schema.abstractColumn);
        if (schema.hasColumn("publish_date")) cols.add("publish_date");
        if (schema.hasColumn("target")) cols.add("target");

        String placeholders = String.join(",", Collections.nCopies(cols.size(), "?"));
        schema.insertColumns = cols;
        return "INSERT INTO papers (" + String.join(",", cols) + ") VALUES (" + placeholders + ")";
    }

    private void bindInsert(PreparedStatement ps, PaperTableSchema schema, Map<String, Object> values) throws SQLException {
        List<String> cols = schema.insertColumns;
        for (int i = 0; i < cols.size(); i++) {
            String c = cols.get(i);
            Object v = values.get(c);
            ps.setObject(i + 1, v);
        }
    }

    private static String selectColumnsForSearch(PaperTableSchema schema) {
        List<String> cols = new ArrayList<>();
        cols.add("id");
        if (schema.hasColumn("doi")) cols.add("doi");
        cols.add("title");
        if (schema.hasColumn("journal")) cols.add("journal");
        if (schema.hasColumn("publish_date")) cols.add("publish_date");
        if (schema.hasColumn("keywords")) cols.add("keywords");
        if (schema.hasColumn("target")) cols.add("target");
        return String.join(", ", cols);
    }

    private static String selectColumnsForDetail(PaperTableSchema schema) {
        List<String> cols = new ArrayList<>();
        cols.add("id");
        if (schema.hasColumn("doi")) cols.add("doi");
        if (schema.hasColumn("wos_id")) cols.add("wos_id");
        cols.add("title");
        if (schema.hasColumn(schema.abstractColumn)) cols.add(schema.abstractColumn);
        if (schema.hasColumn("journal")) cols.add("journal");
        if (schema.hasColumn("publish_date")) cols.add("publish_date");
        if (schema.hasColumn("keywords")) cols.add("keywords");
        if (schema.hasColumn("target")) cols.add("target");
        if (schema.hasColumn("author")) cols.add("author");
        if (schema.hasColumn("country")) cols.add("country");
        if (schema.hasColumn("conference")) cols.add("conference");
        if (schema.hasColumn("citations")) cols.add("citations");
        if (schema.hasColumn("refs")) cols.add("refs");
        return String.join(", ", cols);
    }

    private static final class CsvParseResult {
        final List<String> headers;
        final List<Map<String, Object>> rows;
        CsvParseResult(List<String> headers, List<Map<String, Object>> rows) {
            this.headers = headers;
            this.rows = rows;
        }
    }

    private static final class PaperTableSchema {
        final Set<String> columns = new HashSet<>();
        String abstractColumn = "abstract";
        Boolean publishDateIsInteger = null;
        List<String> insertColumns = List.of();

        boolean hasColumn(String name) {
            if (name == null) return false;
            return columns.contains(name.toLowerCase());
        }

        Map<String, Object> toPublicMap() {
            Map<String, Object> m = new HashMap<>();
            m.put("hasDoi", hasColumn("doi"));
            m.put("hasTitle", hasColumn("title"));
            m.put("hasJournal", hasColumn("journal"));
            m.put("hasKeywords", hasColumn("keywords"));
            m.put("abstractColumn", abstractColumn);
            m.put("publishDateIsInteger", publishDateIsInteger);
            return m;
        }
    }
}
