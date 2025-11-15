
## 🧩 一、分析方法体系总览（针对“比较期刊内容差异”）

> 适用范围：仅分析 2010–2024 年的论文数据，限定在一个具体学科领域（如人工智能，biomedical）。
> 目标：不是排名，而是揭示不同期刊的**内容差异与特色**。

我们要做的是从**期刊聚合层（journal-level）**分析，而非单篇论文。
所以所有指标最终都会汇总成 “期刊–年份–主题–指标”。

爬取出来的总文档加载为df

## 📊 二、各指标计算逻辑（详细说明）

---

### 1️⃣ 主题分布差异（Topic Concentration / Shannon Entropy）

**定义：**
衡量一个期刊的主题是否集中或多样。

* 熵低：主题集中，有鲜明特色。
* 熵高：主题分散，内容广泛。

**计算公式：**
[
H_j = - \sum_i p_{ij} \log(p_{ij})
]
其中 (p_{ij}) 为期刊 (j) 在主题 (i) 上的论文占比。

**用途：** 主题越集中越有特色（但非绝对优劣）。

---

### 2️⃣ 主题引领性（Topic Leadness / Novel Topic Adoption）

**定义：**
衡量期刊对新主题的“敏感度”，即其论文在某主题上首次发表的时间相对其他期刊的领先程度。

**计算方式：**
对每个主题 (t)，找到：

* (year_{first}(t, j))：主题t在期刊j第一次出现的年份；
* (year_{first}(t, all))：全样本中该主题第一次出现的年份；
* 引领分数：
  [
  L_{tj} = year_{first}(t, all) - year_{first}(t, j)
  ]
  越大说明期刊越早关注此主题。

期刊总引领性 = 平均(L_tj) over all topics。

---

### 3️⃣ 内容新颖性（Novelty by Keyword Age）

**定义：**
一个期刊平均发表的论文，其关键词相对“年轻”说明创新性高。

**计算方式：**
对于每篇论文 P：
  关键词集合 K = {k₁, k₂, ..., kₙ}
  对于每个关键词 k，计算其年龄：age(k) = yearₚ - first_occurrence_year(k)
  
  论文新颖性得分：Nₚ = 1 - [∑ age(k) / |K|] / (yearₚ - 2010 + 1)
  
期刊新颖性 = 所有论文 Nₚ 的平均值

第一步：构建每篇论文的关键词表（每篇论文用ai从title、abstract、keywords提取5个，字段名：ai_keywords），存储在results_df.csv文件，位置data/analysis
第二步：收集关键词表的ai_keywords所有关键词，构建每个关键词的年龄表words_age
第三步：为每一篇论文计算关键词平均年龄放在在results_df文件后加一列averagea_age
第四步：以期刊journal聚类，求每个期刊论文的平均新颖性

### 4️⃣ 内容颠覆性（Disruption Index）

**参考 Uzzi (Science, 2013)**
衡量论文是延续性（building）还是颠覆性（disruptive）。

**定义公式：**
基于引文网络公式：
D=(n_i-n_j)/(n_i+n_j+n_k )
定义焦点论文及其参考文献（通过 DOI 关联引文数据）;
统计ni（仅引焦点论文的数量）、nj（引焦点论文 + 其参考文献的数量）、nk（仅引参考文献的数量）;
分组计算 D 值（D∈[-1,1]，值越高颠覆性越强），处理极端值（如剔除 D>1.5 倍四分位距的异常值）。

#### 注意：计算好的指标存储在data/analysis和data/metrics文件中，以csv格式
---

### 5️⃣ 跨学科指数（Interdisciplinarity Index）

**两种实现思路：**

1. **主题多样性熵法**：同上，用主题分布的熵衡量；
2. **引用/作者机构多领域法**：

   * 若论文引用多个不同学科的论文或作者来自不同学科；
   * 用香农熵或多样性指数计算。

[
I_p = -\sum_s p_s \log p_s
]
期刊跨学科性 = 平均(I_p)。

---

### 6️⃣ 方法偏好分布（Methodology Preference）

**定义：**
统计每篇论文中使用的研究方法（由LLM或NER抽取，如“实证分析”“模拟实验”“问卷调查”）。
对每个期刊计算方法占比向量。

**差异衡量：**

* 可用 KL 散度 或 Jensen-Shannon Divergence 比较两个期刊的分布差异。

[
JS(P||Q) = \frac{1}{2} (KL(P||M) + KL(Q||M)), \quad M = \frac{P+Q}{2}
]

---

### 7️⃣ 创新点抽取（Innovation Extraction）

**方法：**
用 LLM（或 fine-tuned 模型）读取论文摘要 → 抽取 1–3 个创新点（短语）。
再统计某期刊的创新点集中在哪些主题、技术或方法上。

**结果：**

* 可生成关键词云或创新点聚类图；
* 定量分析“创新方向分布差异”。

---

### 8️⃣ 主题传播延迟（Topic Diffusion Delay）

**定义：**
衡量主题从一个期刊扩散到另一个期刊的平均时间差。

[
Delay_{A→B} = mean_t (year_{first}(t,B) - year_{first}(t,A))
]
若 Delay 小，说明 B 跟进快；Delay 大，说明 A 是“引领者”。

---

### 9️⃣ 期刊综合画像（Radar Profile）

最终综合图，维度包括：

* 平均新颖性
* 平均颠覆性
* 主题引领性
* 主题专注度
* 方法多样性
* 跨学科指数
  → 用雷达图 / 气泡图展示中外期刊对比。

---


在 VSCode 中新建一个项目文件夹：

```
BankJournalAnalysis/
├─ data/
│  ├─ raw/          # 原始数据（如CSV、JSON）
│  ├─ cleaned/      # 清洗后数据
│  └─ metrics/      # 指标结果文件
├─ notebooks/
│  ├─ 01_data_cleaning.ipynb        # 数据清洗
│  ├─ 02_theme_extraction.ipynb     # 主题提取（LDA+LLM）
│  ├─ 03_indicator_calculation.ipynb # 各指标计算
│  ├─ 04_visualization.ipynb        # 雷达图 & 聚类
│  └─ 05_validation.ipynb           # 验证分析
├─ scripts/
│  ├─ cleaning.py
│  ├─ theme_model.py
│  ├─ metrics.py
│  ├─ visualization.py
│  └─ utils/
├─ sql/
│  ├─ schema.sql     # 建表语句
│  └─ queries.sql
├─ docs/
│  ├─ README.md
│  ├─ method_summary.md   # 指标体系文档（上面这份内容）
│  └─ data_dict.md        # 字段说明
├─ requirements.txt
└─ .gitignore
```
