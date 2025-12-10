# -*- coding: utf-8 -*-
"""
preprocess_wos_data.py
功能：从clean_config.yaml读取配置，处理数据（支持Excel和数据库）
所有参数都从配置文件读取
"""
import pandas as pd
import os, glob, re, yaml, json
from pathlib import Path
import sys
from sqlalchemy import create_engine, text

def load_clean_config(config_path=None):
    """加载清洗配置文件"""
    if config_path is None:
        root_dir = Path(__file__).parent.parent
        config_path = root_dir / "clean_config.yaml"
        
        if not config_path.exists():
            print("[错误] 未找到 clean_config.yaml 文件")
            print(f"请确保在项目根目录创建 clean_config.yaml 文件")
            print(f"预期路径: {config_path}")
            sys.exit(1)
    
    with open(config_path, 'r', encoding='utf-8') as f:
        config = yaml.safe_load(f)
    
    if config is None:
        print("[错误] 配置文件为空")
        sys.exit(1)
    
    # 验证必要配置
    required_sections = ['data_source', 'cleaning', 'field_mapping']
    for section in required_sections:
        if section not in config:
            print(f"[错误] 配置文件中缺少必要部分: {section}")
            sys.exit(1)
    
    return config

def load_analysis_config():
    """加载原有的分析配置文件"""
    root_dir = Path(__file__).parent.parent
    config_path = root_dir / "config.json"
    
    if config_path.exists():
        with open(config_path, 'r', encoding='utf-8') as f:
            return json.load(f)
    return None

def extract_dois_from_references(ref):
    """从参考文献中提取DOI"""
    if pd.isna(ref): 
        return []
    
    patterns = [
        r'DOI\s+([^\s;,\]]+)',
        r'doi:\s*([^\s;,\]]+)',
        r'10\.\d{4,9}/[-._;()/:A-Z0-9]+',
    ]
    
    dois = []
    for pattern in patterns:
        found = re.findall(pattern, str(ref), re.IGNORECASE)
        if found:
            for d in found:
                d_clean = d.strip().lstrip('[').rstrip(',;]')
                if d_clean.startswith('10.') and len(d_clean) > 10:
                    dois.append(d_clean)
    
    return list(set(dois))

def is_conference(title):
    """判断是否为会议论文"""
    if pd.isna(title): 
        return False
    
    t = str(title).upper()
    conference_keywords = [
        'CONFERENCE', 'PROCEEDINGS', 'SYMPOSIUM',
        'MEETING', 'CONGRESS', 'WORKSHOP',
        'PROC.', 'CONF.', 'SYMP.'
    ]
    
    return any(w in t for w in conference_keywords) or bool(re.search(r'20\d{2}', t))

def find_actual_column(df, possible_names):
    """在DataFrame中查找实际存在的列名"""
    for name in possible_names:
        if name in df.columns:
            return name
    
    df_cols_lower = [str(col).lower().strip() for col in df.columns]
    for name in possible_names:
        name_lower = name.lower().strip()
        if name_lower in df_cols_lower:
            idx = df_cols_lower.index(name_lower)
            return df.columns[idx]
    
    return None

def get_needed_columns_from_configs(clean_config, analysis_config):
    """从配置文件中获取所有需要的列"""
    needed_columns = set()
    
    # 从清洗配置中获取字段映射的目标列
    if 'field_mapping' in clean_config:
        for target_col in clean_config['field_mapping'].keys():
            needed_columns.add(target_col)
    
    # 从分析配置中获取需要的列
    if analysis_config:
        for module, config in analysis_config.items():
            if 'columns' in config:
                for col_value in config['columns'].values():
                    if col_value and col_value.strip():
                        needed_columns.add(col_value.strip())
    
    # 添加必要的基础列
    needed_columns.add('Cited References')  # 用于提取DOI
    
    return list(needed_columns)

def load_excel_data(excel_dir, field_mapping):
    """从Excel文件加载数据"""
    # 获取所有可能的列名
    all_possible_columns = set()
    for possible_names in field_mapping.values():
        all_possible_columns.update(possible_names)
    
    print(f"\n[字段筛选] 只读取以下字段:")
    for col in sorted(all_possible_columns):
        print(f"  - {col}")
    
    # 查找Excel文件
    excel_files = glob.glob(os.path.join(excel_dir, "*.xls*"))
    if not excel_files:
        # 如果路径不存在，尝试相对路径
        root_dir = Path(__file__).parent.parent
        excel_dir = root_dir / excel_dir
        excel_files = glob.glob(os.path.join(str(excel_dir), "*.xls*"))
    
    if not excel_files:
        raise FileNotFoundError(f"未找到Excel文件: {excel_dir}")
    
    print(f"\n[数据源] 找到 {len(excel_files)} 个Excel文件:")
    
    # 读取每个文件
    dfs = []
    for excel_file in excel_files:
        try:
            # 检查文件中的列
            temp_df = pd.read_excel(excel_file, nrows=0)
            existing_columns = [col for col in all_possible_columns if col in temp_df.columns]
            
            if not existing_columns:
                print(f"  [警告] {os.path.basename(excel_file)} 中没有找到目标列")
                continue
            
            print(f"  读取 {os.path.basename(excel_file)}...", end="")
            
            # 只读取存在的列
            df_temp = pd.read_excel(excel_file, usecols=existing_columns)
            df_temp['source_file'] = os.path.basename(excel_file)
            dfs.append(df_temp)
            
            print(f" 成功 ({df_temp.shape[0]}行)")
            
        except Exception as e:
            print(f" 失败: {e}")
    
    if not dfs:
        raise ValueError("未能读取任何Excel文件的数据")
    
    # 合并数据
    df = pd.concat(dfs, ignore_index=True)
    print(f"\n[数据加载] Excel数据: {df.shape[0]}行 × {df.shape[1]}列")
    
    return df

def load_database_data(db_config, field_mapping):
    """从数据库加载数据"""
    print("\n[数据源] 从数据库读取数据...")
    
    try:
        # 获取所有可能的列名
        all_possible_columns = []
        for possible_names in field_mapping.values():
            all_possible_columns.extend(possible_names)
        
        # 处理方言映射
        dialect_map = {
            'mysql': 'mysql+pymysql',
            'postgresql': 'postgresql',
            'sqlite': 'sqlite'
        }
        
        dialect = db_config.get('dialect', '').lower()
        if dialect not in dialect_map:
            raise ValueError(f"不支持的数据库类型: {dialect}")
        
        actual_dialect = dialect_map[dialect]
        
        # 构建连接字符串
        if dialect == 'sqlite':
            # SQLite
            database_path = db_config.get('database', '')
            if not database_path:
                raise ValueError("SQLite需要指定数据库文件路径")
            conn_str = f"sqlite:///{database_path}"
        else:
            # MySQL/PostgreSQL
            user = db_config.get('user', '')
            password = db_config.get('password', '')
            host = db_config.get('host', 'localhost')
            port = str(db_config.get('port', ''))
            database = db_config.get('database', '')
            
            # 构建连接字符串
            if dialect == 'mysql':
                # MySQL额外参数（处理中文）
                conn_str = f"{actual_dialect}://{user}:{password}@{host}:{port}/{database}?charset=utf8mb4"
            else:
                conn_str = f"{actual_dialect}://{user}:{password}@{host}:{port}/{database}"
        
        print(f"  连接字符串: {conn_str.replace(password, '***')}")  # 安全显示
        
        # 创建引擎
        engine = create_engine(conn_str, echo=False)
        
        # 测试连接
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        print("  ✓ 数据库连接成功")
        
        # 决定使用SQL查询还是直接读表
        if 'sql' in db_config and db_config['sql']:
            # 使用自定义SQL
            sql_query = db_config['sql']
            print(f"  执行SQL查询: {sql_query[:100]}...")
            df = pd.read_sql(text(sql_query), engine)
        elif 'table' in db_config and db_config['table']:
            # 读取整表
            table_name = db_config['table']
            print(f"  读取表: {table_name}")
            
            # 先获取表的列名
            try:
                with engine.connect() as conn:
                    result = conn.execute(text(f"SELECT * FROM `{table_name}` LIMIT 0"))
                    table_columns = list(result.keys())
            except:
                # 有些数据库不支持反引号
                with engine.connect() as conn:
                    result = conn.execute(text(f'SELECT * FROM "{table_name}" LIMIT 0'))
                    table_columns = list(result.keys())
            
            # 筛选需要的列
            columns_to_read = [col for col in table_columns if col in all_possible_columns]
            
            if columns_to_read:
                print(f"  读取 {len(columns_to_read)} 个列")
                columns_str = ', '.join([f'`{col}`' for col in columns_to_read])
                query = f"SELECT {columns_str} FROM `{table_name}`"
                df = pd.read_sql(text(query), engine)
            else:
                print("  [警告] 表中未找到目标列，读取所有列")
                query = f"SELECT * FROM `{table_name}`"
                df = pd.read_sql(text(query), engine)
        else:
            raise ValueError("数据库配置中必须指定 'sql' 或 'table'")
        
        print(f"  [数据加载] 数据库数据: {df.shape[0]}行 × {df.shape[1]}列")
        return df
        
    except Exception as e:
        print(f"  [错误] 数据库连接失败: {str(e)}")
        import traceback
        traceback.print_exc()
        raise
def map_and_filter_columns(df, field_mapping, needed_columns):
    """映射列名并过滤不需要的列"""
    column_mapping = {}
    
    print("\n[字段映射] 正在映射列名:")
    for target_col, possible_names in field_mapping.items():
        actual_col = find_actual_column(df, possible_names)
        if actual_col:
            column_mapping[actual_col] = target_col
            print(f"  ✓ {actual_col} → {target_col}")
        else:
            print(f"  ✗ 未找到: {target_col}")
    
    # 应用列名映射
    if column_mapping:
        df = df.rename(columns=column_mapping)
    
    # 只保留需要的列
    available_columns = [col for col in needed_columns if col in df.columns]
    df = df[available_columns]
    
    print(f"\n[字段过滤] 最终保留 {len(df.columns)} 个列: {list(df.columns)}")
    
    return df

def run_clean(clean_config_path=None):
    """主清洗函数"""
    print("=" * 60)
    print("WOS数据清洗工具")
    print("=" * 60)
    
    try:
        # 加载配置
        print("[配置] 正在加载配置文件...")
        clean_config = load_clean_config(clean_config_path)
        analysis_config = load_analysis_config()
        
        # 从配置读取参数
        source_type = clean_config['data_source']['type']
        cleaning = clean_config['cleaning']
        field_mapping = clean_config['field_mapping']
        
        # 清洗参数（使用get方法，允许配置文件中某些值为null）
        drop_conference = cleaning.get('drop_conference', True)
        min_year = cleaning.get('min_year')
        target_journals = cleaning.get('target_journals', [])
        top_n = cleaning.get('top_n', 10)
        
        print(f"[配置] 数据源类型: {source_type}")
        print(f"[配置] 清洗规则:")
        print(f"  - 去除会议论文: {drop_conference}")
        print(f"  - 最小年份: {min_year if min_year else '不限制'}")
        if target_journals:
            print(f"  - 指定期刊: {len(target_journals)} 种")
        else:
            print(f"  - 自动选取Top: {top_n}")
        
        # 获取需要的列
        needed_columns = get_needed_columns_from_configs(clean_config, analysis_config)
        print(f"\n[字段需求] 需要字段: {needed_columns}")
        
        # 设置输出路径
        root_dir = Path(__file__).parent.parent
        cleaned_dir = root_dir / "data" / "cleaned"
        cleaned_dir.mkdir(parents=True, exist_ok=True)
        
        # 根据数据源类型加载数据
        if source_type.lower() == 'excel':
            excel_dir = clean_config['data_source']['excel_dir']
            if not os.path.isabs(excel_dir):
                excel_dir = str(root_dir / excel_dir)
            
            df = load_excel_data(excel_dir, field_mapping)
            
        elif source_type.lower() == 'database':
            if 'database' not in clean_config['data_source']:
                raise ValueError("数据库配置缺失，请检查clean_config.yaml")
            
            db_config = clean_config['data_source']['database']
            df = load_database_data(db_config, field_mapping)
            
        else:
            raise ValueError(f"不支持的数据源类型: {source_type}")
        
        # 映射和过滤列
        df = map_and_filter_columns(df, field_mapping, needed_columns)
        
        print(f"\n[清洗] 原始数据: {df.shape[0]}行")
        
        # 1. 生成citing列
        if 'Cited References' in df.columns:
            print("[清洗] 正在从参考文献中提取DOI...")
            df['citing'] = df['Cited References'].apply(extract_dois_from_references)
            total_dois = df['citing'].apply(len).sum()
            print(f"[清洗] 成功提取 {total_dois} 个DOI引用")
        else:
            print("[警告] 未找到'Cited References'列，无法提取DOI")
            df['citing'] = [[] for _ in range(len(df))]
        
        # 2. 去除会议论文
        if drop_conference and 'Source Title' in df.columns:
            before_count = len(df)
            df = df[~df['Source Title'].apply(is_conference)]
            after_count = len(df)
            removed = before_count - after_count
            if removed > 0:
                print(f"[清洗] 去除会议论文: {before_count} → {after_count} (-{removed})")
        
        # 3. 年份筛选（只有当min_year不为None或空时才应用）
        if min_year and 'Publication Year' in df.columns:
            try:
                df['Publication Year'] = pd.to_numeric(df['Publication Year'], errors='coerce')
                before_count = len(df)
                df = df[df['Publication Year'] >= min_year]
                after_count = len(df)
                removed = before_count - after_count
                if removed > 0:
                    print(f"[清洗] 年份筛选(≥{min_year}): {before_count} → {after_count} (-{removed})")
                else:
                    print(f"[清洗] 所有数据年份均≥{min_year}")
            except Exception as e:
                print(f"[警告] 年份筛选失败: {e}")
        elif min_year is None:
            print("[清洗] 未设置年份限制，跳过年份筛选")
        
        # 保存全量数据
        all_data_path = cleaned_dir / "all_data.csv"
        df.to_csv(all_data_path, index=False, encoding='utf-8-sig')
        print(f"\n[保存] 全量数据已保存: {all_data_path}")
        print(f"      数据形状: {df.shape}")
        print(f"      包含列: {list(df.columns)}")
        
        # 生成目标期刊数据
        if 'Source Title' in df.columns and df.shape[0] > 0:
            if target_journals:
                # 使用指定期刊
                target_df = df[df['Source Title'].isin(target_journals)]
                print(f"\n[期刊筛选] 使用指定期刊列表: {len(target_journals)} 种期刊")
            else:
                # 自动取Top-N期刊
                journal_counts = df['Source Title'].value_counts()
                top_journals = journal_counts.head(top_n).index.tolist()
                target_df = df[df['Source Title'].isin(top_journals)]
                
                print(f"\n[期刊筛选] 自动选取Top-{top_n}期刊:")
                for i, (journal, count) in enumerate(journal_counts.head(top_n).items(), 1):
                    print(f"          {i:2d}. {journal}: {count}篇")
            
            print(f"          共找到 {len(target_df)} 条记录")
            
            # 保存target_data.csv
            target_data_path = cleaned_dir / "target_data.csv"
            target_df.to_csv(target_data_path, index=False, encoding='utf-8-sig')
            print(f"[保存] 目标期刊数据已保存: {target_data_path}")
            print(f"      数据形状: {target_df.shape}")
        else:
            print("\n[警告] 无法生成目标期刊数据")
            target_data_path = None
        
        print("\n" + "=" * 60)
        print("清洗完成！")
        print("=" * 60)
        
        return all_data_path, target_data_path
        
    except Exception as e:
        print(f"\n[错误] 清洗过程中出现错误: {e}")
        import traceback
        traceback.print_exc()
        return None, None

if __name__ == "__main__":
    import argparse
    
    parser = argparse.ArgumentParser(description='WOS数据清洗工具')
    parser.add_argument('--config', '-c', help='清洗配置文件路径', default=None)
    args = parser.parse_args()
    
    run_clean(args.config)