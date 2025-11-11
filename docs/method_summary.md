## 🧩 一、分析方法体系总览（针对“比较期刊内容差异”）

> 适用范围：仅分析 2021–2024 年的论文数据，限定在一个具体学科领域（如材料科学、教育学、人工智能等）。
> 目标：不是排名，而是揭示不同期刊的**内容差异与特色**。

我们要做的是从**期刊聚合层（journal-level）**分析，而非单篇论文。
所以所有指标最终都会汇总成 “期刊–年份–主题–指标”。

---

### 🎯 总体思路

| 类别     | 指标名称                                         | 目的                 | 所需数据                 | 是否已在老师评语中提及 |
| ------ | -------------------------------------------- | ------------------ | -------------------- | ----------- |
| 内容差异   | **主题分布差异（Shannon Entropy）**                  | 描述期刊是否专注于某些主题      | 每篇论文的主题分类结果          | ✅           |
| 内容引领性  | **主题引领性（Topic Leadness）**                    | 衡量期刊在新主题上的领先程度     | 主题首次出现时间             | ✅           |
| 内容新颖性  | **关键词年龄法（Novelty by Keyword Age）**           | 衡量期刊论文平均创新程度       | 每篇论文的关键词出现年份         | ✅           |
| 内容颠覆性  | **引用网络颠覆性指数（Disruption Index）**              | 衡量论文打破旧范式的程度       | 引文关系（引用/被引）          | ✅           |
| 内容跨学科性 | **跨学科指数（Interdisciplinarity via Diversity）** | 衡量期刊跨领域融合程度        | 主题或学科分类标签            | ✅           |
| 研究方法差异 | **方法偏好分布（Methodology Preference）**           | 对比期刊常用研究方法         | LLM 或 NER 提取的“方法关键词” | ✅           |
| 内容创新点  | **创新点抽取（Innovation Extraction）**             | 从语义上提取论文创新要素       | LLM 从摘要中抽取           | ✅           |
| 内容传播度  | **主题传播延迟（Topic Diffusion Delay）**            | 看某主题从A期刊到B期刊传播的时间差 | 各期刊中主题首次出现时间         | ✅           |
| 综合特征   | **期刊内容画像（Radar Profile）**                    | 多维展示期刊特征差异         | 上述各指标                | ✅           |

---

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
对每篇论文：

* 取其关键词集合 K；
* 查每个关键词在样本中首次出现的年份 (first(k))；
* 论文新颖性：
  [
  N_p = 1 - \frac{1}{|K|}\sum_k \frac{year_p - first(k)}{year_p - 2021 + 1}
  ]
  然后期刊新颖性 = 论文新颖性的平均值。

---

### 4️⃣ 内容颠覆性（Disruption Index）

**参考 Uzzi (Science, 2013)**
衡量论文是延续性（building）还是颠覆性（disruptive）。

**定义公式：**
[
D_p = \frac{N_i - N_j}{N_i + N_j + N_k}
]
其中：

* (N_i)：后续论文只引用该论文；
* (N_j)：后续论文同时引用该论文和它的参考文献；
* (N_k)：后续论文只引用该论文的参考文献。

取平均即期刊颠覆性。

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