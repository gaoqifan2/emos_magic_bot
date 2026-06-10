#!/usr/bin/env python3
"""
修复文件编码问题脚本
用于修复包含U+FFFD替换字符的文件
"""

import sys
import os
from utils.http_client import http_client

def fix_file_encoding(filepath):
    """修复文件中的编码问题"""
    print(f"正在处理文件: {filepath}")
    
    if not os.path.exists(filepath):
        print(f"错误: 文件不存在 {filepath}")
        return False
    
    # 读取文件内容（二进制模式）
    with open(filepath, 'rb') as f:
        content = f.read()
    
    # 检查是否包含替换字符 U+FFFD (UTF-8: 0xEF 0xBF 0xBD)
    replacement_char = b'\xef\xbf\xbd'
    
    if replacement_char not in content:
        print("未发现编码问题字符 (U+FFFD)")
        # 尝试用UTF-8解码验证
        try:
            text = content.decode('utf-8')
            print("文件编码正常，可以用UTF-8解码")
            return True
        except UnicodeDecodeError as e:
            print(f"警告: 文件存在其他编码问题: {e}")
    else:
        print(f"发现 {content.count(replacement_char)} 个替换字符 (U+FFFD)")
    
    # 尝试用不同编码读取并修复
    encodings = ['utf-8', 'gbk', 'gb2312', 'gb18030', 'latin-1', 'cp936']
    
    for encoding in encodings:
        try:
            # 先用该编码解码
            text = content.decode(encoding, errors='replace')
            
            # 替换损坏的字符
            original_text = text
            text = text.replace('\ufffd', '')  # 移除替换字符
            
            # 如果文本有变化，说明修复了问题
            if text != original_text:
                print(f"使用 {encoding} 编码修复了文件")
                
                # 备份原文件
                backup_path = filepath + '.backup'
                with open(backup_path, 'wb') as f:
                    f.write(content)
                print(f"已备份原文件到: {backup_path}")
                
                # 写入修复后的内容（使用UTF-8）
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(text)
                print(f"已修复文件: {filepath}")
                return True
            else:
                print(f"使用 {encoding} 编码可以正常解码，无需修复")
                return True
                
        except Exception as e:
            continue
    
    print("无法修复文件编码问题")
    return False

if __name__ == '__main__':
    if len(sys.argv) < 2:
        # 默认修复 main.py
        target_file = 'main.py'
    else:
        target_file = sys.argv[1]
    
    success = fix_file_encoding(target_file)
    sys.exit(0 if success else 1)
