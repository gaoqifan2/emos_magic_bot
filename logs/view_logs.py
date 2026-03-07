# view_logs.py
import os
import glob
from datetime import datetime

def list_log_files():
    """列出所有日志文件"""
    log_files = glob.glob('logs/bot_*.log')
    if not log_files:
        print("❌ 没有找到日志文件")
        return []
    
    # 按修改时间排序
    log_files.sort(key=os.path.getmtime, reverse=True)
    
    print("\n📋 可用的日志文件：")
    print("-" * 60)
    for i, log_file in enumerate(log_files[:10], 1):  # 只显示最近10个
        size = os.path.getsize(log_file)
        mod_time = datetime.fromtimestamp(os.path.getmtime(log_file))
        print(f"{i}. {os.path.basename(log_file)}")
        print(f"   大小: {size/1024:.2f} KB")
        print(f"   修改时间: {mod_time.strftime('%Y-%m-%d %H:%M:%S')}")
        print()
    
    return log_files

def view_log(log_file, lines=50):
    """查看日志文件内容"""
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            # 读取最后N行
            all_lines = f.readlines()
            last_lines = all_lines[-lines:]
            
            print(f"\n📄 显示 {os.path.basename(log_file)} 的最后 {lines} 行：")
            print("=" * 60)
            for line in last_lines:
                print(line.strip())
            print("=" * 60)
    except Exception as e:
        print(f"❌ 读取日志失败: {e}")

def search_log(log_file, keyword):
    """搜索日志中的关键词"""
    try:
        with open(log_file, 'r', encoding='utf-8') as f:
            lines = f.readlines()
            
        matches = [line for line in lines if keyword.lower() in line.lower()]
        
        print(f"\n🔍 在 {os.path.basename(log_file)} 中搜索 '{keyword}'")
        print(f"找到 {len(matches)} 条匹配记录：")
        print("=" * 60)
        for match in matches[-20:]:  # 只显示最近20条
            print(match.strip())
        print("=" * 60)
    except Exception as e:
        print(f"❌ 搜索失败: {e}")

def main():
    """主函数"""
    while True:
        print("\n" + "=" * 60)
        print("📝 日志查看工具")
        print("=" * 60)
        print("1. 列出所有日志文件")
        print("2. 查看最新日志")
        print("3. 搜索日志")
        print("4. 退出")
        print("=" * 60)
        
        choice = input("请选择操作 (1-4): ").strip()
        
        if choice == '1':
            list_log_files()
        
        elif choice == '2':
            log_files = list_log_files()
            if log_files:
                try:
                    idx = int(input("请选择日志文件编号: ")) - 1
                    if 0 <= idx < len(log_files):
                        lines = input("请输入要显示的行数 (默认50): ").strip()
                        lines = int(lines) if lines else 50
                        view_log(log_files[idx], lines)
                except:
                    print("❌ 输入无效")
        
        elif choice == '3':
            log_files = list_log_files()
            if log_files:
                try:
                    idx = int(input("请选择日志文件编号: ")) - 1
                    if 0 <= idx < len(log_files):
                        keyword = input("请输入搜索关键词: ").strip()
                        if keyword:
                            search_log(log_files[idx], keyword)
                except:
                    print("❌ 输入无效")
        
        elif choice == '4':
            print("👋 再见！")
            break
        
        else:
            print("❌ 无效选择")

if __name__ == "__main__":
    main()