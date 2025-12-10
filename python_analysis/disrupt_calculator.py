# -*- coding: utf-8 -*-
"""
python_analysis/disrupt_calculator.py
期刊颠覆性指数分析系统 - 最终版
输出：增强型得分图表 + 百分制图表 + 百分制得分列表
百分制得分 = 增强型得分 × 100
"""
import json
import ast
import warnings
from pathlib import Path
import pandas as pd
import numpy as np
from collections import defaultdict
import matplotlib.pyplot as plt
from matplotlib import font_manager

warnings.filterwarnings('ignore')

# 设置中文字体
font_path = "C:/Windows/Fonts/simhei.ttf"
if Path(font_path).exists():
    font_manager.fontManager.addfont(font_path)
    font_name = font_manager.FontProperties(fname=font_path).get_name()
    plt.rcParams['font.sans-serif'] = [font_name]
plt.rcParams['axes.unicode_minus'] = False

def load_config():
    """加载配置文件"""
    config_path = Path(__file__).resolve().parent.parent / 'config.json'
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config.get('disrupt', {})

def log(msg):
    print(f"[disrupt] {msg}")

class DisruptionIndexCalculator:
    def __init__(self, config=None):
        self.citation_network = defaultdict(set)
        self.paper_references = {}
        self.config = config or load_config()
        self.data_config = self.config.get('data_sources', {})
        self.column_config = self.config.get('columns', {})
        self.output_config = self.config.get('output', {})
        self.param_config = self.config.get('parameters', {})

    def get_column_name(self, column_type):
        column_mapping = {
            'id': self.column_config.get('id', 'DOI'),
            'journal': self.column_config.get('journal', 'Source Title'),
            'citing': self.column_config.get('citing', 'citing')
        }
        return column_mapping.get(column_type, column_type)

    def build_citation_network(self, df):
        log("构建引文网络...")
        
        id_col = self.get_column_name('id')
        citing_col = self.get_column_name('citing')
        
        self.citation_network = defaultdict(set)
        self.paper_references = {}
        
        for _, row in df.iterrows():
            pid = row.get(id_col)
            if pd.isna(pid):
                continue
                
            citing_str = row.get(citing_col)
            refs = set()
            
            if pd.notna(citing_str):
                try:
                    if isinstance(citing_str, str):
                        refs = set(ast.literal_eval(citing_str))
                except:
                    pass
            
            self.paper_references[pid] = refs
            for ref in refs:
                self.citation_network[ref].add(pid)
        
        log(f"网络构建完成 | 论文: {len(self.paper_references)}")
        return self

    def calculate_disruption_index(self, focal_pid):
        R = self.paper_references.get(focal_pid, set())
        C = self.citation_network.get(focal_pid, set())
        
        ni = nj = nk = 0
        
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
        d_index = (ni - nj) / denom if denom > 0 else 0.0
        
        return d_index

def calculate_paper_scores(df_background, df_target):
    """计算所有论文的颠覆性指数"""
    calculator = DisruptionIndexCalculator().build_citation_network(df_background)
    
    id_col = calculator.get_column_name('id')
    journal_col = calculator.get_column_name('journal')
    
    results = []
    log("计算论文颠覆性指数...")
    
    for i, (_, row) in enumerate(df_target.iterrows()):
        pid = row.get(id_col)
        
        if pid and pd.notna(pid):
            try:
                d_index = calculator.calculate_disruption_index(pid)
                results.append({
                    id_col: pid,
                    'journal': row.get(journal_col),
                    'disruption_index': d_index
                })
            except:
                results.append({
                    id_col: pid,
                    'journal': row.get(journal_col),
                    'disruption_index': np.nan
                })
        
        # 进度显示
        if len(df_target) > 0 and (i + 1) % max(1, len(df_target) // 10) == 0:
            log(f"进度: {int((i + 1) / len(df_target) * 100)}%")
    
    log("论文计算完成")
    return pd.DataFrame(results), calculator

def calculate_enhanced_metrics(df, top_k=10, volume_weight=0.4):
    """计算增强期刊指标（Top-K加权）"""
    if 'disruption_index' not in df.columns or df.empty:
        log("没有有效的颠覆性指数数据")
        return pd.DataFrame(columns=['journal', 'n_papers', 'enhanced_score', 'original_score'])
    
    # 过滤有效数据
    valid_df = df.dropna(subset=['disruption_index'])
    if valid_df.empty:
        return pd.DataFrame(columns=['journal', 'n_papers', 'enhanced_score', 'original_score'])
    
    # 确保期刊列存在
    journal_col = 'journal' if 'journal' in valid_df.columns else 'Source Title'
    if journal_col not in valid_df.columns:
        log(f"缺少期刊列: {journal_col}")
        return pd.DataFrame(columns=['journal', 'n_papers', 'enhanced_score', 'original_score'])
    
    records = []
    grouped = valid_df.groupby(journal_col)
    
    for journal, group in grouped:
        n_papers = len(group)
        
        # 计算Top-K平均
        k = min(top_k, n_papers)
        if k > 0:
            top_avg = group.nlargest(k, 'disruption_index')['disruption_index'].mean()
            original_avg = group['disruption_index'].mean()
        else:
            top_avg = 0
            original_avg = 0
        
        # 计算规模加权
        log_n = np.log1p(n_papers) if n_papers > 0 else 1
        enhanced_score = (1 - volume_weight) * top_avg + volume_weight * (top_avg / log_n)
        
        records.append({
            'journal': journal,
            'n_papers': n_papers,
            'enhanced_score': enhanced_score,
            'original_score': original_avg
        })
    
    result_df = pd.DataFrame(records)
    if not result_df.empty:
        result_df = result_df.sort_values('enhanced_score', ascending=False).reset_index(drop=True)
    
    return result_df

def create_beautiful_bar_chart(data, title, filename, output_dir, value_col, ylabel, color_scheme='viridis'):
    """创建美观的柱状图"""
    if data.empty:
        log("数据为空，无法生成图表")
        return
    
    # 设置图表尺寸（根据期刊数量调整高度）
    n_journals = len(data)
    fig_height = max(6, n_journals * 0.4)  # 每个期刊0.4高度
    fig, ax = plt.subplots(figsize=(12, fig_height))
    
    # 选择颜色方案
    if color_scheme == 'blues':
        colors = plt.cm.Blues(np.linspace(0.4, 0.9, n_journals))
    elif color_scheme == 'greens':
        colors = plt.cm.Greens(np.linspace(0.4, 0.9, n_journals))
    else:
        colors = plt.cm.viridis(np.linspace(0.2, 0.9, n_journals))
    
    # 创建水平柱状图
    y_positions = np.arange(n_journals)
    bars = ax.barh(y_positions, data[value_col], 
                  color=colors, 
                  alpha=0.85,
                  height=0.7,
                  edgecolor='white',
                  linewidth=1.2)
    
    # 添加数值标签
    for i, (bar, val, journal_name, paper_count) in enumerate(zip(bars, data[value_col], 
                                                                  data['期刊名称'], 
                                                                  data['论文数量'])):
        # 数值标签（右侧）
        label_x = bar.get_width() + max(data[value_col]) * 0.02  # 动态偏移
        
        # 确定标签格式
        if value_col == '百分制得分':
            label_text = f'{val:.1f}分'
        else:
            label_text = f'{val:.4f}'
        
        ax.text(label_x, bar.get_y() + bar.get_height()/2,
               label_text, 
               ha='left', va='center',
               fontsize=10, fontweight='bold',
               color='#2c3e50')
        
        # 在柱子左侧显示期刊名称和排名
        short_name = journal_name[:28] + "..." if len(journal_name) > 28 else journal_name
        rank_text = f"{i+1}. {short_name}"
        ax.text(-max(data[value_col]) * 0.02, bar.get_y() + bar.get_height()/2,
               rank_text,
               ha='right', va='center',
               fontsize=9.5,
               color='#34495e')
        
        # 在柱子内部显示论文数量（如果柱子足够宽）
        if bar.get_width() > max(data[value_col]) * 0.1:
            count_text = f"{paper_count}篇"
            ax.text(bar.get_width()/2, bar.get_y() + bar.get_height()/2,
                   count_text,
                   ha='center', va='center',
                   fontsize=8.5, color='white',
                   fontweight='bold')
    
    # 设置y轴
    ax.set_yticks(y_positions)
    ax.set_yticklabels([])  # 隐藏y轴标签
    
    # 设置x轴
    ax.set_xlabel(ylabel, fontsize=11, fontweight='bold', color='#2c3e50')
    
    # 设置x轴范围
    max_val = max(data[value_col]) * 1.15
    ax.set_xlim([0, max_val])
    
    # 设置标题
    ax.set_title(title, fontsize=14, fontweight='bold', pad=18, color='#2c3e50')
    
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
    
    # 调整布局
    plt.tight_layout()
    
    # 保存图片
    img_path = output_dir / filename
    plt.savefig(img_path, dpi=300, bbox_inches='tight', 
                facecolor=fig.get_facecolor(), edgecolor='none')
    plt.close()
    
    log(f"📊 图表已保存: {img_path}")

def run_analysis(config=None):
    """运行分析"""
    log("=" * 60)
    log("期刊颠覆性指数分析")
    log("=" * 60)
    
    # 加载配置
    if config is None:
        config = load_config()
    
    # 创建输出目录
    output_dir = Path(config.get('output', {}).get('disrupt_dir', 'outputs/disrupt'))
    output_dir.mkdir(parents=True, exist_ok=True)
    log(f"输出目录: {output_dir}")
    
    # 加载数据
    project_root = Path(__file__).resolve().parent.parent
    data_config = config.get('data_sources', {})
    
    bg_path = project_root / data_config['all_data']
    tg_path = project_root / data_config['target_data']
    
    log(f"📂 加载数据...")
    log(f"  背景数据: {bg_path}")
    log(f"  目标数据: {tg_path}")
    
    background_df = pd.read_csv(bg_path)
    target_df = pd.read_csv(tg_path)
    
    # 计算论文分数
    log("\n📈 计算论文颠覆性指数...")
    paper_scores, _ = calculate_paper_scores(background_df, target_df)
    
    # 计算增强指标
    params = config.get('parameters', {})
    top_k = params.get('top_k', 10)
    volume_weight = params.get('volume_weight', 0.4)
    
    log("📊 计算增强型期刊指标...")
    enhanced_metrics = calculate_enhanced_metrics(paper_scores, top_k, volume_weight)
    
    if enhanced_metrics.empty:
        log("⚠️  警告: 未计算到有效的期刊指标")
        return
    
    # 计算百分制得分：增强型得分 × 100
    enhanced_metrics['percent_score'] = enhanced_metrics['enhanced_score'] * 100
    
    # 重命名列
    output_df = enhanced_metrics.copy()
    output_df = output_df.rename(columns={
        'journal': '期刊名称',
        'n_papers': '论文数量',
        'enhanced_score': '增强型得分',
        'original_score': '原始平均得分',
        'percent_score': '百分制得分'
    })
    
    # 保存完整的期刊列表（所有目标期刊）
    final_list = output_df.sort_values('百分制得分', ascending=False).reset_index(drop=True)
    final_list.insert(0, '排名', range(1, len(final_list) + 1))
    
    # 1. 生成增强型得分图表（显示所有期刊）
    log("\n🎨 生成增强型得分图表...")
    create_beautiful_bar_chart(
        data=final_list,
        title='期刊颠覆性指数 - 增强型得分',
        filename='enhanced_disruption_scores.png',
        output_dir=output_dir,
        value_col='增强型得分',
        ylabel='增强型得分',
        color_scheme='blues'
    )
    
    # 2. 生成百分制图表（显示所有期刊）
    log("🎨 生成百分制得分图表...")
    create_beautiful_bar_chart(
        data=final_list,
        title='期刊颠覆性指数 - 百分制得分',
        filename='percent_disruption_scores.png',
        output_dir=output_dir,
        value_col='百分制得分',
        ylabel='百分制得分 (增强型得分 × 100)',
        color_scheme='greens'
    )
    
    # 3. 生成百分制得分列表CSV
    csv_path = output_dir / "journal_disruption_scores.csv"
    final_list.to_csv(csv_path, index=False, encoding="utf-8-sig", float_format='%.2f')
    log(f"📄 百分制得分列表已保存: {csv_path}")
    
    # 显示所有期刊数量
    log(f"\n📋 分析完成，共 {len(final_list)} 种期刊")
    
    log("\n✅ 分析完成！")
    log(f"📁 输出文件:")
    log(f"  1. enhanced_disruption_scores.png - 增强型得分柱状图")
    log(f"  2. percent_disruption_scores.png - 百分制得分柱状图")
    log(f"  3. journal_disruption_scores.csv - 百分制得分列表")

if __name__ == '__main__':
    try:
        run_analysis()
    except FileNotFoundError as e:
        print(f"[错误] 文件未找到: {e}")
    except Exception as e:
        print(f"[错误] 程序执行失败: {e}")
        import traceback
        traceback.print_exc()