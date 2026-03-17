#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
import sys
import subprocess
import time

# 删除锁文件
lock_file = 'bot.lock'
if os.path.exists(lock_file):
    try:
        os.remove(lock_file)
        print("✅ 已删除锁文件")
    except Exception as e:
        print(f"⚠️ 删除锁文件失败: {e}")

# 启动机器人
print("🚀 正在启动机器人...")
print("=" * 60)

# 使用subprocess启动机器人并实时输出
process = subprocess.Popen(
    [sys.executable, 'main.py'],
    stdout=subprocess.PIPE,
    stderr=subprocess.STDOUT,
    text=True,
    bufsize=1,
    universal_newlines=True
)

# 实时输出日志
try:
    for line in iter(process.stdout.readline, ''):
        print(line, end='')
        sys.stdout.flush()
except KeyboardInterrupt:
    print("\n\n🛑 正在停止机器人...")
    process.terminate()
    process.wait()
    print("✅ 机器人已停止")
except Exception as e:
    print(f"\n❌ 发生错误: {e}")
    process.terminate()
