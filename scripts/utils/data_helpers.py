
import pandas as pd
import numpy as np
from typing import Dict, List, Any
import json

class DataConfig:
    """数据配置类"""
    SAMPLE_YEARS = [2021, 2022, 2023, 2024]
    FIELDS = ['material_science', 'ai', 'education']  # 示例学科
    
    # 期刊列表（示例）
    JOURNALS = {
        'journal_A': {'country': 'domestic', 'field': 'material_science'},
        'journal_B': {'country': 'domestic', 'field': 'material_science'}, 
        'journal_C': {'country': 'international', 'field': 'material_science'},
        'journal_D': {'country': 'international', 'field': 'material_science'},
        'journal_E': {'country': 'domestic', 'field': 'ai'},
        'journal_F': {'country': 'international', 'field': 'ai'}
    }

def generate_sample_data(num_papers=1000):
    """生成示例数据用于开发和测试"""
    np.random.seed(42)
    
    data = []
    journals = list(DataConfig.JOURNALS.keys())
    
    for i in range(num_papers):
        journal = np.random.choice(journals)
        year = np.random.choice(DataConfig.SAMPLE_YEARS)
        
        paper = {
            'paper_id': f'paper_{i:04d}',
            'journal': journal,
            'year': year,
            'title': f'Sample Paper Title {i}',
            'abstract': generate_sample_abstract(),
            'keywords': generate_sample_keywords(),
            'citation_count': np.random.poisson(10),
            'reference_count': np.random.randint(5, 50),
            'author_institutions': generate_sample_institutions(),
            'topic_label': np.random.choice(['nanomaterials', 'energy_storage', 'catalysis', 'biomaterials']),
            'methodology': np.random.choice(['experimental', 'computational', 'theoretical', 'review']),
        }
        data.append(paper)
    
    return pd.DataFrame(data)

def generate_sample_abstract():
    """生成示例摘要"""
    templates = [
        "This study investigates the properties of {material} for {application}. Results show significant improvements in {metric}.",
        "We present a novel approach to {process} using {technique}. Our method achieves {result}.",
        "This paper explores the relationship between {factor_a} and {factor_b} in {context}. Findings indicate {outcome}."
    ]
    
    materials = ['graphene', 'perovskite', 'MOF', 'quantum dots']
    applications = ['energy storage', 'catalysis', 'sensing', 'optoelectronics']
    techniques = ['DFT calculations', 'SEM analysis', 'XRD characterization', 'electrochemical testing']
    
    template = np.random.choice(templates)
    return template.format(
        material=np.random.choice(materials),
        application=np.random.choice(applications),
        technique=np.random.choice(techniques),
        metric='efficiency',
        process='synthesis',
        result='enhanced performance',
        factor_a='temperature',
        factor_b='crystal structure', 
        context='nanomaterial synthesis',
        outcome='a strong correlation'
    )

def generate_sample_keywords():
    """生成示例关键词"""
    keyword_pools = {
        'materials': ['graphene', 'MOF', 'nanoparticles', 'composite', 'thin film'],
        'methods': ['DFT', 'SEM', 'XRD', 'electrochemical', 'synthesis'],
        'properties': ['catalytic', 'optical', 'mechanical', 'thermal', 'electronic']
    }
    
    keywords = []
    for category in keyword_pools.values():
        keywords.extend(np.random.choice(category, size=2, replace=False))
    
    return keywords[:5]  # 返回5个关键词

def generate_sample_institutions():
    """生成示例机构"""
    institutions = [
        'Tsinghua University', 'Peking University', 'MIT', 'Stanford University',
        'Chinese Academy of Sciences', 'Max Planck Institute', 'University of Cambridge'
    ]
    return list(np.random.choice(institutions, size=np.random.randint(1, 4), replace=False))

def save_sample_data():
    """保存示例数据"""
    df = generate_sample_data(1000)
    df.to_csv('../data/raw/sample_papers.csv', index=False, encoding='utf-8')
    print(f"生成示例数据: {len(df)} 篇论文")
    
    # 保存数据字典
    data_dict = {
        'paper_id': '论文唯一标识',
        'journal': '期刊名称', 
        'year': '发表年份',
        'title': '论文标题',
        'abstract': '论文摘要',
        'keywords': '关键词列表',
        'citation_count': '被引次数',
        'reference_count': '参考文献数量',
        'author_institutions': '作者机构列表',
        'topic_label': '主题标签',
        'methodology': '研究方法'
    }
    
    with open('../docs/data_dict.md', 'w', encoding='utf-8') as f:
        f.write("# 数据字段说明\n\n")
        for field, desc in data_dict.items():
            f.write(f"- `{field}`: {desc}\n")
    
    return df
