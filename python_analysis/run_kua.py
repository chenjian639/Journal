# python_analysis/kua_interdisciplinary.py
"""
跨学科性(TD)计算模块
用于计算Top10期刊的跨学科性指标
"""

import pandas as pd
import numpy as np
import os
import matplotlib.pyplot as plt
import ast
from typing import Tuple, List, Dict


class InterdisciplinaryAnalyzer:
    """跨学科性分析器"""
    
    def __init__(self, root_dir: str = None):
        """
        初始化分析器
        
        Args:
            root_dir: 项目根目录，默认为当前目录的上一级
        """
        if root_dir is None:
            # 假设src目录在根目录下
            self.root_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        else:
            self.root_dir = root_dir
        
        # 设置路径
        self.data_dir = os.path.join(self.root_dir, 'data', 'raw')
        self.output_dir = os.path.join(self.root_dir, 'outputs', 'kua')
        
        # 创建输出目录
        os.makedirs(self.output_dir, exist_ok=True)
        
        # 初始化数据
        self.df = None
        self.top10_data = None
        self.df_top10 = None
        self.doi_to_category_map = {}
        
        print(f"根目录: {self.root_dir}")
        print(f"输出目录: {self.output_dir}")
    
    def load_data(self) -> bool:
        """
        加载数据文件
        
        Returns:
            bool: 是否成功加载
        """
        try:
            # 加载数据
            df_path = os.path.join(self.data_dir, 'data_with_citing.csv')
            top10_path = os.path.join(self.data_dir, 'top10_journals_data.csv')
            
            if not os.path.exists(df_path) or not os.path.exists(top10_path):
                print(f"❌ 数据文件不存在")
                print(f"  - data_with_citing.csv: {os.path.exists(df_path)}")
                print(f"  - top10_journals_data.csv: {os.path.exists(top10_path)}")
                return False
            
            self.df = pd.read_csv(df_path)
            self.top10_data = pd.read_csv(top10_path)
            
            print(f"数据加载完成")
            print(f"  - 全量数据: {self.df.shape}")
            print(f"  - Top10数据: {self.top10_data.shape}")
            
            return True
            
        except Exception as e:
            print(f"❌ 数据加载失败: {e}")
            return False
    
    def preprocess_data(self):
        """数据预处理"""
        # 处理空值
        self.df['citing'] = self.df['citing'].fillna('')
        
        def safe_literal_eval(x):
            if pd.isna(x) or x == '' or x == '[]':
                return []
            try:
                return ast.literal_eval(x)
            except:
                if isinstance(x, str):
                    x_clean = x.strip('[]').replace("'", "").replace('"', '')
                    items = [item.strip() for item in x_clean.split(',') if item.strip()]
                    return items
                return []
        
        self.df['citing'] = self.df['citing'].apply(safe_literal_eval)
        
        # 获取Top10期刊列表并过滤数据
        top10_journals = self.top10_data['Source Title'].unique().tolist()
        self.df_top10 = self.df[self.df['Source Title'].isin(top10_journals)].copy()
        
        print(f"数据预处理完成")
        print(f"  - 过滤后论文数: {self.df_top10.shape[0]}")
        print(f"  - Top10期刊数: {len(top10_journals)}")
    
    def build_category_mapping(self):
        """建立DOI到学科的映射"""
        for _, row in self.top10_data.iterrows():
            doi = str(row.get('DOI', '')).strip()
            category = row.get('WoS Categories', '')
            
            if doi and doi.lower() != 'nan' and pd.notna(category):
                # 标准化DOI格式
                if doi.startswith('https://doi.org/'):
                    doi = doi.replace('https://doi.org/', '')
                elif doi.startswith('http://doi.org/'):
                    doi = doi.replace('http://doi.org/', '')
                elif doi.startswith('doi:'):
                    doi = doi.replace('doi:', '')
                
                self.doi_to_category_map[doi] = str(category).strip()
        
        print(f"🗺️  学科映射建立完成: {len(self.doi_to_category_map)}个")
    
    def doi_to_categories(self, doi: str) -> List[str]:
        """根据DOI返回学科列表"""
        if not doi or pd.isna(doi):
            return []
        
        doi_str = str(doi).strip()
        # 标准化DOI格式
        if doi_str.startswith('https://doi.org/'):
            doi_str = doi_str.replace('https://doi.org/', '')
        elif doi_str.startswith('http://doi.org/'):
            doi_str = doi_str.replace('http://doi.org/', '')
        elif doi_str.startswith('doi:'):
            doi_str = doi_str.replace('doi:', '')
        
        category = self.doi_to_category_map.get(doi_str)
        return [category] if category else []
    
    def get_reference_categories_with_frequency(self, doi_list: List[str]) -> List[str]:
        """获取包含频率的学科列表"""
        if not doi_list:
            return []
        
        all_categories = []
        for doi in doi_list:
            categories = self.doi_to_categories(doi)
            all_categories.extend(categories)
        
        return all_categories
    
    def get_reference_categories(self, doi_list: List[str]) -> List[str]:
        """获取去重的学科列表"""
        if not doi_list:
            return []
        
        all_categories = []
        for doi in doi_list:
            categories = self.doi_to_categories(doi)
            all_categories.extend(categories)
        
        return list(set(all_categories))
    
    def build_co_occurrence_matrix(self, df: pd.DataFrame) -> Tuple[np.ndarray, List[str]]:
        """构建学科共现矩阵"""
        all_categories = set()
        for doi_list in df['citing']:
            categories = self.get_reference_categories(doi_list)
            all_categories.update(categories)
        
        all_categories = sorted(list(all_categories))
        n_categories = len(all_categories)
        category_index = {cat: idx for idx, cat in enumerate(all_categories)}
        
        co_occurrence = np.zeros((n_categories, n_categories))
        
        for doi_list in df['citing']:
            categories = self.get_reference_categories(doi_list)
            for i in range(len(categories)):
                idx_i = category_index[categories[i]]
                co_occurrence[idx_i, idx_i] += 1
                
                for j in range(i + 1, len(categories)):
                    idx_j = category_index[categories[j]]
                    co_occurrence[idx_i, idx_j] += 1
                    co_occurrence[idx_j, idx_i] += 1
        
        return co_occurrence, all_categories
    
    def calculate_salton_similarity(self, co_occurrence_matrix: np.ndarray) -> np.ndarray:
        """计算Salton余弦相似性矩阵"""
        n = co_occurrence_matrix.shape[0]
        similarity_matrix = np.zeros((n, n))
        
        for i in range(n):
            for j in range(n):
                if i == j:
                    similarity_matrix[i, j] = 1.0
                else:
                    numerator = 0.0
                    for k in range(n):
                        numerator += co_occurrence_matrix[i, k] * co_occurrence_matrix[j, k]
                    
                    denominator_i = np.sqrt(np.sum(co_occurrence_matrix[i, :]**2))
                    denominator_j = np.sqrt(np.sum(co_occurrence_matrix[j, :]**2))
                    denominator = denominator_i * denominator_j
                    
                    if denominator > 0:
                        similarity_matrix[i, j] = numerator / denominator
                    else:
                        similarity_matrix[i, j] = 0.0
        
        return similarity_matrix
    
    def calculate_td_for_paper(self, paper_categories: List[str], 
                              similarity_matrix: np.ndarray, 
                              all_categories: List[str]) -> float:
        """计算单篇论文的TD指标"""
        if not paper_categories:
            return 1.0
        
        category_index = {cat: idx for idx, cat in enumerate(all_categories)}
        
        # 计算学科分布
        category_counts = {}
        for cat in paper_categories:
            category_counts[cat] = category_counts.get(cat, 0) + 1
        
        total_refs = len(paper_categories)
        p_vector = np.zeros(len(all_categories))
        
        for cat, count in category_counts.items():
            if cat in category_index:
                idx = category_index[cat]
                p_vector[idx] = count / total_refs
        
        # 计算TD指标
        sum_term = 0.0
        for i in range(len(all_categories)):
            for j in range(len(all_categories)):
                sum_term += similarity_matrix[i, j] * p_vector[i] * p_vector[j]
        
        if sum_term > 0:
            return 1.0 / sum_term
        else:
            return 1.0
    
    def calculate_interdisciplinarity(self, df: pd.DataFrame) -> Tuple[pd.DataFrame, np.ndarray, List[str], pd.Series]:
        """计算跨学科性指标"""
        print("开始计算跨学科性指标...")
        
        # 构建学科共现矩阵
        print("  1. 构建学科共现矩阵...")
        co_occurrence, all_categories = self.build_co_occurrence_matrix(df)
        print(f"     学科数: {len(all_categories)}")
        
        # 计算相似性矩阵
        print("  2. 计算学科相似性矩阵...")
        similarity_matrix = self.calculate_salton_similarity(co_occurrence)
        
        # 计算每篇论文的TD指标
        print("  3. 计算单篇论文TD指标...")
        td_scores = []
        
        for idx, row in df.iterrows():
            paper_categories = self.get_reference_categories_with_frequency(row['citing'])
            td_score = self.calculate_td_for_paper(paper_categories, similarity_matrix, all_categories)
            td_scores.append(td_score)
        
        df_result = df.copy()
        df_result['TD_Score'] = td_scores
        
        # 计算期刊层面的平均TD
        journal_td = df_result.groupby('Source Title')['TD_Score'].mean().sort_values(ascending=False)
        
        print("跨学科性计算完成")
        return df_result, similarity_matrix, all_categories, journal_td
    
    def save_results(self, df_with_td: pd.DataFrame, 
                     similarity_matrix: np.ndarray, 
                     all_categories: List[str], 
                     journal_td: pd.Series):
        """保存结果到文件"""
        print(" 保存结果文件...")
        
        # 1. 保存期刊TD得分
        journal_td_df = journal_td.reset_index()
        journal_td_df.columns = ['Journal', 'TD_Score']
        journal_td_df['TD_Score'] = journal_td_df['TD_Score'].round(4)
        
        journal_output_path = os.path.join(self.output_dir, 'journal_td_scores.csv')
        journal_td_df.to_csv(journal_output_path, index=False, encoding='utf-8-sig')
        print(f"期刊TD得分: {journal_output_path}")
        
        # 2. 保存每篇论文的TD得分
        paper_output_path = os.path.join(self.output_dir, 'paper_td_scores.csv')
        paper_results = df_with_td[['Source Title', 'DOI', 'TD_Score']].copy()
        paper_results['TD_Score'] = paper_results['TD_Score'].round(4)
        paper_results.to_csv(paper_output_path, index=False, encoding='utf-8-sig')
        print(f"论文TD得分: {paper_output_path}")
        
        # 3. 保存学科相似性矩阵
        similarity_output_path = os.path.join(self.output_dir, 'similarity_matrix.csv')
        similarity_df = pd.DataFrame(similarity_matrix, index=all_categories, columns=all_categories)
        similarity_df.to_csv(similarity_output_path, encoding='utf-8-sig')
        print(f"学科相似性矩阵: {similarity_output_path}")
        
        # 4. 保存学科列表
        categories_output_path = os.path.join(self.output_dir, 'categories_list.csv')
        categories_df = pd.DataFrame({'Category': all_categories})
        categories_df.to_csv(categories_output_path, index=False, encoding='utf-8-sig')
        print(f"学科列表: {categories_output_path}")
        
        # 5. 保存可视化图表
        self.plot_journal_td(journal_td)
    
    def plot_journal_td(self, journal_td: pd.Series):
        """绘制期刊TD图表并保存"""
        plt.figure(figsize=(14, 7))
        bars = plt.bar(journal_td.index, journal_td.values)
        plt.title('Journal Interdisciplinarity (TD Index) - Top 10 Journals', fontsize=14, fontweight='bold')
        plt.xlabel('Journal', fontsize=12)
        plt.ylabel('TD Index', fontsize=12)
        plt.xticks(rotation=45, ha='right', fontsize=10)
        
        # 在每个柱子上添加数值
        for bar in bars:
            height = bar.get_height()
            plt.text(bar.get_x() + bar.get_width()/2., height,
                    f'{height:.3f}', ha='center', va='bottom', fontsize=9)
        
        plt.tight_layout()
        
        # 保存图表
        chart_output_path = os.path.join(self.output_dir, 'journal_td_chart.png')
        plt.savefig(chart_output_path, dpi=300, bbox_inches='tight')
        print(f"可视化图表: {chart_output_path}")
        
        plt.show()
    
    def run_analysis(self):
        """运行完整的分析流程"""
        print("跨学科性(TD)分析开始")
        
        # 1. 加载数据
        if not self.load_data():
            print("❌ 数据加载失败，分析终止")
            return
        
        # 2. 数据预处理
        self.preprocess_data()
        
        # 3. 建立学科映射
        self.build_category_mapping()
        
        # 4. 计算跨学科性
        df_with_td, similarity_matrix, all_categories, journal_td = self.calculate_interdisciplinarity(self.df_top10)
               
        # 6. 保存结果
        self.save_results(df_with_td, similarity_matrix, all_categories, journal_td)
        print(f"所有结果已保存到: {self.output_dir}")


def main():
    """主函数"""
    analyzer = InterdisciplinaryAnalyzer()
    analyzer.run_analysis()


if __name__ == "__main__":
    main()