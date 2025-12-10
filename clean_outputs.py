# -*- coding: utf-8 -*-
"""
clean_outputs.py
清空outputs文件夹下所有输出文件
"""
import os
import shutil
from pathlib import Path

def clean_outputs():
    """清空outputs文件夹下所有文件"""
    # 定位到项目根目录
    project_root = Path(__file__).parent
    
    # outputs文件夹路径
    outputs_dir = project_root / "outputs"
    
    if not outputs_dir.exists():
        print(f"[清理] outputs文件夹不存在: {outputs_dir}")
        return
    
    print(f"[清理] 开始清理outputs文件夹: {outputs_dir}")
    
    # 统计信息
    total_deleted = 0
    total_size = 0
    
    # 遍历所有子文件夹
    for item in outputs_dir.rglob("*"):
        if item.is_file():
            try:
                # 计算文件大小
                file_size = item.stat().st_size
                
                # 删除文件
                item.unlink()
                
                total_deleted += 1
                total_size += file_size
                
                print(f"  删除: {item.relative_to(outputs_dir)} ({file_size:,} bytes)")
                
            except Exception as e:
                print(f"  错误: 无法删除 {item.name}: {e}")
    
    # 删除空文件夹（保留根目录）
    for item in outputs_dir.rglob("*"):
        if item.is_dir():
            try:
                # 检查是否为空文件夹
                if not any(item.iterdir()):
                    # 不要删除outputs根目录本身
                    if item != outputs_dir:
                        item.rmdir()
                        print(f"  删除空文件夹: {item.relative_to(outputs_dir)}")
            except Exception as e:
                print(f"  错误: 无法删除文件夹 {item.name}: {e}")
    
    print(f"\n✅ 清理完成!")
    print(f"   删除文件数: {total_deleted}")
    print(f"   释放空间: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
    print(f"   保留文件夹: {outputs_dir}")

def clean_specific_extensions():
    """按扩展名清理特定类型文件"""
    project_root = Path(__file__).parent
    outputs_dir = project_root / "outputs"
    
    if not outputs_dir.exists():
        print(f"[清理] outputs文件夹不存在: {outputs_dir}")
        return
    
    # 要删除的文件扩展名
    extensions_to_clean = [
        '.csv', '.json', '.png', '.jpg', '.jpeg', '.gif', '.bmp',
        '.xlsx', '.xls', '.pdf', '.txt', '.log'
    ]
    
    print(f"[清理] 清理特定类型文件: {extensions_to_clean}")
    
    deleted_count = 0
    
    for item in outputs_dir.rglob("*"):
        if item.is_file() and item.suffix.lower() in extensions_to_clean:
            try:
                item.unlink()
                deleted_count += 1
                print(f"  删除: {item.relative_to(outputs_dir)}")
            except Exception as e:
                print(f"  错误: 无法删除 {item.name}: {e}")
    
    print(f"\n✅ 清理完成! 删除 {deleted_count} 个文件")

def clean_by_pattern():
    """按文件名模式清理文件"""
    project_root = Path(__file__).parent
    outputs_dir = project_root / "outputs"
    
    if not outputs_dir.exists():
        print(f"[清理] outputs文件夹不存在: {outputs_dir}")
        return
    
    # 要删除的文件名模式
    patterns_to_clean = [
        'journal_', 'paper_', 'td_', 'percent_', 'analysis_',
        'result', 'output', 'data', 'score', 'list', 'chart'
    ]
    
    print(f"[清理] 清理包含以下模式的文件: {patterns_to_clean}")
    
    deleted_count = 0
    
    for item in outputs_dir.rglob("*"):
        if item.is_file():
            filename = item.name.lower()
            # 检查文件名是否包含任何模式
            if any(pattern in filename for pattern in patterns_to_clean):
                try:
                    item.unlink()
                    deleted_count += 1
                    print(f"  删除: {item.relative_to(outputs_dir)}")
                except Exception as e:
                    print(f"  错误: 无法删除 {item.name}: {e}")
    
    print(f"\n✅ 清理完成! 删除 {deleted_count} 个文件")

def show_outputs_info():
    """显示outputs文件夹信息"""
    project_root = Path(__file__).parent
    outputs_dir = project_root / "outputs"
    
    if not outputs_dir.exists():
        print(f"[信息] outputs文件夹不存在: {outputs_dir}")
        return
    
    print(f"[信息] outputs文件夹结构:")
    print(f"  路径: {outputs_dir}")
    
    total_files = 0
    total_size = 0
    file_types = {}
    
    for item in outputs_dir.rglob("*"):
        if item.is_file():
            total_files += 1
            file_size = item.stat().st_size
            total_size += file_size
            
            # 统计文件类型
            ext = item.suffix.lower()
            if ext:
                file_types[ext] = file_types.get(ext, 0) + 1
    
    print(f"  文件总数: {total_files}")
    print(f"  总大小: {total_size:,} bytes ({total_size/1024/1024:.2f} MB)")
    
    if file_types:
        print(f"  文件类型分布:")
        for ext, count in sorted(file_types.items(), key=lambda x: x[1], reverse=True):
            print(f"    {ext}: {count} 个")
    
    # 显示子文件夹
    subdirs = [d for d in outputs_dir.iterdir() if d.is_dir()]
    if subdirs:
        print(f"  子文件夹:")
        for subdir in subdirs:
            subdir_files = sum(1 for _ in subdir.rglob("*") if _.is_file())
            print(f"    {subdir.name}/ ({subdir_files} 个文件)")

def main():
    """主函数 - 提供清理选项"""
    print("=" * 50)
    print("清理输出文件工具")
    print("=" * 50)
    
    while True:
        print("\n请选择操作:")
        print("  1. 清空outputs文件夹下所有文件")
        print("  2. 清理特定类型文件 (.csv, .json, .png等)")
        print("  3. 按文件名模式清理")
        print("  4. 查看outputs文件夹信息")
        print("  5. 退出")
        
        choice = input("\n请输入选择 (1-5): ").strip()
        
        if choice == '1':
            print("\n⚠️ 警告: 这将删除outputs文件夹下所有文件!")
            confirm = input("确认删除? (输入 'yes' 确认): ")
            if confirm.lower() == 'yes':
                clean_outputs()
            else:
                print("取消操作")
        
        elif choice == '2':
            clean_specific_extensions()
        
        elif choice == '3':
            clean_by_pattern()
        
        elif choice == '4':
            show_outputs_info()

        elif choice == '5':
            print("退出程序")

            break
        
        else:
            print("无效选择，请重新输入")

if __name__ == "__main__":
    # 直接运行则清空所有文件
    # clean_outputs()
    
    # 或者运行交互式菜单
    main()