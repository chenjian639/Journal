import pandas as pd
import sqlite3
import numpy as np
from pathlib import Path

import yaml
BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = BASE_DIR / "config" / "clean_config.yaml"

import warnings
import pandas as _pd
# 兼容未来 pandas 行为，避�?bfill/ffill 下的 downcasting 警告
_pd.set_option('future.no_silent_downcasting', True)

def read_excel_file(path):
    """智能读取单个 Excel/HTML 文件�?
    - 根据扩展名优先选择 engine
    - �?.xls 无法读取时尝�?pd.read_html(..., encoding='gbk')（CNKI常见�?
    - 返回 DataFrame 或抛出异�?
    """
    p = Path(path)
    ext = p.suffix.lower()
    # 尝试按扩展名选择 engine
    try:
        if ext in ('.xlsx', '.xlsm', '.xltx', '.xltm'):
            return pd.read_excel(path, engine='openpyxl')
        if ext == '.xlsb':
            return pd.read_excel(path, engine='pyxlsb')
        if ext == '.xls':
            # �?.xls 文件，先尝试 xlrd
            try:
                return pd.read_excel(path, engine='xlrd')
            except Exception as e:
                warnings.warn(f"xlrd 读取失败: {e}; 尝试�?HTML/文本方式回退读取")
                # 回退尝试：有�?.xls �?HTML 表格（CNKI 常见�?
                try:
                    return pd.read_html(path, encoding='gbk')[0]
                except Exception:
                    try:
                        return pd.read_html(path, encoding='utf-8')[0]
                    except Exception:
                        raise

        # 其他扩展名，尝试 openpyxl 再回退�?read_html
        try:
            return pd.read_excel(path, engine='openpyxl')
        except Exception:
            try:
                return pd.read_html(path, encoding='gbk')[0]
            except Exception:
                return pd.read_html(path, encoding='utf-8')[0]

    except Exception:
        # 最后抛出异常给上层处理
        raise

# 读取 clean_config.yaml
with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

# 读取字段映射
field_mapping = config.get("field_mapping", {})

def apply_field_mapping(df, field_mapping):
    """
    根据 clean_config.yaml 中的 field_mapping
    �?CSV 中的列名统一映射为标准字段名
    """
    rename_dict = {}
    # 记录原始列名快照，后面用于提示未映射目标的可能候�?
    original_columns = list(df.columns)

    # 规范化候选名称（小写、去两端空格�?
    norm_map = {}
    for std_field, candidates in field_mapping.items():
        cand_list = candidates if isinstance(candidates, (list, tuple)) else [candidates]
        norm_map[std_field] = [str(c).strip().lower() for c in cand_list if c is not None]

    # 对每个原始列名进行匹配（优先精确匹配，再包含匹配�?
    for col in df.columns:
        norm_col = str(col).strip().lower()
        matched = False
        # 精确匹配
        for std_field, norm_cands in norm_map.items():
            if norm_col in norm_cands:
                rename_dict[col] = std_field
                matched = True
                break
        # 严格模式：只使用规范化后的精确匹配（不做包含/子串匹配�?
        if matched:
            continue

    # 应用映射但不打印中间映射细节（仅在末尾打印最终保留目标列�?
    # 构建反向映射：目标字�?-> 源列列表，用于最后输出说�?"源列 -> 目标�?
    reverse_map = {}
    for orig_col, std_field in rename_dict.items():
        reverse_map.setdefault(std_field, []).append(orig_col)

    if rename_dict:
        df = df.rename(columns=rename_dict)

    # （调试）此处不再打印中间列，下面将只打印最终保留的映射目标�?

    # 合并可能产生的同名列（例如多个源列都被映射为同一目标字段�?
    import pandas as _pd
    final_cols = []
    for std_field in field_mapping.keys():
        # 找出所有同名列（严格匹配）
        same_cols = [c for c in df.columns if str(c) == std_field]
        if len(same_cols) > 1:
            # 使用从左到右的第一个非空值作为合并结�?
            tmp = df[same_cols].bfill(axis=1).iloc[:, 0].infer_objects(copy=False)
            # 删除原列
            df.drop(columns=same_cols, inplace=True)
            # 插入合并后的�?
            df[std_field] = tmp
        final_cols.append(std_field)

    # 确保列名唯一
    df = df.loc[:, ~df.columns.duplicated()]

    # 只保留映射中指定的目标列（避免写入不需要的源列�?
    mapped_targets = [str(k) for k in field_mapping.keys()]
    keep_cols = [c for c in mapped_targets if c in df.columns]
    if keep_cols:
        df = df[keep_cols]

    # 若某些重要目标（例如 keywords）未映射，提示可能的源列候选
    # 打印最终被识别并保留的目标列以及它们对应的源列
    print("📋 最终映射并保留的目标列:")
    if keep_cols:
        for tgt in keep_cols:
            srcs = reverse_map.get(tgt, [])
            if srcs:
                print(f"   {', '.join(srcs)} -> {tgt}")
            else:
                print(f"   {tgt}")
    else:
        print("   （无匹配到的目标列）")

    # 始终列出包含 'keyword' 或 '关键词' 的原始列，并标注是否已被映射到 keywords
    candidates = [c for c in original_columns if 'keyword' in str(c).lower() or '关键词' in str(c)]
    if candidates:
        print('\n关键词候选源列（包含 "keyword" 或 "关键词"）：')
        for c in candidates:
            mapped_flag = ''
            if 'keywords' in reverse_map and c in reverse_map.get('keywords', []):
                mapped_flag = ' (已映射 -> keywords)'
            print(f'   {c}{mapped_flag}')
    else:
        print('\n关键词候选源列：无')

    return df

# 1. 读取 CSV
# 1. 读取数据：优先从 config 中指定的 Excel 目录读取所有 Excel 文件并合并，找不到时回退到 CSV
excel_dir = config.get('data_source', {}).get('excel_dir')
df = None
if excel_dir:
    excel_path = Path(excel_dir)
    if excel_path.exists() and excel_path.is_dir():
        print(f"检测到 Excel 目录：{excel_path}，开始读取所有 Excel 文件...")
        files = sorted([p for p in excel_path.glob('*.xls*')])
        dfs = []
        for f in files:
            try:
                tmp = read_excel_file(f)
                print(f"  读取: {f.name} -> {len(tmp)} 行")
                dfs.append(tmp)
            except Exception as e:
                print(f"  读取失败: {f} - {e}")

        if dfs:
            df = pd.concat(dfs, ignore_index=True)
            print(f"已合并 {len(dfs)} 个文件，共 {len(df)} 条记录")

if df is None:
    # 回退 CSV：优先使用当前工程目录下的数据文件，避免误读到其他目录的同名 CSV
    csv_candidates = [
        BASE_DIR / "data" / "all_data.csv",
        BASE_DIR / "data" / "alldata_cleaned.csv",
        BASE_DIR / "data" / "cleaned_data.csv",
        BASE_DIR / "data" / "targetdata_cleaned.csv",
        BASE_DIR / "cleaned_data.csv",
    ]
    csv_default = None
    for p in csv_candidates:
        if p.exists():
            csv_default = str(p)
            break
    if csv_default is None:
        raise FileNotFoundError(f"未找到回退 CSV，已尝试: {[str(p) for p in csv_candidates]}")
    try:
        # 兼容不同来源 CSV 的常见编码：优先 UTF-8，其次回退到 GB 系（Windows 中文环境常见）
        last_err = None
        for enc in ("utf-8-sig", "utf-8", "gb18030", "gbk", "cp936"):
            try:
                df = pd.read_csv(csv_default, encoding=enc)
                print(f"回退读取 CSV：{csv_default}（encoding={enc}）-> {len(df)} 行")
                break
            except UnicodeDecodeError as e:
                last_err = e
        if df is None:
            raise last_err or RuntimeError("读取 CSV 失败：未知编码错误")
    except Exception as e:
        print(f"读取 CSV 失败：{e}")
        raise

# 在应用字段映射前，打印未被映射识别的原始列，便于补充配置
mapped_candidates = set()
for candidates in field_mapping.values():
    for c in (candidates if isinstance(candidates, (list, tuple)) else [candidates]):
        if c is not None:
            mapped_candidates.add(str(c).strip().lower())

unmapped = [c for c in df.columns if str(c).strip().lower() not in mapped_candidates]
# 不打印未映射的列，以避免冗余输出（如果需要可�?config 中打开�?

# 应用字段映射（只打印映射后的列）
df = apply_field_mapping(df, field_mapping)
# 2. 替换 NaN �?None
df = df.where(pd.notnull(df), None)

with open(CONFIG_PATH, "r", encoding="utf-8") as f:
    config = yaml.safe_load(f)

db_cfg = config["data_source"]["database"]
table_name = db_cfg.get("table", "papers")
# 3. 连接 SQLite
db_path = db_cfg.get("db_path", db_cfg.get("database", ""))
conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# 4. 查询原始数据�?
cursor.execute("SELECT COUNT(*) FROM papers")
original_count = cursor.fetchone()[0] # type: ignore



# 5. 一次性获取已�?DOI 和标�?
cursor.execute("SELECT doi FROM papers")
existing_dois = set(row[0] for row in cursor.fetchall())
cursor.execute("SELECT title FROM papers")
existing_titles = set(row[0] for row in cursor.fetchall())

def to_sqlite_value(v):
    """�?pandas/numpy 的缺失值统一转成 None，避�?nan 写入 SQLite"""
    if v is None:
        return None
    # NaN / NaT
    try:
        if pd.isna(v):
            return None
    except Exception:
        pass

    # 字符串空�?“nan�?
    if isinstance(v, str):
        s = v.strip()
        if s == "" or s.lower() == "nan":
            return None
        return s

    # numpy 标量�?python 标量
    if isinstance(v, np.generic):
        return v.item()

    return v


def parse_publish_year(v):
    """�?publish_date 转成 int 年份；无法解析则返回 None"""
    v = to_sqlite_value(v)
    if v is None:
        return None

    if isinstance(v, (int, np.integer)):
        return int(v)

    if isinstance(v, (float, np.floating)):
        if np.isnan(v):
            return None
        iv = int(v)
        return iv if float(iv) == float(v) else None  # 只接�?2020.0 这种

    if isinstance(v, str):
        s = v.strip()
        # 纯数�?浮点字符串：'2020' / '2020.0'
        try:
            f = float(s)
            iv = int(f)
            if float(iv) == f:
                return iv
        except Exception:
            pass

        # 兜底：从 '2020-01-01' 里抓 4 位年�?
        import re
        m = re.search(r"(19\d{2}|20\d{2})", s)
        if m:
            return int(m.group(0))

    return None
# 6. 插入数据�?
#    - �?DOI 时按 DOI 去重
#    - DOI 为空时按标题去重
inserted_count = 0
skip_no_year = 0
skip_dup_doi = 0
skip_dup_title = 0
total_rows = len(df)
print_interval = max(1, total_rows // 10)  # �?0%打印一次进�?
for idx, row in df.iterrows():
    if inserted_count > 0 and inserted_count % print_interval == 0:
        print(f"进度: {inserted_count}/{total_rows} ({100*inserted_count//total_rows}%)")
    doi = to_sqlite_value(row.get('doi'))
    title = to_sqlite_value(row.get('title'))

    publish_year = parse_publish_year(row.get('publish_date'))
    # 跳过 publish_date 无法解析的行
    if publish_year is None:
        skip_no_year += 1
        continue

    # 情况 1：有 DOI，用 DOI 去重
    if doi not in (None, ""):
        if doi in existing_dois:
            skip_dup_doi += 1
            continue
    # 情况 2：没�?DOI，用标题去重（标题也为空则不做去重）
    else:
        if title in existing_titles:
            skip_dup_title += 1
            continue

    cursor.execute("""
        INSERT INTO papers (doi, journal, keywords, publish_date, target, citations, title, abstract, category)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        doi,
        to_sqlite_value(row.get('journal')),
        to_sqlite_value(row.get('keywords')),
        publish_year,
        to_sqlite_value(row.get('target')),
        to_sqlite_value(row.get('citations')),
        title,
        to_sqlite_value(row.get('abstract')),
        to_sqlite_value(row.get('category'))
    ))

    # 维护去重集合
    if doi not in (None, ""):
        existing_dois.add(doi)
    if title not in (None, ""):
        existing_titles.add(title)

    inserted_count += 1

conn.commit()

# 7. 查询插入后的数据�?
cursor.execute("SELECT COUNT(*) FROM papers")
final_count = cursor.fetchone()[0] # type: ignore

cursor.close()
conn.close()

print(f"\n原有数据量：{original_count}")
print(f"本次插入新数据量：{inserted_count}")
print(f"插入后总数据量：{final_count}")

# 8. 跳过原因统计（便于解释为什么读到 3 万条但只插入 1 万多）
total_rows = len(df)
skipped_total = total_rows - inserted_count
print("\n📊 跳过原因统计：")
print(f"总行数: {total_rows}")
print(f"成功插入: {inserted_count}")
print(f"总跳过: {skipped_total}")
print(f"  - publish_date 无法解析: {skip_no_year}")
print(f"  - DOI 重复跳过: {skip_dup_doi}")
print(f"  - 标题重复跳过: {skip_dup_title}")

