# -*- coding: utf-8 -*-
"""
python_analysis/novelty_analyzer.py
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
