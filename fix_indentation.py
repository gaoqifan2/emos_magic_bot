#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复代码中的缩进和格式问题
"""

import os
import re
import fileinput

# 要处理的文件
TARGET_FILES = [
    r'd:\emos_magic_bot\main.py',
    r'd:\emos_magic_bot\handlers\common.py',
    r'd:\emos_magic_bot\services\service_main.py',
    r'd:\emos_magic_bot\app\handlers\command_handlers.py',
    r'd:\emos_magic_bot\user\user_info.py',
    r'd:\emos_magic_bot\shop\shop_main.py'
]

# 修复模式
FIX_PATTERNS = [
    # 修复 response =await 为 response = await
    (r'(response|user_response|transfer_response)\s*=\s*await', r'\1 = await'),
    # 修复缩进问题（确保正确的4空格缩进）
    (r'^\s{8}(response|user_response|transfer_response) = await', r'    \1 = await'),
    (r'^\s{12}(response|user_response|transfer_response) = await', r'        \1 = await'),
    (r'^\s{16}(response|user_response|transfer_response) = await', r'            \1 = await'),
    # 修复timeout参数
    (r',\s*timeout=\d+\.\d+', ''),
    (r',\s*timeout=\d+', '')
]

def process_file(file_path):
    """处理单个文件"""
    print(f"处理文件: {file_path}")
    
    if not os.path.exists(file_path):
        print(f"  文件不存在: {file_path}")
        return False
    
    changed = False
    with fileinput.FileInput(file_path, inplace=True, backup='.bak', encoding='utf-8') as file:
        for line in file:
            original_line = line
            for pattern, replacement in FIX_PATTERNS:
                line = re.sub(pattern, replacement, line)
            if line != original_line:
                changed = True
            print(line, end='')
    
    if changed:
        print(f"  已修复格式问题")
    else:
        print(f"  无需修复")
    
    return changed

def main():
    """主函数"""
    total_files = 0
    changed_files = 0
    
    for file_path in TARGET_FILES:
        total_files += 1
        if process_file(file_path):
            changed_files += 1
    
    print(f"\n处理完成:")
    print(f"总文件数: {total_files}")
    print(f"更新文件数: {changed_files}")

if __name__ == '__main__':
    main()
