# -*- coding: utf-8 -*-
"""
wos_data_cleaner.py
功能：封装 WOS 数据清洗工具，可作为模块调用
支持 Excel 文件夹、CSV 文件夹和数据库
"""

import pandas as pd
import os, glob, re
import numpy as np
from sqlalchemy import create_engine, text

# ==================== 内置配置 ====================
CLEAN_CONFIG = {
    "data_source": {
        "type": "database",  # excel | csv | database
        "excel_dir": "C:/Users/28623/Downloads/excel文件2",
        "csv_dir": "C:/Users/28623/Downloads/csv文件",
        "database": {
            "dialect": "mysql",
            "host": "127.0.0.1",
            "port": 3306,
            "user": "root",
            "password": "gushuaizhi786315",
            "database": "PAPER_sys",
            "table": "cleaned"
        }
    },
    "cleaning": {
        "drop_conference": True,
        "min_year": None
    },
    "field_mapping": {
        "doi": ["DOI", "doi", "Digital Object Identifier","DOI-DOI"],
        "journal": ["Source Title", "Journal", "Publication Title","journal","Source-文献来源"],
        "keywords": ["Keywords", "Author Keywords", "关键词","keywords","Keywords-关键词","Keyword-关键词"],
        "publish_date": ["Publication Year", "Year","publish_date","Year-出版年","Year-年"],
        "target": ["WoS Categories", "Categories","target","Categories-研究领域"],
        "citations": ["Cited References", "References", "Cited References", "citations", "RFN-参考文献"],
        "title": ["Article Title", "Title", "Document Title","title","Title-标题","Title-题名"],
        "abstract": ["Abstract", "摘要", "abstract","Abstract-摘要","Summary-摘要"],
        "category": ["category","Category","中英文献"]
    }
}
# ================================================

class WosDataCleaner:
    def __init__(self, clean_config=None):
        self.clean_config = clean_config if clean_config else CLEAN_CONFIG
        self.cleaning_rules = self.clean_config['cleaning']
        self.field_mapping = self.clean_config['field_mapping']

    # ------------------- 数据读取 -------------------
    def load_excel_data(self, excel_dir):
        all_possible_columns = set()
        for names in self.field_mapping.values():
            all_possible_columns.update(names)
        excel_files = glob.glob(os.path.join(excel_dir, "*.xls*"))
        if not excel_files:
            raise FileNotFoundError(f"未找到Excel文件: {excel_dir}")
        dfs = []
        for f in excel_files:
            df0 = pd.read_excel(f, nrows=0)
            cols = [c for c in all_possible_columns if c in df0.columns]
            if cols:
                dfs.append(pd.read_excel(f, usecols=cols))
        if not dfs:
            raise ValueError("未能读取任何Excel数据")
        return pd.concat(dfs, ignore_index=True)

    def load_csv_data(self, csv_dir):
        csv_files = glob.glob(os.path.join(csv_dir, "*.csv"))
        if not csv_files:
            raise FileNotFoundError(f"未找到CSV文件: {csv_dir}")
        dfs = []
        for f in csv_files:
            dfs.append(pd.read_csv(f, encoding='utf-8-sig'))
        return pd.concat(dfs, ignore_index=True)

    def load_database_data(self, db_config):
        dialect_map = {'mysql': 'mysql+pymysql', 'postgresql': 'postgresql', 'sqlite': 'sqlite'}
        dialect = db_config.get('dialect', '').lower()
        if dialect not in dialect_map:
            raise ValueError(f"不支持的数据库类型: {dialect}")
        if dialect == 'sqlite':
            db_path = db_config.get('db_path', db_config.get('database', ''))
            conn_str = f"sqlite:///{db_path}"
        else:
            user = db_config.get('user', '')
            password = db_config.get('password', '')
            host = db_config.get('host', 'localhost')
            port = str(db_config.get('port', ''))
            database = db_config.get('database', '')
            conn_str = f"{dialect_map[dialect]}://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
        engine = create_engine(conn_str, echo=False)

        # 优先只读取需要的列，避免全表全列导致性能问题
        if 'sql' in db_config and db_config['sql']:
            df = pd.read_sql(text(db_config['sql']), engine)
            return df

        if 'table' in db_config and db_config['table']:
            table = db_config['table']
            # 需要的原始列名候选（field_mapping 里列出的所有可能名）
            all_possible_columns = set()
            for names in self.field_mapping.values():
                all_possible_columns.update([str(n) for n in names])

            try:
                from sqlalchemy import inspect

                inspector = inspect(engine)
                if inspector.has_table(table):
                    table_cols = [c['name'] for c in inspector.get_columns(table)]
                    cols_to_select = [c for c in table_cols if c in all_possible_columns]

                    # 若没有任何匹配列，回退到全表读取
                    if cols_to_select:
                        def _quote_ident(name: str) -> str:
                            if dialect == 'mysql':
                                return '`' + name.replace('`', '``') + '`'
                            # sqlite/postgresql 用双引号
                            return '"' + name.replace('"', '""') + '"'

                        cols_sql = ", ".join(_quote_ident(c) for c in cols_to_select)
                        table_sql = _quote_ident(str(table))
                        sql = f"SELECT {cols_sql} FROM {table_sql}"
                        df = pd.read_sql(text(sql), engine)
                        return df
            except Exception:
                # 检查表结构失败则回退
                pass

            df = pd.read_sql_table(table, engine)
            return df

        raise ValueError("数据库配置需指定 table 或 sql")

    # ------------------- 清洗辅助 -------------------
    @staticmethod
    def extract_dois_from_references(ref, category=None):
        """提取引用标识：英文优先 DOI；中文优先题名。

        说明：你的中文期刊 disruption 大量为 Null 的核心原因之一，是当前流水线只提取 DOI，
        而中文参考文献通常不含 DOI，导致 citing 为空 -> 无法建网。
        """
        if ref is None or (isinstance(ref, float) and pd.isna(ref)):
            return []

        def _dedup_keep_order(items):
            seen = set()
            out = []
            for x in items:
                x = ("" if x is None else str(x)).strip()
                if not x:
                    continue
                if x not in seen:
                    seen.add(x)
                    out.append(x)
            return out

        def _norm_doi(x: str) -> str:
            t = str(x or "").strip()
            if not t:
                return ""
            low = t.lower()
            for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
                if low.startswith(prefix):
                    t = t[len(prefix):]
                    low = t.lower()
                    break
            if low.startswith("doi:"):
                t = t.split(":", 1)[1]
            t = t.strip().rstrip(".。;；,，)]}\"' ")
            return t.lower()

        def _extract_dois(text: str) -> list[str]:
            s = str(text or "").strip()
            if not s:
                return []
            # 兼容字符串化列表
            if s.startswith('[') and s.endswith(']'):
                try:
                    inner = s[1:-1].strip()
                    for sep in [';', ',', '|']:
                        if sep in inner:
                            parts = [p.strip() for p in inner.split(sep)]
                            dois = [_norm_doi(p) for p in parts if p.strip().startswith('10.') and len(p.strip()) > 10]
                            dois = [d for d in dois if d]
                            if dois:
                                return _dedup_keep_order(dois)
                except Exception:
                    pass
            patterns = [r'DOI\s+([^\s;,\]]+)', r'doi:\s*([^\s;,\]]+)', r'\b10\.\d{4,9}/[-._;()/:A-Z0-9]+']
            out = []
            for pat in patterns:
                for d in re.findall(pat, s, re.IGNORECASE):
                    dn = _norm_doi(d)
                    if dn.startswith('10.') and len(dn) > 10:
                        out.append(dn)
            return _dedup_keep_order(out)

        def _norm_title(x: str) -> str:
            t = str(x or "").strip()
            if not t:
                return ""
            t = t.replace("\u3000", " ")
            t = (
                t.replace("，", ",")
                .replace("；", ";")
                .replace("：", ":")
                .replace("。", ".")
                .replace("（", "(")
                .replace("）", ")")
                .replace("“", '"')
                .replace("”", '"')
                .replace("‘", "'")
                .replace("’", "'")
            )
            t = re.sub(r"\s+", " ", t).strip()
            t = t.strip(" \t\r\n\"'《》<>[](){}")
            return t

        def _has_chinese(s: str) -> bool:
            return bool(re.search(r"[\u4e00-\u9fff]", s or ""))

        def _extract_titles(text: str) -> list[str]:
            s = str(text or "").strip()
            if not s:
                return []
            s = s.replace("　", " ")
            # 先做一轮中英文标点归一化，便于切分与抓取题名
            s = (
                s.replace("．", ".")
                .replace("。", ".")
                .replace("，", ",")
                .replace("；", ";")
                .replace("：", ":")
                .replace("（", "(")
                .replace("）", ")")
            )
            s = re.sub(r"\s+", " ", s).strip()
            if not s:
                return []

            # 1) 引号/书名号优先
            titles = []
            for m in re.finditer(r'["“](?P<t>[^"”]{2,200})["”]', s):
                titles.append(_norm_title(m.group('t')))
            for m in re.finditer(r'《\s*([^》]{2,200}?)\s*》', s):
                titles.append(_norm_title(m.group(1)))
            titles = [t for t in titles if t]
            if titles:
                return _dedup_keep_order(titles)

            # 2) 按常见参考文献编号切分
            if re.search(r"\[\s*\d+\s*\]", s):
                parts = [e.strip() for e in re.split(r"\[\s*\d+\s*\]", s) if e.strip()]
            else:
                # 支持无方括号编号且编号紧贴条目：
                # 例如："...1997,(2)2侯汉清.文献分类法..." 或 "1许慧.检索语言...2侯汉清..."
                marker_a = re.compile(r"(?:(?<=^)|(?<=[\)\]\.\,;:\s]))\s*(\d{1,3})(?=[\u4e00-\u9fffA-Za-z])")
                # 额外支持：年份紧贴下一条编号（如 19906彭...、19967丁...）
                marker_b = re.compile(r"(?<=(?:19|20)\d{2})\s*(\d{1,3})(?=[\u4e00-\u9fffA-Za-z])")

                starts = set()
                for m in marker_a.finditer(s):
                    starts.add(m.start())
                for m in marker_b.finditer(s):
                    starts.add(m.start())

                if starts:
                    idxs = sorted(starts)
                    # 确保从 0 开始（如果文本本身不以编号开头，也允许保留前缀为第一条）
                    if 0 not in starts:
                        idxs = [0] + idxs

                    slices = []
                    for i, start in enumerate(idxs):
                        end = idxs[i + 1] if i + 1 < len(idxs) else len(s)
                        part = s[start:end].strip()
                        if part:
                            slices.append(part)
                    parts = slices if slices else [s]
                else:
                    parts = [s]

            # 3) 每条抽取题名（兼容 "作者.题名,期刊,..." 与 "作者.题名."）
            for p in parts:
                core = _norm_title(p)
                if not core:
                    continue

                # 去掉开头编号（1/2,39 之类）
                core = re.sub(r"^\s*\d+(?:\s*,\s*\d+)*\s*", "", core).strip()
                # 去掉开头的 [1]
                core = re.sub(r"^\s*\[\s*\d+\s*\]\s*", "", core).strip()

                # -------- 核心：两类常见格式 --------
                # A) 作者.题名,期刊,...
                #    注意：作者列表可能包含逗号（如“洪漪,梁树柏.题名,期刊”），
                #    因此不能简单依赖“首个 '.' 是否早于首个 ','”。
                #    这里采用启发式：若首个 '.' 前缀较短（<=20），更可能是作者区。
                # B) 作者1,作者2,题名.期刊,... 或 作者,题名.期刊,...
                first_dot = core.find(".")
                first_comma = core.find(",")

                cand = ""

                prefix = core[:first_dot].strip() if first_dot != -1 else ""
                if prefix:
                    prefix_segs = [x.strip() for x in prefix.split(",") if x.strip()]
                else:
                    prefix_segs = []
                looks_like_author_prefix = (
                    bool(prefix_segs)
                    and len(prefix) <= 30
                    and len(prefix_segs) <= 4
                    and all(len(seg) <= 6 for seg in prefix_segs)
                    and not re.search(r"(?:19|20)\d{2}", prefix)
                )

                # 情况 A：确认为“作者.题名...”
                if first_dot != -1 and (looks_like_author_prefix or first_comma == -1 or first_dot < first_comma):
                    after_author = core[first_dot + 1 :].strip()
                    stop_positions = []
                    for ch in [",", ".", ";"]:
                        pos = after_author.find(ch)
                        if pos != -1:
                            stop_positions.append(pos)
                    stop = min(stop_positions) if stop_positions else -1
                    cand = after_author[:stop].strip() if stop != -1 else after_author.strip()

                # 情况 B：作者用逗号分隔
                if not cand:
                    segs = [seg.strip() for seg in re.split(r"[,;]", core) if seg.strip()]
                    # 过滤掉明显不是题名的段（年份/期次）
                    filtered = []
                    for seg in segs:
                        if re.fullmatch(r"(?:19|20)\d{2}", seg):
                            continue
                        if re.fullmatch(r"\(\d+\)", seg):
                            continue
                        filtered.append(seg)

                    def _score_title(t: str) -> int:
                        if not t:
                            return -10**9
                        score = len(t)
                        if "." in t:
                            score -= 10
                        if len(t) < 4:
                            score -= 50
                        # 很像期刊名/出版信息的后缀
                        if re.search(r"(学报|期刊|杂志|出版社)$", t):
                            score -= 30
                        # 很像中文姓名（2-4 字且无空格/标点）
                        if re.fullmatch(r"[\u4e00-\u9fff]{2,4}", t):
                            score -= 20
                        return score

                    candidates = []
                    for seg in filtered:
                        seg_n = _norm_title(seg)
                        if seg_n:
                            candidates.append(seg_n)

                        if "." in seg:
                            # 处理 "作者.题名.期刊"：取中间段作为题名
                            parts_dot = [p.strip() for p in seg.split(".") if p.strip()]
                            if len(parts_dot) >= 3:
                                mid = _norm_title(parts_dot[1])
                                if mid:
                                    candidates.append(mid)
                            elif len(parts_dot) == 2:
                                after = _norm_title(parts_dot[1])
                                if after:
                                    candidates.append(after)
                                # 处理 "题名.期刊"：题名往往在 '.' 前半段
                                before = _norm_title(parts_dot[0])
                                if before:
                                    candidates.append(before)

                    cand = max(candidates, key=_score_title, default="").strip()

                # 兜底：老格式 作者.题名.
                if not cand:
                    m = re.search(r"^[^.]{1,120}\.(?P<title>[^.]{2,300})\.", core)
                    if m:
                        cand = m.group("title").strip()

                tt = _norm_title(cand)
                # 简单有效性过滤：2-300 字符
                if 2 <= len(tt) <= 300:
                    titles.append(tt)

            return _dedup_keep_order([t for t in titles if t])

        # 统一把 ref 转成文本
        if isinstance(ref, list):
            joined = " ".join([str(x) for x in ref if x is not None])
        else:
            joined = str(ref)

        cat = "" if category is None or (isinstance(category, float) and pd.isna(category)) else str(category)
        cat_low = cat.strip().lower()
        is_cn = ("chinese" in cat_low) or ("中文" in cat_low) or _has_chinese(joined)

        if is_cn:
            titles = _extract_titles(joined)
            # 如果中文也能提到 DOI（极少），附带保留
            dois = _extract_dois(joined)
            return _dedup_keep_order(titles + dois)
        else:
            return _extract_dois(joined)

    @staticmethod
    def is_conference(title):
        if pd.isna(title):
            return False
        t = str(title).upper()
        keywords = ['CONFERENCE', 'PROCEEDINGS', 'SYMPOSIUM', 'MEETING', 'CONGRESS', 'WORKSHOP', 'PROC.', 'CONF.', 'SYMP.']
        return any(k in t for k in keywords) or bool(re.search(r'20\d{2}', t))

    @staticmethod
    def find_actual_column(df, names):
        for n in names:
            if n in df.columns:
                return n
        cols_lower = [str(c).lower().strip() for c in df.columns]
        for n in names:
            n_l = n.lower().strip()
            if n_l in cols_lower:
                return df.columns[cols_lower.index(n_l)]
        return None

    def clean_keywords_in_dataframe(self, df, keywords_col='keywords'):
        if keywords_col not in df.columns:
            return df
        def process(val):
            import ast
            if pd.isna(val):
                return []
            if isinstance(val, list):
                return list(set([str(k).strip().lower() for k in val if k]))
            s = str(val).strip()
            if s.startswith('[') and s.endswith(']'):
                try:
                    items = ast.literal_eval(s)
                    if isinstance(items, list):
                        return list(set([str(k).strip().lower() for k in items if k]))
                except:
                    pass
            for sep in [';', ',', '|', '/', '、', '；', '，']:
                if sep in s:
                    return list(set([p.strip().lower() for p in s.split(sep) if p]))
            return [s.lower()]
        df[keywords_col] = df[keywords_col].apply(process)
        return df

    def map_and_filter_columns(self, df):
        column_mapping = {}
        for target, names in self.field_mapping.items():
            col = self.find_actual_column(df, names)
            if col:
                column_mapping[col] = target
        if column_mapping:
            df = df.rename(columns=column_mapping)
        return df

    @staticmethod
    def extract_year(value):
        if pd.isna(value):
            return np.nan
        try:
            if isinstance(value, (int, float)):
                return int(value)
            s = str(value).strip()
            m = re.search(r'\b(20\d{2}|19\d{2})\b', s)
            if m:
                return int(m.group())
            try:
                dt = pd.to_datetime(s, errors='raise')
                return dt.year
            except:
                pass
            n = pd.to_numeric(s, errors='coerce')
            if not pd.isna(n) and 1000 <= n <= 2100:
                return int(n)
        except:
            pass
        return np.nan

    # ------------------- 主清洗函数 -------------------
    def clean(self, source_type='database', path=None):
        """
        source_type: 'excel', 'csv', 'database'
        path: Excel/CSV 文件夹路径，数据库可忽略
        """
        if source_type.lower() == 'excel':
            if path is None:
                path = self.clean_config['data_source'].get('excel_dir', '')
            df = self.load_excel_data(path)
        elif source_type.lower() == 'csv':
            if path is None:
                path = self.clean_config['data_source'].get('csv_dir', '')
            df = self.load_csv_data(path)
        elif source_type.lower() == 'database':
            db_conf = self.clean_config['data_source'].get('database', {})
            df = self.load_database_data(db_conf)
        else:
            raise ValueError(f"不支持的数据源类型: {source_type}")

        df = self.map_and_filter_columns(df)

        if 'citations' in df.columns:
            # 关键：中文参考文献通常无 DOI，仅靠 DOI 提取会导致 citing 大面积为空。
            # 若存在 category，则按行传入，提高中英文判别准确度。
            if 'category' in df.columns:
                df['citing'] = df.apply(lambda r: self.extract_dois_from_references(r.get('citations'), r.get('category')), axis=1)
            else:
                df['citing'] = df['citations'].apply(self.extract_dois_from_references)
        else:
            df['citing'] = [[] for _ in range(len(df))]

        for col in ['keywords', 'Keywords', 'Author Keywords', '关键词']:
            if col in df.columns:
                df = self.clean_keywords_in_dataframe(df, col)
                break

        if self.cleaning_rules.get('drop_conference', True) and 'journal' in df.columns:
            df = df[~df['journal'].apply(self.is_conference)]

        min_year = self.cleaning_rules.get('min_year')
        if min_year and 'publish_date' in df.columns:
            df['publish_date'] = df['publish_date'].apply(self.extract_year)
            df = df[df['publish_date'] >= min_year]

        if 'journal' in df.columns:
            journal_counts = df['journal'].value_counts()
            valid_journals = journal_counts[journal_counts >= 50].index
            df = df[df['journal'].isin(valid_journals)]

        return df


# ------------------- 用法示例 -------------------
if __name__ == "__main__":
    from pathlib import Path
    cleaner = WosDataCleaner()
    # 默认从数据库读取
    df_cleaned = cleaner.clean(source_type='database')
    # 如果要读取 Excel 文件夹
    # df_cleaned = cleaner.clean(source_type='excel', path="C:/Users/28623/Downloads/excel文件2")
    # 如果要读取 CSV 文件夹
    # df_cleaned = cleaner.clean(source_type='csv', path="C:/Users/28623/Downloads/csv文件")
    
    # 保存到 data 目录
    base_dir = Path(__file__).parent
    data_dir = base_dir / "data"
    data_dir.mkdir(parents=True, exist_ok=True)
    output_path = data_dir / "cleaned_data.csv"
    df_cleaned.to_csv(output_path, index=False, encoding="utf-8-sig")
    print(f"清洗完成，已保存到 {output_path}")
