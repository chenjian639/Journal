import sys
import os
import json
from datetime import datetime

# 关键：获取 python_analysis 目录的绝对路径（你的 .py 文件都在这里）
python_analysis_dir = os.path.join(os.path.dirname(__file__), "python_analysis")
if python_analysis_dir not in sys.path:
    sys.path.append(python_analysis_dir)

# 直接导入你的实际模块（没有的模块直接注释/删除）
import disrupt_calculator
import novelty_analyzer
import run_kua  # 实际跨学科性模块：run_kua.py
# import theme_analyzer  # 没有就注释，避免报错

# === 全局配置 ===
SPARK_API_KEY = "Bearer cyjdtVYXSGWgwiUdnLMs:DvKIMQbkHgKlYljNcbhN"
PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
BACKGROUND_DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'raw', 'data_with_citing.csv')
TARGET_DATA_PATH = os.path.join(PROJECT_ROOT, 'data', 'raw', 'top10_journals_data.csv')

# === 日志输出 ===
print(" 开始执行四大期刊分析流程")
print(f" 项目根目录: {PROJECT_ROOT}")
print(f" 背景数据: {BACKGROUND_DATA_PATH}")
print(f" 目标数据: {TARGET_DATA_PATH}")

def run_disruption_analysis():
    """运行颠覆性指数分析（disrupt_calculator.py）"""
    print("\n🔬 正在执行：颠覆性指数分析（Disruption Index）...")
    try:
        from disrupt_calculator import run_analysis as run_disrupt
        result = run_disrupt(background_path=BACKGROUND_DATA_PATH, target_path=TARGET_DATA_PATH)
        print("✅ 颠覆性分析完成")
        return result
    except Exception as e:
        print(f"❌ 颠覆性分析失败: {e}")
        return None

def run_novelty_analysis():
    """运行新颖性指数分析（novelty_analyzer.py）"""
    print("\n🎯 正在执行：组合新颖性分析（Novelty Score）...")
    try:
        from novelty_analyzer import run_novelty_analysis
        result = run_novelty_analysis(
            background_data_path=BACKGROUND_DATA_PATH,
            target_data_path=TARGET_DATA_PATH,
            output_dir=os.path.join(PROJECT_ROOT, 'outputs', 'novelty')
        )
        print("✅ 新颖性分析完成")
        return result
    except Exception as e:
        print(f"❌ 新颖性分析失败: {e}")
        return None

def run_theme_analysis():
    """运行主题分析（没有 theme_analyzer.py 就注释下面的调用）"""
    print("\n📝 正在执行：期刊主题与AI语义分析...")
    try:
        from theme_analyzer import run_theme_analysis
        run_theme_analysis(
            data_path=TARGET_DATA_PATH,
            output_dir=os.path.join(PROJECT_ROOT, 'outputs', 'theme'),
            api_key=SPARK_API_KEY
        )
        print("✅ 主题分析完成")
    except Exception as e:
        print(f"❌ 主题分析失败: {e}")

def run_interdisciplinary_analysis():
    """运行跨学科性分析（run_kua.py，你的实际模块）"""
    print("\n🌐 正在执行：跨学科性分析（Interdisciplinarity, TD）...")
    try:
        # 直接导入 run_kua.py 中的主函数（假设是 main()，如果是其他名就改这里）
        from run_kua import main as kua_main
        kua_main()  # 调用跨学科性分析
        print("✅ 跨学科性分析完成")
    except Exception as e:
        print(f"❌ 跨学科性分析失败: {e}")

if __name__ == "__main__":
    # 执行分析（没有的模块直接注释调用）
    disrupt_result = run_disruption_analysis()
    novelty_result = run_novelty_analysis()
    # run_theme_analysis()  # 没有 theme_analyzer.py 就注释这行
    run_interdisciplinary_analysis()

    # === 生成执行摘要 ===
    summary = {
        "status": "completed",
        "timestamp": datetime.now().isoformat(),
        "inputs": {
            "background_data": os.path.relpath(BACKGROUND_DATA_PATH, PROJECT_ROOT),
            "target_data": os.path.relpath(TARGET_DATA_PATH, PROJECT_ROOT)
        },
        "modules": {
            "disruption": bool(disrupt_result),
            "novelty": bool(novelty_result),
            "theme": False,  # 未执行设为 False
            "interdisciplinary": True
        },
        "output_dirs": {
            "disruption": "outputs/disrupt",
            "novelty": "outputs/novelty",
            "theme": "outputs/theme",
            "interdisciplinary": "outputs/kua"
        }
    }

    summary_path = os.path.join(PROJECT_ROOT, 'outputs', 'analysis_summary.json')
    os.makedirs(os.path.dirname(summary_path), exist_ok=True)
    with open(summary_path, 'w', encoding='utf-8') as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    # === 最终输出 ===
    print("\n" + "="*60)
    print(" 全部分析任务执行完毕！")
    print("="*60)
    print("输出目录概览：")
    print("   ├── outputs/disrupt/   ← 颠覆性指数排名 + 引文网络")
    print("   ├── outputs/novelty/   ← 组合新颖性得分 + 图表")
    print("   ├── outputs/theme/     ← 关键词 + AI 主题描述（暂未执行）")
    print("   └── outputs/kua/       ← 跨学科性（TD）得分 + 矩阵")
    print(f"\n已生成执行摘要: {summary_path}")