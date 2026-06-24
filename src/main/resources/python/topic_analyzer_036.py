# -*- coding: utf-8 -*-
"""
topic_analyzer.py
跨学科性分析（香农熵方法）封装版
百分制得分 = 原始熵值 × 100
用户传入 DataFrame，返回期刊级结果
"""

import pandas as pd
import numpy as np
import ast
import re
import difflib
from collections import Counter

# ====================================================================
# 完整FOS词典（内置，无需配置）
# ====================================================================
FOS_dict = {
    "psychology": [
        "cognition", "cognitive", "executive function", "working memory",
        "memory retrieval", "attention", "selective attention",
        "decision making", "problem solving", "reasoning",
        "mental representation", "information processing",
        "cognitive control", "metacognition", "inhibition",
        "visual perception", "auditory perception", "language processing",
        "skill acquisition", "implicit learning", "explicit learning",
        "concept formation", "judgment", "mental imagery",
        "semantic processing", "episodic memory", "short-term memory",
        "neural", "neural basis", "neural processing", "brain activity",
        "neurocognition", "neuropsychology", "neurobehavioral",
        "prefrontal cortex", "hippocampus", "amygdala", "cortical",
        "neuroplasticity", "brain networks", "neuroimaging",
        "erp", "p300", "n400", "fmri", "eeg", "p600",
        "emotion", "emotional processing", "affect",
        "emotion regulation", "emotional arousal",
        "empathy", "mood", "affective response",
        "emotion recognition", "emotional cognition",
        "motivation", "intrinsic motivation", "extrinsic motivation",
        "goal orientation", "reward processing", "novelty seeking",
        "sensation seeking", "value processing", "self-efficacy",
        "creativity", "creative thinking", "creative cognition",
        "divergent thinking", "convergent thinking", "idea generation",
        "personality", "personality traits", "big five", "neuroticism",
        "extraversion", "openness", "agreeableness", "conscientiousness",
        "behavior", "behavioral response", "behavioral performance",
        "social cognition", "social interaction", "social influence",
        "developmental psychology", "child development",
        "clinical psychology", "mental health", "psychopathology",
        "depression", "anxiety", "stress", "trauma",
        "educational psychology", "learning motivation", "learning strategies",
    ],
    "neuroscience": [
        "brain", "neural", "neuron", "neural networks",
        "central nervous system", "cns", "neuroscience",
        "synaptic", "neuroplasticity", "neural pathway",
        "neural circuit", "neural dynamics", "neurophysiology",
        "dopamine", "serotonin", "norepinephrine", "acetylcholine",
        "glutamate", "gaba", "oxytocin", "vasopressin",
        "prefrontal cortex", "pfc", "orbitofrontal cortex", "ofc",
        "anterior cingulate cortex", "acc", "posterior cingulate cortex",
        "hippocampus", "amygdala", "insula", "basal ganglia",
        "striatum", "cerebellum", "thalamus", "hypothalamus",
        "synaptic plasticity", "long-term potentiation", "ltp",
        "long-term depression", "ltd", "signal transmission",
        "action potential", "spike train", "neural oscillation",
        "working memory", "executive function", "decision making",
        "reward processing", "attention network",
        "emotion regulation", "perception", "sensory processing",
        "eeg", "erp", "p300", "n400", "p600",
        "meg", "fmri", "bold signal", "pet scan",
        "neuroimaging", "diffusion tensor imaging", "dti",
        "ion channel", "synapse", "axon", "dendrite",
        "behavioral neuroscience", "neurobehavioral",
        "fear conditioning", "reinforcement learning",
        "computational model", "spiking model",
        "neural computation", "neural coding",
        "alzheimer", "parkinson", "adhd",
        "autism", "epilepsy", "schizophrenia",
    ],
    "computer_science": [
        "algorithm", "algorithms", "optimization", "approximation",
        "graph algorithm", "graph theory",
        "search algorithm", "sorting", "complexity",
        "data structure", "tree", "graph", "hashing",
        "machine learning", "supervised learning", "unsupervised learning",
        "reinforcement learning", "deep learning",
        "neural network", "neural networks",
        "convolutional neural network", "cnn",
        "recurrent neural network", "rnn", "transformer",
        "representation learning", "feature extraction",
        "classification", "regression", "clustering",
        "data mining", "data analysis", "data processing",
        "big data", "data visualization",
        "natural language processing", "nlp",
        "text mining", "text classification", "sentiment analysis",
        "language model", "word embedding", "transformer model",
        "computer vision", "image processing", "object detection",
        "image classification", "image recognition",
        "human computer interaction", "hci",
        "robotics", "autonomous system", "autonomous agents",
        "software engineering", "software architecture",
        "operating system", "distributed system",
        "parallel computing", "cloud computing",
        "computer network", "network protocol",
        "cybersecurity", "cryptography", "encryption",
        "simulation", "agent-based model",
        "computational model", "numerical simulation",
    ],
    "education": [
        "education", "educational practice", "educational research",
        "learning", "instruction", "teaching", "pedagogy",
        "instructional design", "curriculum design", "learning outcomes",
        "student performance", "academic performance",
        "learning behavior", "classroom environment",
        "learning process", "knowledge acquisition",
        "constructivism", "social constructivism",
        "experiential learning", "active learning",
        "collaborative learning", "problem-based learning",
        "self-directed learning", "self-regulated learning",
        "educational psychology", "motivation", "learning motivation",
        "self-efficacy", "goal orientation", "engagement",
        "assessment", "evaluation", "formative assessment",
        "summative assessment", "rubric", "performance assessment",
        "learning analytics", "measurement", "testing",
        "instructional method", "instructional strategy",
        "scaffolding", "differentiated instruction",
        "educational technology", "technology-enhanced learning",
        "digital learning", "online learning", "blended learning",
        "e-learning", "mobile learning", "virtual learning",
        "higher education", "tertiary education",
        "k-12 education", "primary education", "secondary education",
        "teacher education", "teacher training", "teacher development",
        "curriculum", "curriculum implementation",
        "educational policy", "education reform",
        "creative behavior", "creative learning",
    ],
    "biomedical_sciences": [
        "dopamine", "serotonin", "glutamate", "gaba", "acetylcholine",
        "genetics", "genomics", "epigenetics", "gene expression",
        "gene regulation", "transcription factor", "molecular pathway",
        "protein expression", "protein folding", "protein interaction",
        "biochemical", "biochemical pathway", "biomarker", "cytokine",
        "inflammation", "inflammatory response", "immune system",
        "immunity", "innate immunity", "adaptive immunity",
        "neural basis", "neural circuit", "neurobiological",
        "neurochemical", "neurophysiological", "synaptic plasticity",
        "synapse", "axon", "dendrite", "neural signaling",
        "cellular process", "cell culture",
        "cell proliferation", "cell differentiation", "stem cell",
        "neural stem cell", "neurogenesis",
        "oxidative stress", "mitochondria", "mitochondrial function",
        "apoptosis", "cell death", "autophagy",
        "endocrine", "hormone", "hormonal regulation",
        "cortisol", "testosterone", "estrogen",
        "neurodevelopmental", "developmental biology",
        "neurodegeneration", "neurodegenerative disease",
        "alzheimer's disease", "parkinson's disease",
        "schizophrenia", "depression", "mental disorder",
        "pharmacology", "drug response", "drug metabolism",
        "metabolism", "metabolic pathway", "lipid metabolism",
        "glucose metabolism", "metabolomics",
        "proteomics", "transcriptomics", "multiomics",
        "microbiome", "gut microbiota",
        "immune response", "cell signaling",
        "signal transduction", "receptor activation",
        "blood brain barrier", "neurovascular",
        "cerebral cortex", "hippocampus", "amygdala",
        "in vivo", "in vitro", "animal model",
        "mouse model", "rat model",
        "biostatistics", "epidemiology",
        "public health", "clinical research",
    ],
}

# ====================================================================
# 工具函数
# ====================================================================
def clean_author_keywords(keywords_str):
    # 检查是否为 None/NaN（处理标量和数组情况）
    if keywords_str is None or (isinstance(keywords_str, float) and pd.isna(keywords_str)):
        return []
    if isinstance(keywords_str, str):
        if keywords_str.startswith('[') and keywords_str.endswith(']'):
            try:
                return [kw.lower().strip() for kw in ast.literal_eval(keywords_str)]
            except Exception:
                pass
        return [kw.strip().lower() for kw in re.split(r'[,;]', keywords_str) if kw.strip()]
    elif isinstance(keywords_str, (list, set)):
        return [str(kw).strip().lower() for kw in keywords_str if str(kw).strip()]
    return []
    
def clean_text(text):
    # 检查是否为 None/NaN（处理标量和数组情况）
    if text is None or (isinstance(text, float) and pd.isna(text)):
        return ""
    text = str(text).lower()
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"\d+", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text

def extract_keywords_from_text(text, min_length=3, max_keywords=20):
    if not text:
        return []
    words = text.split()
    stop_words = {
        'the', 'and', 'for', 'with', 'that', 'this', 'these', 'those',
        'from', 'have', 'has', 'had', 'were', 'was', 'are', 'is',
        'be', 'been', 'being', 'by', 'in', 'on', 'at', 'to', 'of',
        'a', 'an', 'as', 'or', 'but', 'not', 'it', 'its', 'they',
        'them', 'their', 'we', 'our', 'you', 'your', 'he', 'she',
        'his', 'her', 'its', 'my', 'mine', 'us', 'our', 'ours'
    }
    keywords = [w.lower() for w in words if w.isalpha() and len(w) >= min_length and w not in stop_words]
    counts = Counter(keywords)
    return [k for k, _ in counts.most_common(max_keywords)]

# 全局缓存，用于加速 map_keyword_to_fields 的重复查询
_keyword_to_fields_cache = {}

def map_keyword_to_fields(keyword, field_dict, use_cache=True):
    """
    映射关键词到多个研究领域（带缓存优化）
    
    Args:
        keyword: 输入关键词
        field_dict: 领域词典
        use_cache: 是否使用缓存（默认开启以加速）
    
    Returns:
        匹配的领域列表
    """
    keyword = keyword.lower().strip()
    
    # 检查缓存
    if use_cache and keyword in _keyword_to_fields_cache:
        return _keyword_to_fields_cache[keyword]
    
    matched_fields = []
    
    # 第一层：精确匹配（速度快）
    for field, words in field_dict.items():
        if keyword in words:
            matched_fields.append(field)
    
    if matched_fields:
        result = list(set(matched_fields))
        if use_cache:
            _keyword_to_fields_cache[keyword] = result
        return result
    
    # 第二层：模糊匹配（仅限长度相近的词，提高性能）
    # 只对长度相差不超过3的词进行模糊匹配
    keyword_len = len(keyword)
    for field, words in field_dict.items():
        for w in words:
            w_len = len(w)
            # 长度过差异则跳过模糊匹配（提高性能）
            if abs(keyword_len - w_len) > 3:
                continue
            try:
                if difflib.SequenceMatcher(None, keyword, w).ratio() >= 0.75:
                    matched_fields.append(field)
                    break
            except Exception:
                # 如果相似度计算异常，直接跳过
                continue
    
    result = list(set(matched_fields))
    if use_cache:
        _keyword_to_fields_cache[keyword] = result
    return result

def field_distribution(keyword_list, field_dict):
    """计算关键词列表在各领域的分布"""
    counter = Counter()
    for kw in keyword_list:
        try:
            for f in map_keyword_to_fields(kw, field_dict, use_cache=True):
                counter[f] += 1
        except Exception:
            # 如果处理某个关键词出错，跳过该关键词
            continue
    
    total = sum(counter.values())
    if total == 0:
        return {}, {}
    counts = dict(counter)
    shares = {f: c / total for f, c in counts.items()}
    return counts, shares

def calculate_shannon_entropy(shares_dict):
    if not shares_dict:
        return 0.0
    ps = np.array([p for p in shares_dict.values() if p > 0.0], dtype=float)
    if ps.size == 0:
        return 0.0
    ps /= ps.sum()
    return float(-np.sum(ps * np.log2(ps)))

def calculate_percent_score(entropy):
    return round(entropy * 100, 1)


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

# ====================================================================
# 核心封装函数
# ====================================================================
def analyze_topic_entropy(df: pd.DataFrame,
                          top_n: int | None = None,
                          *,
                          id_col="doi",
                          journal_col="journal",
                          keywords_col="keywords") -> pd.DataFrame:
    """
    跨学科性分析（香农熵方法）
    【仅使用作者关键词 keywords】
    """
    results = []

    for idx, row in df.iterrows():
        paper_id = str(row.get(id_col, f"paper_{idx}"))
        journal = row.get(journal_col, "Unknown")

        # ✅ 只用作者关键词
        terms = clean_author_keywords(row.get(keywords_col))

        field_counts, field_shares = field_distribution(terms, FOS_dict)
        entropy = calculate_shannon_entropy(field_shares)

        results.append({
            "paper_id": paper_id,
            "journal": journal,
            "entropy": entropy,
            "field_count": len(field_counts),
            "term_count": len(terms)
        })

    paper_df = pd.DataFrame(results)

    journal_agg = paper_df.groupby("journal").agg({
        "entropy": "mean",
        "field_count": "mean",
        "paper_id": "count"
    }).reset_index()

    journal_agg.columns = ["journal", "entropy_mean", "avg_field_count", "paper_count"]
    journal_agg["percent_score_raw"] = journal_agg["entropy_mean"].apply(calculate_percent_score)
    journal_agg["percent_score"] = _uniform_rank_to_1_100(
        journal_agg["percent_score_raw"],
        tie_breaker=journal_agg["journal"],
    ).round(1)

    journal_agg = journal_agg.sort_values("percent_score", ascending=False).reset_index(drop=True)

    if isinstance(top_n, int) and top_n > 0:
        journal_agg = journal_agg.head(top_n)

    return journal_agg

# =======================
# 本地调试
# =======================
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
    result = analyze_topic_entropy(df, top_n=None)  # top_n=None 返回全部期刊
    print(result)
