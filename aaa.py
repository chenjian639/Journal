# test_db_simple.py
import pymysql
from sqlalchemy import create_engine, text

# 您的配置
configs = [
    {"host": "39.106.90.206", "port": 3306, "user": "paper_sys", "password": "e5f92621", "database": "paper_sys"},
    {"host": "39.106.90.206", "port": 8080, "user": "paper_sys", "password": "e5f92621", "database": "paper_sys"},
    {"host": "39.106.90.206", "port": 3306, "user": "PAPER_sys", "password": "e5f92621", "database": "paper_sys"},
    {"host": "39.106.90.206", "port": 8080, "user": "PAPER_sys", "password": "e5f92621", "database": "paper_sys"},
]

print("测试数据库连接...\n")

# 方法1: 直接pymysql
print("1. 使用pymysql测试:")
for cfg in configs:
    try:
        conn = pymysql.connect(**cfg, connect_timeout=3)
        with conn.cursor() as cursor:
            cursor.execute("SELECT VERSION()")
            version = cursor.fetchone()[0]
            cursor.execute("SHOW TABLES")
            tables = [t[0] for t in cursor.fetchall()]
        conn.close()
        print(f"  ✓ {cfg['host']}:{cfg['port']} ({cfg['user']}) - MySQL {version}")
        print(f"    表: {', '.join(tables[:3])}{'...' if len(tables)>3 else ''}")
        break
    except Exception as e:
        print(f"  ✗ {cfg['host']}:{cfg['port']} ({cfg['user']}) - {e}")

# 方法2: SQLAlchemy
print("\n2. 使用SQLAlchemy测试:")
drivers = ["mysql+pymysql", "mysql+mysqlconnector"]
for driver in drivers:
    for port in [3306, 8080]:
        for username in ["paper_sys", "PAPER_sys"]:
            try:
                conn_str = f"{driver}://{username}:e5f92621@39.106.90.206:{port}/paper_sys"
                engine = create_engine(conn_str, connect_args={'connect_timeout': 3})
                with engine.connect() as conn:
                    conn.execute(text("SELECT 1"))
                print(f"  ✓ {driver} - {username}@{port}")
                break
            except:
                continue