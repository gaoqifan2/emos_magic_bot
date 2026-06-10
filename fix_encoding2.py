#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""修复main.py中的编码问题 - 全面版"""

with open('main.py', 'r', encoding='utf-8', errors='replace') as f:
    content = f.read()

# 替换所有 U+FFFD 替换字符
content = content.replace('\ufffd', '')

# 修复所有单独的 ? 字符（在中文语境下）
# 这些通常是乱码，需要手动修复

# 首先修复引号内的 ?
content = content.replace('"?', '"小')
content = content.replace("'?", "'小")
content = content.replace('?', '')  # 删除剩余的?

# 修复其他常见的乱码
content = content.replace('发?', '发送')
content = content.replace('局?', '局')
content = content