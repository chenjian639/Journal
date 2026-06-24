# -*- coding: utf-8 -*-
"""
preprocess_wos_data.py
功能：从数据库或Excel读取论文数据，按clean_config.yaml规则清洗（对齐Java端字段）
"""
import pandas as pd
import os, glob, re, yaml, sys
import json
from baidu_translator_021 import NewBaiduTranslator
from pathlib import Path
from sqlalchemy import create_engine, text
import argparse
import numpy as np 

def load_clean_config(config_path=None):
    """加载清洗配置文件（python/config/clean_config.yaml）"""
    if config_path is None:
        root_dir = Path(__file__).parent
        config_path = root_dir / "config" / "clean_config.yaml"
        
        if not config_path.exists():
            print("[错误] 未找到 clean_config.yaml 文件")
            print(f"预期路径: {config_path}")
            sys.exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    # 验证必要配置
    required_sections = ['cleaning', 'field_mapping']
    for section in required_sections:
        if section not in config:
            print(f"[错误] 配置文件缺少必要部分: {section}")
            sys.exit(1)
    
    return config

def load_analysis_config():
    """加载分析配置文件（python/config/config.json）"""
    root_dir = Path(__file__).parent
    config_path = root_dir / "config" / "config.json"
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def extract_dois_from_references(ref,category=None):
    if pd.isna(ref):
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

    def _has_chinese(s: str) -> bool:
        return bool(re.search(r"[\u4e00-\u9fff]", s or ""))

    text_for_cat = ""
    if isinstance(ref, list):
        text_for_cat = " ".join([str(x) for x in ref if x is not None])
    elif ref is not None:
        text_for_cat = str(ref)
    cat_lower = "chinese" if _has_chinese(text_for_cat) else "english"

    if cat_lower == "chinese":
        text = text_for_cat.replace("　", " ")
        text = text.replace("．", ".").replace("。", ".")
        text = re.sub(r"\s+", " ", text).strip()
        if not text:
            return []

        def _split_entries(s: str) -> list[str]:
            if re.search(r"[\u2460-\u2473\u24ea]", s):
                parts = re.split(r"[\u2460-\u2473\u24ea]\s*", s)
                return [p.strip(" 　。.") for p in parts if p.strip(" 　。.")]
            if re.search(r"\[\s*\d+\s*\]", s):
                return [e.strip() for e in re.split(r"\[\s*\d+\s*\]", s) if e.strip()]
            marker = re.compile(
                r"(?:(?<=^)|(?<=\s))(\d+(?:\s*,\s*\d+)*)\s*(?=(?:\[|[A-Za-z\u4e00-\u9fff]))"
            )
            hits = list(marker.finditer(s))
            if not hits:
                return [s.strip()] if s.strip() else []
            slices = []
            for i, m in enumerate(hits):
                start = m.start()
                end = hits[i + 1].start() if i + 1 < len(hits) else len(s)
                part = s[start:end].strip()
                if part:
                    slices.append(part)
            return slices

        def _extract_title_from_entry(entry: str) -> str:
            e = entry.strip()
            if not e:
                return ""
            e = re.sub(r"^\s*(\[\s*\d+\s*\]|\d+(?:\s*,\s*\d+)*)\s*", "", e).strip()
            prefix = e
            if re.search(r"https?://", e, re.IGNORECASE):
                prefix = re.split(r"https?://", e, maxsplit=1, flags=re.IGNORECASE)[0]
                prefix = re.sub(r"[\s\.,;；]+$", "", prefix).strip()
                if (not re.search(r"[\u4e00-\u9fffA-Za-z]", prefix)) or re.fullmatch(r"[\[\]\d\-\s\.\(\)]+", prefix or ""):
                    return ""
            e = prefix
            book_mark = re.search(r"(出版社|大学出版社|学会印|印刷|第?\d+版|主编|编著|译|出版)", e)
            journal_mark = re.search(r"(第\s*\d+\s*期|Vol\.|No\.|学刊|杂志|期刊|Journal|Proceedings)", e, re.IGNORECASE)
            if re.search(r"\[(D|M|C|R|S|EB|OL|EB/OL)\]", e, re.IGNORECASE):
                return ""
            m_q = re.search(r'["“](?P<t>[^"”]{2,400})["”]', e)
            if m_q:
                return m_q.group("t").strip().strip(" .，,;；")
            colon_m = re.search(r"(?<![\d\)])[:：]", e)
            colon_ok = False
            if colon_m:
                pos = colon_m.start()
                if pos < 80 and "." not in e[:pos]:
                    colon_ok = True
            if colon_ok:
                after = e[colon_m.end():].strip() # type: ignore
                m_colon_book = re.search(r"^《\s*([^》]{1,200}?)\s*》", after)
                if m_colon_book:
                    if book_mark and not journal_mark:
                        return ""
                    return m_colon_book.group(1).strip()
                m_colon = re.search(r"^(?P<t>[^,，。《。\.]{2,400})", after)
                if m_colon:
                    title = m_colon.group("t").strip().strip(" .，,;；")
                    if book_mark and not journal_mark:
                        return ""
                    return title

            core = e
            core = re.sub(r"\([^)]*\)\s*$", "", core).strip()
            core = re.sub(r"\s*\.\s*", ".", core)

            def _protect_dots(s0: str) -> str:
                def repl(m):
                    return m.group(0).replace(".", "§")
                s1 = re.sub(r"\b(?:[A-Z]\.){2,}", repl, s0)
                s1 = re.sub(r"\b(?:[a-z]{1,3}\.){2,}", repl, s1)
                s1 = re.sub(r"\b\d+\.\d+\b", lambda m: m.group(0).replace(".", "§"), s1)
                return s1

            core2 = _protect_dots(core)
            parts = [p.strip().replace("§", ".") for p in core2.split(".") if p.strip()]
            if not parts:
                return ""
            candidates = parts[1:-1] if len(parts) >= 3 else parts[:]

            def _looks_like_url_piece(s: str) -> bool:
                s0 = s.strip()
                if re.search(r"(https?://|www\.)", s0, re.IGNORECASE):
                    return True
                if "/" in s0 and " " not in s0 and len(s0) > 8:
                    return True
                if re.search(r"\b(html?|pdf|view)\b", s0, re.IGNORECASE):
                    return True
                if re.search(r"\b(com|cn|org|net|edu)\b", s0, re.IGNORECASE) and "/" in s0:
                    return True
                return False

            def _is_date_like(s: str) -> bool:
                return bool(re.search(r"\b(19\d{2}|20\d{2})[-/]\d{1,2}[-/]\d{1,2}\b", s))

            def _is_authorish(s: str) -> bool:
                s0 = s.strip()
                low = s0.lower()
                if "et al" in low:
                    return True
                if s0.count(",") >= 1 and not re.search(r"[a-z]", s0) and len(s0) <= 140:
                    return True
                tokens = [t for t in re.split(r"[\s,]+", s0) if t]
                if len(tokens) >= 3:
                    short_initials = sum(1 for t in tokens if len(t) <= 2 and re.fullmatch(r"[A-Za-z]+", t))
                    if short_initials / len(tokens) >= 0.5:
                        return True
                if re.fullmatch(r"[A-Za-z]{2,}\s+[A-Za-z]\b", s0):
                    return True
                return False

            def _score_title(s: str) -> int:
                score = 0
                L = len(s)
                if 8 <= L <= 300:
                    score += 6
                elif 2 <= L < 8:
                    score += 1
                else:
                    score -= 2
                if re.search(r"[\u4e00-\u9fff]", s):
                    score += 12
                if re.search(r"[a-z]", s):
                    score += 6
                if " " in s:
                    score += 2
                if re.search(r"[:：\?\!—\-]", s):
                    score += 2
                if _looks_like_url_piece(s):
                    score -= 100
                if _is_date_like(s):
                    score -= 20
                if _is_authorish(s):
                    score -= 40
                if re.search(r"\[[^\]]+\]", s):
                    score -= 1
                return score

            title = max(candidates, key=_score_title, default="").strip()
            if not title or len(title) < 2:
                return ""
            title = re.sub(r"\[[^\]]+\]", "", title).strip()
            title = re.sub(r"\s+", " ", title).strip()
            title = title.split("《", 1)[0].strip()
            title = re.sub(r"https?://\S+", "", title, flags=re.IGNORECASE).strip()
            if book_mark and not journal_mark:
                return ""
            return title

        entries = _split_entries(text)
        titles = []
        for ent in entries:
            t = _extract_title_from_entry(ent)
            if t:
                titles.append(t)
        return list(set(titles))

    if isinstance(ref, list):
        dois = []
        for item in ref:
            if isinstance(item, str) and item.startswith("10.") and len(item) > 10:
                dois.append(item.strip())
        return list(set(dois))

    ref_str = str(ref)
    ref_str_stripped = ref_str.strip()
    if ref_str_stripped.startswith("[") and ref_str_stripped.endswith("]"):
        try:
            parsed = json.loads(ref_str_stripped)
            if isinstance(parsed, list):
                return list(set(extract_dois_from_references(parsed, category)))
        except Exception:
            pass
        try:
            inner = ref_str_stripped[1:-1].strip()
            for sep in [";", ",", "|"]:
                if sep in inner:
                    parts = [p.strip() for p in inner.split(sep)]
                    dois = [p for p in parts if p.startswith("10.") and len(p) > 10]
                    if dois:
                        return list(set(dois))
        except Exception:
            pass

    patterns = [
        r"DOI\s+([^\s;,\]]+)",
        r"doi:\s*([^\s;,\]]+)",
        r"10\.\d{4,9}/[-._;()/:A-Z0-9]+",
    ]
    dois = []
    for pattern in patterns:
        found = re.findall(pattern, ref_str, re.IGNORECASE)
        if found:
            for d in found:
                d_clean = d.strip().lstrip("[").rstrip(",;]")
                if d_clean.startswith("10.") and len(d_clean) > 10:
                    dois.append(d_clean)
    return list(set(dois))
    # if pd.isna(ref):
    #     return []

    # cat = "" if category is None or (isinstance(category, float) and pd.isna(category)) else str(category).strip()
    # cat_lower = cat.lower()

    # def _dedup_keep_order(items):
    #     seen = set()
    #     out = []
    #     for x in items:
    #         x = ("" if x is None else str(x)).strip()
    #         if not x:
    #             continue
    #         if x not in seen:
    #             seen.add(x)
    #             out.append(x)
    #     return out

    # # -------------------- Chinese：提取题名（多且准） --------------------
    # if cat_lower == "chinese":
    #     if isinstance(ref, list):
    #         text = " ".join([str(x) for x in ref if x is not None])
    #     else:
    #         text = str(ref)

    #     text = text.replace("　", " ")
    #     text = text.replace("．", ".").replace("。", ".")
    #     text = re.sub(r"\s+", " ", text).strip()
    #     if not text:
    #         return []

    #     def _split_entries(s: str) -> list[str]:
    #         # 标准：[1]...[2]...
    #         if re.search(r"\[\s*\d+\s*\]", s):
    #             return [e.strip() for e in re.split(r"\[\s*\d+\s*\]", s) if e.strip()]

    #         # 不标准：1 xxx 2 yyy；2,39 xxx；14,22,26 xxx
    #         marker = re.compile(
    #             r"(?:(?<=^)|(?<=\s))(\d+(?:\s*,\s*\d+)*)\s+(?=[A-Za-z\u4e00-\u9fff])"
    #         )
    #         hits = list(marker.finditer(s))
    #         if not hits:
    #             return [s.strip()] if s.strip() else []

    #         slices = []
    #         for i, m in enumerate(hits):
    #             start = m.start()
    #             end = hits[i + 1].start() if i + 1 < len(hits) else len(s)
    #             part = s[start:end].strip()
    #             if part:
    #                 slices.append(part)
    #         return slices

    #     def _extract_title_from_entry(entry: str) -> str:
    #         e = entry.strip()
    #         if not e:
    #             return ""

    #         # 去掉开头编号（含 2,39 这种）
    #         e = re.sub(r"^\s*(\[\s*\d+\s*\]|\d+(?:\s*,\s*\d+)*)\s*", "", e).strip()

    #         # 排除：学位论文/图书/会议/报告等（提高准确性）
    #         if re.search(r"\[(D|M|C|R)\]", e, re.IGNORECASE):
    #             return ""
    #         if "出版社" in e:
    #             return ""
    #         if re.search(r"[\u4e00-\u9fff]{1,10}\s*:\s*[\u4e00-\u9fff]{1,30}", e):
    #             return ""

    #         # 标准 [J]：只取 [J] 之前，避免把期刊信息混进题名
    #         m_j = re.search(r"\[J\]", e, re.IGNORECASE)
    #         core = e[: m_j.start()].strip() if m_j else e

    #         # 去掉末尾括号英文对照
    #         core = re.sub(r"\([^)]*\)\s*$", "", core).strip()

    #         # 归一化点号周围空白，确保“题名前后一定是.”可用
    #         core = re.sub(r"\s*\.\s*", ".", core)

    #         # 题名 = 第一个 '.' 与第二个 '.' 之间（你的不标准样例也满足）
    #         m = re.search(r"^[^.\n]{1,200}\.(?P<title>[^.\n]{1,600}?)\.", core)
    #         if not m:
    #             return ""

    #         title = m.group("title").strip()
    #         if not title or len(title) < 2:
    #             return ""

    #         # 对非 [J] 条目：要求后文能看到年份，避免把奇怪文本误当题名
    #         if not m_j:
    #             tail = e[m.end():] if m.end() < len(e) else ""
    #             if not re.search(r"\b(19\d{2}|20\d{2})\b", tail):
    #                 return ""

    #         return title

    #     entries = _split_entries(text)
    #     titles = []
    #     for ent in entries:
    #         t = _extract_title_from_entry(ent)
    #         if t:
    #             titles.append(t)

    #     return _dedup_keep_order(titles)

    # # -------------------- English：保持原 DOI 提取逻辑不变 --------------------
    # if isinstance(ref, list):
    #     dois = []
    #     for item in ref:
    #         if isinstance(item, str) and item.startswith('10.') and len(item) > 10:
    #             dois.append(item.strip())
    #     return list(set(dois))

    # ref_str = str(ref)

    # ref_str_stripped = ref_str.strip()
    # if ref_str_stripped.startswith('[') and ref_str_stripped.endswith(']'):
    #     try:
    #         inner = ref_str_stripped[1:-1].strip()
    #         for sep in [';', ',', '|']:
    #             if sep in inner:
    #                 parts = [p.strip() for p in inner.split(sep)]
    #                 dois = [p for p in parts if p.startswith('10.') and len(p) > 10]
    #                 if dois:
    #                     return list(set(dois))
    #     except:
    #         pass

    # patterns = [
    #     r'DOI\s+([^\s;,\]]+)',
    #     r'doi:\s*([^\s;,\]]+)',
    #     r'10\.\d{4,9}/[-._;()/:A-Z0-9]+',
    # ]

    # dois = []
    # for pattern in patterns:
    #     found = re.findall(pattern, ref_str, re.IGNORECASE)
    #     if found:
    #         for d in found:
    #             d_clean = d.strip().lstrip('[').rstrip(',;]')
    #             if d_clean.startswith('10.') and len(d_clean) > 10:
    #                 dois.append(d_clean)

    # return list(set(dois))
    # """从参考文献中提取DOI（增强版，保持原逻辑）"""
    # if pd.isna(ref): 
    #     return []
    
    # # 新增：如果是列表类型，直接处理
    # if isinstance(ref, list):
    #     # 过滤出以'10.'开头的字符串
    #     dois = []
    #     for item in ref:
    #         if isinstance(item, str) and item.startswith('10.') and len(item) > 10:
    #             dois.append(item.strip())
    #     return list(set(dois))
    
    # ref_str = str(ref)
    
    # # 新增：如果是字符串化的列表
    # ref_str_stripped = ref_str.strip()
    # if ref_str_stripped.startswith('[') and ref_str_stripped.endswith(']'):
    #     try:
    #         # 提取方括号内的内容
    #         inner = ref_str_stripped[1:-1].strip()
    #         # 按常见分隔符分割
    #         for sep in [';', ',', '|']:
    #             if sep in inner:
    #                 parts = [p.strip() for p in inner.split(sep)]
    #                 dois = [p for p in parts if p.startswith('10.') and len(p) > 10]
    #                 if dois:
    #                     return list(set(dois))
    #     except:
    #         pass  # 如果解析失败，回退到原逻辑
    
    # # =================== 以下是原函数逻辑（不要修改）===================
    # patterns = [
    #     r'DOI\s+([^\s;,\]]+)',
    #     r'doi:\s*([^\s;,\]]+)',
    #     r'10\.\d{4,9}/[-._;()/:A-Z0-9]+',
    # ]
    
    # dois = []
    # for pattern in patterns:
    #     found = re.findall(pattern, ref_str, re.IGNORECASE)
    #     if found:
    #         for d in found:
    #             d_clean = d.strip().lstrip('[').rstrip(',;]')
    #             if d_clean.startswith('10.') and len(d_clean) > 10:
    #                 dois.append(d_clean)
    
    # return list(set(dois))
def is_conference(title):
    """判断是否为会议论文"""
    if pd.isna(title): 
        return False
    
    t = str(title).upper()
    conference_keywords = [
        'CONFERENCE', 'PROCEEDINGS', 'SYMPOSIUM', 'MEETING', 
        'CONGRESS', 'WORKSHOP', 'PROC.', 'CONF.', 'SYMP.'
    ]
    
    return any(w in t for w in conference_keywords) or bool(re.search(r'20\d{2}', t))

def find_actual_column(df, possible_names):
    """在DataFrame中查找实际存在的列名（兼容大小写/别名）"""
    for name in possible_names:
        if name in df.columns:
            return name
    
    df_cols_lower = [str(col).lower().strip() for col in df.columns]
    for name in possible_names:
        name_lower = name.lower().strip()
        if name_lower in df_cols_lower:
            idx = df_cols_lower.index(name_lower)
            return df.columns[idx]
    
    return None

def get_needed_columns_from_configs(clean_config, analysis_config):
    """从配置文件中获取所有需要的列"""
    needed_columns = set()
    
    # 清洗配置的目标列（Java标准字段）
    if 'field_mapping' in clean_config:
        for target_col in clean_config['field_mapping'].keys():
            needed_columns.add(target_col)
    
    # 分析配置的需要列
    if analysis_config:
        for module, config in analysis_config.items():
            if 'columns' in config:
                for col_value in config['columns'].values():
                    if col_value and col_value.strip():
                        needed_columns.add(col_value.strip())
    
    # 基础必要列
    needed_columns.add('citations')
    needed_columns.add('id')  # 添加id列作为必要列
    return list(needed_columns)

def load_excel_data(excel_dir, field_mapping):
    """备用：从Excel加载数据"""
    all_possible_columns = set()
    for possible_names in field_mapping.values():
        all_possible_columns.update(possible_names)
    
    excel_files = glob.glob(os.path.join(excel_dir, "*.xls*"))
    if not excel_files:
        root_dir = Path(__file__).parent
        excel_dir = root_dir / excel_dir
        excel_files = glob.glob(os.path.join(str(excel_dir), "*.xls*"))
    
    if not excel_files:
        raise FileNotFoundError(f"未找到Excel文件: {excel_dir}")
    
    dfs = []
    for excel_file in excel_files:
        try:
            temp_df = pd.read_excel(excel_file, nrows=0)
            existing_columns = [col for col in all_possible_columns if col in temp_df.columns]
            if not existing_columns:
                print(f"[警告] {os.path.basename(excel_file)} 无目标列")
                continue
            
            df_temp = pd.read_excel(excel_file, usecols=existing_columns)
            dfs.append(df_temp)
        except Exception as e:
            print(f"[错误] 读取Excel失败: {e}")
    
    if not dfs:
        raise ValueError("未能读取任何Excel数据")
    
    df = pd.concat(dfs, ignore_index=True)
    print(f"[数据源] Excel数据: {df.shape[0]}行 × {df.shape[1]}列")
    return df

def load_database_data(db_config, field_mapping):
    """从数据库加载数据"""
    all_possible_columns = []
    for possible_names in field_mapping.values():
        all_possible_columns.extend(possible_names)
    
    dialect_map = {
        'mysql': 'mysql+pymysql',
        'postgresql': 'postgresql',
        'sqlite': 'sqlite'
    }
    
    dialect = db_config.get('dialect', '').lower()
    if dialect not in dialect_map:
        raise ValueError(f"不支持的数据库类型: {dialect}")
    
    # 构建连接字符串
    if dialect == 'sqlite':
        conn_str = f"sqlite:///{db_config.get('database', '')}"
    else:
        user = db_config.get('user', '')
        password = db_config.get('password', '')
        host = db_config.get('host', 'localhost')
        port = str(db_config.get('port', ''))
        database = db_config.get('database', '')
        conn_str = f"{dialect_map[dialect]}://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
    
    # 连接数据库
    engine = create_engine(conn_str, echo=False)
    with engine.connect() as conn:
        conn.execute(text("SELECT 1"))
    
    # 读取数据
    if 'sql' in db_config and db_config['sql']:
        df = pd.read_sql(text(db_config['sql']), engine)
    elif 'table' in db_config and db_config['table']:
        table_name = db_config['table']
        df = pd.read_sql_table(table_name, engine)
    else:
        raise ValueError("数据库配置需指定table或sql")
    
    print(f"[数据源] 数据库数据: {df.shape[0]}行 × {df.shape[1]}列")
    return df

def clean_keywords_in_dataframe(df, keywords_col='keywords', translator=None, clean_glossary_path=None):
    """
    在数据清洗阶段处理关键词列
    基于topic_analyzer.py的clean_author_keywords逻辑，但简化
    将中文关键词翻译为英文后直接更新到keywords列中
    """
    if keywords_col not in df.columns:
        print(f"[清洗] 警告：没有找到关键词列 '{keywords_col}'")
        return df
    
    print(f"[清洗] 开始处理关键词列: {keywords_col}")
    print(f"[清洗] 处理前数据类型示例: {type(df[keywords_col].iloc[0]) if len(df) > 0 else '空'}")
    
    def process_keywords(keywords_val):
        """处理单个关键词值"""
        import ast
        import re
        
        # 空值处理
        if pd.isna(keywords_val):
            return []
        
        # 已经是列表类型
        if isinstance(keywords_val, list):
            cleaned = []
            for kw in keywords_val:
                if kw is not None:
                    kw_str = str(kw).strip()
                    if kw_str:
                        cleaned.append(kw_str.lower())
            return list(set(cleaned))
        
        keywords_str = str(keywords_val).strip()
        
        # 空字符串
        if not keywords_str:
            return []
        
        # 尝试解析为Python列表
        if keywords_str.startswith('[') and keywords_str.endswith(']'):
            try:
                items = ast.literal_eval(keywords_str)
                if isinstance(items, list):
                    cleaned = []
                    for item in items:
                        if item is not None:
                            item_str = str(item).strip()
                            if item_str:
                                cleaned.append(item_str.lower())
                    return list(set(cleaned))
            except:
                # 解析失败，继续其他方法
                pass
        
        # 尝试多种分隔符分割
        # 优先级：先按分号，再按逗号，再按其他分隔符
        separators = [';', ',', '|', '/', '、', '；', '，']
        
        for sep in separators:
            if sep in keywords_str:
                # 分割并清理
                parts = [part.strip() for part in keywords_str.split(sep)]
                cleaned = [part.lower() for part in parts if part]
                if cleaned:
                    return list(set(cleaned))
        
        # 没有分隔符，作为单个关键词
        return [keywords_str.lower()]
    
    # 记录处理前统计
    original_non_empty = df[keywords_col].notna().sum()
    original_samples = df[keywords_col].head(3).tolist() if len(df) > 0 else []
    
    # 应用处理
    df[keywords_col] = df[keywords_col].apply(process_keywords)
    
    # 记录处理后统计
    processed_samples = df[keywords_col].head(3).tolist() if len(df) > 0 else []
    total_keywords = df[keywords_col].apply(len).sum()
    avg_keywords = df[keywords_col].apply(len).mean() if len(df) > 0 else 0
    empty_count = df[keywords_col].apply(lambda x: len(x) == 0).sum()
    
    print(f"[清洗] 关键词处理完成:")
    print(f"      处理前行数: {len(df)}")
    print(f"      非空关键词行数: {original_non_empty}")
    print(f"      处理后空关键词行数: {empty_count}")
    print(f"      示例处理前: {original_samples}")
    print(f"      示例处理后: {processed_samples}")
    print(f"      总关键词数: {total_keywords}")
    print(f"      平均每篇关键词数: {avg_keywords:.2f}")
    # ---- 翻译阶段：将中文关键词翻译为英文（使用词表优先，缺失时调用百度翻译并写回词表） ----
    # 尝试加载“清理后的”词表（plain keys 没有 _zh_en 后缀），优先使用该文件作为快速查表
    plain_glossary = {}
    try:
        if clean_glossary_path is None:
            cg_path = Path(__file__).parent / 'keyword_glossary_clean.json'
        else:
            cg_path = Path(clean_glossary_path)
        if cg_path.exists():
            with open(cg_path, 'r', encoding='utf-8') as f:
                plain_glossary = json.load(f)
    except Exception:
        plain_glossary = {}

    # 中文检测函数（移动到外层作用域，供多个函数使用）
    def is_chinese(text):
        return any('\u4e00' <= ch <= '\u9fff' for ch in text)

    def translate_list(kw_list):
        if not kw_list:
            return []
        out = []
        for kw in kw_list:
            if not kw:
                continue
            kw_str = str(kw).strip()
            # 调试信息：查看关键词内容和是否为中文
            print(f"[调试] 处理关键词: '{kw_str}', 包含中文: {is_chinese(kw_str)}, 在词表中: {kw_str in plain_glossary}")
            # 优先查 plain_glossary（键为纯中文）
            if kw_str in plain_glossary:
                out.append(plain_glossary[kw_str])
                continue

            # 若包含中文，优先使用 translator 的词表（带后缀形式），否则调用翻译
            if is_chinese(kw_str):
                translated = None
                if translator is not None:
                    gkey = f"{kw_str}_zh_en"
                    try:
                        # translator.translation_glossary keys 通常带后缀
                        if hasattr(translator, 'translation_glossary') and gkey in translator.translation_glossary:
                            translated = translator.translation_glossary[gkey]
                        else:
                            # 调用 translate，设置 add_to_glossary=True 以便回写词表
                            translated = translator.translate(kw_str, from_lang='zh', to_lang='en', add_to_glossary=True)
                    except Exception:
                        translated = None

                if translated:
                    out.append(translated)
                    # 同步写入 plain_glossary（plain 键：纯中文 -> 英文），并持久化到文件
                    try:
                        if isinstance(cg_path, Path):
                            plain_glossary[kw_str] = translated
                            with open(cg_path, 'w', encoding='utf-8') as _f:
                                json.dump(plain_glossary, _f, ensure_ascii=False, indent=2)
                    except Exception:
                        # 写入失败不影响主流程
                        pass
                else:
                    out.append(kw_str)
            else:
                # 非中文项直接保留（或可视为已是英文）
                out.append(kw_str)

        # 去重并保留顺序
        seen = set()
        uniq = []
        for x in out:
            if x not in seen:
                seen.add(x)
                uniq.append(x)
        return uniq

    # 生成新的英文关键词列 'keywords_en'
    try:
        # 添加进度跟踪
        total_keywords = sum(len(kw_list) for kw_list in df[keywords_col] if kw_list)
        translated_count = 0
        
        def translate_list_with_progress(kw_list):
            nonlocal translated_count
            if not kw_list:
                return []
            out = []
            for kw in kw_list:
                if not kw:
                    continue
                kw_str = str(kw).strip()
                # 调试信息：查看关键词内容和是否为中文
                print(f"[调试] 处理关键词: '{kw_str}', 包含中文: {is_chinese(kw_str)}, 在词表中: {kw_str in plain_glossary}")
                # 优先查 plain_glossary（键为纯中文）
                if kw_str in plain_glossary:
                    out.append(plain_glossary[kw_str])
                    continue

                # 若包含中文，优先使用 translator 的词表（带后缀形式），否则调用翻译
                if is_chinese(kw_str):
                    translated_count += 1
                    translated = None
                    if translator is not None:
                        gkey = f"{kw_str}_zh_en"
                        try:
                            # translator.translation_glossary keys 通常带后缀
                            if hasattr(translator, 'translation_glossary') and gkey in translator.translation_glossary:
                                translated = translator.translation_glossary[gkey]
                                print(f"[翻译进度] {translated_count}/{total_keywords} - 从词表获取: {kw_str} → {translated}")
                            else:
                                # 调用 translate，设置 add_to_glossary=True 以便回写词表
                                translated = translator.translate(kw_str, from_lang='zh', to_lang='en', add_to_glossary=True)
                                print(f"[翻译进度] {translated_count}/{total_keywords} - 百度翻译: {kw_str} → {translated}")
                        except Exception as e:
                            print(f"[翻译进度] {translated_count}/{total_keywords} - 翻译失败: {kw_str} → 保留原文 ({str(e)[:20]}...)")
                            translated = None

                    if translated:
                        out.append(translated)
                        # 同步写入 plain_glossary（plain 键：纯中文 -> 英文），并持久化到文件
                        try:
                            if isinstance(cg_path, Path):
                                plain_glossary[kw_str] = translated
                                with open(cg_path, 'w', encoding='utf-8') as _f:
                                    json.dump(plain_glossary, _f, ensure_ascii=False, indent=2)
                        except Exception:
                            # 写入失败不影响主流程
                            pass
                    else:
                        out.append(kw_str)
                else:
                    # 非中文项直接保留（或可视为已是英文）
                    out.append(kw_str)

            # 去重并保留顺序
            seen = set()
            uniq = []
            for x in out:
                if x not in seen:
                    seen.add(x)
                    uniq.append(x)
            return uniq
        
        print(f"[翻译] 开始处理关键词，预计总翻译量: {total_keywords}个关键词")
        df[keywords_col] = df[keywords_col].apply(translate_list_with_progress)
        print("[清洗] 已将关键词翻译为英文（词表优先，缺失时调用百度翻译并回写词表）")
    except Exception as e:
        print(f"[清洗] 关键字翻译失败: {e}")
    # 返回处理后的 DataFrame（keywords列已更新为英文关键词）
    return df
def map_and_filter_columns(df, field_mapping, needed_columns):
    """字段映射（原始列→Java标准列）+ 过滤无关列"""
    column_mapping = {}
    
    print("\n[字段映射] 原始列 → Java标准列:")
    for target_col, possible_names in field_mapping.items():
        actual_col = find_actual_column(df, possible_names)
        if actual_col:
            column_mapping[actual_col] = target_col
            print(f"  OK {actual_col} → {target_col}")
        else:
            print(f"  NO 未找到: {target_col}")
    
    if column_mapping:
        df = df.rename(columns=column_mapping)
    
    available_columns = [col for col in needed_columns if col in df.columns]
    df = df[available_columns]
    print(f"\n[字段过滤] 保留列（Java标准）: {list(df.columns)}")
    
    return df


def save_cleaned_to_db(df, write_back_config):
    """
    将清洗后的 DataFrame 写回数据库（根据 write_back_config）

    write_back_config 示例结构：
    write_back:
      enabled: true
      database:
        dialect: mysql
        user: xxx
        password: xxx
        host: 127.0.0.1
        port: 3306
        database: mydb
      table: cleaned_papers
      if_exists: replace    # or 'append'
      chunksize: 1000
    """
    if not write_back_config or not write_back_config.get('enabled'):
        print("[写回] 配置未启用，跳过写回数据库")
        return False

    db_conf = write_back_config.get('database', {})
    table = write_back_config.get('table', 'cleaned')
    # 规范化历史遗留表名，强制写入 `cleaned` 表
    try:
        tbl_norm = str(table).strip().lower()
        # 列出可能的历史/错误表名，全部映射到 cleaned
        legacy_names = ('cleaned_paper', 'cleaned_papers', 'cleanedpaper', 'cleaned_paper_s')
        if tbl_norm in legacy_names:
            print(f"[写回] 将写回目标表名从 `{table}` 映射为 `cleaned`")
            table = 'cleaned'
    except Exception:
        # 若解析表名失败，回退为默认值
        table = 'cleaned'
    if_exists = write_back_config.get('if_exists', 'replace')
    chunksize = write_back_config.get('chunksize', 1000)

    dialect_map = {
        'mysql': 'mysql+pymysql',
        'postgresql': 'postgresql',
        'sqlite': 'sqlite'
    }

    dialect = str(db_conf.get('dialect', '')).lower()
    if dialect not in dialect_map:
        print(f"[写回] 不支持的数据库类型: {dialect}")
        return False

    # 构建连接字符串
    try:
        if dialect == 'sqlite':
            db_path = db_conf.get('db_path', db_conf.get('database', ''))
            conn_str = f"sqlite:///{db_path}"
        else:
            user = db_conf.get('user', '')
            password = db_conf.get('password', '')
            host = db_conf.get('host', 'localhost')
            port = str(db_conf.get('port', ''))
            database = db_conf.get('database', '')
            conn_str = f"{dialect_map[dialect]}://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"

        engine = create_engine(conn_str, echo=False)

        print(f"[写回] 开始写入表 `{table}` (if_exists={if_exists}, chunksize={chunksize})")
        # 准备写入：序列化 list/dict 列为 JSON 字符串以避免 SQL 参数错误
        df_to_write = df.copy()
        for col in df_to_write.columns:
            try:
                if df_to_write[col].apply(lambda x: isinstance(x, (list, dict))).any():
                    df_to_write[col] = df_to_write[col].apply(lambda x: json.dumps(x, ensure_ascii=False) if x is not None else None)
            except Exception:
                # 如果列无法按 element-wise 判断（如全部为 None），跳过
                pass

        # 如果目标表已存在且采用 append 模式，仅写入表中已有的列（避免 Unknown column 错误）
        from sqlalchemy import inspect
        inspector = inspect(engine)
        if inspector.has_table(table) and str(if_exists).lower() == 'append':
            try:
                table_cols = [c['name'] for c in inspector.get_columns(table)]
                print(f"[写回] 表 `{table}` 中的列: {table_cols}")
                print(f"[写回] 准备写入的列: {list(df_to_write.columns)}")
                cols_to_keep = [c for c in df_to_write.columns if c in table_cols]
                dropped = [c for c in df_to_write.columns if c not in table_cols]
                if dropped:
                    print(f"[写回] 注意：目标表已存在，将移除这些在表中不存在的列以避免错误: {dropped}")
                if not cols_to_keep:
                    print(f"[写回] 错误：目标表 `{table}` 中没有可写入的列，取消写入")
                    return False
                print(f"[写回] 实际写入的列: {cols_to_keep}")
                df_to_write = df_to_write[cols_to_keep]
            except Exception as e:
                print(f"[写回] 检查目标表结构失败，尝试按原始方式写入: {e}")

        # 使用事务写入
        with engine.begin() as conn:
            df_to_write.to_sql(table, conn, if_exists=if_exists, index=False, chunksize=chunksize)

        print(f"[写回] 成功写入表: {table}")
        return True
    except Exception as e:
        print(f"[写回] 写入失败: {e}")
        return False

def run_clean(clean_config_path=None):
    """
    主清洗函数
    :param clean_config_path: 清洗配置文件路径
    :return: 清洗后的DataFrame、输出路径
    """
    print("=" * 70)
    print("WOS数据清洗工具（对齐Java字段）")
    print("=" * 70)
    
    try:
        clean_config = load_clean_config(clean_config_path)
        analysis_config = load_analysis_config()
        cleaning_rules = clean_config['cleaning']
        field_mapping = clean_config['field_mapping']
        
        drop_conference = cleaning_rules.get('drop_conference', True)
        min_year = cleaning_rules.get('min_year')
        target_journals = cleaning_rules.get('target_journals', [])
        top_n = cleaning_rules.get('top_n', 5)
        
        # 读取数据源
        source_config = clean_config.get('data_source', {})
        source_type = source_config.get('type', 'database')
        
        if source_type.lower() == 'excel':
            excel_dir = source_config.get('excel_dir', '')
            if not os.path.isabs(excel_dir):
                excel_dir = str(Path(__file__).parent / excel_dir)
            df = load_excel_data(excel_dir, field_mapping)
        elif source_type.lower() == 'database':
            db_config = source_config.get('database', {})
            df = load_database_data(db_config, field_mapping)
        else:
            raise ValueError(f"不支持的数据源类型：{source_type}")
        
        # 字段映射与过滤
        needed_columns = get_needed_columns_from_configs(clean_config, analysis_config)
        df = map_and_filter_columns(df, field_mapping, needed_columns)
        
        # 数据清洗
        print(f"\n[清洗] 原始数据量：{df.shape[0]}行")
        if 'citations' in df.columns:
            print("[清洗] 从参考文献提取DOI...")
            print("[清洗] 从参考文献生成 citing（English: DOI；Chinese: 题名）...")
            if "category" in df.columns:
                df["citing"] = df.apply(
                    lambda r: extract_dois_from_references(r.get("citations"), r.get("category")),
                    axis=1
                )
            else:
                df["citing"] = df["citations"].apply(extract_dois_from_references)

            total_items = df["citing"].apply(len).sum()
            print(f"[清洗] 生成 citing 条目数量：{total_items}")
            total_dois = df['citing'].apply(len).sum()
            print(f"[清洗] 提取DOI数量：{total_dois}")
        else:
            df['citing'] = [[] for _ in range(len(df))]
            print("[警告] 无citations列，无法提取DOI")
        # ==================== 新增：关键词处理 ====================
        # 从field_mapping获取关键词列名（支持多种可能名称）
        keywords_col_candidates = ['keywords', 'Keywords', 'Author Keywords', '关键词']
        keywords_col_name = None
        
        for col in keywords_col_candidates:
            if col in df.columns:
                keywords_col_name = col
                break
        
        if keywords_col_name:
            # 初始化翻译器（若有词表文件，可通过参数指定）
            glossary_candidates = [
                Path(__file__).parent / 'keyword_glossary_clean.json',
                Path(__file__).parent / 'keyword_glossary.json',
                Path(__file__).parent / 'rebuilt_keyword_glossary.json',
            ]
            chosen = None
            for p in glossary_candidates:
                if p.exists():
                    chosen = p
                    break

            translator = None
            try:
                if chosen:
                    # 将词表文件传给翻译器（翻译器期望带后缀的键，但也能加载任何JSON）
                    translator = NewBaiduTranslator(glossary_file=str(chosen), rate_limit=0.33)  # 进一步降低请求频率到每3秒1个请求
                else:
                    translator = NewBaiduTranslator(rate_limit=0.33)  # 进一步降低请求频率到每3秒1个请求
            except Exception as e:
                print(f"[翻译器] 初始化失败: {e}，关键词翻译将回退为仅表内查找")
                translator = None

            df = clean_keywords_in_dataframe(df, keywords_col_name, translator=translator, clean_glossary_path=str(Path(__file__).parent / 'keyword_glossary_clean.json'))
        else:
            print("[清洗] 未找到关键词列，跳过关键词处理")
        # ==================== 关键词处理结束 ====================
        if drop_conference and 'journal' in df.columns:
            before = len(df)
            df = df[~df['journal'].apply(is_conference)]
            after = len(df)
            print(f"[清洗] 去除会议论文：{before} → {after} (-{before-after})")
        
        if min_year and 'publish_date' in df.columns:
            # 新增：智能提取年份函数
            """
            从各种格式中提取整数年份
            支持：2023, "2023", "2023-05-20", "2023/05/20", "2023.05.20", "May 20, 2023"
            """
            def extract_year(value):
                if pd.isna(value):
                    return np.nan
                try:
                    # 尝试直接转换为整数
                    if isinstance(value, (int, float)):
                        return int(value)
                    
                    value_str = str(value).strip()
                    
                    # 1. 尝试正则提取年份（优先）
                    year_match = re.search(r'\b(20\d{2}|19\d{2})\b', value_str)
                    if year_match:
                        return int(year_match.group())
                    
                    # 2. 尝试解析日期字符串
                    try:
                        dt = pd.to_datetime(value_str, errors='raise')
                        return dt.year
                    except:
                        pass
                    
                    # 3. 尝试数值转换
                    numeric = pd.to_numeric(value_str, errors='coerce')
                    if not pd.isna(numeric) and 1000 <= numeric <= 2100:
                        return int(numeric)
                    
                except Exception:
                    pass
                return np.nan
            # 应用年份提取
            df['publish_date'] = df['publish_date'].apply(extract_year)
            # 执行筛选
            before = len(df)
            df = df[df['publish_date'] >= min_year]
            after = len(df)
            print(f"[清洗] 年份筛选(≥{min_year})：{before} → {after} (-{before-after})")
        if 'journal' in df.columns and df.shape[0] > 0:
            if target_journals:
                target_df = df[df['journal'].isin(target_journals)]
                print(f"[清洗] 指定期刊筛选：{len(target_df)}条记录")
            else:
                top_journals = df['journal'].value_counts().head(top_n).index.tolist()
                target_df = df[df['journal'].isin(top_journals)]
                print(f"[清洗] Top-{top_n}期刊筛选：{len(target_df)}条记录")
        else:
            target_df = df
        
        # 保存清洗后的数据（直接保存到 data 目录）
        root_dir = Path(__file__).parent
        data_dir = root_dir / "data"
        data_dir.mkdir(parents=True, exist_ok=True)
        
        all_data_path = data_dir / "alldata_cleaned.csv"
        df.to_csv(all_data_path, index=False, encoding='utf-8-sig')
        
        target_data_path = data_dir / "targetdata_cleaned.csv"
        target_df.to_csv(target_data_path, index=False, encoding='utf-8-sig')
        
        print(f"\n[保存] 全量数据：{all_data_path} (形状：{df.shape})")
        print(f"[保存] 目标期刊数据：{target_data_path} (形状：{target_df.shape})")
        print("\n" + "=" * 70)
        print("清洗完成！输出字段已对齐Java端标准字段")
        print("=" * 70)
        
        return df, all_data_path, target_data_path

    except Exception as e:
        print(f"\n[错误] 清洗失败：{str(e)}")
        import traceback
        traceback.print_exc()
        return None, None, None


class WOSCleanService:
    """WOS 数据清洗服务类，用作其他模块调用的接口。"""

    def __init__(self, clean_config_path: str | None = None):
        self.clean_config_path = clean_config_path
        try:
            self.clean_config = load_clean_config(clean_config_path)
        except Exception:
            self.clean_config = None

    def run(self, write_back: bool = True):
        """执行完整清洗流程，并按需写回数据库。"""
        df, all_path, target_path = run_clean(self.clean_config_path)

        if not write_back or df is None:
            return df, all_path, target_path

        clean_config = self.clean_config
        if clean_config is None:
            try:
                clean_config = load_clean_config(self.clean_config_path)
            except Exception:
                clean_config = None

        if clean_config and 'write_back' in clean_config:
            wb_conf = clean_config.get('write_back', {})
            if wb_conf.get('enabled', False):
                if 'id' in df.columns:
                    df = df.drop(columns=['id'])
                saved = save_cleaned_to_db(df, wb_conf)
                if not saved:
                    print("[写回] 写回数据库失败，请检查配置与数据库连接")

        return df, all_path, target_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='WOS数据清洗工具')
    parser.add_argument('--config', '-c', help='清洗配置文件路径', default=None)
    args = parser.parse_args()

    service = WOSCleanService(args.config)
    service.run(write_back=True)
