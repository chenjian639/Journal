# -*- coding: utf-8 -*-
"""
python/interdisciplinary.py

跨学科性（TD）计算核心模块
- 无图表
- 无文件输出
- 配置内置，面向 API / 第三方调用
"""
import ast
import numpy as np
import pandas as pd
from collections import Counter


# ===================== 内置配置 =====================
DEFAULT_CONFIG = {
    "columns": {
        "id": "doi",
        "journal": "journal",
        "category": "target",
        "refs": "citing"
    },
    "parameters": {}
}


# ===================== 核心计算类 =====================
class InterdisciplinaryAnalyzer:
    def __init__(self, config=None):
        self.config = config or DEFAULT_CONFIG
        self.column_config = self.config.get("columns", {})

    # ---------- 工具函数 ----------
    def parse_categories(self, value):
        if value is None:
            return []
        if isinstance(value, float):
            if pd.isna(value):
                return []
            return []  # float 值不是有效的类别
        if pd.isna(value):
            return []

        try:
            if isinstance(value, str):
                value = value.strip()
                if not value:
                    return []
                if value.startswith("[") and value.endswith("]"):
                    parsed = ast.literal_eval(value)
                    if isinstance(parsed, list):
                        return [str(v).strip() for v in parsed if v]
                    return []
                for sep in [";", "|", "/"]:
                    if sep in value:
                        return [v.strip() for v in value.split(sep) if v.strip()]
                return [value]
            elif isinstance(value, (list, tuple)):
                return [str(v).strip() for v in value if v]
        except Exception:
            pass

        return []

    # ---------- 相似度矩阵 ----------
    def build_similarity_matrix(self, paper_categories: dict):
        all_categories = sorted({c for cats in paper_categories.values() for c in cats})
        n = len(all_categories)
        
        # 限制类别数量，避免内存问题
        MAX_CATEGORIES = 500
        if n > MAX_CATEGORIES:
            # 只保留出现频率最高的类别
            from collections import Counter
            cat_freq = Counter()
            for cats in paper_categories.values():
                cat_freq.update(cats)
            top_cats = [c for c, _ in cat_freq.most_common(MAX_CATEGORIES)]
            all_categories = sorted(top_cats)
            n = len(all_categories)
        
        cat_to_idx = {c: i for i, c in enumerate(all_categories)}
        co_matrix = np.zeros((n, n), dtype=np.float32)  # 使用 float32 减少内存

        for cats in paper_categories.values():
            # 只保留在 all_categories 中的类别
            valid_cats = [c for c in cats if c in cat_to_idx]
            if len(valid_cats) < 2:
                continue
            for i, c1 in enumerate(valid_cats):
                idx1 = cat_to_idx[c1]
                co_matrix[idx1, idx1] += 1
                for c2 in valid_cats[i + 1:]:
                    idx2 = cat_to_idx[c2]
                    co_matrix[idx1, idx2] += 1
                    co_matrix[idx2, idx1] += 1

        sim = np.zeros((n, n), dtype=np.float32)
        for i in range(n):
            for j in range(n):
                if i == j:
                    sim[i, j] = 1.0
                else:
                    norm_i = np.linalg.norm(co_matrix[i])
                    norm_j = np.linalg.norm(co_matrix[j])
                    denom = norm_i * norm_j
                    sim[i, j] = np.dot(co_matrix[i], co_matrix[j]) / denom if denom > 0 else 0.0

        self.all_categories = all_categories
        self.cat_to_idx = cat_to_idx
        self.similarity_matrix = sim

    # ---------- TD 计算 ----------
    def rao_stirling(self, categories):
        if not categories or len(set(categories)) <= 1:
            return 0.0
        
        # 安全检查
        if not hasattr(self, 'all_categories') or not self.all_categories:
            return 0.0

        total = len(categories)
        probs = Counter(categories)

        n = len(self.all_categories)
        p = np.zeros(n, dtype=np.float32)
        for cat, cnt in probs.items():
            if cat in self.cat_to_idx:
                idx = self.cat_to_idx[cat]
                if 0 <= idx < n:
                    p[idx] = cnt / total

        # 使用矩阵运算代替双重循环
        try:
            # diversity = sum((1 - S[i,j]) * p[i] * p[j])
            outer_p = np.outer(p, p)
            diversity = np.sum((1 - self.similarity_matrix) * outer_p)
        except Exception:
            diversity = 0.0

        return float(diversity)

    def td_index(self, categories):
        d = self.rao_stirling(categories)
        # 平滑压缩：2/(1+d)，将值域压缩到 (0, 2]
        return 2.0 / (1.0 + d) if d > 0 else 1.0


# ===================== 对外统一接口 =====================
def analyze_interdisciplinary(
    df_all: pd.DataFrame,
    *,
    top_n: int | None = None,
    config: dict | None = None
) -> pd.DataFrame:
    """
    跨学科性（TD）分析接口
    完全保留所有期刊，如果论文没有引用或没有数据，td_score 为 0
    """
    if df_all.empty:
        raise ValueError("输入数据为空")

    analyzer = InterdisciplinaryAnalyzer(config)

    # 字段映射
    id_col = analyzer.column_config.get("id", "doi")
    journal_col = analyzer.column_config.get("journal", "journal")
    category_col = analyzer.column_config.get("category", "target")
    refs_col = analyzer.column_config.get("refs", "citing")

    required = {id_col, journal_col, category_col, refs_col}
    missing = required - set(df_all.columns)
    if missing:
        raise ValueError(f"数据缺少列: {missing}")

    # ---------- 构建分类知识库 ----------
    paper_categories = {}
    for _, row in df_all.iterrows():
        pid = str(row[id_col])
        cats = analyzer.parse_categories(row[category_col])
        if cats:
            paper_categories[pid] = cats

    analyzer.build_similarity_matrix(paper_categories)

    # ---------- 论文级 TD ----------
    records = []
    for _, row in df_all.iterrows():
        pid = str(row[id_col])
        journal = row[journal_col]
        refs_raw = row[refs_col]
        
        # 安全解析 refs
        refs = []
        if refs_raw is None or (isinstance(refs_raw, float) and pd.isna(refs_raw)):
            refs = []
        elif isinstance(refs_raw, str):
            refs_raw = refs_raw.strip()
            if refs_raw:
                try:
                    parsed = ast.literal_eval(refs_raw)
                    if isinstance(parsed, (list, tuple)):
                        refs = list(parsed)
                except Exception:
                    refs = []
        elif isinstance(refs_raw, (list, tuple)):
            refs = list(refs_raw)

        ref_cats = []
        for r in refs:
            r_str = str(r)
            if r_str in paper_categories:
                ref_cats.extend(paper_categories[r_str])

        # TD 计算：没有引用或者没有分类也返回 0
        td = analyzer.td_index(ref_cats) if ref_cats else 0.0
        has_ref_cats = bool(ref_cats)

        records.append({
            "doi": pid,
            "journal": journal,
            "td_score": td,
            "has_ref_cats": has_ref_cats,
        })

    paper_df = pd.DataFrame(records)

    # ---------- 期刊聚合 ----------
    # 保证期刊完整
    all_journals = df_all[journal_col].fillna("UNKNOWN").unique()
    journal_df = (
        paper_df
        .groupby("journal")
        .agg(
            td_mean=("td_score", "mean"),
            paper_count=("td_score", "count"),
            valid_ref_papers=("has_ref_cats", lambda s: int(pd.to_numeric(s, errors="coerce").fillna(0).astype(int).sum())),
        )
        .reindex(all_journals, fill_value=0)  # 确保每个期刊都有行
        .reset_index()
    )

    # 百分制（线性调节到 0–100）：td_mean ∈ (0,2] → percent ∈ (0,100]
    journal_df["percent_score"] = (journal_df["td_mean"] / 2 * 100).round(1)
    journal_df = journal_df.sort_values("percent_score", ascending=False)

    if isinstance(top_n, int) and top_n > 0:
        journal_df = journal_df.head(top_n)

    return journal_df.reset_index(drop=True)

# ===================== 本地调试示例 =====================
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
    data_path = None
    for p in csv_candidates:
        if p.exists():
            data_path = p
            break
    if data_path is None:
        raise FileNotFoundError(f"未找到数据文件，已尝试: {[str(p) for p in csv_candidates]}")
    df = pd.read_csv(data_path, encoding="utf-8-sig")
    result = analyze_interdisciplinary(df)
    print(result)
