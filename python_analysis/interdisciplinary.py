# -*- coding: utf-8 -*-
"""
python_analysis/interdisciplinary.py
跨学科性(TD)计算模块 - 精简版
只输出：两个柱状图 + 百分制得分列表
"""
import json
import pandas as pd
import numpy as np
import ast
import matplotlib.pyplot as plt
from pathlib import Path
from collections import Counter

plt.rcParams['font.sans-serif'] = ['SimHei']
plt.rcParams['axes.unicode_minus'] = False

def load_config():
    """加载配置文件"""
    config_path = Path(__file__).parent.parent / 'config.json'
    if not config_path.exists():
        raise FileNotFoundError(f"配置文件不存在: {config_path}")
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = json.load(f)
    
    return config.get("interdisciplinary", {})

def log(msg):
    print(f"[interdisciplinary] {msg}")

class InterdisciplinaryAnalyzer:
    def __init__(self, config=None):
        self.config = config or load_config()
        
        # 创建输出目录
        output_dir = Path(self.config['output']['interdisciplinary_dir'])
        output_dir.mkdir(parents=True, exist_ok=True)
        self.output_dir = output_dir

    def parse_categories(self, category_str):
        """解析分类字符串"""
        if pd.isna(category_str):
            return []
        
        try:
            if isinstance(category_str, str):
                cleaned = category_str.strip()
                if cleaned.startswith('[') and cleaned.endswith(']'):
                    return ast.literal_eval(cleaned)
                else:
                    separators = [';', '|', '/']
                    for sep in separators:
                        if sep in cleaned:
                            return [cat.strip() for cat in cleaned.split(sep) if cat.strip()]
                    return [cleaned]
        except:
            pass
        
        return []

    def calculate_similarity_matrix(self, papers_data):
        """计算学科分类间的相似性矩阵"""
        log("计算学科分类相似性矩阵...")
        
        all_categories = set()
        for categories in papers_data.values():
            all_categories.update(categories)
        
        all_categories = sorted(list(all_categories))
        
        n = len(all_categories)
        co_occurrence = np.zeros((n, n))
        cat_to_idx = {cat: i for i, cat in enumerate(all_categories)}
        
        for categories in papers_data.values():
            if len(categories) < 2:
                continue
            
            for i in range(len(categories)):
                idx_i = cat_to_idx[categories[i]]
                co_occurrence[idx_i, idx_i] += 1
                
                for j in range(i+1, len(categories)):
                    idx_j = cat_to_idx[categories[j]]
                    co_occurrence[idx_i, idx_j] += 1
                    co_occurrence[idx_j, idx_i] += 1
        
        similarity = np.zeros((n, n))
        for i in range(n):
            for j in range(n):
                if i == j:
                    similarity[i, j] = 1.0
                else:
                    numerator = np.dot(co_occurrence[i, :], co_occurrence[j, :])
                    denom_i = np.sqrt(np.sum(co_occurrence[i, :] ** 2))
                    denom_j = np.sqrt(np.sum(co_occurrence[j, :] ** 2))
                    
                    if denom_i > 0 and denom_j > 0:
                        similarity[i, j] = numerator / (denom_i * denom_j)
                    else:
                        similarity[i, j] = 0.0
        
        self.all_categories = all_categories
        self.cat_to_idx = cat_to_idx
        self.similarity_matrix = similarity
        
        return similarity

    def calculate_rao_stirling_diversity(self, categories):
        """计算Rao-Stirling多样性指数"""
        if not categories or len(set(categories)) <= 1:
            return 0.0
        
        total = len(categories)
        category_probs = Counter(categories)
        
        prob_vector = np.zeros(len(self.all_categories))
        for cat, count in category_probs.items():
            if cat in self.cat_to_idx:
                prob_vector[self.cat_to_idx[cat]] = count / total
        
        diversity = 0.0
        n = len(self.all_categories)
        
        for i in range(n):
            for j in range(n):
                similarity = self.similarity_matrix[i, j]
                diversity += (1 - similarity) * prob_vector[i] * prob_vector[j]
        
        return diversity

    def calculate_td_index(self, categories):
        """计算TD指数"""
        diversity = self.calculate_rao_stirling_diversity(categories)
        
        if diversity > 0:
            return 1.0 / diversity
        else:
            return 1.0

    def normalize_to_percent(self, scores):
        """归一化到百分制 (0-100)"""
        if isinstance(scores, (list, np.ndarray)):
            return [round(score * 5, 1) for score in scores]
        else:
            return round(scores * 5, 1)

    def run_analysis(self, background_df=None, target_df=None):
        """运行跨学科性分析"""
        try:
            log("=" * 50)
            log("开始跨学科性分析")
            log("=" * 50)
            
            # 加载数据
            if background_df is None or target_df is None:
                project_root = Path(__file__).parent.parent
                all_path = project_root / self.config['data_sources']['all_data']
                target_path = project_root / self.config['data_sources']['target_data']
                
                log(f"加载全量数据: {all_path}")
                log(f"加载目标数据: {target_path}")
                
                background_df = pd.read_csv(all_path)
                target_df = pd.read_csv(target_path)
            
            # 获取列名
            id_col = self.config['columns']['id']
            journal_col = self.config['columns']['journal']
            category_col = self.config['columns']['category']
            refs_col = self.config['columns']['refs']
            
            # 检查必要列
            required_cols = [id_col, journal_col, category_col, refs_col]
            missing_cols = [col for col in required_cols if col not in background_df.columns]
            if missing_cols:
                raise ValueError(f"背景数据缺少列: {missing_cols}")
            
            missing_cols = [col for col in required_cols if col not in target_df.columns]
            if missing_cols:
                raise ValueError(f"目标数据缺少列: {missing_cols}")
            
            log(f"使用列名: ID={id_col}, 期刊={journal_col}, 分类={category_col}, 引用={refs_col}")
            
            # 阶段1: 构建学科分类知识库
            log("\n[阶段1] 构建学科分类知识库...")
            paper_categories = {}
            
            for _, row in background_df.iterrows():
                paper_id = str(row[id_col])
                if pd.isna(paper_id):
                    continue
                
                categories = self.parse_categories(row[category_col])
                if categories:
                    paper_categories[paper_id] = categories
            
            log(f"  处理 {len(paper_categories)} 篇论文的分类信息")
            
            # 计算学科相似性矩阵
            self.calculate_similarity_matrix(paper_categories)
            
            # 阶段2: 分析目标数据
            log("\n[阶段2] 分析目标期刊数据...")
            paper_results = []
            
            target_df = target_df.copy()
            target_df['parsed_refs'] = target_df[refs_col].apply(
                lambda x: ast.literal_eval(x) if isinstance(x, str) and x.startswith('[') else []
            )
            
            td_scores = []
            for idx, row in target_df.iterrows():
                paper_id = str(row[id_col])
                journal = row[journal_col]
                refs = row['parsed_refs']
                
                ref_categories = []
                for ref_id in refs:
                    if ref_id in paper_categories:
                        ref_categories.extend(paper_categories[ref_id])
                
                td_score = self.calculate_td_index(ref_categories)
                td_scores.append(td_score)
                
                paper_results.append({
                    'paper_id': paper_id,
                    'journal': journal,
                    'td_score': td_score
                })
                
                if (idx + 1) % 100 == 0:
                    log(f"  处理进度: {idx + 1}/{len(target_df)}")
            
            # 创建论文结果DataFrame
            paper_df = pd.DataFrame(paper_results)
            
            # 计算归一化百分制分数
            log("\n[阶段3] 计算归一化百分制分数...")
            normalized_percent = self.normalize_to_percent(td_scores)
            paper_df['td_score_percent'] = normalized_percent
            
            # 按期刊聚合
            if 'journal' in paper_df.columns:
                journal_col_name = 'journal'
            elif 'Journal' in paper_df.columns:
                journal_col_name = 'Journal'
            else:
                journal_col_name = paper_df.columns[1]
            
            # 聚合统计
            journal_agg = paper_df.groupby(journal_col_name).agg({
                'td_score': ['mean', 'std'],
                'td_score_percent': ['mean', 'std'],
                'paper_id': 'count'
            }).round(4)
            
            journal_agg.columns = ['TD_Mean', 'TD_Std', 'TD_Percent_Mean', 'TD_Percent_Std', 'Paper_Count']
            journal_agg = journal_agg.sort_values('TD_Percent_Mean', ascending=False).reset_index()
            journal_agg = journal_agg.rename(columns={journal_col_name: 'Journal'})
            
            # 生成两个柱状图和百分制得分列表
            self.generate_outputs(journal_agg)
            
            log("\n✅ 分析完成！")
            log(f"📊 生成文件:")
            log(f"  1. journal_td_original.png - 原始TD得分柱状图")
            log(f"  2. journal_td_percent.png - 百分制得分柱状图")
            log(f"  3. journal_percent_scores.csv - 百分制得分列表")
            
        except Exception as e:
            log(f"[错误] 分析过程中出现异常: {e}")
            import traceback
            traceback.print_exc()

    def generate_outputs(self, journal_agg):
        """生成两个柱状图和百分制得分列表"""
        # 只输出前20个期刊（或全部）
        display_data = journal_agg.head(20) if len(journal_agg) > 20 else journal_agg
        
        # 1. 生成原始TD得分柱状图
        self.create_bar_chart(
            data=display_data,
            value_col='TD_Mean',
            title='期刊跨学科性指数 - 原始TD得分',
            xlabel='原始TD指数',
            filename='journal_td_original.png',
            color='steelblue'
        )
        
        # 2. 生成百分制得分柱状图
        self.create_bar_chart(
            data=display_data,
            value_col='TD_Percent_Mean',
            title='期刊跨学科性指数 - 百分制得分',
            xlabel='百分制得分 (0-100)',
            filename='journal_td_percent.png',
            color='forestgreen',
            is_percent=True
        )
        
        # 3. 生成百分制得分列表
        percent_list = journal_agg[['Journal', 'TD_Percent_Mean', 'TD_Mean', 'Paper_Count']].copy()
        percent_list = percent_list.rename(columns={
            'Journal': '期刊名称',
            'TD_Percent_Mean': '百分制得分',
            'TD_Mean': '原始TD得分',
            'Paper_Count': '论文数量'
        })
        
        # 排序并保存
        percent_list = percent_list.sort_values('百分制得分', ascending=False)
        csv_path = self.output_dir / "journal_percent_scores.csv"
        percent_list.to_csv(csv_path, index=False, encoding="utf-8-sig", float_format='%.2f')
        log(f"📄 百分制得分列表已保存: {csv_path}")

    def create_bar_chart(self, data, value_col, title, xlabel, filename, color, is_percent=False):
        """创建美观的柱状图"""
        fig, ax = plt.subplots(figsize=(12, 8))
        
        # 设置期刊名称（缩短长名称）
        journal_names = []
        for name in data['Journal']:
            if len(str(name)) > 25:
                journal_names.append(str(name)[:22] + '...')
            else:
                journal_names.append(str(name))
        
        # 创建柱状图
        bars = ax.barh(range(len(data)), data[value_col], 
                      color=color, alpha=0.8, height=0.7, 
                      edgecolor='white', linewidth=1)
        
        # 添加数值标签
        for i, (bar, val, count) in enumerate(zip(bars, data[value_col], data['Paper_Count'])):
            # 在柱子右侧显示数值
            if is_percent:
                label_text = f'{val:.1f}分\n({count}篇)'
            else:
                label_text = f'{val:.2f}\n({count}篇)'
            
            ax.text(bar.get_width() + 0.5, bar.get_y() + bar.get_height()/2,
                   label_text, ha='left', va='center',
                   fontsize=10, color='black')
        
        # 设置y轴标签（期刊名称）
        ax.set_yticks(range(len(data)))
        ax.set_yticklabels(journal_names, fontsize=10)
        
        # 设置x轴
        ax.set_xlabel(xlabel, fontsize=12, fontweight='bold')
        
        # 设置标题
        ax.set_title(title, fontsize=14, fontweight='bold', pad=20)
        
        # 美化网格
        ax.grid(axis='x', alpha=0.2, linestyle='--')
        
        # 反转y轴（从高到低）
        ax.invert_yaxis()
        
        # 如果显示百分制，设置x轴范围为0-100
        if is_percent:
            ax.set_xlim([0, 105])
        
        # 调整布局
        plt.tight_layout()
        
        # 保存图片
        img_path = self.output_dir / filename
        plt.savefig(img_path, dpi=300, bbox_inches='tight', facecolor='white')
        plt.close()
        
        log(f"📈 柱状图已保存: {img_path}")

def main():
    """主函数"""
    try:
        analyzer = InterdisciplinaryAnalyzer()
        results = analyzer.run_analysis()
    except Exception as e:
        print(f"[错误] 程序执行失败: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    main()