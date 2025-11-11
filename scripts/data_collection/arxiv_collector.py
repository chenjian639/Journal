# scripts/data_collection/arxiv_collector.py
import requests
import pandas as pd
import xml.etree.ElementTree as ET
from datetime import datetime
import time
import os

def fetch_arxiv_papers(keywords, max_results=100):
    """从arXiv API获取论文数据"""
    
    papers_data = []
    
    for keyword in keywords:
        print(f"🔍 搜索关键词: {keyword}")
        
        url = "http://export.arxiv.org/api/query"
        params = {
            'search_query': f'all:{keyword}',
            'start': 0,
            'max_results': max_results,
            'sortBy': 'submittedDate',
            'sortOrder': 'descending'
        }
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            
            # 解析XML响应
            root = ET.fromstring(response.content)
            
            # arXiv使用Atom格式，命名空间
            ns = {'atom': 'http://www.w3.org/2005/Atom'}
            
            for entry in root.findall('atom:entry', ns):
                paper = {}
                
                # 提取论文信息
                paper['id'] = entry.find('atom:id', ns).text.split('/')[-1] if entry.find('atom:id', ns) is not None else ''
                paper['title'] = entry.find('atom:title', ns).text.strip() if entry.find('atom:title', ns) is not None else ''
                paper['summary'] = entry.find('atom:summary', ns).text.strip() if entry.find('atom:summary', ns) is not None else ''
                paper['published'] = entry.find('atom:published', ns).text if entry.find('atom:published', ns) is not None else ''
                paper['updated'] = entry.find('atom:updated', ns).text if entry.find('atom:updated', ns) is not None else ''
                
                # 提取作者
                authors = []
                for author in entry.findall('atom:author', ns):
                    name = author.find('atom:name', ns).text if author.find('atom:name', ns) is not None else ''
                    authors.append(name)
                paper['authors'] = ', '.join(authors)
                
                # 提取分类
                categories = []
                for category in entry.findall('atom:category', ns):
                    cat = category.get('term', '')
                    categories.append(cat)
                paper['categories'] = ', '.join(categories)
                
                # 提取期刊信息（如果有）
                paper['journal_ref'] = entry.find('atom:journal_ref', ns).text if entry.find('atom:journal_ref', ns) is not None else 'arXiv'
                
                papers_data.append(paper)
            
            print(f"✅ 获取到 {len(papers_data)} 篇论文")
            
            # 避免请求过快
            time.sleep(1)
            
        except Exception as e:
            print(f"❌ 获取 {keyword} 时出错: {e}")
            continue
    
    return papers_data

def save_arxiv_data(papers_data, output_file):
    """保存arXiv数据到CSV"""
    df = pd.DataFrame(papers_data)
    
    # 数据清洗和处理
    df['year'] = pd.to_datetime(df['published']).dt.year
    df['published_date'] = pd.to_datetime(df['published'])
    
    # 重命名列以匹配我们的分析系统
    df = df.rename(columns={
        'summary': 'abstract',
        'journal_ref': 'journal'
    })
    
    # 选择需要的列
    final_columns = ['id', 'title', 'abstract', 'authors', 'journal', 'year', 'published_date', 'categories']
    df = df[[col for col in final_columns if col in df.columns]]
    
    # 保存到文件
    os.makedirs(os.path.dirname(output_file), exist_ok=True)
    df.to_csv(output_file, index=False, encoding='utf-8')
    print(f"💾 数据已保存到: {output_file}")
    
    return df

def main():
    """主函数"""
    # 搜索关键词（可以根据需要修改）
    keywords = [
        "machine learning",
        "deep learning", 
        "artificial intelligence",
        "computer vision",
        "natural language processing"
    ]
    
    # 输出文件路径
    output_file = "data/raw/arxiv_ai_papers.csv"
    
    print("🚀 开始从arXiv收集AI领域论文...")
    
    # 获取数据
    papers_data = fetch_arxiv_papers(keywords, max_results=50)  # 每个关键词50篇
    
    if papers_data:
        # 保存数据
        df = save_arxiv_data(papers_data, output_file)
        
        # 显示统计信息
        print(f"\n📊 数据统计:")
        print(f"   总论文数: {len(df)}")
        print(f"   时间范围: {df['year'].min()} - {df['year'].max()}")
        print(f"   期刊分布: {df['journal'].nunique()} 种来源")
        print(f"   领域分布: {df['categories'].str.split(',').explode().str.strip().nunique()} 个分类")
        
        print(f"\n📝 前3篇论文示例:")
        for i, row in df.head(3).iterrows():
            print(f"   {i+1}. {row['title'][:80]}...")
            
    else:
        print("❌ 未获取到数据")

if __name__ == "__main__":
    main()