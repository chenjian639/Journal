# python_analysis/theme_analyzer.py

"""
theme_analyzer.py - 期刊主题分析模块
功能：
- 提取每个期刊的Top5高频关键词
- 调用星火API对期刊研究主题进行描述性分析
- 输出结构化JSON结果到 outputs/theme/
"""

import os
import json
import pandas as pd
from collections import Counter
import requests
import ast
from typing import Dict, List


def _extract_all_keywords(df: pd.DataFrame) -> Dict[str, List[str]]:
    """提取所有论文的关键词"""
    paper_keywords = {}

    for idx, row in df.iterrows():
        paper_id = f"paper_{idx}"
        keywords = []

        if pd.notna(row.get('Keywords')):
            try:
                if isinstance(row['Keywords'], str):
                    if row['Keywords'].startswith('['):
                        keywords = ast.literal_eval(row['Keywords'])
                    else:
                        if ';' in row['Keywords']:
                            keywords = [kw.strip() for kw in row['Keywords'].split(';') if kw.strip()]
                        else:
                            keywords = [kw.strip() for kw in row['Keywords'].split(',') if kw.strip()]
                else:
                    keywords = []
            except:
                keywords = []

        cleaned_keywords = [str(kw).lower().strip() for kw in keywords if str(kw).strip()]
        paper_keywords[paper_id] = cleaned_keywords

    return paper_keywords


def _calculate_journal_keyword_freq(df: pd.DataFrame, paper_keywords: Dict[str, List[str]], min_papers: int = 5) -> Dict[str, Counter]:
    """按期刊统计关键词频率"""
    journal_keywords = {}

    for paper_id, keywords in paper_keywords.items():
        idx = int(paper_id.split('_')[1])
        journal = df.iloc[idx]['Source Title']

        if pd.isna(journal):
            continue

        if journal not in journal_keywords:
            journal_keywords[journal] = []

        journal_keywords[journal].extend(keywords)

    # 过滤小期刊
    journal_keyword_freq = {}
    for journal, keywords in journal_keywords.items():
        journal_papers = df[df['Source Title'] == journal]
        if len(journal_papers) >= min_papers and keywords:
            journal_keyword_freq[journal] = Counter(keywords)

    return journal_keyword_freq


def analyze_keywords(df: pd.DataFrame, min_papers: int = 5) -> Dict[str, List[str]]:
    """
    分析每个期刊的Top5关键词
    :param df: 输入数据框，需包含 'Keywords' 和 'Source Title'
    :param min_papers: 最少论文数门槛
    :return: {期刊名: [Top5关键词]}
    """
    print("开始分析期刊关键词频率...")

    paper_keywords = _extract_all_keywords(df)
    journal_keyword_freq = _calculate_journal_keyword_freq(df, paper_keywords, min_papers)

    journal_top_keywords = {}
    for journal, counter in journal_keyword_freq.items():
        top5 = [kw for kw, cnt in counter.most_common(5)]
        journal_top_keywords[journal] = top5

    print(f" 关键词分析完成，共 {len(journal_top_keywords)} 个期刊")
    return journal_top_keywords


def get_answer(message: List[Dict], api_key: str) -> str:
    """
    调用星火大模型获取回答（禁用思维链）
    :param message: 消息列表，符合 chat 格式
    :param api_key: 认证用 Bearer Token
    :return: 模型返回的字符串
    """
    url = "https://spark-api-open.xf-yun.com/v2/chat/completions"
    headers = {
        'Authorization': api_key,
        'content-type': "application/json"
    }
    body = {
        "model": "x1",
        "user": "journal_analyzer",
        "messages": message,
        "stream": True,
        "max_tokens": 1024,
        "temperature": 0.7,
        "reasoning": False
    }

    full_response = ""
    try:
        response = requests.post(url=url, json=body, headers=headers, stream=True)
        for chunk_line in response.iter_lines():
            if chunk_line and b'[DONE]' not in chunk_line:
                try:
                    if chunk_line.startswith(b'data: '):
                        data_org = chunk_line[6:]
                    else:
                        data_org = chunk_line
                    chunk = json.loads(data_org)
                    text = chunk['choices'][0]['delta']
                    if 'content' in text and text['content']:
                        content = text["content"]
                        full_response += content
                except:
                    continue
    except Exception as e:
        return f"API调用失败: {str(e)}"

    return full_response


def analyze_journal_topics(journal_top_keywords: Dict[str, List[str]], api_key: str) -> Dict[str, str]:
    """
    对每个期刊生成主题分析文本
    :param journal_top_keywords: {期刊名: [关键词]}
    :param api_key: 星火API密钥
    :return: {期刊名: 分析文本}
    """
    print("开始调用AI分析期刊主题...")
    results = {}

    for journal, keywords in journal_top_keywords.items():
        print(f"\n分析期刊: {journal}")
        prompt = f"""请根据这个学术期刊的名称和其高频关键词，简要分析该期刊的主要研究方向和主题侧重点。

期刊名称：{journal}
高频关键词：{', '.join(keywords)}

请用100字左右描述该期刊的研究主题特点、技术方法和应用领域。直接输出分析结果，不要有任何思维过程。"""

        message = [{"role": "user", "content": prompt}]

        try:
            analysis = get_answer(message, api_key)
            results[journal] = analysis.strip()
            print(f"完成: {journal}")
        except Exception as e:
            print(f"❌ 失败: {e}")
            results[journal] = "分析失败"

    print("AI分析全部完成")
    return results


def run_theme_analysis(data_path: str = None, output_dir: str = None, api_key: str = None):
    """
    主函数：端到端运行期刊主题分析
    :param data_path: CSV 数据路径，默认为 data/raw/top10_journals_data.csv
    :param output_dir: 输出目录，默认为 outputs/theme/
    :param api_key: 星火API密钥，必须提供！
    """
    if api_key is None:
        raise ValueError("❌ 错误: 必须传入 api_key 参数！")

    # 设置路径
    project_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))  # 上两级是项目根目录
    data_path = data_path or os.path.join(project_root, 'data', 'raw', 'top10_journals_data.csv')
    output_dir = output_dir or os.path.join(project_root, 'outputs', 'theme')

    # 加载数据
    if not os.path.exists(data_path):
        raise FileNotFoundError(f"未找到数据文件: {data_path}")

    print(f"加载数据: {data_path}")
    df = pd.read_csv(data_path)

    # 创建输出目录
    os.makedirs(output_dir, exist_ok=True)

    # 阶段1: 关键词分析
    journal_top_keywords = analyze_keywords(df, min_papers=5)

    # 阶段2: AI 主题分析
    results = analyze_journal_topics(journal_top_keywords, api_key)

    # 阶段3: 输出到 JSON
    keywords_output = os.path.join(output_dir, 'journal_keywords.json')
    analysis_output = os.path.join(output_dir, 'journal_analysis.json')

    metadata = {
        "source_file": os.path.basename(data_path),
        "total_journals": len(journal_top_keywords)
    }

    # 输出关键词
    with open(keywords_output, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": metadata,
            "data": journal_top_keywords
        }, f, ensure_ascii=False, indent=2)
    print(f"期刊关键词表已保存至:\n   {keywords_output}")

    # 输出AI分析
    with open(analysis_output, 'w', encoding='utf-8') as f:
        json.dump({
            "metadata": metadata,
            "data": results
        }, f, ensure_ascii=False, indent=2)
    print(f"期刊主题分析结果已保存至:\n   {analysis_output}")
