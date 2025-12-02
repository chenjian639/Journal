# -*- coding: utf-8 -*-
"""
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
            if pd.notna(citing_str):
                try:
                    if isinstance(citing_str, str):
                        refs = set(ast.literal_eval(citing_str))
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
        for citing_paper in C:
            citing_refs = self.paper_references.get(citing_paper, set())
            if citing_refs & R:
                nj += 1
            else:
                ni += 1
        
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