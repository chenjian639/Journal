# -*- coding: utf-8 -*-
"""
<<<<<<< HEAD
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
            
=======
python_analysis/disrupt_calculator.py  # 注意：路径已改为 python_analysis/
期刊颠覆性指数分析系统（模块化封装版）
功能：计算论文级 D-index → 生成期刊级颠覆性排名 → 导出结果至 outputs/disrupt/
"""

# === 基础库 ===
import os
import json
from matplotlib import pyplot as plt
import pandas as pd
import numpy as np
from collections import defaultdict
import ast
import warnings
# === 设置 ===
pd.options.mode.chained_assignment = None  # 关闭警告
os.makedirs('../outputs/disrupt', exist_ok=True)  # 修正：从 python_analysis 指向根目录 outputs
# === 设置 ===
warnings.filterwarnings('ignore')
plt.rcParams['font.sans-serif'] = ['SimHei']  # 中文字体支持
plt.rcParams['axes.unicode_minus'] = False   # 正常显示负号

class DisruptionIndexCalculator:
    """
    颠覆性指数计算器（基于 Wu et al., Nature 2019）
    """
    def __init__(self):
        self.citation_network = defaultdict(set)  # cited -> {citing}
        self.paper_references = {}               # paper_id -> {refs}

    def build_citation_network(self, df):
        """构建全局引文网络"""
        print("正在构建引文网络...")
        for _, row in df.iterrows():
            paper_id = row['DOI']
            citing_str = row.get('citing', None)
            
            refs = set()
>>>>>>> 325a45d1acde271d3e82f31155b95d174bbec114
            if pd.notna(citing_str):
                try:
                    if isinstance(citing_str, str):
                        refs = set(ast.literal_eval(citing_str))
<<<<<<< HEAD
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
        
=======
                    else:
                        refs = set(citing_str)
                except (ValueError, SyntaxError):
                    pass  # 解析失败则留空
            
            self.paper_references[paper_id] = refs
            for ref in refs:
                self.citation_network[ref].add(paper_id)
        
        print(f"引文网络构建完成 | 涉及论文数: {len(df)}")
        return self

    def calculate_disruption_index(self, focal_paper_id):
        """计算单篇论文的 D-index"""
        R = self.paper_references.get(focal_paper_id, set())  # 参考文献
        C = self.citation_network.get(focal_paper_id, set())  # 施引文献
        
        ni = nj = nk = 0
        
        # ni: 引FP但不引R；nj: 同时引FP和R
>>>>>>> 325a45d1acde271d3e82f31155b95d174bbec114
        for citing_paper in C:
            citing_refs = self.paper_references.get(citing_paper, set())
            if citing_refs & R:
                nj += 1
            else:
                ni += 1
        
<<<<<<< HEAD
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
=======
        # nk: 引R但不引FP
        papers_citing_R = set()
        for r in R:
            papers_citing_R.update(self.citation_network.get(r, set()))
        nk = len(papers_citing_R - C)
        
        denom = ni + nj + nk
        d_index = (ni - nj) / denom if denom > 0 else 0.0
        return d_index, (ni, nj, nk)


def export_citation_network(calculator, paper_scores_df, output_file=None):
    """
    导出带 D-index 的引文网络（JSON 格式）
    
    Parameters:
        calculator: 构建好的 DisruptionIndexCalculator 实例
        paper_scores_df: 包含 'DOI' 和 'disruption_index' 的 DataFrame
        output_file: 输出路径；默认为 PROJECT_ROOT/outputs/disrupt/citation_network.json
    """
    # 修正：从 python_analysis 目录推导项目根目录（关键修改）
    try:
        current_dir = os.path.dirname(__file__)  # 当前文件目录：python_analysis/
    except NameError:
        current_dir = os.getcwd()
    project_root = os.path.abspath(os.path.join(current_dir, '..'))  # 上一级：根目录
    
    if output_file is None:
        output_file = os.path.join(project_root, 'outputs', 'disrupt', 'citation_network.json')

    print("📦 正在导出带 D-index 的引文网络...")

    # 构建边
    edges = []
    for cited_doi, citing_set in calculator.citation_network.items():
        for citing_doi in citing_set:
            edges.append({'source': cited_doi, 'target': citing_doi})

    # 构建节点（统一 nan -> None -> JSON null）
    d_index_series = paper_scores_df.set_index('DOI')['disruption_index']
    d_index_map = {}
    for doi, val in d_index_series.items():
        d_index_map[doi] = None if pd.isna(val) else val

    nodes = []
    for paper_id in calculator.paper_references.keys():
        nodes.append({
            'id': paper_id,
            'type': 'paper',
            'n_references': len(calculator.paper_references[paper_id]),
            'disruption_index': d_index_map.get(paper_id, None)
        })

    graph_data = {'nodes': nodes, 'edges': edges}
    os.makedirs(os.path.dirname(output_file), exist_ok=True)

    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(graph_data, f, ensure_ascii=False, indent=2)

    print(f"成功导出引文网络：共 {len(nodes)} 个节点，{len(edges)} 条边")
    print(f"文件已保存至: {output_file}")


def calculate_paper_disruption_scores(df_background, df_target):
    """
    主函数：为 df_target 中的每篇论文计算 D-index
    返回结果表 和 构建好的计算器
    """
    calc = DisruptionIndexCalculator().build_citation_network(df_background)
    
    results = []
    total = len(df_target)
    progress_checkpoint = 0

    print("📊 开始计算论文颠覆性指数...")
    for i, (_, row) in enumerate(df_target.iterrows()):
        doi = row['DOI']
        try:
            d_index, _ = calc.calculate_disruption_index(doi)
            results.append({'DOI': doi, 'disruption_index': d_index})
        except Exception:
            results.append({'DOI': doi, 'disruption_index': np.nan})

        current_progress = (i + 1) / total
        if current_progress >= progress_checkpoint:
            print(f"✅ 进度: {int(progress_checkpoint * 100)}%", end="\r")
            progress_checkpoint += 0.1

    print("\n🎉 计算完成！")
    result_df = pd.DataFrame(results)
    final_df = result_df.merge(df_target[['DOI', 'Source Title']], on='DOI', how='left')
    
    return final_df, calc


def calculate_original_metrics(df):
    """原始方法：所有论文平均 D-index"""
    return (df.groupby('Source Title')
              .agg({'disruption_index': 'mean', 'DOI': 'count'})
              .rename(columns={'disruption_index': 'disruption_mean', 'DOI': 'paper_count'})
              .sort_values('disruption_mean', ascending=False)
              .reset_index())


def calculate_enhanced_metrics(df, top_k=10, volume_weight=0.4):
    """增强方法：Top-k 平均 + 规模加权"""
    valid = df.dropna(subset=['disruption_index'])
    grouped = valid.groupby('Source Title')
    
    records = []
    for journal, group in grouped:
        n_papers = len(group)
        k = min(top_k, n_papers)
        top_avg = group.nlargest(k, 'disruption_index')['disruption_index'].mean()
        log_n = np.log1p(n_papers)
        score = (1 - volume_weight) * top_avg + volume_weight * (top_avg / log_n)

        records.append({
            'Source Title': journal,
            'n_papers': n_papers,
            'top_k_mean': top_avg,
            'enhanced_disruption': score
        })
    
    return pd.DataFrame(records).sort_values('enhanced_disruption', ascending=False).reset_index(drop=True)


def visualize_journal_ranking(journal_metrics, top_n=None, title=None, value_col='disruption_mean'):
    """
    通用期刊排名可视化（需要调用 plt.show() 显示）
    """
    try:
        import matplotlib.pyplot as plt
    except ImportError:
        print("⚠️ matplotlib 未安装，跳过可视化")
        return

    data = journal_metrics.head(top_n) if top_n is not None else journal_metrics.copy()
    
    plt.figure(figsize=(14, max(8, len(data) * 0.4)))
    colors = plt.cm.viridis(np.linspace(0.3, 0.9, len(data)))

    bars = plt.barh(
        data['Source Title'],
        data[value_col],
        color=colors,
        alpha=0.8,
        edgecolor='black',
        linewidth=0.5,
        height=0.7
    )

    max_val = data[value_col].max()
    text_x = max_val * 1.08

    for bar, val in zip(bars, data[value_col]):
        plt.text(text_x, bar.get_y() + bar.get_height()/2,
                 f'{val:.4f}', ha='left', va='center', fontsize=10,
                 bbox=dict(boxstyle='round,pad=0.3', facecolor='white', alpha=0.8, edgecolor='gray'))

    plt.xlabel("颠覆性指数", fontsize=13, fontweight='bold')
    plt.ylabel("期刊名称", fontsize=13, fontweight='bold')
    plt.title(title or "期刊颠覆性指数排名", fontsize=16, fontweight='bold', pad=20)

    ax = plt.gca()
    ax.spines['top'].set_visible(False)
    ax.spines['right'].set_visible(False)
    ax.spines['left'].set_linewidth(0.5)
    ax.spines['bottom'].set_linewidth(0.5)
    ax.grid(axis='x', linestyle='--', alpha=0.3, color='gray')
    ax.set_facecolor('#f8f9fa')
    plt.gcf().patch.set_facecolor('white')
    ax.invert_yaxis()
    plt.tight_layout()


def run_analysis(background_path=None, target_path=None, output_dir=None):
    """
    主执行函数：端到端运行颠覆性分析
    
    自动识别项目根目录，确保路径正确。
    所有结果输出至 outputs/disrupt/
    """
    # ========== 1. 推导项目根目录（关键修改：适配 python_analysis/ 目录） ==========
    try:
        current_dir = os.path.dirname(__file__)  # 当前文件目录：python_analysis/
    except NameError:
        current_dir = os.getcwd()
    project_root = os.path.abspath(os.path.join(current_dir, '..'))  # 上一级：根目录

    print(f"项目根目录识别为: {project_root}")

    # ========== 2. 设置默认路径 ==========
    if background_path is None:
        background_path = os.path.join(project_root, 'data', 'raw', 'data_with_citing.csv')  # 根目录/data/
    if target_path is None:
        target_path = os.path.join(project_root, 'data', 'raw', 'top10_journals_data.csv')  # 根目录/data/
    if output_dir is None:
        output_dir = os.path.join(project_root, 'outputs', 'disrupt')  # 根目录/outputs/

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # ========== 3. 加载数据 ==========
    print("正在加载背景数据...")
    df_all = pd.read_csv(background_path)
    print("正在加载目标数据...")
    df_top10 = pd.read_csv(target_path)

    # ========== 4. 计算论文级 D-index ==========
    paper_scores, calculator = calculate_paper_disruption_scores(df_all, df_top10)

    # ========== 5. 生成期刊级指标 ==========
    original_metrics = calculate_original_metrics(paper_scores)
    enhanced_metrics = calculate_enhanced_metrics(paper_scores, top_k=10, volume_weight=0.4)

    # ========== 6. 导出所有结果 ==========
    # 6.1 引文网络
    export_citation_network(calculator, paper_scores, 
                           output_file=os.path.join(output_dir, 'citation_network.json'))

    # 6.2 原始方法排名 CSV
    orig_csv = os.path.join(output_dir, 'top10_original_ranking.csv')
    original_metrics.to_csv(orig_csv, index=False, encoding='utf-8-sig')
    print(f"原始方法排名已保存: {orig_csv}")

    # 6.3 增强方法排名 CSV
    enh_csv = os.path.join(output_dir, 'top10_enhanced_ranking.csv')
    enhanced_metrics.to_csv(enh_csv, index=False, encoding='utf-8-sig')
    print(f"增强方法排名已保存: {enh_csv}")

    # 6.4 期刊名称列表 TXT
    txt_path = os.path.join(output_dir, 'top10_journals_list.txt')
    with open(txt_path, 'w', encoding='utf-8') as f:
        for journal in original_metrics['Source Title']:
            f.write(f"{journal}\n")
    print(f"期刊列表已保存: {txt_path}")

    # ========== 7. 可视化 ==========
    try:
        visualize_journal_ranking(
            original_metrics,
            top_n=10,
            title="【方法一】期刊平均颠覆性排名",
            value_col='disruption_mean'
        )
        plt.show()

        visualize_journal_ranking(
            enhanced_metrics,
            top_n=10,
            title="【方法二】Top10高影响力论文+规模加权",
            value_col='enhanced_disruption'
        )
        plt.show()
    except:
        print("⚠️ 可视化显示失败（可能环境不支持），但数据已正常导出。")

    # ========== 8. 返回结果 ==========
    return {
        'paper_scores': paper_scores,
        'original_metrics': original_metrics,
        'enhanced_metrics': enhanced_metrics,
        'calculator': calculator
    }

# ========================
# 如果直接运行此脚本，则执行主流程
# ========================
if __name__ == "__main__":
    run_analysis()
>>>>>>> 325a45d1acde271d3e82f31155b95d174bbec114
