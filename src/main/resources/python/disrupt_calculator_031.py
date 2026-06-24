# -*- coding: utf-8 -*-
"""
期刊颠覆性指数计算（中英文混合：中文用题名，英文用 DOI）
"""
import ast
import warnings
from collections import defaultdict
import pandas as pd
import numpy as np
import re
from pathlib import Path

warnings.filterwarnings("ignore")


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

def log(msg: str):
    import sys
    print(f"[disrupt] {msg}", file=sys.stderr)

disrupt_config = {
    "columns": {
        "id": "doi",          # 仍然把 DOI 当默认 id，缺失时用行号占位
        "journal": "journal",
        "citing": "citing",
        "title": "title",     # 新增：标题列名
        "category": "category"
    },
    "parameters": {
        "top_k": 10,
        "volume_weight": 0.4,
        "visualize_top_n": 10,
        # 你指定的策略：认为 disruption_index==0 属于引用导出/清洗导致的脏数据，
        # 为避免影响期刊聚合，直接剔除这些论文。
        # 注意：理论上 0 也可能是有效值；这里按你的业务假设处理。
        # 中文期刊在“题名引用”场景下，论文 disruption_index 很容易为 0。
        # 0 既可能是“可计算但结果为 0”，也可能是“引用稀疏导致的 0”。
        # 为避免期刊层面整列缺失（Java 页面显示为空），这里默认不再剔除 0。
        "exclude_zero_papers": False,
        # 是否打印建网质量诊断信息（建议在跑全量 10万+ 数据时开启一次用于核对）
        "print_diagnostics": False,
        # 诊断输出：按 journal 展示的 Top-N（按论文量排序）
        "diagnostics_top_n_journals": 15,
        # 是否输出“参与期刊聚合的论文数”（排除 NaN/0 后）到 outputs/disrupt
        # 注意：默认关闭，避免在脚本目录生成 outputs 文件夹；main.py 会单独控制输出目录
        "export_participating_paper_counts": False,

        # 动态过滤：剔除“高频且疑似期刊名”的 title token，避免形成超级节点抬高指标
        # 注意：这里刻意不包含“报告”后缀（报告也可能是论文题名）。
        "dynamic_filter_high_freq_journalish_title_tokens": True,
        "high_freq_title_token_min_citers": 50,
        "high_freq_title_token_suffixes": ["学报", "期刊", "杂志", "工作", "通讯", "导报", "学刊"],
    }
}


def _default_disrupt_outputs_dir() -> Path:
    # 以本文件所在目录为基准：python_sum/outputs/disrupt
    base = Path(__file__).resolve().parent
    out_dir = base / "outputs" / "disrupt"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir

class DisruptionIndexCalculator:
    def __init__(self, config: dict):
        self.config = config
        self.column_config = config.get("columns", {})
        # 注意：这里的“被引节点”不再要求必须是样本内论文 pid。
        # 我们把引用规范化为 token（doi:/title:/pid:），这样中文题名引用也能进网。
        self.citation_network = defaultdict(set)   # ref_token/node_token -> {citing_pid}
        self.paper_references = {}                 # pid -> set(ref_token)
        self.paper_attrs = {}                      # pid -> {doi,title,category,node}
        self.row_pid_map = {}                      # row_idx -> pid
        self.journal_name_set = set()              # normalized journal names for filtering bad ref tokens

    def get_column_name(self, column_type: str) -> str:
        mapping = {
            "id": self.column_config.get("id", "doi"),
            "journal": self.column_config.get("journal", "journal"),
            "citing": self.column_config.get("citing", "citing"),
            "title": self.column_config.get("title", "title"),
            "category": self.column_config.get("category", "category"),
        }
        return mapping.get(column_type, column_type)

    def _derive_pid(self, row, row_idx: int, id_col: str) -> str:
        pid = row.get(id_col)
        if pid is None or (isinstance(pid, float) and pd.isna(pid)) or str(pid).strip() == "":
            pid = f"row_{row_idx}"
        return str(pid).strip()

    @staticmethod
    def _to_list(val):
        if val is None or (isinstance(val, float) and pd.isna(val)):
            return []
        if isinstance(val, (list, tuple, set)):
            return list(val)
        if isinstance(val, str):
            try:
                parsed = ast.literal_eval(val)
                if isinstance(parsed, (list, tuple, set)):
                    return list(parsed)
            except Exception:
                # 不可解析则视为单条
                return [val]
        return []

    @staticmethod
    def _norm_doi(s: str) -> str:
        """尽量把 DOI 归一化到同一形式：去前缀/去空白/转小写/去尾部标点。"""
        if s is None:
            return ""
        t = str(s).strip()
        if not t:
            return ""

        t_low = t.lower().strip()
        # 常见前缀
        for prefix in ("https://doi.org/", "http://doi.org/", "https://dx.doi.org/", "http://dx.doi.org/"):
            if t_low.startswith(prefix):
                t = t[len(prefix):]
                break
        if t.lower().startswith("doi:"):
            t = t.split(":", 1)[1]

        t = t.strip()
        # 去尾部常见标点
        t = t.rstrip(".。;；,，)]}\"' ")
        return t.lower()

    @staticmethod
    def _extract_doi_from_text(s: str) -> str:
        """从字符串中尽量提取 DOI（如果存在）。"""
        if not s:
            return ""
        txt = str(s).strip()
        if not txt:
            return ""
        # 优先匹配 10.xxxx/... 主体
        m = re.search(r"\b10\.\d{4,9}/[-._;()/:A-Z0-9]+", txt, re.IGNORECASE)
        return m.group(0) if m else ""

    @staticmethod
    def _norm_title(s: str) -> str:
        """题名归一化：压缩空白、统一中英文标点、去两侧引号/书名号等。"""
        if not isinstance(s, str):
            return ""
        t = s.strip()
        if not t:
            return ""
        # 全角空格
        t = t.replace("\u3000", " ")
        # 常见中文标点统一
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
        # 去两侧引号/书名号
        t = t.strip(" \t\r\n\"'《》<>[](){}")
        # 压缩空白
        t = re.sub(r"\s+", " ", t).strip()
        return t

    def _paper_node_token(self, doi_norm: str, title_norm: str, pid: str) -> str:
        if doi_norm:
            return f"doi:{doi_norm}"
        if title_norm:
            return f"title:{title_norm}"
        return f"pid:{pid}"

    def _ref_token(self, x) -> str:
        """把引用条目转成可入网 token：优先 DOI，否则按题名。"""
        if x is None or (isinstance(x, float) and pd.isna(x)):
            return ""
        s = str(x).strip()
        if not s:
            return ""

        # 明显 URL/网页片段直接丢弃（会形成超级节点）
        s_low = s.lower()
        if "http://" in s_low or "https://" in s_low or s_low.startswith("www."):
            return ""

        doi_guess = self._extract_doi_from_text(s)
        if doi_guess:
            doi_norm = self._norm_doi(doi_guess)
            return f"doi:{doi_norm}" if doi_norm else ""

        title_norm = self._norm_title(s)
        if not title_norm:
            return ""

        # 太短/无意义的片段不入网
        if len(title_norm) < 4:
            return ""
        # 若题名 token 恰好等于样本内期刊名，极大概率是抽取错误（会形成超级节点）
        if title_norm in self.journal_name_set:
            return ""
        # 进一步过滤明显的 url 残片
        if title_norm.lower().startswith("http") or title_norm.lower().startswith("www"):
            return ""
        return f"title:{title_norm}"

    def build_citation_network(self, df: pd.DataFrame):
        log("Building citation network...")
        id_col = self.get_column_name("id")
        citing_col = self.get_column_name("citing")
        title_col = self.get_column_name("title")
        cat_col = self.get_column_name("category")
        journal_col = self.get_column_name("journal")

        self.citation_network.clear()
        self.paper_references.clear()
        self.paper_attrs.clear()
        self.row_pid_map.clear()
        self.journal_name_set = set()

        rows_cache = []

        # 先收集样本内期刊名（用于过滤“期刊名被当作引用题名”的坏 token）
        if journal_col in df.columns:
            try:
                for j in df[journal_col].dropna().astype(str).tolist():
                    jn = self._norm_title(j)
                    if jn:
                        self.journal_name_set.add(jn)
            except Exception:
                self.journal_name_set = set()

        # 首轮：收集节点属性并建索引
        for idx, row in df.reset_index(drop=True).iterrows():
            pid = self._derive_pid(row, idx, id_col) # type: ignore
            self.row_pid_map[idx] = pid

            doi_val = row.get(id_col)
            doi_norm = self._norm_doi(doi_val) if doi_val is not None and not (isinstance(doi_val, float) and pd.isna(doi_val)) else "" # type: ignore
            title_val = row.get(title_col)
            title_norm = self._norm_title(title_val) # type: ignore
            cat_raw = str(row.get(cat_col) or "").strip().lower()
            if ("chinese" in cat_raw) or ("中文" in cat_raw) or ("中" == cat_raw):
                cat = "chinese"
            elif ("english" in cat_raw) or ("英文" in cat_raw) or ("en" == cat_raw):
                cat = "english"
            else:
                cat = "unknown"

            node_token = self._paper_node_token(doi_norm, title_norm, pid)

            self.paper_attrs[pid] = {
                "doi": doi_norm,
                "title": title_norm,
                "category": cat,
                "node": node_token,
            }

            rows_cache.append((idx, row, pid, cat))

        # 二轮：把引用条目规范化为 token 入网。
        # 优先处理“样本内 pid 引用”（例如 main.py 的 citing_td）：若引用条目就是样本内 pid，
        # 则直接转成该论文的 node token（doi:/title:/pid:），构建样本内引用网络。
        # 否则回退到通用 _ref_token（doi/题名）逻辑，允许外部引用节点存在。
        pid_to_node = {p: (a.get("node") or "") for p, a in (self.paper_attrs or {}).items()}
        for _, row, pid, _cat in rows_cache:
            raw_refs = self._to_list(row.get(citing_col))
            ref_tokens = set()
            for x in raw_refs:
                # 1) pid 直连：引用条目可能是 row_123 / 10.xxxx/... / 纯 pid
                s = ""
                if x is not None and not (isinstance(x, float) and pd.isna(x)):
                    s = str(x).strip()

                tok = ""
                if s:
                    # 支持 pid:xxx 形式
                    pid_key = s.split(":", 1)[1] if s.startswith("pid:") and ":" in s else s
                    node = pid_to_node.get(pid_key)
                    if node:
                        tok = str(node)

                # 2) 通用 token 化：DOI/题名（外部节点）
                if not tok:
                    tok = self._ref_token(x)
                if tok:
                    ref_tokens.add(tok)

            # 写入引用关系
            self.paper_references[pid] = ref_tokens
            for ref_tok in ref_tokens:
                self.citation_network[ref_tok].add(pid)

        # 三轮：动态剔除“高频且疑似期刊名”的 title token（不含“报告”后缀）
        try:
            params = (self.config or {}).get("parameters", {})
            if bool(params.get("dynamic_filter_high_freq_journalish_title_tokens", True)):
                min_citers = int(params.get("high_freq_title_token_min_citers", 50))
                suffixes = params.get("high_freq_title_token_suffixes", None)
                if not isinstance(suffixes, (list, tuple)) or not suffixes:
                    suffixes = ["学报", "期刊", "杂志", "工作", "通讯", "导报", "学刊"]
                removed = self._filter_high_freq_journalish_title_tokens(min_citers=min_citers, suffixes=list(suffixes))
                if removed:
                    log(f"Dynamic filter removed high-freq journal-like title tokens: {len(removed)}")
        except Exception as e:
            log(f"Dynamic filter failed (not critical): {e}")

        log(f"Network built | Papers: {len(self.paper_references)}")
        return self

    def _filter_high_freq_journalish_title_tokens(self, *, min_citers: int, suffixes: list[str]) -> set[str]:
        """剔除高频且疑似期刊名的 title token。

        判定：token 形如 title:xxx，且 citer_count>=min_citers，且 xxx 以 suffixes 任一后缀结尾。
        说明：suffixes 默认不包含“报告”，避免误伤真实论文题名。
        """
        if not self.citation_network or not self.paper_references:
            return set()
        if min_citers is None or int(min_citers) <= 0:
            return set()
        suf = [str(x) for x in (suffixes or []) if str(x).strip()]
        if not suf:
            return set()

        # 统计 title token 被多少论文引用
        candidates = []
        for tok, citers in self.citation_network.items():
            if not isinstance(tok, str) or not tok.startswith("title:"):
                continue
            cnt = len(citers) if citers is not None else 0
            if cnt >= int(min_citers):
                candidates.append((tok, cnt))

        if not candidates:
            return set()

        bad = set()
        for tok, _cnt in candidates:
            title_text = tok[len("title:"):]
            if any(title_text.endswith(s) for s in suf):
                bad.add(tok)

        if not bad:
            return set()

        # 从每篇论文的引用集合中移除
        for pid, refs in self.paper_references.items():
            if refs:
                refs.difference_update(bad)

        # 从 citation_network 中移除这些 token（释放内存/避免诊断干扰）
        for tok in bad:
            try:
                self.citation_network.pop(tok, None)
            except Exception:
                pass
        return bad

    def get_ref_count_series(self, df: pd.DataFrame) -> pd.Series:
        """返回与 df 行顺序一致的参考文献（token）数量。"""
        id_col = self.get_column_name("id")
        out = []
        for idx, row in df.reset_index(drop=True).iterrows():
            pid = self._derive_pid(row, idx, id_col) # type: ignore
            out.append(len(self.paper_references.get(pid, set())))
        return pd.Series(out, index=df.reset_index(drop=True).index, name="ref_count")

    def get_in_degree_series(self, df: pd.DataFrame) -> pd.Series:
        """返回与 df 行顺序一致的样本内入度（多少样本论文引用了该论文的 node token）。"""
        id_col = self.get_column_name("id")
        out = []
        for idx, row in df.reset_index(drop=True).iterrows():
            pid = self._derive_pid(row, idx, id_col) # type: ignore
            node = (self.paper_attrs.get(pid, {}) or {}).get("node", f"pid:{pid}")
            out.append(len(self.citation_network.get(node, set())))
        return pd.Series(out, index=df.reset_index(drop=True).index, name="in_degree")

    def calculate_disruption_index(self, focal_pid):
        R = self.paper_references.get(focal_pid, set())
        focal_node = (self.paper_attrs.get(focal_pid, {}) or {}).get("node", f"pid:{focal_pid}")
        C = self.citation_network.get(focal_node, set())
        if not R:            # 无参考文献，直接视为缺失
            return np.nan

        ni = nj = 0
        for citing_paper in C:
            citing_refs = self.paper_references.get(citing_paper, set())
            if citing_refs & R:
                nj += 1
            else:
                ni += 1

        papers_citing_R = set()
        for r in R:
            papers_citing_R.update(self.citation_network.get(r, set()))
        nk = len(papers_citing_R - C)

        denom = ni + nj + nk
        if denom == 0:
            # 在用户上传数据场景里，很多论文可能没有形成可用的引用/被引闭环。
            # 这时指数“无法定义”会导致期刊整行缺失；业务上更希望视为 0 分。
            return 0.0
        return (ni - nj) / denom

# ===================== 论文级计算 =====================
def calculate_paper_scores(df_all: pd.DataFrame, config: dict):
    calculator = DisruptionIndexCalculator(config)
    calculator.build_citation_network(df_all)
    id_col = calculator.get_column_name("id")
    journal_col = calculator.get_column_name("journal")

    records = []
    log("Calculating paper disruption index...")
    for idx, row in df_all.reset_index(drop=True).iterrows():
        pid = calculator._derive_pid(row, idx, id_col) # type: ignore
        try:
            d_index = calculator.calculate_disruption_index(pid)
        except Exception:
            d_index = np.nan
        records.append(
            {
                id_col: calculator.paper_attrs.get(pid, {}).get("doi") or pid,
                "journal": row.get(journal_col),
                "disruption_index": d_index,
            }
        )

    log("Paper-level calculation done")
    return pd.DataFrame(records), calculator


def _print_diagnostics(
    df_all: pd.DataFrame,
    paper_scores: pd.DataFrame,
    calculator: DisruptionIndexCalculator,
    *,
    top_n_journals: int = 15,
):
    """打印建网质量诊断：引用为空比例、参考数分布、入度分布、NaN/0 disruption 占比等。"""
    try:
        id_col = calculator.get_column_name("id")
        journal_col = calculator.get_column_name("journal")
        cat_col = calculator.get_column_name("category")

        df0 = df_all.reset_index(drop=True).copy()
        df0["ref_count"] = calculator.get_ref_count_series(df0)
        df0["in_degree"] = calculator.get_in_degree_series(df0)

        ps = paper_scores.reset_index(drop=True).copy()
        # paper_scores 里 journal 是直接写死键名
        df0 = df0.assign(_journal=ps["journal"].astype(str))
        df0 = df0.assign(_disruption=ps["disruption_index"])

        # category 规范化（缺失则标记 unknown）
        if cat_col in df0.columns:
            cat = df0[cat_col].astype(str).str.strip().str.lower()
            df0["_category"] = np.where(cat.eq("chinese"), "chinese", np.where(cat.eq("english"), "english", "unknown"))
        else:
            df0["_category"] = "unknown"

        log("--- 建网质量诊断（摘要）---")
        n = len(df0)
        if n == 0:
            log("诊断：输入为空")
            return

        empty_ref = int((df0["ref_count"] == 0).sum())
        log(f"样本论文数: {n}")
        log(f"ref_count=0（无可用引用token）: {empty_ref} ({empty_ref / n:.2%})")

        # disruption 分布
        dn = df0["_disruption"]
        nan_cnt = int(dn.isna().sum())
        zero_cnt = int((dn == 0).sum())
        log(f"disruption_index 为 NaN: {nan_cnt} ({nan_cnt / n:.2%})")
        log(f"disruption_index == 0: {zero_cnt} ({zero_cnt / n:.2%})")

        # 按 category 汇总
        cat_sum = (
            df0.groupby("_category")
            .agg(
                papers=("_category", "size"),
                ref_empty=("ref_count", lambda s: int((s == 0).sum())),
                ref_avg=("ref_count", "mean"),
                ref_median=("ref_count", "median"),
                indeg0=("in_degree", lambda s: int((s == 0).sum())),
                d_nan=("_disruption", lambda s: int(pd.isna(s).sum())),
                d_zero=("_disruption", lambda s: int((s == 0).sum())),
            )
            .reset_index()
        )
        cat_sum["ref_empty_rate"] = (cat_sum["ref_empty"] / cat_sum["papers"]).round(4)
        cat_sum["indeg0_rate"] = (cat_sum["indeg0"] / cat_sum["papers"]).round(4)
        cat_sum["d_nan_rate"] = (cat_sum["d_nan"] / cat_sum["papers"]).round(4)
        cat_sum["d_zero_rate"] = (cat_sum["d_zero"] / cat_sum["papers"]).round(4)
        log("按 category 汇总（papers/ref_empty_rate/ref_avg/ref_median/indeg0_rate/d_nan_rate/d_zero_rate）：")
        log(cat_sum.sort_values("papers", ascending=False).to_string(index=False))

        # 按 journal（Top-N）汇总：优先用 paper_scores 里的 journal
        j_sum = (
            df0.groupby("_journal")
            .agg(
                papers=("_journal", "size"),
                ref_empty=("ref_count", lambda s: int((s == 0).sum())),
                ref_avg=("ref_count", "mean"),
                indeg0=("in_degree", lambda s: int((s == 0).sum())),
                d_nan=("_disruption", lambda s: int(pd.isna(s).sum())),
                d_zero=("_disruption", lambda s: int((s == 0).sum())),
            )
            .reset_index()
            .sort_values("papers", ascending=False)
        )
        j_sum["ref_empty_rate"] = (j_sum["ref_empty"] / j_sum["papers"]).round(4)
        j_sum["d_nan_rate"] = (j_sum["d_nan"] / j_sum["papers"]).round(4)
        j_sum["d_zero_rate"] = (j_sum["d_zero"] / j_sum["papers"]).round(4)
        top_n = max(0, int(top_n_journals))
        if top_n > 0:
            log(f"Top-{top_n} 期刊（按论文量）诊断：")
            log(j_sum.head(top_n).to_string(index=False))

        # token 碰撞诊断：node token（doi/title/pid）是否在样本内大量重复
        try:
            nodes = []
            for pid, attrs in (calculator.paper_attrs or {}).items():
                node = (attrs or {}).get("node")
                if node:
                    nodes.append(node)
            if nodes:
                node_s = pd.Series(nodes, name="node")
                dup = node_s.value_counts()
                dup = dup[dup > 1]
                if not dup.empty:
                    total = len(nodes)
                    dup_papers = int(dup.sum())
                    log("--- token 碰撞诊断（重要：会导致网络异常密集/指标偏高）---")
                    log(f"样本内 node token 总数: {total}")
                    log(f"发生重复的 node token 个数: {len(dup)}")
                    log(f"落在重复 node token 上的论文数: {dup_papers} ({dup_papers / total:.2%})")

                    title_dup = dup[dup.index.astype(str).str.startswith("title:")]
                    if not title_dup.empty:
                        log(f"其中 title token 重复个数: {len(title_dup)} | 涉及论文数: {int(title_dup.sum())}")
                        show_n = min(20, len(title_dup))
                        log(f"Top-{show_n} 重复 title token（截断显示）：")
                        for tok, cnt in title_dup.head(show_n).items():
                            # tok 可能很长，只显示前 80 字符
                            tshow = tok[:80] + ("..." if len(tok) > 80 else "") # type: ignore
                            log(f"  {cnt}\t{tshow}")
                else:
                    log("token 碰撞诊断：未发现 node token 重复")
        except Exception as e:
            log(f"token 碰撞诊断失败（不影响主流程）：{e}")

        # 高频引用 token：检查是否出现“期刊名/出版信息”被当作题名 token（会造成超级节点，抬高指标）
        try:
            if calculator.citation_network:
                # citation_network: token -> set(citing_pids)
                items = []
                for tok, citers in calculator.citation_network.items():
                    if not tok:
                        continue
                    # 这里只关心引用 token（doi:/title:）；node token 也会在图中出现，但它们通常不作为 ref_tok
                    if not (str(tok).startswith("doi:") or str(tok).startswith("title:")):
                        continue
                    items.append((str(tok), len(citers)))

                if items:
                    vc = pd.DataFrame(items, columns=["token", "citer_count"]).sort_values("citer_count", ascending=False)
                    topn = min(30, len(vc))
                    log(f"--- 高频引用 token Top-{topn}（按 citer_count）---")

                    journalish = re.compile(r"(学报|期刊|杂志|通讯|导报|工作|大学出版社|出版社)$")
                    for _, r in vc.head(topn).iterrows():
                        tok = r["token"]
                        cnt = int(r["citer_count"])
                        flag = ""
                        if tok.startswith("title:"):
                            title_text = tok[len("title:"):]
                            if journalish.search(title_text):
                                flag = " [疑似期刊/出版信息]"
                        tshow = tok[:90] + ("..." if len(tok) > 90 else "")
                        log(f"  {cnt}\t{tshow}{flag}")
        except Exception as e:
            log(f"高频引用token诊断失败（不影响主流程）：{e}")
    except Exception as e:
        log(f"诊断输出失败（不影响主流程）：{e}")


def export_participating_paper_counts(
    paper_scores: pd.DataFrame,
    *,
    exclude_zero_papers: bool,
    out_path: str | Path | None = None,
) -> pd.DataFrame:
    """导出每个期刊参与最终聚合的论文数。

    参与口径：与 calculate_enhanced_metrics 一致：先 dropna(disruption_index)，再按需排除 0。
    """
    if paper_scores is None or paper_scores.empty:
        df_out = pd.DataFrame(columns=["journal", "n_papers_participating"])  # type: ignore
    else:
        df0 = paper_scores.copy()
        if "disruption_index" in df0.columns:
            df0 = df0.dropna(subset=["disruption_index"])
            if exclude_zero_papers:
                df0 = df0[df0["disruption_index"] != 0]

        if df0.empty or "journal" not in df0.columns:
            df_out = pd.DataFrame(columns=["journal", "n_papers_participating"])  # type: ignore
        else:
            df_out = (
                df0.groupby("journal", dropna=False)
                .size()
                .rename("n_papers_participating")
                .reset_index()
                .sort_values("n_papers_participating", ascending=False)
                .reset_index(drop=True)
            )

    if out_path is None:
        out_path = _default_disrupt_outputs_dir() / "participating_paper_counts.csv"
    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    df_out.to_csv(out_path, index=False, encoding="utf-8-sig")
    log(f"已输出参与聚合论文数到: {out_path}")
    return df_out

# ===================== 期刊级聚合 =====================
def calculate_enhanced_metrics(df: pd.DataFrame, config: dict):
    params = config.get("parameters", {})
    top_k = params.get("top_k", 10)
    volume_weight = params.get("volume_weight", 0.4)
    exclude_zero_papers = bool(params.get("exclude_zero_papers", True))
    # 期刊级聚合策略：
    # - topk_mean: 取 Top-K disruption_index 均值（原默认，容易让大刊更占优）
    # - mean:      取全刊均值（方案B）
    # - median:    取全刊中位数（方案B，默认更稳健）
    agg = str(params.get("journal_aggregation", "mean")).strip().lower()
    min_participating = int(params.get("min_participating_papers", 5))

    if df.empty or "disruption_index" not in df.columns:
        return pd.DataFrame()

    df = df.dropna(subset=["disruption_index"])
    if exclude_zero_papers:
        df = df[df["disruption_index"] != 0]
    if df.empty:
        return pd.DataFrame()

    records = []
    for journal, group in df.groupby("journal"):
        n_papers = len(group)
        # 过滤“可计算论文太少”的期刊，避免单篇论文极值主导排序
        if min_participating > 0 and n_papers < min_participating:
            continue
        if agg == "topk_mean":
            k = min(int(top_k), n_papers)
            base = group.nlargest(k, "disruption_index")["disruption_index"].mean() if k > 0 else 0.0
        elif agg == "mean":
            base = group["disruption_index"].mean() if n_papers > 0 else 0.0
        else:
            # median (default)
            base = group["disruption_index"].median() if n_papers > 0 else 0.0

        log_n = np.log1p(n_papers) if n_papers > 0 else 1
        enhanced_score = (1 - volume_weight) * base + volume_weight * (base / log_n)
        records.append({"journal": journal, "n_papers": n_papers, "enhanced_score": enhanced_score})

    result = pd.DataFrame(records)
    return result.sort_values("enhanced_score", ascending=False).reset_index(drop=True)

# ===================== 对外核心 API =====================
def analyze_disruption(df_all: pd.DataFrame, *, top_n: int | None = None, config: dict | None = None) -> pd.DataFrame:
    if df_all.empty:
        raise ValueError("输入数据为空")
    if config is None:
        config = disrupt_config

    paper_scores, calculator = calculate_paper_scores(df_all, config)
    params = config.get("parameters", {})
    if bool(params.get("print_diagnostics", True)):
        _print_diagnostics(
            df_all,
            paper_scores,
            calculator,
            top_n_journals=int(params.get("diagnostics_top_n_journals", 15)),
        )

    # 输出：每个期刊参与最终聚合的论文数（排除 NaN/0 口径）
    if bool(params.get("export_participating_paper_counts", True)):
        export_participating_paper_counts(
            paper_scores,
            exclude_zero_papers=bool(params.get("exclude_zero_papers", True)),
        )
    journal_metrics = calculate_enhanced_metrics(paper_scores, config)
    if journal_metrics.empty:
        return journal_metrics

    # 先算原始百分制，再做“均匀化”末端映射到 1~100
    journal_metrics["percent_score_raw"] = (journal_metrics["enhanced_score"] * 100).round(2)
    journal_metrics["percent_score"] = _uniform_rank_to_1_100(
        journal_metrics["percent_score_raw"],
        tie_breaker=journal_metrics.get("journal"),
    ).round(2)
    journal_metrics = journal_metrics.sort_values("percent_score", ascending=False).reset_index(drop=True)
    if isinstance(top_n, int) and top_n > 0:
        journal_metrics = journal_metrics.head(top_n)
    return journal_metrics

if __name__ == "__main__":
    try:
        from pathlib import Path
        log("直接运行模式示例")
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
        result = analyze_disruption(df)
        log(str(result))
    except Exception as e:
        log(f"[错误] 程序执行失败: {e}")
        import traceback
        traceback.print_exc()