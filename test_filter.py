#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 filters.Dice 的使用方式
"""

from telegram.ext import filters

print("=== 测试 filters.Dice ===")

try:
    # 测试 filters.Dice 的属性
    print("filters.Dice 类型:", type(filters.Dice))
    print("filters.Dice 存在:", hasattr(filters, 'Dice'))
    
    # 测试 filters.Dice.ALL
    if hasattr(filters.Dice, 'ALL'):
        print("filters.Dice.ALL 存在:", True)
        print("filters.Dice.ALL 类型:", type(filters.Dice.ALL))
    else:
        print("filters.Dice.ALL 不存在")
    
    print("\n✅ 测试成功！")
except Exception as e:
    print(f"\n❌ 测试失败: {e}")
    import traceback
    traceback.print_exc()
