# -*- coding: utf-8 -*-
import sqlite3
import pandas as pd
import json
from pathlib import Path


def upload_journal_metrics(
    disrupt_df: pd.DataFrame,
    interdisciplinary_df: pd.DataFrame,
    novelty_df: pd.DataFrame,
    topic_df: pd.DataFrame,
    theme_df: pd.DataFrame,
    year: int,
    db_config: dict = None,
    paper_count_df: pd.DataFrame = None,
    papers_df: pd.DataFrame = None,
):
    """
    上传期刊指标到 SQLite 数据库（增加 top_keywords、paper_count、category 列）

    参数:
        disrupt_df: disruption 结果 DataFrame, ['journal','percent_score']
        interdisciplinary_df: 跨学科指标 DataFrame, ['journal','percent_score']
        novelty_df: 新颖性指标 DataFrame, ['journal','percent_score']
        topic_df: topic entropy 指标 DataFrame, ['journal','percent_score']
        theme_df: theme 指标 DataFrame, ['journal','theme_concentration','hot_response','top_keywords']
        year: int, 指标年份
        db_config: 数据库配置字典, 默认使用内置配置
        paper_count_df: 期刊论文数 DataFrame, ['journal','paper_count']（可选）
        papers_df: 论文级数据 DataFrame, 至少包含 ['journal','category']（可选，用于计算 journal 的 category 众数）
    """

    if db_config is None:
        # 默认 SQLite 数据库路径（相对于脚本目录）
        db_config = {
            "dialect": "sqlite",
            "db_path": str(Path(__file__).resolve().parent.parent.parent.parent / "data" / "paper_system.db"),
        }

    # 获取数据库路径
    db_path = db_config.get("db_path", db_config.get("database", ""))
    print(f"📌 journal_metrics 写入目标: SQLite {db_path}")

    # -------------------- 合并各指标 --------------------
    dfs = [
        disrupt_df.rename(columns={"percent_score": "disruption"})[["journal", "disruption"]],
        interdisciplinary_df.rename(columns={"percent_score": "interdisciplinary"})[
            ["journal", "interdisciplinary"]
        ],
        novelty_df.rename(columns={"percent_score": "novelty"})[["journal", "novelty"]],
        topic_df.rename(columns={"percent_score": "topic"})[["journal", "topic"]],
        theme_df[[
            "journal", "theme_concentration", "hot_response",
            "top_keywords_2021", "top_keywords_2022", "top_keywords_2023", "top_keywords_2024", "top_keywords_2025"
        ]],
            ]

    if paper_count_df is not None and not paper_count_df.empty:
        cols = set(paper_count_df.columns)
        if "journal" in cols and "paper_count" in cols:
            dfs.append(paper_count_df[["journal", "paper_count"]])

    # 计算每个 journal 的主导 category（两类时：数量多的一方；数量相同则按字母序更小的那个）
    if papers_df is not None and not papers_df.empty:
        cols = set(papers_df.columns)
        if "journal" in cols and "category" in cols:
            tmp = papers_df[["journal", "category"]].copy()
            tmp = tmp.dropna(subset=["journal", "category"])
            tmp["category"] = tmp["category"].astype(str).str.strip()
            tmp = tmp[tmp["category"] != ""]
            if not tmp.empty:
                counts = (
                    tmp.groupby(["journal", "category"])
                    .size()
                    .reset_index(name="cnt")
                    .sort_values(["journal", "cnt", "category"], ascending=[True, False, True])
                )
                journal_category_df = counts.drop_duplicates(subset=["journal"], keep="first")[
                    ["journal", "category"]
                ]
                dfs.append(journal_category_df)

    # 外连接合并，保证所有期刊都保留
    merged_df = dfs[0]
    for df in dfs[1:]:
        merged_df = pd.merge(merged_df, df, on="journal", how="outer")

    # 添加年份列
    merged_df["year"] = year

    # paper_count：表里是 NOT NULL，缺失时补 0
    if "paper_count" not in merged_df.columns:
        merged_df["paper_count"] = 0
    merged_df["paper_count"] = merged_df["paper_count"].fillna(0).astype(int)

    # -------------------- 写入数据库 --------------------
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # SQLite 使用 INSERT OR REPLACE 而不是 ON DUPLICATE KEY UPDATE
    insert_sql = """
        INSERT OR REPLACE INTO journal_metrics
            (journal, year, disruption, interdisciplinary, novelty, topic,
            theme_concentration, hot_response,
            top_keywords_2021, top_keywords_2022, top_keywords_2023, top_keywords_2024, top_keywords_2025,
            paper_count, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """

    for _, row in merged_df.iterrows():
        def _kw_to_json(v):
            if isinstance(v, float) and pd.isna(v):
                v = []
            if v is None:
                v = []
            # 兼容异常输入：字符串形式的 list / JSON
            if isinstance(v, str):
                s = v.strip()
                if not s or s.lower() in {"nan", "none", "null"}:
                    v = []
                else:
                    parsed = None
                    try:
                        parsed = json.loads(s)
                    except Exception:
                        parsed = None
                    if parsed is None and s.startswith("[") and s.endswith("]"):
                        try:
                            import ast

                            parsed = ast.literal_eval(s)
                        except Exception:
                            parsed = None
                    if isinstance(parsed, list):
                        v = parsed
                    elif isinstance(parsed, (tuple, set)):
                        v = list(parsed)
                    elif isinstance(parsed, str):
                        # 极端情况：JSON 里包了一层字符串
                        inner = parsed.strip()
                        if inner == "[]":
                            v = []
            return json.dumps(v, ensure_ascii=False)

        kw_2021 = _kw_to_json(row.get("top_keywords_2021"))
        kw_2022 = _kw_to_json(row.get("top_keywords_2022"))
        kw_2023 = _kw_to_json(row.get("top_keywords_2023"))
        kw_2024 = _kw_to_json(row.get("top_keywords_2024"))
        kw_2025 = _kw_to_json(row.get("top_keywords_2025"))

        params = [
            row.get("journal"),
            row.get("year"),
            row.get("disruption"),
            row.get("interdisciplinary"),
            row.get("novelty"),
            row.get("topic"),
            row.get("theme_concentration"),
            row.get("hot_response"),
            kw_2021, kw_2022, kw_2023, kw_2024, kw_2025,
            int(row.get("paper_count", 0)) if not pd.isna(row.get("paper_count", 0)) else 0,
            row.get("category"),
        ]

        # 将 pandas 的 NaN 转换为 None（paper_count 已保证为 int 不为空）
        clean_params = [None if pd.isna(x) else x for x in params]
        cursor.execute(insert_sql, tuple(clean_params))

    conn.commit()
    cursor.close()
    conn.close()

    print(f"✅ 成功上传 {len(merged_df)} 条期刊指标数据到 journal_metrics 表")