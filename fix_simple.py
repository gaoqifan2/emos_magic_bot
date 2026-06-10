#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""简单直接修复所有缺少左引号的 reply_text 调用"""

with open('main.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

new_lines = []
for line in lines:
    if 'reply_text(' in line:
        # 找到 reply_text( 的位置
        idx = line.find('reply_text(')
        if idx >= 0:
            bracket_pos = idx + 11  # reply_text( 长度是 11
            if bracket_pos < len(line):
                next_char = line[bracket_pos]
                # 检查左括号后面的字符是否不是引号、f、r、b等
                if next_char not in ['"', "'", 'f', 'r', 'b', ' ']:
                    # 在左括号后插入左引号
                    line = line[:bracket_pos] + '"' + line[bracket_pos:]
    new_lines.append(line)

with open('main.py', 'w', encoding='utf-8') as f:
    f.writelines(new_lines)

print('修复完成')
