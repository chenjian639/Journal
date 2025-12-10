# -*- coding: utf-8 -*-
"""
python_analysis/novelty_analyzer.py
<<<<<<< HEAD
期刊新颖性指数分析系统 - 修正版
百分制得分 = 新颖性得分 × 600
输出：新颖性得分列表 + 百分制得分柱状图
"""
import json
import pandas as pd
import numpy as np
import ast
import matplotlib.pyplot as plt
from pathlib import Path
from collections import defaultdict, Counter
from itertools import combinations

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
    config_path = Path(__file__).resolve().parent.parent / 'config.json'
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config.get("novelty", {})

def log(msg):
    print(f"[novelty] {msg}")

def clean_keywords(keywords_str):
    """清洗关键词"""
    if pd.isna(keywords_str):
        return []
    
    if isinstance(keywords_str, str):
        if keywords_str.startswith('[') and keywords_str.endswith(']'):
            try:
                return ast.literal_eval(keywords_str)
            except:
                pass
        
        # 按分隔符分割
        separators = [';', ',', '|', '、']
        for sep in separators:
            if sep in keywords_str:
                return [k.strip().lower() for k in keywords_str.split(sep) if k.strip()]
        
        return [keywords_str.strip().lower()]
    
    return []

def calculate_percent_score(novelty_score):
    """计算百分制得分：新颖性得分 × 600"""
    if pd.isna(novelty_score):
        return 0.0
    percent_score = novelty_score * 600
    return percent_score  # 保留原始小数位数

class NoveltyAnalyzer:
    def __init__(self, config=None):
        self.config = config or load_config()
        
        # 创建输出目录
        output_dir = Path(self.config['output']['novelty_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = output_dir

    def run_analysis(self):
        """运行新颖性分析"""
        try:
            log("=" * 50)
            log("开始期刊新颖性分析（Uzzi组合方法）")
            log("=" * 50)
            
            # 加载数据
            project_root = Path(__file__).resolve().parent.parent
            data_config = self.config.get('data_sources', {})
            
            # 加载背景数据（构建时间线）
            bg_path = project_root / data_config['all_data']
            tg_path = project_root / data_config['target_data']
            
            log(f"📂 加载数据...")
            log(f"  背景数据: {bg_path}")
            log(f"  目标数据: {tg_path}")
            
            background_df = pd.read_csv(bg_path)
            target_df = pd.read_csv(tg_path)
            
            # 获取列名
            id_col = self.config['columns']['id']
            journal_col = self.config['columns']['journal']
            keywords_col = self.config['columns']['keywords']
            year_col = self.config['columns']['year']
            
            log(f"使用列: ID={id_col}, 期刊={journal_col}, 关键词={keywords_col}, 年份={year_col}")
            
            # 阶段1: 使用背景数据构建关键词对时间线
            log("\n📊 构建关键词对时间线（背景数据）...")
            bg_pair_timeline = self._build_pair_timeline(background_df, id_col, keywords_col, year_col)
            
            # 阶段2: 计算目标数据的新颖性
            log("🎯 计算目标期刊新颖性...")
            journal_scores = self._calculate_target_novelty(target_df, bg_pair_timeline, 
                                                          id_col, journal_col, keywords_col, year_col)
            
            # 阶段3: 计算百分制得分
            log("📈 计算百分制得分...")
            for journal in journal_scores:
                if 'novelty_score' in journal_scores[journal]:
                    raw_score = journal_scores[journal]['novelty_score']
                    journal_scores[journal]['percent_score'] = calculate_percent_score(raw_score)
            
            # 生成输出文件
            self.generate_outputs(journal_scores)
            
            log("\n✅ 分析完成！")
            log(f"📁 输出文件:")
            log(f"  1. journal_novelty_scores.csv - 期刊新颖性得分列表")
            log(f"  2. journal_novelty_percent_chart.png - 百分制得分柱状图")
            
            return journal_scores
            
        except Exception as e:
            log(f"错误: {e}")
            import traceback
            traceback.print_exc()

    def _build_pair_timeline(self, df, id_col, keywords_col, year_col):
        """构建关键词对首次出现时间线"""
        pair_year = defaultdict(lambda: float('inf'))
        
        for idx, row in df.iterrows():
            paper_id = str(row[id_col]) if pd.notna(row.get(id_col)) else f"paper_{idx}"
            
            # 获取关键词
            keywords = []
            if keywords_col in row and pd.notna(row[keywords_col]):
                keywords = clean_keywords(row[keywords_col])
            
            if len(keywords) < 2:
                continue
            
            # 获取年份
            if year_col in row and pd.notna(row[year_col]):
                try:
                    year = int(float(row[year_col]))
                except:
                    continue
            else:
                continue
            
            # 生成所有关键词对
            for pair in combinations(keywords, 2):
                norm_pair = tuple(sorted(pair))
                if year < pair_year[norm_pair]:
                    pair_year[norm_pair] = year
        
        log(f"时间线构建完成: {len(pair_year)} 个关键词对")
        return dict(pair_year)

    def _calculate_target_novelty(self, df, pair_timeline, id_col, journal_col, keywords_col, year_col):
        """计算目标数据的新颖性"""
        # 从配置获取参数
        threshold_years = self.config.get('parameters', {}).get('novel_threshold_years', 1)
        
        # 确定当前年份（使用目标数据的最新年份）
        current_year = df[year_col].max() if year_col in df.columns else pd.Timestamp.now().year
        if pd.isna(current_year):
            current_year = pd.Timestamp.now().year
        else:
            current_year = int(current_year)
        
        log(f"新颖性参数: 阈值={threshold_years}年, 基准年份={current_year}")
        
        # 按论文计算新颖性
        paper_results = []
        journal_results = defaultdict(lambda: {'scores': [], 'paper_count': 0})
        
        for idx, row in df.iterrows():
            paper_id = str(row[id_col]) if pd.notna(row.get(id_col)) else f"paper_{idx}"
            journal = row[journal_col] if pd.notna(row.get(journal_col)) else "Unknown"
            
            # 获取关键词
            keywords = []
            if keywords_col in row and pd.notna(row[keywords_col]):
                keywords = clean_keywords(row[keywords_col])
            
            if len(keywords) < 2:
                continue
            
            # 生成所有关键词对并计算新颖性
            pairs = list(combinations(keywords, 2))
            novel_pairs = 0
            
            for pair in pairs:
                norm_pair = tuple(sorted(pair))
                first_year = pair_timeline.get(norm_pair)
                
                # 判断是否新颖：从未出现过或出现时间很近
                if first_year is None or (current_year - first_year) <= threshold_years:
                    novel_pairs += 1
            
            # 计算新颖性得分
            if pairs:
                score = novel_pairs / len(pairs)
                paper_results.append({
                    'paper_id': paper_id,
                    'journal': journal,
                    'novelty_score': score,
                    'keyword_count': len(keywords),
                    'novel_pairs': novel_pairs,
                    'total_pairs': len(pairs)
                })
                
                # 按期刊聚合
                journal_results[journal]['scores'].append(score)
                journal_results[journal]['paper_count'] += 1
        
        # 计算期刊平均新颖性
        journal_scores = {}
        for journal, data in journal_results.items():
            if data['scores']:
                journal_scores[journal] = {
                    'novelty_score': np.mean(data['scores']),
                    'paper_count': data['paper_count'],
                    'score_std': np.std(data['scores']) if len(data['scores']) > 1 else 0
                }
        
        log(f"新颖性计算完成: {len(paper_results)} 篇论文, {len(journal_scores)} 种期刊")
        return journal_scores

    def generate_outputs(self, journal_scores):
        """生成输出文件"""
        if not journal_scores:
            log("警告: 没有计算到期刊新颖性得分")
            return
        
        # 1. 创建得分列表DataFrame
        score_list = []
        for journal, scores in journal_scores.items():
            percent_score = scores.get('percent_score', 0)
            score_list.append({
                '期刊名称': journal,
                '新颖性得分': scores['novelty_score'],  # 保留原始小数位数
                '百分制得分': percent_score,  # 保留原始小数位数
                '论文数量': scores['paper_count'],
                '得分标准差': scores.get('score_std', 0)
            })
        
        score_df = pd.DataFrame(score_list)
        score_df = score_df.sort_values('百分制得分', ascending=False).reset_index(drop=True)
        score_df.insert(0, '排名', range(1, len(score_df) + 1))
        
        # 保存CSV（不格式化，保留原始小数位数）
        csv_path = self.output_dir / "journal_novelty_scores.csv"
        score_df.to_csv(csv_path, index=False, encoding="utf-8-sig")
        log(f"📄 得分列表已保存: {csv_path}")
        
        # 2. 生成美观的百分制得分柱状图
        self.create_percent_chart(score_df)

    def create_percent_chart(self, data):
        """创建美观的百分制得分柱状图"""
        if len(data) == 0:
            log("没有数据可生成图表")
            return
        
        # 设置图表尺寸（根据期刊数量调整高度）
        n_journals = len(data)
        fig_height = max(6, n_journals * 0.35)
        fig, ax = plt.subplots(figsize=(14, fig_height))
        
        # 使用渐变色（橙色系，适合创新主题）
        colors = plt.cm.autumn(np.linspace(0.3, 0.9, n_journals))
        
        # 创建水平柱状图
        y_positions = np.arange(n_journals)
        bars = ax.barh(y_positions, data['百分制得分'], 
                      color=colors, 
                      alpha=0.85,
                      height=0.7,
                      edgecolor='white',
                      linewidth=1.5)
        
        # 添加数值标签
        max_percent = max(data['百分制得分'])
        for i, (bar, percent_score, journal_name, paper_count, raw_score) in enumerate(
            zip(bars, data['百分制得分'], data['期刊名称'], data['论文数量'], data['新颖性得分'])):
            
            # 百分制得分标签（右侧）
            label_x = bar.get_width() + max_percent * 0.02
            ax.text(label_x, bar.get_y() + bar.get_height()/2,
                   f'{percent_score:.1f}分', 
                   ha='left', va='center',
                   fontsize=10, fontweight='bold',
                   color='#2c3e50',
                   bbox=dict(boxstyle='round,pad=0.2', facecolor='white', alpha=0.8))
            
            # 在柱子左侧显示期刊名称和排名
            short_name = journal_name[:28] + "..." if len(journal_name) > 28 else journal_name
            rank_text = f"{i+1}. {short_name}"
            ax.text(-max_percent * 0.02, bar.get_y() + bar.get_height()/2,
                   rank_text,
                   ha='right', va='center',
                   fontsize=9.5, fontweight='medium',
                   color='#34495e')
            
            # 在柱子内部显示论文数量和原始新颖性得分
            if bar.get_width() > max_percent * 0.1:
                inner_text = f"{paper_count}篇\n{raw_score:.4f}"
                ax.text(bar.get_width()/2, bar.get_y() + bar.get_height()/2,
                       inner_text,
                       ha='center', va='center',
                       fontsize=8, color='white',
                       fontweight='bold')
        
        # 设置y轴
        ax.set_yticks(y_positions)
        ax.set_yticklabels([])
        
        # 设置x轴
        ax.set_xlabel('百分制得分 (分)', fontsize=11, fontweight='bold', color='#2c3e50')
        
        # 动态设置x轴范围
        max_score = max(data['百分制得分'])
        ax.set_xlim([0, max_score * 1.15])
        
        # 设置标题
        ax.set_title('期刊新颖性排名 - 百分制得分 (得分 = 新颖性得分 × 100)', 
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
        formula_text = "得分公式: 百分制得分 = 新颖性得分 × 100"
        ax.text(0.5, -0.05, formula_text,
               transform=ax.transAxes,
               ha='center', va='center',
               fontsize=9, style='italic',
               color='#7f8c8d')
        
        # 调整布局
        plt.tight_layout()
        plt.subplots_adjust(bottom=0.12)
        
        # 保存图片
        img_path = self.output_dir / "journal_novelty_percent_chart.png"
        plt.savefig(img_path, dpi=300, bbox_inches='tight', 
                    facecolor=fig.get_facecolor(), edgecolor='none')
        plt.close()
        
        log(f"📊 百分制得分柱状图已保存: {img_path}")

def main():
    try:
        analyzer = NoveltyAnalyzer()
        results = analyzer.run_analysis()
        
        # 显示结果
        if results:
            print("\n" + "="*85)
            print("期刊新颖性得分（百分制得分 = 新颖性得分 × 600）")
            print("="*85)
            
            # 创建临时DataFrame用于显示
            display_list = []
            for journal, scores in results.items():
                display_list.append({
                    '期刊名称': journal,
                    '百分制得分': scores.get('percent_score', 0),
                    '新颖性得分': scores.get('novelty_score', 0),
                    '论文数量': scores.get('paper_count', 0)
                })
            
            display_df = pd.DataFrame(display_list)
            display_df = display_df.sort_values('百分制得分', ascending=False).reset_index(drop=True)
            
            print(f"{'排名':^4} | {'期刊名称':^40} | {'百分制得分':^12} | {'新颖性得分':^12} | {'论文数':^8}")
            print("-"*85)
            
            for i, row in display_df.iterrows():
                journal_name = row['期刊名称']
                if len(journal_name) > 38:
                    journal_name = journal_name[:35] + "..."
                
                print(f"{i+1:^4} | {journal_name:^40} | {row['百分制得分']:^12.1f} | "
                      f"{row['新颖性得分']:^12.4f} | {row['论文数量']:^8}")
            
            print("="*85)
            
    except Exception as e:
        print(f"程序错误: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()
=======
期刊新颖性指数分析系统（基于 Uzzi et al., Science 2013 的组合新颖性方法）
"""

# === 基础库 ===
import os
import json
import pandas as pd
import numpy as np
from collections import defaultdict, Counter
from itertools import combinations
import ast

# === 可视化支持 ===
import matplotlib.pyplot as plt
import seaborn as sns

# === 设置 ===
plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False
pd.options.mode.chained_assignment = None


class NoveltyAnalyzer:
    """
    组合新颖性分析器（Combination Novelty）
    基于关键词共现模式识别“前所未有”的知识组合
    """

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        self.paper_keywords = {}           # DOI -> [keywords]
        self.keyword_pairs_first_seen = {} # (k1,k2) -> first_year
        self.results = {}

    def analyze(self) -> dict:
        """
        执行组合新颖性分析
        
        流程：
        1. 提取每篇论文的关键词
        2. 构建所有关键词对的历史首次出现年份
        3. 计算每篇论文中“首次出现”的新组合比例
        4. 按期刊聚合为平均新颖性得分
        
        Returns:
            {期刊名: 新颖性得分}
        """
        print("🔍 开始组合新颖性分析（Uzzi 方法）...")

        # Step 1: 提取关键词
        self._extract_paper_keywords()

        # Step 2: 构建全局关键词对时间线
        self._build_keyword_pair_timeline()

        # Step 3: 计算每篇论文的新颖性得分
        paper_novelty_df = self._calculate_paper_combination_novelty()

        # Step 4: 按期刊计算平均得分
        journal_novelty = self._aggregate_to_journal(paper_novelty_df)

        self.results = journal_novelty
        return journal_novelty

    def _extract_paper_keywords(self):
        """提取并清洗关键词"""
        print("📝 提取论文关键词...")
        stop_words = {
            'review', 'studies', 'study', 'analysis', 'method', 'methods',
            'approach', 'approaches', 'framework', 'model', 'system',
            'based', 'using', 'via', 'case study', 'research', 'development'
        }

        for _, row in self.df.iterrows():
            paper_id = row['DOI'] if pd.notna(row['DOI']) else f"paper_{_}"
            keywords = []

            if pd.notna(row.get('Keywords')):
                word_content = str(row['Keywords']).strip()
                try:
                    if word_content.startswith('[') and word_content.endswith(']'):
                        raw_list = ast.literal_eval(word_content)
                        keywords = [str(kw).strip().lower() for kw in raw_list if str(kw).strip()]
                    else:
                        keywords = [kw.strip().lower() for kw in word_content.replace(';', ',').split(',') if kw.strip()]
                except (ValueError, SyntaxError):
                    keywords = [word_content.lower()] if word_content else []

            # 清洗：去停用词、去空格、标准化
            keywords = [kw for kw in keywords if kw not in stop_words and len(kw) > 1]
            self.paper_keywords[paper_id] = sorted(set(keywords))  # 排序便于 pair 一致

        total_papers = len(self.paper_keywords)
        papers_with_kw = sum(1 for kw in self.paper_keywords.values() if kw)
        total_keywords = sum(len(kw) for kw in self.paper_keywords.values())
        unique_keywords = len(set(kw for kws in self.paper_keywords.values() for kw in kws))

        print(f"✅ 关键词提取完成: {papers_with_kw}/{total_papers} 篇有关键词")
        print(f"   共 {unique_keywords} 个独特关键词, 总共出现 {total_keywords} 次")

    def _build_keyword_pair_timeline(self):
        """构建所有关键词对的首次出现年份"""
        print("📅 构建关键词组合时间线...")
        pair_first_year = defaultdict(lambda: float('inf'))

        missing_year_count = 0
        for paper_id, keywords in self.paper_keywords.items():
            if len(keywords) < 2:
                continue

            year = self._get_paper_year(paper_id)
            if not year:
                missing_year_count += 1
                continue

            # 生成所有无序两两组合
            for pair in combinations(keywords, 2):
                # 规范化顺序：字典序，确保 ('a','b') == ('b','a')
                norm_pair = tuple(sorted(pair))
                if year < pair_first_year[norm_pair]:
                    pair_first_year[norm_pair] = year

        self.keyword_pairs_first_seen = dict(pair_first_year)
        print(f"✅ 构建完成: 共 {len(pair_first_year)} 个关键词对组合")
        if missing_year_count:
            print(f"⚠️  {missing_year_count} 篇论文缺少年份信息被跳过")

    def _get_paper_year(self, paper_id: str) -> int:
        """获取论文出版年份"""
        try:
            if 'DOI' not in self.df.columns:
                return None
            matched = self.df[self.df['DOI'] == paper_id]
            if len(matched) == 0:
                return None
            year_val = matched.iloc[0]['Publication Year']
            return int(year_val) if pd.notna(year_val) else None
        except Exception:
            return None

    def _calculate_paper_combination_novelty(self) -> pd.DataFrame:
        """计算每篇论文的组合新颖性得分"""
        print("🎯 计算论文组合新颖性得分...")
        results = []

        current_year = self.df['Publication Year'].max() if 'Publication Year' in self.df.columns else 2024

        for paper_id, keywords in self.paper_keywords.items():
            if len(keywords) < 2:
                results.append({'DOI': paper_id, 'novelty_score': np.nan})
                continue

            pairs = list(combinations(keywords, 2))
            novel_pairs = 0
            total_pairs = len(pairs)

            for pair in pairs:
                norm_pair = tuple(sorted(pair))
                first_year = self.keyword_pairs_first_seen.get(norm_pair, None)

                if first_year is None:
                    # 完全未见的组合 → 极新颖
                    novel_pairs += 1
                elif abs(first_year - current_year) <= 1:  # 当前或前一年才首次出现
                    novel_pairs += 1

            # 新颖性得分 = 新组合占比
            novelty_score = novel_pairs / total_pairs if total_pairs > 0 else np.nan
            results.append({'DOI': paper_id, 'novelty_score': novelty_score})

        df_out = pd.DataFrame(results)
        valid_count = df_out['novelty_score'].notna().sum()
        print(f"✅ 完成: {valid_count}/{len(df_out)} 篇论文获得有效得分")
        return df_out

    def _aggregate_to_journal(self, paper_novelty_df: pd.DataFrame) -> dict:
        """按期刊聚合平均新颖性得分"""
        print("📚 按期刊聚合结果...")

        # 合并期刊信息
        journal_map = self.df.drop_duplicates('DOI')[['DOI', 'Source Title']].set_index('DOI')['Source Title'].to_dict()
        paper_novelty_df['Source Title'] = paper_novelty_df['DOI'].map(journal_map)

        # 过滤无效值
        valid_df = paper_novelty_df.dropna(subset=['novelty_score', 'Source Title'])

        # 计算每种期刊的平均新颖性
        journal_scores = valid_df.groupby('Source Title')['novelty_score'].mean().round(6).to_dict()

        print(f"✅ 聚合完成: 共 {len(journal_scores)} 种期刊")
        return journal_scores

    def get_detailed_results(self) -> dict:
        """返回详细中间结果（用于调试或扩展）"""
        return {
            'journal_novelty': self.results,
            'paper_novelty': self._calculate_paper_combination_novelty(),
            'keyword_pairs_first_seen': self.keyword_pairs_first_seen,
            'paper_keywords': self.paper_keywords
        }


def run_novelty_analysis(
    background_data_path: str = '../data/raw/data_with_citing.csv',
    target_data_path: str = '../data/raw/top10_journals_data.csv',
    output_dir: str = '../outputs/novelty'
) -> dict:
    """
    主执行函数：使用全量数据构建背景知识库，评估 Top10 期刊的新颖性
    """
    # ========== 1. 推导项目根目录 ==========
    try:
        current_dir = os.path.dirname(__file__)
    except NameError:
        current_dir = os.getcwd()
    project_root = os.path.abspath(os.path.join(current_dir, '..'))

    bg_path = os.path.join(project_root, background_data_path.lstrip('./'))
    tg_path = os.path.join(project_root, target_data_path.lstrip('./'))
    out_dir = os.path.join(project_root, output_dir.lstrip('./'))

    os.makedirs(out_dir, exist_ok=True)

    print(f"📁 加载背景数据（全量）: {bg_path}")
    df_background = pd.read_csv(bg_path)

    print(f"📁 加载目标数据（Top10）: {tg_path}")
    df_target = pd.read_csv(tg_path)

    # ========== 2. 使用全量数据构建组合时间线 ==========
    print("\n🔄 正在使用全量数据构建关键词组合时间线...")
    analyzer_bg = NoveltyAnalyzer(df_background)
    
    # 我们只需要它的 _extract 和 _build 功能
    analyzer_bg._extract_paper_keywords()
    analyzer_bg._build_keyword_pair_timeline()  # ← 关键：全局组合数据库

    print(f"✅ 全局时间线构建完成 | 共 {len(analyzer_bg.keyword_pairs_first_seen)} 个关键词对")

    # ========== 3. 在 Top10 数据上计算新颖性（使用全局时间线）==========
    print("\n📊 开始计算 Top10 期刊的组合新颖性...")
    analyzer_target = NoveltyAnalyzer(df_target)
    analyzer_target._extract_paper_keywords()

    # 注入全局组合时间线（核心改进！）
    analyzer_target.keyword_pairs_first_seen = analyzer_bg.keyword_pairs_first_seen

    # 正常计算得分（现在是基于全局背景）
    paper_novelty_df = analyzer_target._calculate_paper_combination_novelty()
    journal_novelty = analyzer_target._aggregate_to_journal(paper_novelty_df)

    analyzer_target.results = journal_novelty

    # ========== 4. 输出结果 ==========
    result_json = os.path.join(out_dir, 'journal_novelty_scores.json')
    with open(result_json, 'w', encoding='utf-8') as f:
        json.dump(journal_novelty, f, ensure_ascii=False, indent=2)
    print(f"✅ 已保存 JSON: {result_json}")

    result_df = pd.DataFrame(list(journal_novelty.items()), 
                           columns=['Source Title', 'novelty_score'])
    result_df = result_df.sort_values('novelty_score', ascending=False).reset_index(drop=True)

    result_csv = os.path.join(out_dir, 'journal_novelty_ranking.csv')
    result_df.to_csv(result_csv, index=False, encoding='utf-8-sig')
    print(f"✅ 已保存 CSV: {result_csv}")

    txt_path = os.path.join(out_dir, 'top_journals_by_novelty.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        for journal in result_df['Source Title']:
            f.write(f"{journal}\n")
    print(f"✅ 已保存 TXT: {txt_path}")

    # ========== 5. 可视化 ==========
    try:
        top10 = result_df.head(10)
        plt.figure(figsize=(12, 8))
        bars = plt.barh(top10['Source Title'], top10['novelty_score'], color='steelblue', alpha=0.8)

        for bar, val in zip(bars, top10['novelty_score']):
            plt.text(bar.get_width() + 0.001, bar.get_y() + bar.get_height()/2,
                     f'{val:.4f}', ha='left', va='center', fontsize=10,
                     bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8))

        plt.xlabel('组合新颖性得分（基于全量背景）')
        plt.title('期刊组合新颖性排名（前10）\n(Uzzi et al., Science 2013) - 全局知识基线')
        plt.gca().invert_yaxis()
        plt.tight_layout()

        img_path = os.path.join(out_dir, 'novelty_ranking.png')
        plt.savefig(img_path, dpi=150, bbox_inches='tight')
        plt.show()
        print(f"✅ 已保存图表: {img_path}")
    except Exception as e:
        print(f"⚠️ 图表保存失败: {e}")

    return {
        'analyzer': analyzer_target,
        'results': journal_novelty,
        'ranking': result_df,
        'global_analyzer': analyzer_bg
    }

# ========================
# 如果直接运行此脚本，则执行主流程
# ========================
if __name__ == "__main__":
    run_novelty_analysis()
>>>>>>> 325a45d1acde271d3e82f31155b95d174bbec114
