# -*- coding: utf-8 -*-
"""
main.py - 用户数据分析主入口

支持两种运行模式：
1. 用户模式：基于用户上传目录 (uploads/{username}/) 进行分析
2. 全量模式：执行完整的 01/02/03 流水线

用法：
    python main.py --user <username>        # 分析指定用户的数据
    python main.py --user-dir <dir_path>    # 分析指定目录的数据
    python main.py --pipeline               # 执行完整流水线（01/02/03）
"""

from __future__ import annotations

import argparse
import subprocess
import sys
import glob
import json
import os
from pathlib import Path
import re
import ast

import pandas as pd

# 全局变量：是否为 JSON 模式（日志输出到 stderr）
_json_mode = False

def log(msg: str):
    """日志输出函数：JSON模式输出到stderr，否则输出到stdout"""
    if _json_mode:
        print(msg, file=sys.stderr)
    else:
        print(msg)


def analyze_user_data(user_dir: Path, output_dir: Path = None) -> dict:
    """
    分析用户目录下的所有CSV文件
    
    Args:
        user_dir: 用户数据目录路径
        output_dir: 输出目录路径（默认为 user_dir/outputs）
    
    Returns:
        分析结果字典
    """
    if not user_dir.exists():
        return {"success": False, "message": f"Directory not found: {user_dir}"}
    
    # 设置输出目录
    if output_dir is None:
        output_dir = user_dir / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 收集所有CSV文件
    csv_files = list(user_dir.glob("*.csv"))
    if not csv_files:
        return {"success": False, "message": "No CSV files in directory"}
    
    # 合并所有CSV数据
    dfs = []
    processed_files = []
    for csv_file in csv_files:
        try:
            # 尝试多种编码
            for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk"):
                try:
                    df = pd.read_csv(csv_file, encoding=enc)
                    dfs.append(df)
                    processed_files.append(csv_file.name)
                    log(f"[OK] {csv_file.name} ({len(df)} records, encoding: {enc})")
                    break
                except UnicodeDecodeError:
                    continue
        except Exception as e:
            log(f"[FAIL] {csv_file.name}: {e}")
    
    if not dfs:
        return {"success": False, "message": "Failed to read any CSV files"}
    
    # 合并数据
    combined_df = pd.concat(dfs, ignore_index=True)
    log(f"\n[Merged] {len(combined_df)} records from {len(processed_files)} files")
    
    # 执行分析（传入输出目录）
    result = perform_analysis(combined_df, output_dir)
    result["processed_files"] = processed_files
    result["total_files"] = len(processed_files)
    result["output_dir"] = str(output_dir)
    result["success"] = True
    
    # 将结果写入文件，供 Java 读取
    result_file = output_dir / "analysis_result.json"
    try:
        with open(result_file, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        result["result_file"] = str(result_file)
        log(f"\n[Saved] {result_file}")
    except Exception as e:
        log(f"[WARN] Failed to save result: {e}")
    
    return result


def perform_analysis(df: pd.DataFrame, output_dir: Path = None) -> dict:
    """
    执行数据分析
    
    Args:
        df: 合并后的DataFrame
        output_dir: 输出目录（用于保存各指标的结果文件）
    
    Returns:
        分析结果
    """
    result = {
        "total_records": len(df),
        "columns": list(df.columns),
    }

    # =====================
    # 关键预处理：剔除“嵌入式表头行”
    # =====================
    # 某些数据集在导出/拼接过程中会把表头再次写入数据区，表现为：
    # doi=DOI-DOI, journal=Source-xxx, publish_date=Year-xx, title=Title-xxx, abstract=Summary-xxx 等。
    # 这些行会污染 journal 统计，导致 TOP 期刊出现乱码/识别不全。
    def _drop_embedded_header_rows(input_df: pd.DataFrame) -> tuple[pd.DataFrame, int]:
        if input_df.empty:
            return input_df, 0

        df2 = input_df.copy()
        # 统一处理：把参与判断的列转成字符串并 strip
        def _norm_series(col: str) -> pd.Series:
            if col not in df2.columns:
                return pd.Series(["" for _ in range(len(df2))], index=df2.index)
            s = df2[col]
            if not pd.api.types.is_string_dtype(s):
                s = s.astype(str)
            return s.fillna("").astype(str).str.strip()

        doi = _norm_series("doi")
        journal = _norm_series("journal")
        publish_date = _norm_series("publish_date")
        title = _norm_series("title")
        abstract = _norm_series("abstract")
        keywords = _norm_series("keywords")

        # 强信号：doi 字段直接等于 DOI-DOI（大小写不敏感）
        sig_doi = doi.str.upper().eq("DOI-DOI")
        # 其他信号：常见“列名-中文/乱码”形态
        sig_journal = journal.str.lower().str.startswith("source-") | journal.str.contains("文献来源", na=False)
        sig_year = publish_date.str.lower().str.startswith("year-")
        sig_title = title.str.lower().str.startswith("title-")
        sig_abs = abstract.str.lower().str.startswith("summary-")
        sig_kw = keywords.str.contains("keyword-", case=False, na=False)

        # 多信号合并：命中 >=2 基本可确定是嵌入式表头行
        score = (
            sig_doi.astype(int)
            + sig_journal.astype(int)
            + sig_year.astype(int)
            + sig_title.astype(int)
            + sig_abs.astype(int)
            + sig_kw.astype(int)
        )
        drop_mask = sig_doi | (score >= 2)

        dropped = int(drop_mask.sum())
        if dropped > 0:
            df2 = df2.loc[~drop_mask].copy()
        return df2, dropped

    df, dropped_header_rows = _drop_embedded_header_rows(df)
    if dropped_header_rows > 0:
        result["dropped_embedded_header_rows"] = dropped_header_rows
        log(f"[Prep] Dropped embedded header-like rows: {dropped_header_rows}")
        # 更新基础信息
        result["total_records"] = len(df)

    # =====================
    # 关键预处理：生成 / 补齐 citing
    # =====================
    # 多个指标模块依赖 citing 列。
    # 注意：用户上传的 CSV 可能“带了 citing 列但全是 []/空串”，尤其中文期刊会出现
    # citing 全空 -> 引用网络无法构建 -> 颠覆性等指标大面积为 0。
    # 因此这里不仅在缺列时生成，也会对“citing 为空且 citations 有内容”的行进行补齐。

    def _to_list(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return []
        if isinstance(val, (list, tuple, set)):
            return list(val)
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return []
            # 常见空列表字符串
            if s in ("[]", "[ ]"):
                return []
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = ast.literal_eval(s)
                    if isinstance(parsed, (list, tuple, set)):
                        return list(parsed)
                except Exception:
                    pass
            # 不可解析则按单条处理（后续模块会进一步做 token 化与过滤）
            return [val]
        return []

    def _is_nonblank_text(x) -> bool:
        if x is None:
            return False
        if isinstance(x, float) and pd.isna(x):
            return False
        return str(x).strip() != ""

    if "citations" in df.columns:
        try:
            from translate_keywords_02 import extract_dois_from_references

            if "citing" not in df.columns:
                log("[Prep] Generating citing from citations (missing column)...")
                if "category" in df.columns:
                    df["citing"] = df.apply(
                        lambda r: extract_dois_from_references(r.get("citations"), r.get("category")),
                        axis=1,
                    )
                else:
                    df["citing"] = df["citations"].apply(extract_dois_from_references)
                result["citing_generated_mode"] = "created"
            else:
                # 只对空 citing 的行补齐（不覆盖已有非空数据）
                citing_lens = df["citing"].apply(lambda x: len(_to_list(x)))
                empty_citing = citing_lens.eq(0)
                has_citations = df["citations"].apply(_is_nonblank_text)
                refill_mask = empty_citing & has_citations
                refill_rows = int(refill_mask.sum())
                if refill_rows > 0:
                    log(f"[Prep] Refilling empty citing from citations... rows: {refill_rows}")
                    if "category" in df.columns:
                        df.loc[refill_mask, "citing"] = df.loc[refill_mask].apply(
                            lambda r: extract_dois_from_references(r.get("citations"), r.get("category")),
                            axis=1,
                        )
                    else:
                        df.loc[refill_mask, "citing"] = df.loc[refill_mask, "citations"].apply(extract_dois_from_references)
                    result["citing_generated_mode"] = "refilled_empty"
                    result["citing_refilled_rows"] = refill_rows
                else:
                    result["citing_generated_mode"] = "kept"

            # 统计：citing 总条目数 + 非空论文比例（按期刊名是否含中文粗分，避免依赖 category 列）
            try:
                citing_lens2 = df["citing"].apply(lambda x: len(_to_list(x)))
                result["citing_nonempty_rate"] = round(float((citing_lens2 > 0).mean()), 4)
                result["citing_total_items"] = int(citing_lens2.sum())

                if "journal" in df.columns:
                    j = df["journal"].astype(str)
                    is_cn_journal = j.str.contains(r"[\u4e00-\u9fff]", regex=True, na=False)
                    cn_total = int(is_cn_journal.sum())
                    if cn_total > 0:
                        result["citing_nonempty_rate_cn_journal"] = round(float((citing_lens2[is_cn_journal] > 0).mean()), 4)
                    noncn_total = int((~is_cn_journal).sum())
                    if noncn_total > 0:
                        result["citing_nonempty_rate_noncn_journal"] = round(float((citing_lens2[~is_cn_journal] > 0).mean()), 4)
            except Exception:
                pass

        except Exception as e:
            # 兜底：保证列存在，不阻塞后续指标
            result["citing_generated_mode"] = "failed"
            result["citing_error"] = str(e)
            if "citing" not in df.columns:
                df["citing"] = [[] for _ in range(len(df))]
            log(f"[WARN] Failed to generate/refill citing, keep existing or fallback empty: {e}")
    else:
        if "citing" not in df.columns:
            df["citing"] = [[] for _ in range(len(df))]
        result["citing_generated_mode"] = "missing_citations"
        result["citing_error"] = "Missing citations column; cannot generate citing"

    # =====================
    # 为跨学科性：把 citing（可能是中文题名/DOI混合）尽量解析成“样本内 paper_id”
    # =====================
    # disrupt_calculator_031 支持 title token 入网；但 interdisciplinary_032 只会把 refs 当作“样本内论文 id”，
    # 如果 citing 是中文题名，就无法匹配到 paper_categories（以 paper_id 为 key），会导致大量 td_score=0。
    # 这里做一层解析：
    # - 给每篇论文生成 paper_id（优先 DOI，否则 row_{idx}）
    # - 建立 doi_norm->paper_id、title_norm->paper_id 的索引
    # - 把 citing 中的条目尽量解析/匹配成 paper_id，落到 citing_td 列（供跨学科性使用）

    def _is_blank(x) -> bool:
        if x is None:
            return True
        if isinstance(x, float) and pd.isna(x):
            return True
        return str(x).strip() == ""

    def _norm_doi(s: str) -> str:
        if not s:
            return ""
        t = str(s).strip()
        if not t:
            return ""
        low = t.lower()
        for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
            if low.startswith(prefix):
                t = t[len(prefix):]
                break
        if t.lower().startswith("doi:"):
            t = t.split(":", 1)[1]
        t = t.strip().rstrip(".。;；,，)]}\"' ")
        return t.lower()

    def _extract_doi_from_text(s: str) -> str:
        if not s:
            return ""
        m = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", str(s), re.IGNORECASE)
        return m.group(0) if m else ""

    def _norm_title(s: str) -> str:
        if not isinstance(s, str):
            return ""
        t = s.strip()
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
             .replace("【", "[")
             .replace("】", "]")
             .replace("“", '"')
             .replace("”", '"')
             .replace("‘", "'")
             .replace("’", "'")
        )
        t = t.strip(" \t\r\n\"'《》<>[](){}")
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _to_list(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return []
        if isinstance(val, (list, tuple, set)):
            return list(val)
        if isinstance(val, str):
            s = val.strip()
            if not s:
                return []
            # Python list literal
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, (list, tuple, set)):
                    return list(parsed)
            except Exception:
                pass
            # JSON list
            if s.startswith("[") and s.endswith("]"):
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        return parsed
                except Exception:
                    pass
            return [s]
        return [val]

    # 生成 paper_id
    if "paper_id" not in df.columns:
        doi_series = df["doi"] if "doi" in df.columns else pd.Series([None] * len(df))
        paper_ids = []
        for i, v in enumerate(doi_series.tolist()):
            if _is_blank(v):
                paper_ids.append(f"row_{i}")
            else:
                paper_ids.append(str(v).strip())
        df["paper_id"] = paper_ids

    doi_to_pid = {}
    if "doi" in df.columns:
        for pid, doi in zip(df["paper_id"].tolist(), df["doi"].tolist()):
            if _is_blank(doi):
                continue
            dn = _norm_doi(str(doi))
            if dn and dn not in doi_to_pid:
                doi_to_pid[dn] = str(pid)

    title_to_pid = {}
    if "title" in df.columns:
        for pid, title in zip(df["paper_id"].tolist(), df["title"].tolist()):
            if _is_blank(title):
                continue
            tn = _norm_title(str(title))
            if tn and tn not in title_to_pid:
                title_to_pid[tn] = str(pid)

    def _resolve_refs_to_paper_ids(refs_val):
        items = _to_list(refs_val)
        out = []
        seen = set()
        for x in items:
            if _is_blank(x):
                continue
            s = str(x).strip()
            if not s:
                continue

            doi_guess = _extract_doi_from_text(s)
            if doi_guess:
                dn = _norm_doi(doi_guess)
                pid = doi_to_pid.get(dn)
                if pid and pid not in seen:
                    seen.add(pid)
                    out.append(pid)
                continue

            # 直接是 DOI 形态
            if s.startswith("10.") and len(s) > 10:
                dn = _norm_doi(s)
                pid = doi_to_pid.get(dn)
                if pid and pid not in seen:
                    seen.add(pid)
                    out.append(pid)
                continue

            # 尝试按题名匹配
            tn = _norm_title(s)
            pid = title_to_pid.get(tn)
            if pid and pid not in seen:
                seen.add(pid)
                out.append(pid)
        return out

    df["citing_td"] = df["citing"].apply(_resolve_refs_to_paper_ids) if "citing" in df.columns else [[] for _ in range(len(df))]

    try:
        td_nonempty = int(df["citing_td"].apply(lambda x: len(x) if isinstance(x, (list, tuple)) else 0).gt(0).sum())
        result["citing_td_nonempty_papers"] = td_nonempty
        result["citing_td_nonempty_rate"] = round(td_nonempty / max(1, len(df)), 4)

        if "category" in df.columns:
            cat = df["category"].fillna("").astype(str).str.strip().str.lower()
            is_cn = cat.eq("chinese")
            cn_total = int(is_cn.sum())
            if cn_total > 0:
                cn_nonempty = int(df.loc[is_cn, "citing_td"].apply(lambda x: len(x) if isinstance(x, (list, tuple)) else 0).gt(0).sum())
                result["citing_td_nonempty_rate_chinese"] = round(cn_nonempty / max(1, cn_total), 4)
            en_total = int(cat.eq("english").sum())
            if en_total > 0:
                en_nonempty = int(df.loc[cat.eq("english"), "citing_td"].apply(lambda x: len(x) if isinstance(x, (list, tuple)) else 0).gt(0).sum())
                result["citing_td_nonempty_rate_english"] = round(en_nonempty / max(1, en_total), 4)
    except Exception:
        pass
    
    # 基础统计
    if "journal" in df.columns:
        journal_counts = df["journal"].value_counts()
        result["journal_count"] = len(journal_counts)
        result["top_journals"] = journal_counts.head(10).to_dict()
    
    if "keywords" in df.columns:
        # 统计关键词
        result["has_keywords"] = int(df["keywords"].notna().sum())
    
    if "publish_date" in df.columns or "year" in df.columns:
        year_col = "year" if "year" in df.columns else "publish_date"
        try:
            years = pd.to_numeric(df[year_col], errors="coerce").dropna()
            if len(years) > 0:
                result["year_range"] = {
                    "min": int(years.min()),
                    "max": int(years.max())
                }
        except Exception:
            pass
    
    if "citations" in df.columns:
        try:
            # 尝试提取引用数量
            result["has_citations"] = int(df["citations"].notna().sum())
        except Exception:
            pass

    # =====================
    # 小样本期刊：在计算各指标前剔除，但保留名单用于最终展示备注
    # =====================
    # 规则：同一期刊在当前数据集中论文数 < 5
    # 说明：不影响“论文总数/期刊分布统计”；仅影响五大指标的计算口径。
    small_sample_threshold = 5
    df_metrics = df
    try:
        if "journal" in df.columns:
            journals = df["journal"].fillna("").astype(str).str.strip()
            counts = journals.value_counts(dropna=False)
            small = counts[(counts > 0) & (counts < small_sample_threshold)]

            result["small_sample_threshold"] = small_sample_threshold
            result["small_sample_journal_count"] = int(len(small))
            # 注意：列表可能较大，但这是用户明确要求“最终期刊列表要能看到并备注”。
            result["small_sample_journals"] = [
                {
                    "journal": str(j),
                    "paper_count": int(c),
                    "note": "论文数量过少，不具有代表性",
                }
                for j, c in small.items()
            ]

            # 写出 CSV，方便前端/Java 直接读取（并支持下载 zip）
            if output_dir is not None:
                small_sample_file = output_dir / "small_sample_journals.csv"
                pd.DataFrame(result["small_sample_journals"]).to_csv(
                    small_sample_file,
                    index=False,
                    encoding="utf-8-sig",
                )
                result["small_sample_file"] = str(small_sample_file)

            # 用于指标计算的过滤数据集
            keep_mask = journals.map(counts).fillna(0).astype(int) >= small_sample_threshold
            df_metrics = df.loc[keep_mask].copy()
            result["metrics_records"] = int(len(df_metrics))
            if len(small) > 0:
                log(f"[Prep] Small-sample journals (<{small_sample_threshold}) excluded from metrics: {len(small)}")
                log(f"[Prep] Records used for metrics: {len(df_metrics)}")
    except Exception as e:
        # 不阻塞后续指标计算
        result["small_sample_error"] = str(e)
        df_metrics = df
    
    # 尝试调用指标计算模块（如果可用）
    try:
        from disrupt_calculator_031 import analyze_disruption
        from interdisciplinary_032 import analyze_interdisciplinary
        from novelty_analyzer_033 import analyze_journal_novelty
        from topic_analyzer_036 import analyze_topic_entropy
        from theme_034 import ThemeHotnessAnalyzer
        
        log("\n[Metrics Calculation]")

        # =====================
        # 关键词前置处理（用户上传分析不会自动跑 02 translate_keywords_02.py）
        # - 统一选择关键词源列（优先 keywords_alt1）
        # - 可选翻译（默认 glossary，仅词表；也可 baidu）
        # - novelty/topic 等关键词相关指标统一使用同一列
        # =====================
        translate_mode_global = os.getenv("PM_KEYWORD_TRANSLATE_MODE", "glossary").strip().lower()
        result["keyword_translate_mode"] = translate_mode_global

        def _has_chinese(text: str) -> bool:
            return bool(re.search(r"[\u4e00-\u9fff]", text or ""))

        def _choose_keyword_source_col(df0: pd.DataFrame) -> str | None:
            for c in [
                "keywords_alt1",
                "keywords",
                "keywords_alt",
                "author_keywords",
                "Author Keywords",
                "DE",
            ]:
                if c in df0.columns:
                    return c
            return None

        def _load_plain_glossary() -> dict:
            try:
                p = Path(__file__).resolve().parent / "keyword_glossary_clean.json"
                if p.exists():
                    with open(p, "r", encoding="utf-8") as f:
                        data = json.load(f)
                    return data if isinstance(data, dict) else {}
            except Exception:
                return {}
            return {}

        def _parse_kw_list(val) -> list[str]:
            if val is None or (isinstance(val, float) and pd.isna(val)):
                return []
            if isinstance(val, (list, tuple, set)):
                items = list(val)
            else:
                s = str(val).strip()
                if not s or s.lower() in {"nan", "none", "null"}:
                    return []
                items = None
                try:
                    parsed = json.loads(s)
                    if isinstance(parsed, list):
                        items = parsed
                    elif isinstance(parsed, str):
                        s = parsed.strip()
                except Exception:
                    pass
                if items is None and s.startswith("[") and s.endswith("]"):
                    try:
                        parsed = ast.literal_eval(s)
                        if isinstance(parsed, (list, tuple, set)):
                            items = list(parsed)
                    except Exception:
                        items = None
                if items is None:
                    items = re.split(r"[;,\|/、；，]", s)

            out: list[str] = []
            for x in items or []:
                if x is None:
                    continue
                t = str(x).strip()
                if not t:
                    continue
                t = t.strip().lstrip("[").rstrip("]").strip().strip("\"'").strip()
                if not t or t in {"[]", "[ ]"}:
                    continue
                out.append(t)

            seen = set()
            uniq: list[str] = []
            for x in out:
                if x not in seen:
                    seen.add(x)
                    uniq.append(x)
            return uniq

        # 为 novelty/topic 构建统一关键词列
        df_metrics_for_kw = df_metrics
        metrics_kw_col = "keywords"
        try:
            src_kw_col = _choose_keyword_source_col(df_metrics)
            if src_kw_col is not None:
                glossary = _load_plain_glossary()

                translator = None
                if translate_mode_global == "baidu":
                    try:
                        from baidu_translator_021 import NewBaiduTranslator  # type: ignore

                        translator = NewBaiduTranslator(
                            glossary_file=str(Path(__file__).resolve().parent / "translation_glossary.json")
                        )
                    except Exception:
                        translator = None

                def _translate_items(items: list[str]) -> list[str]:
                    out: list[str] = []
                    for kw in items:
                        k = ("" if kw is None else str(kw)).strip()
                        if not k:
                            continue
                        if k in glossary:
                            v = glossary.get(k)
                            if isinstance(v, str) and v.strip():
                                out.append(v.strip())
                                continue
                        if translate_mode_global == "baidu" and translator is not None and _has_chinese(k):
                            try:
                                v = translator.translate(k, from_lang="zh", to_lang="en", add_to_glossary=True)
                                v = ("" if v is None else str(v)).strip()
                                if v:
                                    out.append(v)
                                    continue
                            except Exception:
                                pass
                        out.append(k)

                    seen = set()
                    uniq: list[str] = []
                    for x in out:
                        if x not in seen:
                            seen.add(x)
                            uniq.append(x)
                    return uniq

                metrics_kw_col = "metrics_keywords"
                df_metrics_for_kw = df_metrics.copy()
                df_metrics_for_kw[metrics_kw_col] = df_metrics_for_kw[src_kw_col].apply(lambda v: _translate_items(_parse_kw_list(v)))
                result["metrics_keyword_source_col"] = src_kw_col
                result["metrics_keyword_col"] = metrics_kw_col
        except Exception as _e:
            result["metrics_keyword_error"] = str(_e)
            df_metrics_for_kw = df_metrics
            metrics_kw_col = "keywords"
        
        # 创建输出子目录
        if output_dir:
            disrupt_out = output_dir / "disrupt"
            inter_out = output_dir / "interdisciplinary"
            novelty_out = output_dir / "novelty"
            topic_out = output_dir / "topic"
            theme_out = output_dir / "theme"
            for d in [disrupt_out, inter_out, novelty_out, topic_out, theme_out]:
                d.mkdir(parents=True, exist_ok=True)
        
        try:
            log("  Calculating disruption index...")
            disrupt_cfg = None
            try:
                # 优先使用样本内引用（citing_td），能显著降低中英文引用表示差异导致的偏置。
                if "citing_td" in df_metrics.columns:
                    td_nonempty_rate = float(
                        df_metrics["citing_td"].apply(lambda x: isinstance(x, (list, tuple)) and len(x) > 0).mean()
                    )
                    # 有一定比例的样本内引用才启用，否则回退到原 citing。
                    if td_nonempty_rate >= 0.05:
                        import copy
                        from disrupt_calculator_031 import disrupt_config as _disrupt_config

                        disrupt_cfg = copy.deepcopy(_disrupt_config)
                        disrupt_cfg.setdefault("columns", {})["citing"] = "citing_td"
                        result["disruption_citing_source"] = "citing_td"
                        result["disruption_citing_td_nonempty_rate"] = round(td_nonempty_rate, 4)
                    else:
                        result["disruption_citing_source"] = "citing"
                        result["disruption_citing_td_nonempty_rate"] = round(td_nonempty_rate, 4)
                else:
                    result["disruption_citing_source"] = "citing"
            except Exception as _e:
                # 不影响主流程
                result["disruption_citing_source"] = "citing"

            disrupt_df = analyze_disruption(df_metrics, config=disrupt_cfg)
            result["disruption"] = disrupt_df.head(10).to_dict(orient="records")
            if output_dir:
                disrupt_df.to_csv(disrupt_out / "disruption.csv", index=False, encoding="utf-8-sig")
                result["disruption_file"] = str(disrupt_out / "disruption.csv")
        except Exception as e:
            log(f"  Disruption index failed: {e}")
        
        try:
            log("  Calculating interdisciplinarity...")
            inter_df = analyze_interdisciplinary(df_metrics)
            result["interdisciplinary"] = inter_df.head(10).to_dict(orient="records")
            if output_dir:
                inter_df.to_csv(inter_out / "interdisciplinary.csv", index=False, encoding="utf-8-sig")
                result["interdisciplinary_file"] = str(inter_out / "interdisciplinary.csv")
        except Exception as e:
            log(f"  Interdisciplinarity failed: {e}")
        
        try:
            log("  Calculating novelty...")
            novelty_df = analyze_journal_novelty(df_metrics_for_kw, keywords_col=metrics_kw_col)
            result["novelty"] = novelty_df.head(10).to_dict(orient="records")

            # 诊断：中英文期刊（以期刊名是否含中文粗分）在 percent_score 上是否出现系统性偏高/偏低
            try:
                if not novelty_df.empty and "journal" in novelty_df.columns:
                    j = novelty_df["journal"].astype(str)
                    cn_mask = j.str.contains(r"[\u4e00-\u9fff]", regex=True, na=False)
                    stats = {
                        "journals_total": int(len(novelty_df)),
                        "cn_journals": int(cn_mask.sum()),
                        "non_cn_journals": int((~cn_mask).sum()),
                    }
                    if "percent_score" in novelty_df.columns:
                        if int(cn_mask.sum()) > 0:
                            stats["cn_percent_score_mean"] = round(float(novelty_df.loc[cn_mask, "percent_score"].mean()), 4)
                        if int((~cn_mask).sum()) > 0:
                            stats["non_cn_percent_score_mean"] = round(float(novelty_df.loc[~cn_mask, "percent_score"].mean()), 4)
                    if "percent_score_raw" in novelty_df.columns:
                        if int(cn_mask.sum()) > 0:
                            stats["cn_percent_score_raw_mean"] = round(float(novelty_df.loc[cn_mask, "percent_score_raw"].mean()), 4)
                        if int((~cn_mask).sum()) > 0:
                            stats["non_cn_percent_score_raw_mean"] = round(float(novelty_df.loc[~cn_mask, "percent_score_raw"].mean()), 4)
                    if "novelty_z_lang" in novelty_df.columns:
                        if int(cn_mask.sum()) > 0:
                            stats["cn_novelty_z_lang_mean"] = round(float(novelty_df.loc[cn_mask, "novelty_z_lang"].mean()), 6)
                        if int((~cn_mask).sum()) > 0:
                            stats["non_cn_novelty_z_lang_mean"] = round(float(novelty_df.loc[~cn_mask, "novelty_z_lang"].mean()), 6)
                    result["novelty_lang_stats"] = stats
            except Exception:
                pass
            if output_dir:
                novelty_df.to_csv(novelty_out / "novelty.csv", index=False, encoding="utf-8-sig")
                result["novelty_file"] = str(novelty_out / "novelty.csv")
        except Exception as e:
            log(f"  Novelty failed: {e}")
        
        try:
            log("  Calculating topic complexity...")
            topic_df = analyze_topic_entropy(df_metrics_for_kw, keywords_col=metrics_kw_col)
            result["topic"] = topic_df.head(10).to_dict(orient="records")
            if output_dir:
                topic_df.to_csv(topic_out / "topic.csv", index=False)
                result["topic_file"] = str(topic_out / "topic.csv")
        except Exception as e:
            log(f"  Topic complexity failed: {e}")
        
        try:
            log("  Calculating theme hotness...")

            def _has_chinese(text: str) -> bool:
                return bool(re.search(r"[\u4e00-\u9fff]", text or ""))

            def _load_plain_glossary() -> dict:
                # 纯中文 -> 英文 的“清理后词表”
                try:
                    p = Path(__file__).resolve().parent / "keyword_glossary_clean.json"
                    if p.exists():
                        with open(p, "r", encoding="utf-8") as f:
                            data = json.load(f)
                        return data if isinstance(data, dict) else {}
                except Exception:
                    return {}
                return {}

            def _parse_kw_list(val) -> list[str]:
                if val is None or (isinstance(val, float) and pd.isna(val)):
                    return []
                if isinstance(val, (list, tuple, set)):
                    items = list(val)
                else:
                    s = str(val).strip()
                    if not s or s.lower() in {"nan", "none", "null"}:
                        return []
                    items = None
                    try:
                        parsed = json.loads(s)
                        if isinstance(parsed, list):
                            items = parsed
                        elif isinstance(parsed, str):
                            s = parsed.strip()
                    except Exception:
                        pass
                    if items is None and s.startswith("[") and s.endswith("]"):
                        try:
                            parsed = ast.literal_eval(s)
                            if isinstance(parsed, (list, tuple, set)):
                                items = list(parsed)
                        except Exception:
                            items = None
                    if items is None:
                        items = re.split(r"[;,\|/、；，]", s)
                out: list[str] = []
                for x in items or []:
                    if x is None:
                        continue
                    t = str(x).strip()
                    if not t:
                        continue
                    t = t.strip().lstrip("[").rstrip("]").strip().strip("\"'").strip()
                    if not t or t in {"[]", "[ ]"}:
                        continue
                    out.append(t)
                return out

            def _translate_keywords_series_to_en(s: pd.Series, *, mode: str) -> tuple[pd.Series, dict]:
                mode_norm = (mode or "").strip().lower()
                if mode_norm not in {"glossary", "baidu"}:
                    return s, {"mode": mode_norm, "enabled": False}

                glossary = _load_plain_glossary()
                translator = None
                baidu_calls = 0
                if mode_norm == "baidu":
                    try:
                        from baidu_translator_021 import NewBaiduTranslator  # type: ignore

                        translator = NewBaiduTranslator(
                            glossary_file=str(Path(__file__).resolve().parent / "translation_glossary.json")
                        )
                    except Exception as _e:
                        translator = None

                cache: dict[str, str] = {}
                glossary_hits = 0
                kept_cn = 0
                translated = 0

                def _translate_list(items: list[str]) -> list[str]:
                    nonlocal baidu_calls, glossary_hits, kept_cn, translated
                    out: list[str] = []
                    for kw in items:
                        k = ("" if kw is None else str(kw)).strip()
                        if not k:
                            continue
                        # 命中词表（纯中文 -> 英文）
                        if k in glossary:
                            v = glossary.get(k)
                            if isinstance(v, str) and v.strip():
                                out.append(v.strip())
                                glossary_hits += 1
                                translated += 1
                                continue
                        # 非中文：直接保留
                        if not _has_chinese(k):
                            out.append(k)
                            continue
                        # 中文：可选百度翻译，否则保留原文
                        if translator is None:
                            out.append(k)
                            kept_cn += 1
                            continue

                        if k in cache:
                            out.append(cache[k])
                            translated += 1
                            continue
                        try:
                            v = translator.translate(k, from_lang="zh", to_lang="en", add_to_glossary=True)
                            baidu_calls += 1
                            v = ("" if v is None else str(v)).strip()
                            if v:
                                cache[k] = v
                                out.append(v)
                                translated += 1
                            else:
                                out.append(k)
                                kept_cn += 1
                        except Exception:
                            out.append(k)
                            kept_cn += 1

                    # 去重保序
                    seen = set()
                    uniq: list[str] = []
                    for x in out:
                        if x not in seen:
                            seen.add(x)
                            uniq.append(x)
                    return uniq

                translated_series = s.apply(lambda v: _translate_list(_parse_kw_list(v)))
                meta = {
                    "mode": mode_norm,
                    "enabled": True,
                    "glossary_path": str(Path(__file__).resolve().parent / "keyword_glossary_clean.json"),
                    "glossary_hits": int(glossary_hits),
                    "baidu_calls": int(baidu_calls),
                    "translated_items": int(translated),
                    "kept_chinese_items": int(kept_cn),
                }
                return translated_series, meta

            # 关键：theme.csv 的 top_keywords_2021~2025 需要基于“用户上传全量数据”统计，
            # 不能使用 df_metrics（它会剔除小样本期刊，导致这些期刊在详情页没有关键词 Top-5）。

            # 关键词翻译说明：
            # - 目前用户模式不会自动跑 02 translate_keywords_02.py；因此 CSV 里若是中文关键词，会原样进入 theme.csv。
            # - 可通过环境变量开启翻译，让落库的 top_keywords 变为英文。
            #   - PM_KEYWORD_TRANSLATE_MODE=glossary  仅用 keyword_glossary_clean.json 查表（快、离线，未命中仍保留中文）
            #   - PM_KEYWORD_TRANSLATE_MODE=baidu     未命中时调用百度翻译（慢、需要联网/额度）
            translate_mode = os.getenv("PM_KEYWORD_TRANSLATE_MODE", "").strip().lower()
            df_for_theme = df
            try:
                if translate_mode in {"glossary", "baidu"}:
                    # 优先用 keywords_alt1（你当前数据集真实关键词在这列），否则退回 keywords
                    src_kw_col = "keywords_alt1" if "keywords_alt1" in df.columns else ("keywords" if "keywords" in df.columns else None)
                    if src_kw_col is not None:
                        dst_kw_col = f"{src_kw_col}_en"
                        df_for_theme = df.copy()
                        df_for_theme[dst_kw_col], meta = _translate_keywords_series_to_en(df_for_theme[src_kw_col], mode=translate_mode)
                        result["theme_keyword_translation"] = {
                            **meta,
                            "source_col": src_kw_col,
                            "target_col": dst_kw_col,
                        }
                        theme_analyzer = ThemeHotnessAnalyzer(df_for_theme, keyword_col=dst_kw_col)
                    else:
                        theme_analyzer = ThemeHotnessAnalyzer(df_for_theme)
                else:
                    theme_analyzer = ThemeHotnessAnalyzer(df_for_theme)
            except Exception as _e:
                result["theme_keyword_translation_error"] = str(_e)
                theme_analyzer = ThemeHotnessAnalyzer(df)

            theme_df = theme_analyzer.run(top_n=None)
            # analysis_result.json 仅保留 Top10 预览，避免文件过大
            result["theme"] = theme_df.head(10).to_dict(orient="records")
            if "has_data" in theme_df.columns:
                try:
                    result["theme_has_data_journals"] = int((theme_df["has_data"] == True).sum())
                except Exception:
                    pass
            if output_dir:
                theme_df.to_csv(theme_out / "theme.csv", index=False, encoding="utf-8-sig")
                result["theme_file"] = str(theme_out / "theme.csv")

                # ===== Debug: per-journal keyword counts (2021-2025) =====
                # 目的：开发调试时能看到“每个期刊每年的关键词统计(含次数)”，快速定位为什么 top_keywords 为空。
                try:
                    kw_out = output_dir / "keywords"
                    kw_out.mkdir(parents=True, exist_ok=True)

                    kw_counts = theme_analyzer.keyword_counts_long(top_k=20)
                    kw_counts.to_csv(kw_out / "keyword_counts_2021_2025_top20.csv", index=False, encoding="utf-8-sig")

                    # 写出本次 theme 模块实际使用的关键词列名
                    (kw_out / "_keyword_col_used.txt").write_text(
                        f"keyword_col={getattr(theme_analyzer, 'keyword_col', '')}\n",
                        encoding="utf-8",
                    )
                    result["keyword_counts_file"] = str(kw_out / "keyword_counts_2021_2025_top20.csv")
                except Exception as _e:
                    result["keyword_counts_error"] = str(_e)
        except Exception as e:
            log(f"  Theme hotness failed: {e}")
        
    except ImportError as e:
        log(f"[INFO] Metrics modules not found: {e}")
    
    return result


def _run_step(args: list[str], *, cwd: Path, name: str) -> None:
    """运行子脚本"""
    log(f"\n========== RUN {name} ==========")
    log(" ".join(args))
    proc = subprocess.run(args, cwd=str(cwd))
    if proc.returncode != 0:
        raise SystemExit(f"步骤 {name} 失败，退出码: {proc.returncode}")


def run_pipeline(base_dir: Path, clean_config: str, metrics_db_config: str, year: int | None) -> None:
    """执行完整的 01/02/03 流水线"""
    py = sys.executable

    # 01：upload_01.py
    _run_step([py, "upload_01.py"], cwd=base_dir, name="01 upload_01")

    # 02：translate_keywords_02.py
    _run_step([py, "translate_keywords_02.py", "--config", clean_config], cwd=base_dir, name="02 translate_keywords_02")

    # 03：main_03.py
    cmd3 = [py, "main_03.py", "--clean-config", clean_config, "--metrics-db-config", metrics_db_config]
    if year:
        cmd3 += ["--year", str(year)]
    _run_step(cmd3, cwd=base_dir, name="03 main_03")

    log("\n========== ALL DONE ==========")


def main() -> None:
    base_dir = Path(__file__).resolve().parent
    # 项目根目录（uploads在项目根目录下）
    project_root = base_dir.parent.parent.parent.parent

    parser = argparse.ArgumentParser(description="用户数据分析 / 全量流水线")
    
    # 用户模式参数
    parser.add_argument("--user", type=str, help="用户名，分析 uploads/{username}/ 目录下的数据")
    parser.add_argument("--user-dir", type=str, help="直接指定用户数据目录路径")
    
    # 流水线模式参数
    parser.add_argument("--pipeline", action="store_true", help="执行完整的 01/02/03 流水线")
    parser.add_argument(
        "--clean-config",
        default=str(base_dir / "config" / "clean_config.yaml"),
        help="clean_config.yaml 路径（供 02/03 使用）",
    )
    parser.add_argument(
        "--metrics-db-config",
        default=str(base_dir / "config" / "metrics_db.json"),
        help="指标上传数据库配置 JSON（供 03 使用）",
    )
    parser.add_argument("--year", type=int, default=None, help="指标年份（可选）")
    
    # 输出参数
    parser.add_argument("--output", type=str, help="输出结果到JSON文件")
    parser.add_argument("--json", action="store_true", help="以JSON格式输出结果（用于Java调用）")
    
    args = parser.parse_args()

    # 设置 JSON 模式全局变量（日志输出到 stderr）
    global _json_mode
    _json_mode = args.json

    # 模式选择
    if args.user:
        # 用户模式：分析 uploads/{username}/ 目录
        user_dir = project_root / "uploads" / args.user
        log(f"[User Mode] Dir: {user_dir}")
        result = analyze_user_data(user_dir)
        
    elif args.user_dir:
        # 直接指定目录
        user_dir = Path(args.user_dir)
        log(f"[Dir Mode] Dir: {user_dir}")
        result = analyze_user_data(user_dir)
        
    elif args.pipeline:
        # 流水线模式
        log("[Pipeline Mode] Running 01/02/03")
        run_pipeline(base_dir, args.clean_config, args.metrics_db_config, args.year)
        return
        
    else:
        # 默认：显示帮助
        parser.print_help()
        print("\n示例:")
        print("  python main.py --user admin        # 分析 admin 用户的数据")
        print("  python main.py --user-dir ./data   # 分析指定目录")
        print("  python main.py --pipeline          # 执行完整流水线")
        return
    
    # 输出结果
    if args.json:
        # JSON 模式：单行输出，不带缩进，方便 Java 解析
        print(json.dumps(result, ensure_ascii=False))
    elif args.output:
        output_path = Path(args.output)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, indent=2)
        log(f"\n[Output] Saved to: {output_path}")
    else:
        log("\n========== Analysis Result ==========")
        log(f"Success: {result.get('success', False)}")
        log(f"Total records: {result.get('total_records', 0)}")
        log(f"Files processed: {result.get('total_files', 0)}")
        if "journal_count" in result:
            log(f"Journal count: {result['journal_count']}")
        if "year_range" in result:
            log(f"Year range: {result['year_range']['min']} - {result['year_range']['max']}")


if __name__ == "__main__":
    main()
