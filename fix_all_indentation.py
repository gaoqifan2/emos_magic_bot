#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
批量修复代码中的缩进问题
"""

import os
import re
import fileinput

# 要处理的文件
TARGET_FILES = [
    r'd:\emos_magic_bot\handlers\common.py'
]

# 修复模式 - 只修复缩进，不改变其他内容
FIX_PATTERNS = [
    # 修复 response = await 缩进问题
    (r'^\s{8}response = await', r'    response = await'),
    (r'^\s{12}response = await', r'        response = await'),
    (r'^\s{16}response = await', r'            response = await'),
    # 修复 user_response = await 缩进问题
    (r'^\s{8}user_response = await', r'    user_response = await'),
    (r'^\s{12}user_response = await', r'        user_response = await'),
    (r'^\s{16}user_response = await', r'            user_response = await'),
    # 修复 transfer_response = await 缩进问题
    (r'^\s{8}transfer_response = await', r'    transfer_response = await'),
    (r'^\s{12}transfer_response = await', r'        transfer_response = await'),
    (r'^\s{16}transfer_response = await', r'            transfer_response = await'),
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
        print(f"  已修复缩进问题")
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
