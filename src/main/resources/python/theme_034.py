# -*- coding: utf-8 -*-
"""
theme.py
纯函数式封装版：计算2021-2025五年窗口的主题集中度与热点响应度
增加 top_keywords 列：每个期刊出现频率最高的5个关键词，按频率从高到低
保证所有期刊都有输出，遇到无关键词或无论文的期刊返回0
"""

import pandas as pd
import numpy as np
import re
import json
import ast

class ThemeHotnessAnalyzer:
    def __init__(self, df, journal_col="journal", keyword_col="keywords"):
        self.journal_col = journal_col
        self.keyword_col = keyword_col
        self.original_df = df.copy()
        self.df = self.original_df.copy()
        self._prepare_data()

    # 一些常见的“伪关键词/停用词”（中英混合），用于过滤掉占比过高但信息量很低的词。
    # 说明：这里的停用词是“关键词层面”的（不是分词后的单词），因此以整 token 匹配为主。
    _STOPWORDS = {
        # English generic
        "study", "studies", "analysis", "approach", "method", "methods", "model", "models",
        "system", "systems", "framework", "review", "survey", "application", "applications",
        "research", "paper", "papers", "article", "articles", "case", "cases", "based",
        "using", "use", "used", "new", "novel", "data", "results", "effect", "effects",
        "impact", "impacts", "development", "design", "evaluation", "algorithm", "algorithms",
        "performance", "implementation",
        # Chinese generic
        "研究", "分析", "方法", "模型", "系统", "框架", "综述", "应用", "设计", "评价", "算法",
        "实验", "结果", "影响", "发展", "现状", "对策", "探讨", "基于", "机制", "策略", "管理",
        "构建", "优化", "改进", "实证", "比较", "测度", "计量", "可视化",
    }

    @staticmethod
    def _is_all_ascii(s: str) -> bool:
        try:
            s.encode("ascii")
            return True
        except Exception:
            return False

    def _normalize_keyword_token(self, kw: str) -> str:
        if kw is None:
            return ""
        s = str(kw).strip()
        if not s:
            return ""

        # 去掉一些常见的首尾标点
        s = s.strip().strip("·•" )
        s = re.sub(r"^[\s\-–—_\.,;:!\?\(\)\[\]\{\}<>\"']+", "", s)
        s = re.sub(r"[\s\-–—_\.,;:!\?\(\)\[\]\{\}<>\"']+$", "", s)

        # 折叠空白
        s = re.sub(r"\s+", " ", s).strip()

        # ASCII 关键词统一小写，便于合并计数
        if self._is_all_ascii(s):
            s = s.lower()

        # 去掉明显无效 token
        if not s:
            return ""
        if s.lower() in {"nan", "none", "null"}:
            return ""
        if re.fullmatch(r"\d+", s):
            return ""
        if len(s) <= 1:
            return ""

        # 过滤只包含标点的情况
        if re.fullmatch(r"[\W_]+", s, flags=re.UNICODE):
            return ""

        return s

    def _filter_stopwords(self, tokens: list[str]) -> list[str]:
        """仅用于 Top Keywords/关键词频次导出。

        说明：按你的需求，停用词过滤不要影响其它指标（如 theme_concentration/hot_response），
        但在 top5 关键词统计/展示里需要过滤掉低信息量的“伪关键词”。
        """
        if not tokens:
            return []
        return [t for t in tokens if t and t not in self._STOPWORDS]
    
    def _prepare_data(self):
        # 关键词列兼容：部分数据集 keywords 为空，但存在 keywords_alt1
        # 这里做“列选择 + 有效性”探测，确保后续 top_keywords_2021~2025 能产出。
        kw_candidates = [
            self.keyword_col,
            "keywords",
            "keywords_alt1",
            "keywords_alt",
            "author_keywords",
            "Author Keywords",
            "DE",
        ]

        year_candidates = ["year", "publish_year", "publish_date"]
        year_col_found = None
        for cand in year_candidates:
            if cand in self.df.columns:
                s = self.df[cand]
                self.df["year"] = self._extract_year_from_series(s)
                year_col_found = cand
                break
        if year_col_found is None or self.df["year"].isna().all():
            raise ValueError("No valid year column found")
        self.df = self.df[(self.df["year"] >= 2021) & (self.df["year"] <= 2025)].copy()

        # 选取最可用的关键词列：优先使用传入列名，其次尝试候选列。
        chosen_kw_col = None
        for c in kw_candidates:
            if c and c in self.df.columns:
                chosen_kw_col = c
                break
        if chosen_kw_col is None:
            # 没有任何关键词列：降级为全空（仍保证程序可运行）
            self.df[self.keyword_col] = [[] for _ in range(len(self.df))]
            self.df = self.df.dropna(subset=[self.journal_col])
            return

        # 先用 chosen 列尝试解析
        self.keyword_col = chosen_kw_col
        self.df[self.keyword_col] = self.df[self.keyword_col].apply(self._split_keywords)

        # 若整体解析后仍几乎全空，则回退到 keywords_alt1（常见在 WoS/清洗后的数据集中）
        try:
            nonempty = float(self.df[self.keyword_col].apply(lambda lst: isinstance(lst, list) and len(lst) > 0).mean())
        except Exception:
            nonempty = 0.0

        if nonempty == 0.0 and self.keyword_col != "keywords_alt1" and "keywords_alt1" in self.df.columns:
            alt = "keywords_alt1"
            parsed_alt = self.df[alt].apply(self._split_keywords)
            try:
                alt_nonempty = float(parsed_alt.apply(lambda lst: isinstance(lst, list) and len(lst) > 0).mean())
            except Exception:
                alt_nonempty = 0.0
            if alt_nonempty > 0.0:
                self.keyword_col = alt
                self.df[self.keyword_col] = parsed_alt

        self.df = self.df.dropna(subset=[self.journal_col])
    
    def _extract_year_from_series(self, s):
        if pd.api.types.is_integer_dtype(s) or pd.api.types.is_float_dtype(s):
            yrs = pd.to_numeric(s, errors='coerce').dropna().astype(int)
            return yrs.reindex(s.index)
        s_str = s.astype(str).fillna("")
        extracted = s_str.str.extract(r'(\b(19|20)\d{2}\b)')[0]
        if extracted.notna().sum() / max(1, len(extracted)) > 0.1:
            return pd.to_numeric(extracted, errors='coerce')
        try:
            dt = pd.to_datetime(s_str, errors='coerce')
            years = dt.dt.year
            return years
        except Exception:
            return pd.Series([np.nan]*len(s), index=s.index)
    
    def _split_keywords(self, x):
        # 目标：把 cleaned 表里可能出现的多种格式统一成 list[str]
        # 支持：list/tuple/set、JSON字符串(例如 '["a","b"]')、Python字面量(例如 "['a','b']")、分隔符字符串
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return []

        items = None

        # 已经是容器类型
        if isinstance(x, (list, tuple, set)):
            items = list(x)

        s = x if isinstance(x, str) else None
        if items is None:
            s = str(x).strip() if s is None else s.strip()
            if not s:
                return []
            if s.lower() in {"nan", "none", "null"}:
                return []

            # 1) JSON 优先（cleaned 表通常是 json.dumps(list) 的结果）
            try:
                parsed = json.loads(s)
                if isinstance(parsed, list):
                    items = parsed
                elif isinstance(parsed, str):
                    s = parsed.strip()
            except Exception:
                pass

            # 2) Python 字面量兜底（兼容 "['a', 'b']"）
            if items is None and s.startswith("[") and s.endswith("]"):
                try:
                    parsed = ast.literal_eval(s)
                    if isinstance(parsed, (list, tuple, set)):
                        items = list(parsed)
                except Exception:
                    items = None

            # 3) 分隔符切分兜底（兼容老格式 'a; b, c'）
            if items is None:
                items = re.split(r"[;,\|/、；，]", s)

        # 归一化 + 停用词过滤 + 过滤伪关键词（例如 '[]'） + 保序去重
        out: list[str] = []
        for item in items or []:
            if item is None:
                continue
            kw = str(item).strip()
            if not kw:
                continue

            # 去掉外层括号/引号碎片："['bipoc'" / "'aids']" / '"keyword"'
            kw = kw.strip().lstrip("[").rstrip("]").strip()
            kw = kw.strip("\"'").strip()
            kw = kw.strip().lstrip("[").rstrip("]").strip()
            kw = kw.strip("\"'").strip()

            if not kw:
                continue
            if kw in {"[]", "[ ]"}:
                continue

            kw2 = self._normalize_keyword_token(kw)
            if not kw2:
                continue

            out.append(kw2)

        seen = set()
        uniq: list[str] = []
        for kw in out:
            if kw not in seen:
                seen.add(kw)
                uniq.append(kw)
        return uniq
    
    def _compute_theme_concentration(self, group_df):
        keywords = [kw for lst in group_df[self.keyword_col] for kw in lst]
        if len(keywords) == 0:
            return 0.0
        counts = pd.Series(keywords).value_counts()
        p = counts / counts.sum()
        H = -(p * np.log(p + 1e-12)).sum()
        H_norm = H / np.log(len(p)) if len(p) > 1 else 0.0
        return 1 - H_norm
    
    def _compute_hot_response(self, group_df, global_hotwords):
        keywords = [kw for lst in group_df[self.keyword_col] for kw in lst]
        if len(keywords) == 0:
            return 0.0
        hits = sum(1 for kw in keywords if kw in global_hotwords)
        return hits / len(keywords)
    
    def _get_top_keywords(self, group_df, top_k=5):
        """返回期刊中出现频率最高的前 top_k 个关键词，按频率从高到低"""
        keywords = [kw for lst in group_df[self.keyword_col] for kw in lst]
        keywords = self._filter_stopwords(keywords)
        if len(keywords) == 0:
            return []
        counts = pd.Series(keywords).value_counts()
        top_keywords = counts.head(top_k).index.tolist()
        return top_keywords  # 保持从高到低
    
    def _get_top_keywords_for_year(self, group_df, year, top_k=5):
        """返回某期刊在某一年出现频率最高的前 top_k 个关键词"""
        g_year = group_df[group_df["year"] == year]
        if g_year.empty:
            return []
        keywords = [kw for lst in g_year[self.keyword_col] for kw in lst]
        keywords = self._filter_stopwords(keywords)
        if not keywords:
            return []
        counts = pd.Series(keywords).value_counts()
        return counts.head(top_k).index.tolist()
    
    @staticmethod
    def _format_percent(x):
        return round(x * 100, 2)

    @staticmethod
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
    
    def run(self, top_n=None):
        all_keywords = [kw for lst in self.df[self.keyword_col] for kw in lst]
        global_hotwords = set(pd.Series(all_keywords).value_counts().head(50).index)
        all_journals_complete = pd.Series(self.original_df[self.journal_col].dropna().unique()).tolist()

        records = []
        years = [2021, 2022, 2023, 2024, 2025]
        for journal in all_journals_complete:
            g = self.df[self.df[self.journal_col] == journal]

            has_data = (not g.empty) and (not all(len(lst) == 0 for lst in g[self.keyword_col]))
            if not has_data:
                theme_score = 0.0
                hot_score = 0.0
                top_by_year = {y: [] for y in years}
            else:
                theme_score = self._compute_theme_concentration(g)
                hot_score = self._compute_hot_response(g, global_hotwords)
                top_by_year = {y: self._get_top_keywords_for_year(g, y, top_k=5) for y in years}

            records.append({
                "journal": journal,
                "has_data": bool(has_data),
                "theme_concentration_raw": self._format_percent(theme_score),
                "hot_response_raw": self._format_percent(hot_score),
                "top_keywords_2021": top_by_year[2021],
                "top_keywords_2022": top_by_year[2022],
                "top_keywords_2023": top_by_year[2023],
                "top_keywords_2024": top_by_year[2024],
                "top_keywords_2025": top_by_year[2025],
            })
        
        out_df = pd.DataFrame(records)

        # 均匀化映射：仅对有关键词数据的期刊做 1~100；无数据期刊保持 0
        out_df["theme_concentration"] = 0.0
        out_df["hot_response"] = 0.0
        valid = out_df["has_data"] == True
        out_df.loc[valid, "theme_concentration"] = self._uniform_rank_to_1_100(
            out_df.loc[valid, "theme_concentration_raw"],
            tie_breaker=out_df.loc[valid, "journal"],
        ).round(2)
        out_df.loc[valid, "hot_response"] = self._uniform_rank_to_1_100(
            out_df.loc[valid, "hot_response_raw"],
            tie_breaker=out_df.loc[valid, "journal"],
        ).round(2)

        out_df = out_df.sort_values("theme_concentration", ascending=False).reset_index(drop=True)
        if top_n is not None:
            out_df = out_df.head(top_n)
        return out_df

    def keyword_counts_long(self, *, top_k: int = 20, years: list[int] | None = None) -> pd.DataFrame:
        """导出关键词频次（long format）：journal, year, keyword, count。

        用于调试：你可以直接看到每个期刊在每一年（2021-2025）哪些关键词出现次数最多。

        Args:
            top_k: 每个 (journal, year) 只保留前 top_k 个关键词（避免文件过大）。
            years: 指定年份列表；为空则使用 2021-2025。
        """
        if years is None:
            years = [2021, 2022, 2023, 2024, 2025]

        dfw = self.df
        if dfw is None or dfw.empty:
            return pd.DataFrame(columns=["journal", "year", "keyword", "count"])

        # 限定年份窗口
        dfw = dfw[dfw["year"].isin(years)].copy()
        if dfw.empty:
            return pd.DataFrame(columns=["journal", "year", "keyword", "count"])

        recs: list[dict] = []
        for (journal, year), g in dfw.groupby([self.journal_col, "year"], dropna=True):
            keywords = [kw for lst in g[self.keyword_col] for kw in (lst or [])]
            keywords = self._filter_stopwords(keywords)
            if not keywords:
                continue
            vc = pd.Series(keywords).value_counts()
            for kw, cnt in vc.head(int(top_k)).items():
                recs.append({
                    "journal": journal,
                    "year": int(year),
                    "keyword": str(kw),
                    "count": int(cnt),
                })

        out = pd.DataFrame(recs)
        if not out.empty:
            out = out.sort_values(["journal", "year", "count", "keyword"], ascending=[True, True, False, True]).reset_index(drop=True)
        return out


# =================== 本地调试示例 ===================
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
    
    analyzer = ThemeHotnessAnalyzer(df)
    result = analyzer.run()
    print(result)
