# 01_data_cleaning.ipynb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import seaborn as sns
from pathlib import Path
import sqlite3

# 连接爬虫数据库
DB_PATH = Path('../data/raw/wos.db')          # 相对 notebooks 目录
conn    = sqlite3.connect(DB_PATH)

# 中文字体
plt.rcParams['font.sans-serif'] = ['SimHei', 'DejaVu Sans']
plt.rcParams['axes.unicode_minus'] = False
print("✅ SQLite 环境完成，路径：", DB_PATH.resolve())
#  第二个单元格 读取真实爬取结果（tsinghua 为例，可改成列表循环）
school     = 'tsinghua_university'
raw_df     = pd.read_sql(f'SELECT * FROM "{school}"', conn)

print(f"📥 原始数据形状: {raw_df.shape}")
print(f"时间范围: {raw_df['pub_date'].min()} - {raw_df['pub_date'].max()}")
print(f"期刊数量: {raw_df['source'].nunique()}")
raw_df.head()
# 第三个单元格：基础清洗（期刊+年份+缺失处理）
df = raw_df.copy()

# 1. 缺失填充
df['abstract']   = df['abstract'].fillna('')
df['conference'] = df['conference'].fillna('')
df['citations']  = df['citations'].fillna(0).astype(int)
df['refs']       = df['refs'].fillna(0).astype(int)

# 2. 踢掉会议录
conf_kws = [
    'proceedings', 'conference', 'companion', 'symposium', 'workshop',
    'iccv', 'cvpr', 'eccv', 'icml', 'neurips', 'nips', 'chi', 'hri', 'icde',
    'siggraph', 'mm ', 'icra', 'iros', 'ecc', 'esscirc', 'ieee/cvf'
]

pattern = '|'.join(conf_kws)
df = df[~df['source'].str.contains(pattern, case=False, na=False)]
print(f"📚 去会议后: {df.shape[0]} 条")

# 3. 年份解析 + 2010-2024 过滤
df['year'] = pd.to_datetime(df['pub_date'], errors='coerce').dt.year
df = df.dropna(subset=['year'])
df = df[df['year'].between(2010, 2024)]
print(f"📅 年份过滤后: {df.shape[0]} 条 (2010-2024)")

# 4. 落盘
OUT_DIR = Path('../data/cleaned')
OUT_DIR.mkdir(exist_ok=True)
clean_file = OUT_DIR / f'{school}_cleaned.csv'
df.to_csv(clean_file, index=False, encoding='utf-8')

print(f"✅ 已保存: {clean_file} , 最终形状: {df.shape}")
df.head()
# 期刊分布 第四个单元格
# 提取短名
df['short_source'] = df['source'].str.extract(r'([A-Z]{2,}(?:\s[A-Z]{2,})*)')[0].fillna(df['source'])

# 只取 Top10
top10 = df['short_source'].value_counts().head(10)
plt.figure(figsize=(10, 6))
plt.barh(top10.index[::-1], top10.values[::-1], color=plt.cm.tab10(range(10)))
plt.title(f'{school} 期刊/会议短名 Top10')
plt.xlabel('篇数')
for i, v in enumerate(top10.values[::-1]):
    plt.text(v + 0.5, i, str(v), va='center')
plt.tight_layout()
plt.show()
# 年份趋势
plt.figure(figsize=(10, 6))
year_counts = df['year'].value_counts().sort_index()
plt.plot(year_counts.index, year_counts.values, marker='o')
plt.title(f'{school} 年度发文趋势')
plt.xlabel('年份')
plt.ylabel('篇数')
plt.tight_layout()
plt.show()