# -*- coding: utf-8 -*-
"""
python_analysis/novelty_analyzer.py
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