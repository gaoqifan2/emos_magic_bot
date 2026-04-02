#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复所有缺少左引号的 reply_text 调用"""

import re

with open('main.py', 'r', encoding='utf-8') as f:
    content = f.read()

# 匹配所有 reply_text( 后面没有引号的情况
# 例如: reply_text(游戏已经开始... -> reply_text("游戏已经开始...
def fix_quotes(match):
    full_text = match.group(0)
    if 'reply_text(' in full_text:
        # 检查左括号后面是否是引号
        after_bracket = full_text[full_text.index('reply_text(') + 11:]
        if after_bracket and after_bracket[0] not in ['"', "'", 'f"', "f'"]:
            # 缺少左引号，添加一个
            return full_text.replace('reply_text(', 'reply_text("', 1)
    return full_text

# 使用正则表达式来匹配并修复
# 匹配 reply_text(...) 模式
content = re.sub(r'reply_text\([^f"\'].*?\)$', fix_quotes, content, flags=re.MULTILINE)

# 更简单直接的方法：替换所有 reply_text( 后面不是引号的情况
lines = content.split('\n')
new_lines = []
for line in lines:
    if 'reply_text(' in line:
        idx = line.find('reply_text(')
        if idx >= 0:
            after_bracket = line[idx + 11:] if idx + 11 < len(line) else ''
            if after_bracket and after_bracket[0] not in ['"', "'", 'f', 'r', 'b']:
                # 添加左引号
                line = line[:idx + 11] + '"' + line[idx + 11:]
    new_lines.append(line)

content = '\n'.join(new_lines)

with open('main.py', 'w', encoding='utf-8') as f:
    f.write(content)

print('修复完成')
