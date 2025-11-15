# export_result.py
import sqlite3
import pandas as pd
from pathlib import Path

DB_PATH   = Path('data/raw/wos.db')          # ① 指向新库
OUT_DIR   = Path('data/raw')                 # ② 输出目录
OUT_DIR.mkdir(exist_ok=True)

conn = sqlite3.connect(DB_PATH)

# ① 列出所有学校表
tables = [t[0] for t in conn.execute(
    "SELECT name FROM sqlite_master WHERE type='table' AND name!='infos' AND name!='sqlite_sequence'"
).fetchall()]

print('库中表:', tables)

# ② 逐个表导出 → data/raw/
for tbl in tables:
    df = pd.read_sql_query(f'SELECT * FROM "{tbl}"', conn)
    df.to_csv(OUT_DIR / f'{tbl}_cleaned.csv', index=False, encoding='utf-8-sig')
    df.to_excel(OUT_DIR / f'{tbl}_cleaned.xlsx', index=False)

print('已导出：', [f'{t}_cleaned.csv/.xlsx' for t in tables])
conn.close()