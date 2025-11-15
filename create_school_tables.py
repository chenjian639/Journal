from pathlib import Path
import sqlite3

DB_PATH = Path('data/raw/wos.db')
schools = [
    'tsinghua_university',
    'peking_university',
    'fudan_university',
    'sjtu',
    'zhejiang_university'
]

conn = sqlite3.connect(DB_PATH)
cur = conn.cursor()
for s in schools:
    cur.execute(f'''
        CREATE TABLE IF NOT EXISTS "{s}" (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            address    TEXT,
            title      TEXT,
            authors    TEXT,
            pub_date   TEXT,
            conference TEXT,
            source     TEXT,
            citations  INTEGER,
            refs       INTEGER,
            wos_id     TEXT UNIQUE,
            abstract   TEXT
        );
    ''')
conn.commit()
conn.close()
print('各校表已建好！')