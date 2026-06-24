package com.paper.service;

import java.io.BufferedWriter;
import java.io.IOException;
import java.io.InputStream;
import java.io.OutputStream;
import java.io.OutputStreamWriter;
import java.nio.ByteBuffer;
import java.nio.channels.FileChannel;
import java.nio.charset.Charset;
import java.nio.charset.MalformedInputException;
import java.nio.charset.StandardCharsets;
import java.nio.file.Files;
import java.nio.file.Path;
import java.nio.file.StandardCopyOption;
import java.nio.file.StandardOpenOption;
import java.time.LocalDateTime;
import java.time.format.DateTimeFormatter;
import java.util.ArrayList;
import java.util.Collections;
import java.util.HashMap;
import java.util.HashSet;
import java.util.LinkedHashMap;
import java.util.List;
import java.util.Locale;
import java.util.Map;
import java.util.Set;

import org.apache.commons.csv.CSVFormat;
import org.apache.commons.csv.CSVParser;
import org.apache.commons.csv.CSVPrinter;
import org.apache.commons.csv.CSVRecord;
import org.springframework.core.io.Resource;
import org.springframework.core.io.ResourceLoader;
import org.springframework.stereotype.Service;
import org.yaml.snakeyaml.Yaml;

@Service
public class UserUploadCsvNormalizer {

    private static final List<Charset> CHARSET_CANDIDATES = List.of(
            StandardCharsets.UTF_8,
            Charset.forName("GB18030"),
            Charset.forName("GBK"),
            Charset.forName("CP936")
    );

        private static final int ENCODING_PROBE_CHUNK_BYTES = 64 * 1024;
        private static final int ENCODING_PROBE_MAX_CHUNKS = 4;

    private static final List<Character> DELIMITER_CANDIDATES = List.of(',', '\t', ';', '|');

    private final Map<String, String> candidateToStandardField;

    public UserUploadCsvNormalizer(ResourceLoader resourceLoader) {
        this.candidateToStandardField = Collections.unmodifiableMap(loadCandidateMap(resourceLoader));
    }

    public record NormalizationReport(
            boolean changed,
            String encoding,
            char detectedDelimiter,
            Map<String, String> renamedHeaders,
            List<String> warnings
    ) {
    }

    public NormalizationReport normalizeInPlace(Path csvPath) throws IOException {
        if (csvPath == null || !Files.exists(csvPath) || !Files.isRegularFile(csvPath)) {
            return new NormalizationReport(false, null, ',', Map.of(), List.of("CSV 文件不存在"));
        }
        String filename = csvPath.getFileName().toString().toLowerCase(Locale.ROOT);
        if (!filename.endsWith(".csv")) {
            return new NormalizationReport(false, null, ',', Map.of(), List.of());
        }

        ParseAttempt attempt = parse(csvPath);
        List<String> oldHeaders = attempt.headers;
        if (oldHeaders.isEmpty()) {
            return new NormalizationReport(false, attempt.charsetName, attempt.delimiter, Map.of(),
                    List.of("无法识别 CSV 表头（可能为空文件或分隔符/编码不正确）"));
        }

        HeaderNormalization normalized = normalizeHeaders(oldHeaders);

        List<String> warnings = new ArrayList<>();
        if (!normalized.newHeaders.contains("journal")) {
            warnings.add("未识别到期刊列（journal）。请确认 CSV 是否包含期刊名字段，或列名是否能映射到 Source Title/Journal/Publication Title 等。");
        }

        boolean needRewrite = attempt.delimiter != ',' || !normalized.renamedHeaders.isEmpty();
        if (!needRewrite) {
            return new NormalizationReport(false, attempt.charsetName, attempt.delimiter, normalized.renamedHeaders, warnings);
        }

        Path userDir = csvPath.getParent();
        Path rawDir = userDir.resolve("raw");
        Files.createDirectories(rawDir);

        String ts = LocalDateTime.now().format(DateTimeFormatter.ofPattern("yyyyMMdd_HHmmss"));
        Path rawPath = rawDir.resolve(csvPath.getFileName().toString().replaceAll("\\.csv$", "") + "." + ts + ".raw.csv");

        Files.move(csvPath, rawPath, StandardCopyOption.REPLACE_EXISTING);

        writeNormalizedCsv(rawPath, csvPath, attempt.charset, attempt.delimiter, normalized.newHeaders);

        return new NormalizationReport(true, attempt.charsetName, attempt.delimiter, normalized.renamedHeaders, warnings);
    }

    private void writeNormalizedCsv(
            Path rawCsv,
            Path targetCsv,
            Charset inputCharset,
            char inputDelimiter,
            List<String> newHeaders
    ) throws IOException {
        CSVFormat inFormat = CSVFormat.DEFAULT.builder()
                .setDelimiter(inputDelimiter)
                .setTrim(false)
                .setIgnoreEmptyLines(true)
                .setQuote('"')
                .build()
                .withFirstRecordAsHeader();

        try (CSVParser parser = CSVParser.parse(rawCsv, inputCharset, inFormat);
             OutputStream os = Files.newOutputStream(targetCsv);
             BufferedWriter writer = new BufferedWriter(new OutputStreamWriter(os, StandardCharsets.UTF_8))) {

            // 写入 UTF-8 BOM，提升 Windows/Excel 打开兼容性
            os.write(0xEF);
            os.write(0xBB);
            os.write(0xBF);

            CSVFormat outFormat = CSVFormat.DEFAULT.builder()
                    .setDelimiter(',')
                    .setQuote('"')
                    .setRecordSeparator("\n")
                    .build();

            try (CSVPrinter printer = new CSVPrinter(writer, outFormat)) {
                printer.printRecord(newHeaders);

                int columnCount = parser.getHeaderNames().size();
                for (CSVRecord record : parser) {
                    List<String> row = new ArrayList<>(columnCount);
                    for (int i = 0; i < columnCount; i++) {
                        row.add(record.get(i));
                    }
                    printer.printRecord(row);
                }
            }
        }
    }

    private static final class ParseAttempt {
        final Charset charset;
        final String charsetName;
        final char delimiter;
        final List<String> headers;


        final int mappedHeaderCount;
        final int replacementCharCount;
        final int headerCount;

        final int contentReplacementCharCount;
        final int contentHanCharCount;

        private ParseAttempt(
            Charset charset,
            char delimiter,
            List<String> headers,
            int mappedHeaderCount,
            int replacementCharCount,
            int contentReplacementCharCount,
            int contentHanCharCount
        ) {
            this.charset = charset;
            this.charsetName = charset != null ? charset.name() : null;
            this.delimiter = delimiter;
            this.headers = headers != null ? headers : List.of();

            this.mappedHeaderCount = mappedHeaderCount;
            this.replacementCharCount = replacementCharCount;
            this.headerCount = this.headers.size();

            this.contentReplacementCharCount = contentReplacementCharCount;
            this.contentHanCharCount = contentHanCharCount;
        }
    }

    private record CharsetProbe(int replacementCharCount, int hanCharCount) {
    }

    private ParseAttempt parse(Path csvPath) throws IOException {
        IOException last = null;
        ParseAttempt best = null;

        // 编码探针：用“数据内容”判定编码（仅看表头会误判，例如表头全是 ASCII 但正文包含大量中文）
        Map<Charset, CharsetProbe> probes = probeCharsets(csvPath);

        for (Charset charset : CHARSET_CANDIDATES) {
            String firstLine;
            try {
                try (var reader = Files.newBufferedReader(csvPath, charset)) {
                    firstLine = reader.readLine();
                }
            } catch (MalformedInputException e) {
                last = e;
                continue;
            }

            if (firstLine == null) {
                continue;
            }

            char delimiter = detectDelimiter(firstLine);

            CSVFormat format = CSVFormat.DEFAULT.builder()
                    .setDelimiter(delimiter)
                    .setIgnoreEmptyLines(true)
                    .setQuote('"')
                    .build()
                    .withFirstRecordAsHeader();

            try (CSVParser parser = CSVParser.parse(csvPath, charset, format)) {
                List<String> headers = parser.getHeaderNames();
                CharsetProbe probe = probes.getOrDefault(charset, new CharsetProbe(0, 0));
                ParseAttempt attempt = scoreAttempt(charset, delimiter, headers, probe);
                if (best == null || compareAttempt(attempt, best) > 0) {
                    best = attempt;
                }
            } catch (IllegalArgumentException e) {
                last = new IOException(e);
            } catch (IOException e) {
                last = e;
            }
        }

        if (best != null) {
            return best;
        }

        if (last != null) {
            throw last;
        }
        throw new IOException("无法解析 CSV（未知原因）");
    }

    private ParseAttempt scoreAttempt(Charset charset, char delimiter, List<String> headers, CharsetProbe probe) {
        int mapped = 0;
        int replacement = 0;

        if (headers != null) {
            for (String h : headers) {
                if (h == null) {
                    continue;
                }
                for (int i = 0; i < h.length(); i++) {
                    if (h.charAt(i) == '\uFFFD') {
                        replacement++;
                    }
                }

                String norm = normalizeToken(h);
                if (candidateToStandardField.containsKey(norm)) {
                    mapped++;
                }
            }
        }

        int contentReplacement = probe == null ? 0 : probe.replacementCharCount();
        int contentHan = probe == null ? 0 : probe.hanCharCount();
        return new ParseAttempt(charset, delimiter, headers, mapped, replacement, contentReplacement, contentHan);
    }

    /**
     * attempt A 是否优于 B：
     * 1) 能映射到标准字段的表头数量更多（优先确保 journal 等关键列能识别）
     * 2) 乱码替换字符更少（\uFFFD）
     * 3) 表头列数更多（更像结构化 CSV）
     */
    private int compareAttempt(ParseAttempt a, ParseAttempt b) {
        if (a.mappedHeaderCount != b.mappedHeaderCount) {
            return Integer.compare(a.mappedHeaderCount, b.mappedHeaderCount);
        }

        // 先看内容乱码（比表头更可靠）
        if (a.contentReplacementCharCount != b.contentReplacementCharCount) {
            return Integer.compare(b.contentReplacementCharCount, a.contentReplacementCharCount);
        }
        // 内容中文信息更多，优先（用于区分 UTF-8 vs GB18030 的正文可读性）
        if (a.contentHanCharCount != b.contentHanCharCount) {
            return Integer.compare(a.contentHanCharCount, b.contentHanCharCount);
        }

        if (a.replacementCharCount != b.replacementCharCount) {
            return Integer.compare(b.replacementCharCount, a.replacementCharCount);
        }
        if (a.headerCount != b.headerCount) {
            return Integer.compare(a.headerCount, b.headerCount);
        }
        return 0;
    }

    private Map<Charset, CharsetProbe> probeCharsets(Path csvPath) {
        long size;
        try {
            size = Files.size(csvPath);
        } catch (IOException e) {
            return Map.of();
        }
        if (size <= 0) {
            return Map.of();
        }

        List<Long> offsets = new ArrayList<>();
        offsets.add(0L);
        if (size > ENCODING_PROBE_CHUNK_BYTES) {
            offsets.add(size / 3);
            offsets.add((size * 2) / 3);
            offsets.add(Math.max(0L, size - ENCODING_PROBE_CHUNK_BYTES));
        }
        if (offsets.size() > ENCODING_PROBE_MAX_CHUNKS) {
            offsets = offsets.subList(0, ENCODING_PROBE_MAX_CHUNKS);
        }

        Map<Charset, int[]> acc = new HashMap<>(); // [0]=replacement, [1]=han

        try (FileChannel ch = FileChannel.open(csvPath, StandardOpenOption.READ)) {
            for (long rawOffset : offsets) {
                long offset = Math.max(0L, rawOffset - 4); // 避免落在多字节字符中间

                ByteBuffer buf = ByteBuffer.allocate(ENCODING_PROBE_CHUNK_BYTES);
                ch.position(offset);
                int n = ch.read(buf);
                if (n <= 0) {
                    continue;
                }
                buf.flip();

                for (Charset cs : CHARSET_CANDIDATES) {
                    String s;
                    try {
                        s = cs.decode(buf.asReadOnlyBuffer()).toString();
                    } catch (Exception e) {
                        // 极端情况：解码异常时强行惩罚
                        int[] a = acc.computeIfAbsent(cs, k -> new int[2]);
                        a[0] += 10_000;
                        continue;
                    }

                    int rep = 0;
                    int han = 0;
                    for (int i = 0; i < s.length(); i++) {
                        char c = s.charAt(i);
                        if (c == '\uFFFD') rep++;
                        if (Character.UnicodeScript.of(c) == Character.UnicodeScript.HAN) han++;
                    }
                    int[] a = acc.computeIfAbsent(cs, k -> new int[2]);
                    a[0] += rep;
                    a[1] += han;
                }
            }
        } catch (IOException e) {
            return Map.of();
        }

        Map<Charset, CharsetProbe> out = new HashMap<>();
        for (Map.Entry<Charset, int[]> e : acc.entrySet()) {
            int[] v = e.getValue();
            out.put(e.getKey(), new CharsetProbe(v[0], v[1]));
        }
        return out;
    }

    private char detectDelimiter(String headerLine) {
        if (headerLine == null || headerLine.isBlank()) {
            return ',';
        }

        int bestCount = -1;
        char best = ',';
        for (char d : DELIMITER_CANDIDATES) {
            int count = 0;
            for (int i = 0; i < headerLine.length(); i++) {
                if (headerLine.charAt(i) == d) {
                    count++;
                }
            }
            if (count > bestCount) {
                bestCount = count;
                best = d;
            }
        }

        return best;
    }

    private static final class HeaderNormalization {
        final List<String> newHeaders;
        final Map<String, String> renamedHeaders;

        private HeaderNormalization(List<String> newHeaders, Map<String, String> renamedHeaders) {
            this.newHeaders = newHeaders;
            this.renamedHeaders = renamedHeaders;
        }
    }

    private HeaderNormalization normalizeHeaders(List<String> headers) {
        Map<String, String> renamed = new LinkedHashMap<>();
        List<String> newHeaders = new ArrayList<>(headers.size());

        Set<String> usedStandard = new HashSet<>();
        Map<String, Integer> dupCounter = new HashMap<>();

        for (String header : headers) {
            String original = header == null ? "" : header;
            String norm = normalizeToken(original);

            String std = candidateToStandardField.get(norm);
            String finalHeader;
            if (std != null) {
                if (!usedStandard.contains(std)) {
                    finalHeader = std;
                    usedStandard.add(std);
                    if (!original.equals(std)) {
                        renamed.put(original, std);
                    }
                } else {
                    int next = dupCounter.merge(std, 1, Integer::sum);
                    finalHeader = std + "_alt" + next;
                }
            } else {
                finalHeader = original;
            }

            newHeaders.add(finalHeader);
        }

        return new HeaderNormalization(newHeaders, renamed);
    }

    private String normalizeToken(String token) {
        if (token == null) {
            return "";
        }
        String s = token;
        // 去 BOM
        s = s.replace("\uFEFF", "");
        s = s.trim().toLowerCase(Locale.ROOT);
        s = s.replace('_', ' ');
        s = s.replace('-', ' ');
        s = s.replaceAll("\\s+", " ");
        return s;
    }

    private Map<String, String> loadCandidateMap(ResourceLoader resourceLoader) {
        Map<String, Set<String>> standardToCandidates = new LinkedHashMap<>();

        // 1) 从 clean_config.yaml 读取 field_mapping
        try {
            Resource res = resourceLoader.getResource("classpath:python/config/clean_config.yaml");
            if (res.exists()) {
                try (InputStream is = res.getInputStream()) {
                    Object loaded = new Yaml().load(is);
                    if (loaded instanceof Map<?, ?> root) {
                        Object fieldMapping = root.get("field_mapping");
                        if (fieldMapping instanceof Map<?, ?> fm) {
                            for (Map.Entry<?, ?> entry : fm.entrySet()) {
                                String std = String.valueOf(entry.getKey());
                                standardToCandidates.putIfAbsent(std, new HashSet<>());
                                Object val = entry.getValue();
                                if (val instanceof List<?> list) {
                                    for (Object x : list) {
                                        if (x != null) {
                                            standardToCandidates.get(std).add(normalizeToken(String.valueOf(x)));
                                        }
                                    }
                                } else if (val != null) {
                                    standardToCandidates.get(std).add(normalizeToken(String.valueOf(val)));
                                }
                            }
                        }
                    }
                }
            }
        } catch (Exception e) {
            // 忽略：依赖 YAML 读取失败时走兜底
        }

        // 2) 兜底/增强：补充常见 WoS/CNKI 列名变体（不改 Python，只在 Java 侧兼容）
        add(standardToCandidates, "journal", "so", "source title", "source_title", "source", "publication title", "journal name", "journal_name", "期刊", "期刊名", "刊名", "来源出版物");
        add(standardToCandidates, "doi", "di", "doi doi", "digital object identifier", "doi-doi");
        add(standardToCandidates, "keywords", "author keywords", "de", "id", "关键词", "关键字");
        add(standardToCandidates, "publish_date", "year", "py", "publication year", "出版年", "发表年份");
        add(standardToCandidates, "target", "wos categories", "wc", "categories", "研究领域", "学科");
        add(standardToCandidates, "citations", "cited references", "cr", "references", "参考文献", "rf", "rfn");
        add(standardToCandidates, "title", "article title", "ti", "document title", "标题", "题名");
        add(standardToCandidates, "abstract", "ab", "摘要", "summary");
        add(standardToCandidates, "category", "中英文献", "language");

        // 3) 反向索引：candidate -> std
        Map<String, String> candidateToStd = new HashMap<>();
        for (Map.Entry<String, Set<String>> e : standardToCandidates.entrySet()) {
            String std = e.getKey();
            candidateToStd.put(normalizeToken(std), std);
            for (String cand : e.getValue()) {
                if (cand != null && !cand.isBlank()) {
                    candidateToStd.putIfAbsent(cand, std);
                }
            }
        }

        return candidateToStd;
    }

    private void add(Map<String, Set<String>> m, String std, String... candidates) {
        m.putIfAbsent(std, new HashSet<>());
        for (String c : candidates) {
            if (c != null && !c.isBlank()) {
                m.get(std).add(normalizeToken(c));
            }
        }
    }
}
