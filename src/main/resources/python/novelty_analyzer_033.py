# -*- coding: utf-8 -*-
"""
novelty_analyzer.py
期刊新颖性计算（Uzzi et al. 2013）
工程版 / 服务版
保证：target_df 中出现的期刊一定有结果（无值则为 0）
"""

import pandas as pd
import numpy as np
import ast
import json
import re
from pathlib import Path
from itertools import combinations
from collections import defaultdict


def _uniform_rank_to_1_100(values: pd.Series, *, tie_breaker: pd.Series | None = None) -> pd.Series:
    """把任意数值序列按排序位置均匀映射到 1~100（仅调整最终分布，不改算法）。"""
    s = pd.to_numeric(values, errors="coerce")
    mask = s.notna()
    if mask.sum() == 0:
        return pd.Series([np.nan] * len(values), index=values.index, dtype=float)

    sub = pd.DataFrame({"v": s[mask].astype(float)})
    if tie_breaker is not None:
        sub["tie"] = tie_breaker[mask].astype(str)
        sub = sub.sort_values(["v", "tie"], ascending=[False, True])
    else:
        sub = sub.sort_values(["v"], ascending=[False])

    n = len(sub)
    if n == 1:
        score = pd.Series([100.0], index=sub.index, dtype=float)
    else:
        ranks = np.arange(1, n + 1, dtype=float)
        score = 100.0 - (ranks - 1.0) * (99.0 / (n - 1.0))
        score = pd.Series(score, index=sub.index, dtype=float)

    out = pd.Series([np.nan] * len(values), index=values.index, dtype=float)
    out.loc[sub.index] = score
    return out

# =========================
# 工具函数
# =========================
_GLOSSARY_CACHE: dict[str, str] | None = None


def _load_glossary() -> dict[str, str]:
    """加载中文->英文关键词词表（若存在）。

    文件格式：JSON object，key 为中文短语，value 为英文翻译。
    """
    global _GLOSSARY_CACHE
    if _GLOSSARY_CACHE is not None:
        return _GLOSSARY_CACHE

    try:
        p = Path(__file__).parent / "keyword_glossary_clean.json"
        if p.exists():
            with open(p, "r", encoding="utf-8") as f:
                obj = json.load(f)
            if isinstance(obj, dict):
                # 只保留 str->str
                _GLOSSARY_CACHE = {
                    str(k).strip(): str(v).strip()
                    for k, v in obj.items()
                    if isinstance(k, str) and isinstance(v, str) and str(k).strip() and str(v).strip()
                }
            else:
                _GLOSSARY_CACHE = {}
        else:
            _GLOSSARY_CACHE = {}
    except Exception:
        _GLOSSARY_CACHE = {}

    return _GLOSSARY_CACHE


def _has_chinese(s: str) -> bool:
    return bool(re.search(r"[\u4e00-\u9fff]", s or ""))


def _normalize_keyword_text(s: str) -> str:
    """把关键词尽量规范化为稳定的英文 token。

    目标：降低“同一概念不同写法（空格/连字符/大小写/&/复数）”带来的虚假组合增量。
    """
    if not s:
        return ""
    t = str(s).strip()
    if not t:
        return ""

    # 统一引号/全角空格
    t = t.replace("\u3000", " ")
    t = t.replace("“", '"').replace("”", '"').replace("‘", "'").replace("’", "'")

    # 常见连接符统一为空格：information-science -> information science
    t = t.replace("_", " ")
    t = t.replace("-", " ")
    t = t.replace("/", " ")
    t = t.replace("\\", " ")

    # & 统一为 and
    t = re.sub(r"\s*&\s*", " and ", t)

    # 去掉大部分标点（保留字母数字空格）
    t = re.sub(r"[^A-Za-z0-9\s]", " ", t)
    t = re.sub(r"\s+", " ", t).strip().lower()

    if not t:
        return ""

    # 简单复数归一：
    # - humanities -> humanity
    # - words -> word
    # 避免过度误伤：长度<=3 不处理。
    tokens = []
    for w in t.split():
        if len(w) > 3:
            if w.endswith("ies") and len(w) > 4:
                w = w[:-3] + "y"
            elif w.endswith("s") and not w.endswith("ss"):
                w = w[:-1]
        tokens.append(w)
    t = " ".join(tokens).strip()
    return t


def clean_keywords(val):
    """统一清洗关键词"""
    # 检查是否为 None/NaN（处理标量和数组情况）
    if val is None or (isinstance(val, float) and pd.isna(val)):
        return []

    stop_words = {
        'review', 'study', 'analysis', 'method',
        'model', 'approach', 'system', 'research'
    }

    try:
        if isinstance(val, str) and val.startswith('['):
            kws = ast.literal_eval(val)
        elif isinstance(val, (list, set)):
            kws = val
        else:
            kws = str(val).replace(';', ',').split(',')
    except Exception:
        return []

    glossary = _load_glossary()

    out = []
    for k in kws:
        raw = ("" if k is None else str(k)).strip()
        if not raw:
            continue

        # 若包含中文，尝试用词表映射到英文（映射不到则保留原文，后续再归一）
        if _has_chinese(raw):
            mapped = glossary.get(raw)
            if mapped:
                raw = mapped

        norm = _normalize_keyword_text(raw)
        if not norm:
            continue
        if norm in stop_words:
            continue
        if len(norm) <= 1:
            continue
        out.append(norm)

    return sorted(set(out))


def parse_year(val):
    try:
        y = int(float(val))
        return y if 1900 <= y <= 2100 else None
    except Exception:
        return None


# =========================
# 核心函数
# =========================
def analyze_journal_novelty(
    background_df: pd.DataFrame,
    target_df: pd.DataFrame = None,
    top_n: int | None = None,
    journal_col: str = "journal",
    keywords_col: str = "keywords",
    year_col: str = "publish_date",
    percentile_blend_alpha: float = 0.7,
    lang_center_beta: float = 0.6,
    min_group_size_for_centering: int = 30,
    keywords_fallback_cols: list[str] | None = None,
) -> pd.DataFrame:
    """
    期刊新颖性计算（连续值）
    使用分批处理避免内存问题
    """
    if target_df is None:
        target_df = background_df

    # 检查必需列
    if journal_col not in target_df.columns:
        raise ValueError(f"Missing column: {journal_col}")

    all_journals = target_df[journal_col].dropna().astype(str).unique()
    
    # 检查 keywords 列
    if keywords_col not in background_df.columns:
        return pd.DataFrame({
            "journal": all_journals,
            "novelty_score": 0.0,
            "paper_count": 0,
            "percent_score_raw": 0.0,
            "percent_score": 0.0
        })

    if keywords_fallback_cols is None:
        # 常见导出会把可用关键词放在 alt 列
        keywords_fallback_cols = [
            "keywords_alt1",
            "keywords_alt2",
            "keywords_plus",
            "author_keywords",
            "keywords_alt",
        ]

    def _keywords_from_row(row: pd.Series) -> list[str]:
        # 先用主列；如果清洗后不足 2 个关键词，则回退到候选列
        primary = clean_keywords(row.get(keywords_col))
        if len(primary) >= 2:
            return primary
        for c in keywords_fallback_cols:
            if c == keywords_col:
                continue
            if c not in row.index:
                continue
            kws = clean_keywords(row.get(c))
            if len(kws) >= 2:
                return kws
        return primary

    # 构建关键词组合首次出现年份（分批处理）
    pair_first_year = {}
    BATCH_SIZE = 5000
    
    for batch_start in range(0, len(background_df), BATCH_SIZE):
        batch = background_df.iloc[batch_start:batch_start + BATCH_SIZE]
        for _, row in batch.iterrows():
            kws = _keywords_from_row(row)
            # 限制每篇论文的关键词数量，避免组合爆炸
            if len(kws) > 15:
                kws = kws[:15]
            year = parse_year(row.get(year_col))
            if len(kws) < 2 or year is None:
                continue
            for pair in combinations(kws, 2):
                pair = tuple(sorted(pair))
                if pair not in pair_first_year:
                    pair_first_year[pair] = year
                else:
                    pair_first_year[pair] = min(year, pair_first_year[pair])

    # 当前年份
    valid_years = [parse_year(y) for y in background_df[year_col] if parse_year(y) is not None]
    current_year = max(valid_years) if valid_years else 2025

    # 论文级新颖性（分批处理）
    paper_scores = []
    for batch_start in range(0, len(target_df), BATCH_SIZE):
        batch = target_df.iloc[batch_start:batch_start + BATCH_SIZE]
        for _, row in batch.iterrows():
            kws = _keywords_from_row(row)
            if len(kws) > 15:
                kws = kws[:15]
            journal = row.get(journal_col, "Unknown")
            year = parse_year(row.get(year_col))
            if year is None:
                year = current_year
            if len(kws) < 2:
                paper_scores.append((journal, year, 0.0))
                continue

            novelty_sum = 0
            count = 0
            for pair in combinations(kws, 2):
                pair = tuple(sorted(pair))
                first_year = pair_first_year.get(pair)
                if first_year is None:
                    novelty = 1.0
                else:
                    delta = current_year - first_year
                    novelty = 1.0 / (1.0 + delta)
                novelty_sum += novelty
                count += 1
            score = novelty_sum / count if count > 0 else 0.0
            paper_scores.append((journal, year, score))

    paper_df = pd.DataFrame(paper_scores, columns=["journal", "year", "paper_novelty_score"])

    # =====================
    # 去偏置：把论文级分数先映射为“当年分位数”，再做语言组内分位数融合
    # 直觉：不同年份的整体分布、以及中文期刊/英文期刊的关键词表达差异，会让 raw 分数出现系统性偏移。
    # 这里不修改 raw 算法，仅在输出用于排序的 percent_score 上做标准化。
    #
    # pct_global: 同一年内全体论文分位数
    # pct_lang:   同一年内按期刊名是否含中文分组后的分位数
    # pct_blend:  两者加权融合（alpha 越大越偏向全体；越小越强调组内可比）
    # =====================
    a = float(percentile_blend_alpha)
    if not (0.0 <= a <= 1.0):
        a = 0.7

    paper_df["lang_group"] = paper_df["journal"].astype(str).apply(lambda j: "cn" if _has_chinese(j) else "non_cn")
    paper_df["pct_global"] = (
        paper_df.groupby("year")["paper_novelty_score"].rank(method="average", pct=True) * 100.0
    )
    paper_df["pct_lang"] = (
        paper_df.groupby(["year", "lang_group"])["paper_novelty_score"].rank(method="average", pct=True) * 100.0
    )
    paper_df["pct_blend"] = (a * paper_df["pct_global"] + (1.0 - a) * paper_df["pct_lang"]).astype(float)

    # 期刊聚合
    journal_df = (
        paper_df.groupby("journal")
        .agg(
            novelty_score_raw=("paper_novelty_score", "mean"),
            paper_count=("paper_novelty_score", "count"),
            novelty_percentile_blend_raw=("pct_blend", "mean"),
        )
        .reset_index()
    )

    # 补全期刊
    journal_df = pd.DataFrame({"journal": all_journals}).merge(journal_df, on="journal", how="left")
    journal_df["novelty_score_raw"] = journal_df["novelty_score_raw"].fillna(0.0)
    journal_df["novelty_percentile_blend_raw"] = journal_df["novelty_percentile_blend_raw"].fillna(0.0)
    journal_df["paper_count"] = journal_df["paper_count"].fillna(0).astype(int)

    # 兼容旧列名：novelty_score 仍保留 raw 均值
    journal_df["novelty_score"] = journal_df["novelty_score_raw"].astype(float)

    # 百分制映射（raw，按原算法的 0~1 映射到 0~100，仅供诊断/展示）
    journal_df["percent_score_raw"] = (journal_df["novelty_score_raw"] * 100.0).round(2)

    # 期刊级再去偏置（温和版）：按“期刊名是否含中文”分组做均值校正 + 收缩。
    # 目标：避免一组整体偏高/偏低，但也避免 z-score 在小样本组上把分数拉到两极。
    #
    # base:  0~100 的融合分位数均值
    # adj:   全局均值 + (base - 组均值) * beta  （beta < 1 会把极端拉回中间）
    # 小组（组内期刊数太少）不做校正。
    beta = float(lang_center_beta)
    if not (0.0 <= beta <= 1.0):
        beta = 0.6

    journal_df["lang_group"] = journal_df["journal"].astype(str).apply(lambda j: "cn" if _has_chinese(j) else "non_cn")
    journal_df["novelty_percentile_adjusted"] = 0.0
    valid = journal_df["paper_count"].fillna(0).astype(int) > 0
    if valid.any():
        base = journal_df.loc[valid, "novelty_percentile_blend_raw"].astype(float)
        global_mean = float(base.mean())

        sub = journal_df.loc[valid, ["lang_group", "novelty_percentile_blend_raw"]].copy()
        sub["novelty_percentile_blend_raw"] = sub["novelty_percentile_blend_raw"].astype(float)

        group_sizes = sub.groupby("lang_group")["novelty_percentile_blend_raw"].transform("count")
        group_means = sub.groupby("lang_group")["novelty_percentile_blend_raw"].transform("mean")

        # 小样本组：不做组均值校正（避免过拟合）
        group_means = group_means.where(group_sizes >= int(min_group_size_for_centering), other=global_mean)

        adjusted = global_mean + (sub["novelty_percentile_blend_raw"] - group_means) * beta
        adjusted = adjusted.clip(lower=0.0, upper=100.0)
        journal_df.loc[valid, "novelty_percentile_adjusted"] = adjusted.astype(float)

    # percent_score：当校正后的期刊分数几乎没有差异时，不做 1~100 拉伸（会把噪声+字典序放大成两极）。
    journal_df["percent_score"] = 0.0
    if valid.any():
        v_adj = journal_df.loc[valid, "novelty_percentile_adjusted"].astype(float)
        if v_adj.nunique(dropna=True) <= 3 or float(v_adj.std(ddof=0)) < 1e-6:
            journal_df.loc[valid, "percent_score"] = 50.0
        else:
            journal_df.loc[valid, "percent_score"] = _uniform_rank_to_1_100(
                v_adj,
                tie_breaker=journal_df.loc[valid, "journal"],
            ).round(2)

    if isinstance(top_n, int) and top_n > 0:
        journal_df = journal_df.head(top_n)

    return journal_df.reset_index(drop=True)

# =========================
# 本地调试
# =========================
if __name__ == "__main__":
    from pathlib import Path

    base = Path(__file__).parent
    # 优先使用 data 目录下的 CSV
    data_dir = base / "data"
    csv_candidates = [
        data_dir / "alldata_cleaned.csv",
        data_dir / "all_data.csv",
        data_dir / "cleaned_data.csv",
        base / "cleaned_data.csv",
    ]
    csv_path = None
    for p in csv_candidates:
        if p.exists():
            csv_path = p
            break
    if csv_path is None:
        raise FileNotFoundError(f"未找到数据文件，已尝试: {[str(p) for p in csv_candidates]}")
    df = pd.read_csv(csv_path, encoding="utf-8-sig")

    result = analyze_journal_novelty(
        background_df=df,
        target_df=df,
        top_n=None
    )

    print(result)
