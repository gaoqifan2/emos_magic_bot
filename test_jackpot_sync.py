#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试奖池同步到数据库
"""

from app.database.jackpot import get_jackpot_pool, add_to_jackpot_pool, reset_jackpot_pool

def test_jackpot_sync():
    """测试奖池同步功能"""
    print("开始测试奖池同步...")
    
    # 1. 重置奖池
    print("\n1. 重置奖池")
    reset_amount = reset_jackpot_pool()
    print(f"   重置后奖池金额: {reset_amount}")
    
    # 2. 获取初始奖池金额
    print("\n2. 获取初始奖池金额")
    initial_amount = get_jackpot_pool()
    print(f"   初始奖池金额: {initial_amount}")
    
    # 3. 添加金额到奖池
    print("\n3. 向奖池添加100元")
    added_amount = add_to_jackpot_pool(100)
    print(f"   添加后奖池金额: {added_amount}")
    
    # 4. 再次获取奖池金额，验证是否同步
    print("\n4. 再次获取奖池金额")
    current_amount = get_jackpot_pool()
    print(f"   当前奖池金额: {current_amount}")
    
    # 5. 验证结果
    print("\n5. 验证结果")
    if current_amount == 100:
        print("   ✅ 奖池同步成功！")
    else:
        print(f"   ❌ 奖池同步失败，期望100，实际{current_amount}")
    
    # 6. 再次重置奖池
    print("\n6. 再次重置奖池")
    final_reset_amount = reset_jackpot_pool()
    print(f"   重置后奖池金额: {final_reset_amount}")
    
    # 7. 验证重置结果
    print("\n7. 验证重置结果")
    final_amount = get_jackpot_pool()
    print(f"   最终奖池金额: {final_amount}")
    
    if final_amount == 0:
        print("   ✅ 奖池重置成功！")
    else:
        print(f"   ❌ 奖池重置失败，期望0，实际{final_amount}")

if __name__ == "__main__":
    test_jackpot_sync()
