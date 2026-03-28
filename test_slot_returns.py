#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试老虎机游戏的返奖率
"""

import random

def test_slot_returns():
    """测试老虎机游戏的返奖率"""
    print("开始测试老虎机返奖率...")
    
    # 图案定义
    symbols = ["BAR", "🍇", "🍋", "7️⃣"]  # 0: BAR, 1: 葡萄, 2: 柠檬, 3: 7
    
    # 测试次数
    test_count = 100000
    
    # 统计数据
    total_bet = 0
    total_win = 0
    jackpot_count = 0
    three_same_count = 0
    two_same_count = 0
    all_different_count = 0
    
    # 模拟老虎机游戏
    for i in range(test_count):
        # 下注金额
        bet_amount = 100
        total_bet += bet_amount
        
        # 模拟老虎机结果（1-64）
        slot_value = random.randint(1, 64)
        x = slot_value - 1  # 转换为 0-63
        left = x // 16  # 左轴
        middle = (x % 16) // 4  # 中轴
        right = x % 4  # 右轴
        
        # 判断中奖情况
        is_win = False
        win_amount = -bet_amount  # 默认输
        is_jackpot = False
        
        # 检查是否触发Jackpot（7️⃣-BAR-7️⃣组合）
        is_jackpot_triggered = False
        if left == 3 and middle == 0 and right == 3:
            # 1/4的概率实际触发Jackpot，这样总概率约为1/256
            if random.random() < 0.25:
                is_jackpot = True
                is_win = True
                is_jackpot_triggered = True
                # 模拟实际游戏中的Jackpot奖金计算
                # 固定奖励 + 奖池按比例
                # 假设用户等级为青铜，奖池为10000
                fixed_bonus = bet_amount * 5  # 青铜等级5倍
                pool_bonus = int(10000 * 0.05)  # 青铜等级5%奖池
                win_amount = fixed_bonus + pool_bonus
                jackpot_count += 1
            else:
                # 不触发Jackpot，视为普通组合
                is_jackpot = False
                is_win = False
                win_amount = -bet_amount
        # 大奖：三个相同图案
        elif left == middle == right:
            is_win = True
            three_same_count += 1
            # 进一步调整后的赔率：降低三个相同的倍率
            if left == 3:  # 7️⃣7️⃣7️⃣
                win_amount = bet_amount * 6  # 7倍
            elif left == 2:  # 🍋🍋🍋
                win_amount = bet_amount * 1.5  # 2.5倍
            elif left == 1:  # 🍇🍇🍇
                win_amount = bet_amount * 0.5  # 1.5倍
            else:  # BAR BAR BAR
                win_amount = int(bet_amount * 0.1)  # 1.1倍
        # 小奖：两个相同图案
        elif left == middle or middle == right or left == right:
            is_win = True
            two_same_count += 1
            win_amount = int(bet_amount * 0.3)  # 0.3倍（提高两个相同的倍率）
        # 未中奖：全不同图案
        else:
            all_different_count += 1
        
        # 计算抽水（如果赢了）
        if not is_jackpot and win_amount > 0:
            # 10%抽水入池，5%服务器费用
            jackpot_contribution = int(win_amount * 0.10)
            service_fee = max(1, int(win_amount * 0.05))
            win_amount = win_amount - service_fee
        
        total_win += win_amount
    
    # 计算返奖率
    total_bet_amount = total_bet
    total_win_amount = total_win + total_bet  # 因为win_amount包含了下注金额的盈亏
    return_rate = (total_win_amount / total_bet_amount) * 100
    
    # 计算庄家优势
    house_edge = 100 - return_rate
    
    # 打印结果
    print(f"\n测试结果（{test_count}次）:")
    print(f"总下注金额: {total_bet_amount}")
    print(f"总赢取金额: {total_win_amount}")
    print(f"返奖率 (RTP): {return_rate:.2f}%")
    print(f"庄家优势: {house_edge:.2f}%")
    print(f"\n中奖分布:")
    print(f"Jackpot: {jackpot_count}次 ({jackpot_count/test_count*100:.4f}%)")
    print(f"三个相同: {three_same_count}次 ({three_same_count/test_count*100:.2f}%)")
    print(f"两个相同: {two_same_count}次 ({two_same_count/test_count*100:.2f}%)")
    print(f"全不同: {all_different_count}次 ({all_different_count/test_count*100:.2f}%)")
    
    # 验证结果
    if return_rate < 95:
        print("\n✅ 返奖率合理，庄家有盈利空间")
    else:
        print("\n⚠️ 返奖率过高，可能导致庄家亏损")

if __name__ == "__main__":
    test_slot_returns()
