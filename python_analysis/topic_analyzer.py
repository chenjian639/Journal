# -*- coding: utf-8 -*-
"""
python_analysis/topic_analyzer.py
跨学科性分析（香农熵方法）- 完整版
百分制得分 = 原始熵值 × 100 × 5
输出：得分列表 + 百分制得分柱状图
"""
import json
import pandas as pd
import numpy as np
import ast
import re
import difflib
import matplotlib.pyplot as plt
from pathlib import Path
from collections import Counter
import warnings
warnings.filterwarnings('ignore')

# 设置中文字体
import matplotlib.font_manager as fm
try:
    font_path = "C:/Windows/Fonts/simhei.ttf"
    if Path(font_path).exists():
        fm.fontManager.addfont(font_path)
        font_name = fm.FontProperties(fname=font_path).get_name()
        plt.rcParams['font.sans-serif'] = [font_name]
    plt.rcParams['axes.unicode_minus'] = False
except:
    plt.rcParams['font.sans-serif'] = ['SimHei']
    plt.rcParams['axes.unicode_minus'] = False

def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent.parent / 'config.json'
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config.get("topic", {})

def log(msg):
    """简单的日志函数"""
    print(f"[topic] {msg}")

# ============================================================================
#  完整的领域分类字典（使用完整的字典）
# ============================================================================
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

# ============================================================================
#  关键词处理函数
# ============================================================================
def clean_author_keywords(keywords_str):
    """清洗作者关键词"""
    if pd.isna(keywords_str):
        return []
    
    if isinstance(keywords_str, str):
        # 处理列表格式
        if keywords_str.startswith('[') and keywords_str.endswith(']'):
            try:
                return ast.literal_eval(keywords_str)
            except:
                pass
        
        # 处理字符串格式
        keywords = re.split(r'[,;]', keywords_str)
        cleaned_keywords = []
        for kw in keywords:
            kw = kw.strip().lower()
            if kw:
                cleaned_keywords.append(kw)
        return cleaned_keywords
    
    return []

def clean_text(text):
    """清洗文本"""
    if pd.isna(text):
        return ""
    
    text = text.lower()
    text = re.sub(r"http\S+|www\S+", "", text)
    text = re.sub(r"\d+", "", text)
    text = re.sub(r"[^\w\s]", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    
    return text

def extract_keywords_from_text(text, min_length=3, max_keywords=20):
    """从文本中提取关键词"""
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
    
    keywords = []
    for word in words:
        word_lower = word.lower()
        if (len(word_lower) >= min_length and 
            word_lower not in stop_words and
            word_lower.isalpha()):
            keywords.append(word_lower)
    
    word_counts = Counter(keywords)
    top_keywords = [word for word, _ in word_counts.most_common(max_keywords)]
    
    return top_keywords

def map_keyword_to_fields(keyword, field_dict):
    """映射关键词到领域"""
    keyword = keyword.lower().strip()
    
    # 精确匹配
    matched_fields = []
    for field, words in field_dict.items():
        if keyword in words:
            matched_fields.append(field)
    
    if matched_fields:
        return list(set(matched_fields))
    
    # 模糊匹配
    for field, words in field_dict.items():
        for w in words:
            ratio = difflib.SequenceMatcher(None, keyword, w).ratio()
            if ratio >= 0.75:  # 降低阈值以提高匹配率
                matched_fields.append(field)
                break
    
    return list(set(matched_fields))

def field_distribution(keyword_list, field_dict):
    """计算领域分布"""
    field_counter = Counter()

    for kw in keyword_list:
        fields = map_keyword_to_fields(kw, field_dict)
        for f in fields:
            field_counter[f] += 1
    
    total = sum(field_counter.values())
    if total == 0:
        return {}, {}
    
    counts = dict(field_counter)
    shares = {f: count/total for f, count in counts.items()}
    
    return counts, shares

def calculate_shannon_entropy(shares_dict):
    """计算香农熵"""
    if not shares_dict:
        return 0.0
    
    ps = np.array([p for p in shares_dict.values() if p > 0.0], dtype=float)
    if ps.size == 0:
        return 0.0
    
    ps = ps / ps.sum()
    entropy = -np.sum(ps * np.log2(ps))
    
    return float(entropy)

def calculate_percent_score(entropy):
    """计算百分制得分：原始熵值 × 100 × 5"""
    percent_score = entropy * 100 * 5
    return round(percent_score, 1)

# ============================================================================
#  主分析器类
# ============================================================================
class InterdisciplinaryEntropyAnalyzer:
    def __init__(self, config=None):
        self.config = config or load_config()
        
        # 从配置获取术语来源设置
        self.term_source = self.config.get('parameters', {}).get('term_source', 'keywords')
        
        # 创建输出目录
        output_dir_key = 'topic_dir'
        if output_dir_key not in self.config.get('output', {}):
            output_dir_key = 'topic_dir'
        
        output_dir = Path(self.config['output'][output_dir_key])
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = output_dir
        
        log(f"输出目录: {self.output_dir}")
        log(f"术语来源: {self.term_source}")

    def extract_terms_from_paper(self, row):
        """从单篇论文中提取术语"""
        terms = []
        
        # 从关键词提取
        if self.term_source in ['keywords', 'both']:
            keywords_col = self.config['columns']['keywords'] if 'keywords' in self.config['columns'] else 'Keywords'
            if keywords_col in row:
                author_keywords = clean_author_keywords(row[keywords_col])
                terms.extend(author_keywords)
        
        # 从摘要提取
        if self.term_source in ['abstract', 'both']:
            if 'Abstract' in row:
                clean_abstract = clean_text(row['Abstract'])
                abstract_keywords = extract_keywords_from_text(clean_abstract, max_keywords=15)
                terms.extend(abstract_keywords)
        
        # 去重并返回
        unique_terms = list(set(terms))
        return unique_terms

    def run_analysis(self):
        """运行分析"""
        try:
            log("=" * 50)
            log("开始期刊跨学科性分析（香农熵方法）")
            log("=" * 50)
            
            # 加载数据
            project_root = Path(__file__).parent.parent
            target_path = project_root / self.config['data_sources']['target_data']
            
            log(f"加载数据: {target_path}")
            target_df = pd.read_csv(target_path)
            log(f"数据形状: {target_df.shape}")
            
            # 获取列名
            id_col = self.config['columns']['id']
            journal_col = self.config['columns']['journal']
            
            log(f"使用列: ID={id_col}, 期刊={journal_col}")
            
            # 计算每篇论文的熵值
            log("\n📊 计算论文熵值...")
            results = []
            
            total_papers = len(target_df)
            for idx, row in target_df.iterrows():
                paper_id = str(row[id_col]) if pd.notna(row.get(id_col)) else f"paper_{idx}"
                journal = row[journal_col] if pd.notna(row.get(journal_col)) else "Unknown"
                
                # 提取术语
                terms = self.extract_terms_from_paper(row)
                
                # 计算领域分布
                field_counts, field_shares = field_distribution(terms, FOS_dict)
                
                # 计算香农熵
                entropy = calculate_shannon_entropy(field_shares)
                
                results.append({
                    'paper_id': paper_id,
                    'journal': journal,
                    'entropy': entropy,
                    'field_count': len(field_counts),
                    'term_count': len(terms)
                })
                
                # 进度显示
                if (idx + 1) % 100 == 0 or (idx + 1) == total_papers:
                    progress = (idx + 1) / total_papers * 100
                    log(f"进度: {idx + 1}/{total_papers} ({progress:.1f}%)")
            
            paper_df = pd.DataFrame(results)
            log(f"论文计算完成，共 {len(paper_df)} 篇论文")
            log(f"平均每篇论文术语数: {paper_df['term_count'].mean():.1f}")
            log(f"平均每篇论文领域数: {paper_df['field_count'].mean():.1f}")
            
            # 按期刊聚合
            log("\n📈 按期刊聚合...")
            journal_agg = paper_df.groupby('journal').agg({
                'entropy': 'mean',
                'field_count': 'mean',
                'paper_id': 'count'
            }).reset_index()
            
            journal_agg.columns = ['期刊名称', '原始熵值', '平均领域数', '论文数量']
            
            # 计算百分制得分：原始熵值 × 100 × 5
            log("🎯 计算百分制得分...")
            journal_agg['百分制得分'] = journal_agg['原始熵值'].apply(calculate_percent_score)
            
            # 按百分制得分排序
            journal_agg = journal_agg.sort_values('百分制得分', ascending=False).reset_index(drop=True)
            
            # 添加排名
            journal_agg.insert(0, '排名', range(1, len(journal_agg) + 1))
            
            # 输出统计信息
            log(f"\n📊 得分统计:")
            log(f"  原始熵值范围: {journal_agg['原始熵值'].min():.4f} - {journal_agg['原始熵值'].max():.4f}")
            log(f"  原始熵值均值: {journal_agg['原始熵值'].mean():.4f}")
            log(f"  百分制得分范围: {journal_agg['百分制得分'].min():.1f} - {journal_agg['百分制得分'].max():.1f}")
            log(f"  百分制得分均值: {journal_agg['百分制得分'].mean():.1f}")
            log(f"  总期刊数: {len(journal_agg)}")
            
            # 输出文件
            self.generate_outputs(journal_agg)
            
            log("\n✅ 分析完成！")
            log(f"📁 输出文件:")
            log(f"  1. journal_entropy_scores.csv - 期刊熵值得分列表")
            log(f"  2. journal_entropy_percent_chart.png - 百分制得分柱状图")
            
            return journal_agg
            
        except Exception as e:
            log(f"错误: {e}")
            import traceback
            traceback.print_exc()

    def generate_outputs(self, journal_data):
        """生成输出文件"""
        # 1. 保存CSV文件
        csv_path = self.output_dir / "journal_entropy_scores.csv"
        
        # 格式化输出
        output_df = journal_data.copy()
        output_df['原始熵值'] = output_df['原始熵值'].round(4)
        output_df['平均领域数'] = output_df['平均领域数'].round(2)
        output_df['百分制得分'] = output_df['百分制得分'].round(1)
        
        output_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        log(f"📄 得分列表已保存: {csv_path}")
        
        # 2. 生成美观的柱状图
        self.create_beautiful_chart(journal_data)

    def create_beautiful_chart(self, data):
        """创建美观的百分制得分柱状图"""
        if len(data) == 0:
            log("没有数据可生成图表")
            return
        
        # 设置图表尺寸
        n_journals = len(data)
        fig_height = max(6, n_journals * 0.35)
        fig, ax = plt.subplots(figsize=(14, fig_height))
        
        # 使用渐变色
        colors = plt.cm.plasma(np.linspace(0.2, 0.9, n_journals))
        
        # 创建水平柱状图
        y_positions = np.arange(n_journals)
        bars = ax.barh(y_positions, data['百分制得分'], 
                      color=colors, 
                      alpha=0.85,
                      height=0.7,
                      edgecolor='white',
                      linewidth=1.5)
        
        # 添加数值标签
        for i, (bar, percent_score, journal_name, paper_count, raw_score) in enumerate(
            zip(bars, data['百分制得分'], data['期刊名称'], data['论文数量'], data['原始熵值'])):
            
            # 百分制得分标签（右侧）
            label_x = bar.get_width() + max(data['百分制得分']) * 0.02
            ax.text(label_x, bar.get_y() + bar.get_height()/2,
                   f'{percent_score:.1f}分', 
                   ha='left', va='center',
                   fontsize=10, fontweight='bold',
                   color='#2c3e50',
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
            
            # 在柱子左侧显示期刊名称和排名
            short_name = journal_name[:28] + "..." if len(journal_name) > 28 else journal_name
            rank_text = f"{i+1}. {short_name}"
            ax.text(-max(data['百分制得分']) * 0.02, bar.get_y() + bar.get_height()/2,
                   rank_text,
                   ha='right', va='center',
                   fontsize=9.5, fontweight='medium',
                   color='#34495e')
            
            # 在柱子内部显示论文数量和原始熵值
            if bar.get_width() > max(data['百分制得分']) * 0.1:
                inner_text = f"{paper_count}篇\n{raw_score:.3f}"
                ax.text(bar.get_width()/2, bar.get_y() + bar.get_height()/2,
                       inner_text,
                       ha='center', va='center',
                       fontsize=8, color='white',
                       fontweight='bold')
        
        # 设置y轴
        ax.set_yticks(y_positions)
        ax.set_yticklabels([])
        
        # 设置x轴
        ax.set_xlabel('百分制得分 ', fontsize=11, fontweight='bold', color='#2c3e50')
        
        # 动态设置x轴范围
        max_score = max(data['百分制得分'])
        ax.set_xlim([0, max_score * 1.15])
        
        # 设置标题
        title_source = {
            'keywords': '关键词',
            'abstract': '摘要',
            'both': '关键词+摘要'
        }.get(self.term_source, self.term_source)
        
        ax.set_title(f'期刊复杂度排名 - 基于{title_source}的香农熵分析', 
                    fontsize=14, fontweight='bold', pad=20, color='#2c3e50')
        
        # 美化样式
        ax.spines['top'].set_visible(False)
        ax.spines['right'].set_visible(False)
        ax.spines['left'].set_visible(False)
        ax.spines['bottom'].set_color('#95a5a6')
        
        # 网格线
        ax.grid(axis='x', linestyle='--', alpha=0.25, color='#bdc3c7')
        
        # 反转y轴（从高到低）
        ax.invert_yaxis()
        
        # 背景色
        ax.set_facecolor('#f8f9fa')
        fig.patch.set_facecolor('white')
        
        # 刻度线
        ax.tick_params(axis='x', colors='#7f8c8d')
        ax.tick_params(axis='y', length=0)
        
        # 添加公式说明
        formula_text = "得分公式: 百分制得分 = 原始熵值 × 100"
        ax.text(0.5, -0.05, formula_text,
               transform=ax.transAxes,
               ha='center', va='center',
               fontsize=9, style='italic',
               color='#7f8c8d')
        
        # 调整布局
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.12)
        
        # 保存图片
        img_path = self.output_dir / "journal_entropy_percent_chart.png"
        plt.savefig(img_path, dpi=300, bbox_inches='tight', 
                    facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        
        log(f"📊 柱状图已保存: {img_path}")

# ============================================================================
#  主函数
# ============================================================================
def main():
    try:
        analyzer = InterdisciplinaryEntropyAnalyzer()
        results = analyzer.run_analysis()
        
        # 显示结果
        if results is not None and len(results) > 0:
            print("\n" + "="*80)
            print("期刊跨学科性得分）")
            print("="*80)
            print(f"{'排名':^4} | {'期刊名称':^40} | {'百分制得分':^12} | {'原始熵值':^10} | {'论文数':^8}")
            print("-"*80)
            
            for i, row in results.iterrows():
                journal_name = row['期刊名称']
                if len(journal_name) > 38:
                    journal_name = journal_name[:35] + "..."
                
                print(f"{row['排名']:^4} | {journal_name:^40} | {row['百分制得分']:^12.1f} | "
                      f"{row['原始熵值']:^10.4f} | {row['论文数量']:^8}")
            
            print("="*80)
            
            # 显示前5名详细信息
            print(f"\n🏆 Top 5 期刊详情:")
            for i, row in results.head(5).iterrows():
                print(f"{row['排名']}. {row['期刊名称']}")
                print(f"   百分制得分: {row['百分制得分']:.1f} | 原始熵值: {row['原始熵值']:.4f} | "
                      f"论文数: {row['论文数量']} | 平均领域数: {row['平均领域数']:.2f}")
                print()
            
    except Exception as e:
        print(f"程序错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()