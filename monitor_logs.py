#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import time
import os

# 日志文件路径
log_file = 'bot_error.log'

# 获取文件当前大小
def get_file_size(file_path):
    if os.path.exists(file_path):
        return os.path.getsize(file_path)
    return 0

# 实时监控日志
def monitor_logs():
    print(f"开始监控日志文件: {log_file}")
    print("按 Ctrl+C 停止监控")
    print("=" * 60)
    
    # 获取初始文件大小
    last_size = get_file_size(log_file)
    
    try:
        while True:
            # 检查文件大小是否变化
            current_size = get_file_size(log_file)
            if current_size > last_size:
                # 读取新增的内容
                try:
                    with open(log_file, 'r', encoding='utf-8', errors='replace') as f:
                        f.seek(last_size)
                        new_content = f.read()
                        if new_content:
                            print(new_content, end='')
                except Exception as e:
                    print(f"读取日志文件时出错: {e}")
                last_size = current_size
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n监控停止")

if __name__ == "__main__":
    monitor_logs()