# -*- coding: utf-8 -*-
# main函数
# 从数据库读取数据，用 preprocess 清洗后计算各指标并上传到 journal_metrics 表
import argparse
import json
from pathlib import Path

import pandas as pd

try:
    import yaml
except Exception:  # pragma: no cover
    yaml = None

from disrupt_calculator_031 import analyze_disruption
from interdisciplinary_032 import analyze_interdisciplinary
from novelty_analyzer_033 import analyze_journal_novelty
from topic_analyzer_036 import analyze_topic_entropy
from theme_034 import ThemeHotnessAnalyzer
from upload_journal_metrics_035 import upload_journal_metrics
from preprocess_wos_data_030 import WosDataCleaner


def _load_yaml(path: Path) -> dict:
    if yaml is None:
        raise RuntimeError("未安装 PyYAML，无法读取 yaml 配置")
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def _load_metrics_db_config(path: Path) -> tuple[dict, int | None]:
    """读取指标上传数据库配置。

    支持两种格式：
    1) 直接是 db_config 字典：{host,port,user,password,database,charset}
    2) 包一层：{ "year": 2025, "db_config": {...} }
    """
    if not path.exists():
        return {}, None
    with open(path, "r", encoding="utf-8") as f:
        obj = json.load(f) or {}
    if "db_config" in obj and isinstance(obj.get("db_config"), dict):
        return obj.get("db_config") or {}, obj.get("year")
    return obj, None


def run_pipeline(*, clean_config_path: str | None = None, metrics_db_config_path: str | None = None, year: int | None = None):
    # -------------------- 读取原始论文数据 --------------------
    clean_cfg = None
    if clean_config_path:
        cfg_path = Path(clean_config_path)
        if cfg_path.exists():
            clean_cfg = _load_yaml(cfg_path)
            # 关键：03 要从 cleaned 表读取（使用 write_back.table 作为读取表）
            try:
                wb_table = (((clean_cfg or {}).get("write_back") or {}).get("table") or "").strip()
                if wb_table:
                    clean_cfg.setdefault("data_source", {})
                    clean_cfg["data_source"].setdefault("database", {})
                    clean_cfg["data_source"]["type"] = "database"
                    clean_cfg["data_source"]["database"]["table"] = wb_table
            except Exception:
                pass

    cleaner = WosDataCleaner(clean_config=clean_cfg) if clean_cfg else WosDataCleaner()
    df = cleaner.clean(source_type="database")

    # 每本期刊论文数（用于写入 journal_metrics.paper_count）
    if "journal" in df.columns:
        paper_count_df = (
            df["journal"].value_counts(dropna=False).rename("paper_count").reset_index().rename(columns={"index": "journal"})
        )
    else:
        paper_count_df = pd.DataFrame(columns=["journal", "paper_count"])
    # -------------------- 计算五个指标 --------------------
    print("计算 disruption...")
    disrupt_df = analyze_disruption(df)  # 返回 ['journal','percent_score']

    print("计算 interdisciplinary...")
    interdisciplinary_df = analyze_interdisciplinary(df)  # 返回 ['journal','percent_score']

    print("计算 novelty...")
    novelty_df = analyze_journal_novelty(df)  # 返回 ['journal','percent_score']

    print("计算 topic 主题复杂度...")
    topic_df = analyze_topic_entropy(df)  # 返回 ['journal','percent_score']

    print("计算 theme...")
    theme_analyzer = ThemeHotnessAnalyzer(df)
    theme_df = theme_analyzer.run(top_n=None)  # 返回 ['journal','theme_concentration','hot_response']

    # -------------------- 上传到数据库 --------------------
    # 默认年份/数据库配置（SQLite）
    default_year = 2025
    metrics_db_config = {
        "dialect": "sqlite",
        "db_path": str(Path(__file__).resolve().parent.parent.parent.parent / "data" / "paper_system.db"),
    }

    cfg_year = None
    if metrics_db_config_path:
        cfg_path = Path(metrics_db_config_path)
        cfg_db, cfg_year = _load_metrics_db_config(cfg_path)
        if cfg_db:
            metrics_db_config.update(cfg_db)

    y = year if isinstance(year, int) and year > 0 else (cfg_year if isinstance(cfg_year, int) and cfg_year > 0 else default_year)
    upload_journal_metrics(
        disrupt_df=disrupt_df,
        interdisciplinary_df=interdisciplinary_df,
        novelty_df=novelty_df,
        topic_df=topic_df,
        theme_df=theme_df,
        year=y,
        db_config=metrics_db_config,
        paper_count_df=paper_count_df,
    )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="一键运行指标计算并上传（从 cleaned 表读取）")
    parser.add_argument("--clean-config", default=str(Path(__file__).resolve().parent / "config" / "clean_config.yaml"), help="clean_config.yaml 路径")
    parser.add_argument("--metrics-db-config", default=str(Path(__file__).resolve().parent / "config" / "metrics_db.json"), help="指标上传数据库配置 JSON")
    parser.add_argument("--year", type=int, default=None, help="指标年份（可选，覆盖配置文件）")
    args = parser.parse_args()

    run_pipeline(clean_config_path=args.clean_config, metrics_db_config_path=args.metrics_db_config, year=args.year)
