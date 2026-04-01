#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试猜大小游戏核心逻辑
"""

import sys
import io

# 修复编码问题
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_guess_logic():
    """测试猜大小游戏逻辑"""
    print("=== 测试猜大小游戏逻辑 ===")
    
    # 测试数据
    test_cases = [
        (1, "小", True),   # 1点，猜小，应该赢
        (2, "小", True),   # 2点，猜小，应该赢
        (3, "小", True),   # 3点，猜小，应该赢
        (4, "大", True),   # 4点，猜大，应该赢
        (5, "大", True),   # 5点，猜大，应该赢
        (6, "大", True),   # 6点，猜大，应该赢
        (1, "大", False),  # 1点，猜大，应该输
        (6, "小", False),  # 6点，猜小，应该输
    ]
    
    for dice_value, guess, should_win in test_cases:
        # 判断大小
        if dice_value in [4, 5, 6]:
            actual_result = "大"
        else:
            actual_result = "小"
        
        # 判断是否赢
        is_win = (guess == actual_result)
        
        status = "OK" if is_win == should_win else "ERROR"
        print(f"{status} 骰子: {dice_value}, 猜测: {guess}, 实际: {actual_result}, 结果: {'赢' if is_win else '输'}, 预期: {'赢' if should_win else '输'}")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    test_guess_logic()
