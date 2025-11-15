# build_db.py
# 负责：创建 wos 分析库 + 写入待爬机构清单

from pathlib import Path
import sqlite3

# 1. 统一路径
DB_PATH = Path('data/raw/wos.db')
DB_PATH.parent.mkdir(exist_ok=True)   # 确保目录存在

# 2. 连接数据库（自动创建）
conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()

# 3. 建表
cur.execute('''
CREATE TABLE IF NOT EXISTS infos (
    school           TEXT,
    address          TEXT PRIMARY KEY,
    url              TEXT,
    result_count     INTEGER,
    page_count       INTEGER,
    crawled_or_not   INTEGER DEFAULT 0
);
''')

# 4. 示例机构（可继续追加）
sample = [
    ('tsinghua_university', 'Tsinghua Univ, Beijing, Peoples R China'),
    ('peking_university',   'Peking Univ, Beijing, Peoples R China'),
    ('zhejiang_university', 'Zhejiang Univ, Hangzhou, Peoples R China'),
    ('fudan_university',    'Fudan Univ, Shanghai, Peoples R China'),
    ('sjtu',                'Shanghai Jiao Tong Univ, Shanghai, Peoples R China'),
]
cur.executemany('INSERT OR IGNORE INTO infos (school, address) VALUES (?, ?)', sample)

conn.commit()
conn.close()
print(f'{DB_PATH.name} 已建好，示例机构已插入！')