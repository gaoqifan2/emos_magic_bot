import random

# 猜大小游戏逻辑
def play_guess_game(bet_amount, user_guess):
    """
    猜大小游戏
    :param bet_amount: 下注金额
    :param user_guess: 用户猜测的大小（"大"或"小"）
    :return: (是否赢, 结果描述, 赢得金额)
    """
    # 掷骰子，1-6点
    dice = random.randint(1, 6)
    
    # 判断大小
    if dice in [4, 5, 6]:
        actual_result = "大"
    else:
        actual_result = "小"
    
    # 判断用户是否猜对
    if user_guess == actual_result:
        is_win = True
        win_amount = bet_amount  # 赢了获得下注金额的1倍
    else:
        is_win = False
        win_amount = -bet_amount  # 输了失去下注金额
    
    # 骰子贴图
    dice_emoji = "🎲"
    
    return is_win, f"{dice_emoji} 骰子点数: {dice} ({actual_result})\n你猜的是: {user_guess}", win_amount

# 老虎机游戏逻辑
# 全局奖池变量
slot_jackpot = 0
MAX_JACKPOT = 10000  # 奖池上限
SERVICE_FEE_RATE = 0.05  # 服务费比例
MAX_BET_AMOUNT = 5000  # 最大下注金额
WINNER_JACKPOT_RATE = 0.05  # 胜方抽取奖池的比例

def play_slot_game(bet_amount):
    """
    老虎机游戏
    :param bet_amount: 下注金额
    :return: (是否赢, 结果描述, 赢得金额, 奖池变化, 是否中jackpot)
    """
    global slot_jackpot
    
    # 检查下注金额是否超过限制
    if bet_amount > MAX_BET_AMOUNT:
        return False, f"下注金额超过限制！最大下注金额为 {MAX_BET_AMOUNT}", -bet_amount, 0, False
    
    # 老虎机图案和对应的赔率
    symbols = ["🍇", "🍋", "7️⃣", "BAR"]  # 葡萄、柠檬、7、BAR
    # 三个相同的赔率：按图案顺序分别为1倍、2倍、3倍、3倍
    three_same_multipliers = [1, 2, 3, 3]  # 🍇:1倍, 🍋:2倍, 7️⃣:3倍, BAR:3倍
    
    # 随机生成三个图案
    reels = [random.choice(symbols) for _ in range(3)]
    
    # 判断中奖情况
    is_win = False
    win_amount = -bet_amount  # 默认输
    result = f"{reels[0]} {reels[1]} {reels[2]} - 全不同！"
    is_jackpot = False
    
    if reels[0] == reels[1] == reels[2]:
        # 三个相同
        is_win = True
        # 获取图案对应的赔率
        symbol_index = symbols.index(reels[0])
        multiplier = three_same_multipliers[symbol_index]
        win_amount = bet_amount * multiplier
        result = f"{reels[0]} {reels[1]} {reels[2]} - 三个相同！赔率 {multiplier} 倍！"
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        # 两个相同
        is_win = True
        win_amount = bet_amount * 0.4  # 赢了获得下注金额的0.4倍
        result = f"{reels[0]} {reels[1]} {reels[2]} - 两个相同！赔率 0.4 倍！"
    
    # 检查是否触发Jackpot（7️⃣-BAR-7️⃣组合）
    if reels[0] == "7️⃣" and reels[1] == "BAR" and reels[2] == "7️⃣":
        # 1/4的概率实际触发Jackpot
        if random.random() < 0.25:
            is_jackpot = True
            is_win = True
            # 根据下注金额确定用户等级（用于Jackpot奖励比例）
            def get_bet_level(bet_amount):
                if bet_amount >= 200:
                    return "钻石", 0.5, 1.0  # 固定5倍，100%奖池
                elif bet_amount >= 51:
                    return "黄金", 0.5, 0.6  # 固定5倍，60%奖池
                elif bet_amount >= 11:
                    return "白银", 0.5, 0.3  # 固定5倍，30%奖池
                else:
                    return "青铜", 0.5, 0.1  # 固定5倍，10%奖池
            
            level, fixed_multiplier, pool_ratio = get_bet_level(bet_amount)
            
            # 计算Jackpot奖金
            fixed_bonus = bet_amount * 5
            pool_bonus = int(slot_jackpot * pool_ratio)
            win_amount = fixed_bonus + pool_bonus
            
            # 构建结果消息
            result = f"{reels[0]} {reels[1]} {reels[2]} - JACKPOT大奖！"
            
            # 更新Jackpot奖池
            if pool_ratio == 1.0:
                # 钻石用户拿走全部奖池，重置为0
                jackpot_change = -slot_jackpot
                slot_jackpot = 0
            elif pool_ratio > 0:
                # 其他等级用户只拿走部分，更新奖池
                jackpot_change = -pool_bonus
                slot_jackpot -= pool_bonus
            else:
                jackpot_change = 0
            
            return is_win, result, win_amount, jackpot_change, is_jackpot
    
    # 处理奖池
    jackpot_change = 0
    service_fee = 0
    winner_jackpot_contribution = 0
    
    if not is_win:
        # 玩家输了，下注金额进入奖池
        if slot_jackpot < MAX_JACKPOT:
            # 奖池未满，全额进入
            add_to_jackpot = bet_amount
            slot_jackpot += add_to_jackpot
            jackpot_change = add_to_jackpot
        else:
            # 奖池已满，只抽服务费
            service_fee = bet_amount * SERVICE_FEE_RATE
            jackpot_change = service_fee
    elif is_win and win_amount > 0:
        # 玩家赢了
        if slot_jackpot < MAX_JACKPOT:
            # 奖池未满，抽取5%进入奖池
            winner_jackpot_contribution = win_amount * WINNER_JACKPOT_RATE
            # 从奖金中扣除
            win_amount -= winner_jackpot_contribution
            # 加入奖池
            slot_jackpot += winner_jackpot_contribution
            jackpot_change = winner_jackpot_contribution
        else:
            # 奖池已满，只抽服务费
            service_fee = win_amount * SERVICE_FEE_RATE
            win_amount -= service_fee
            jackpot_change = service_fee
    
    # 处理服务费
    if service_fee > 0:
        jackpot_change = service_fee
    
    return is_win, result, win_amount, jackpot_change, is_jackpot
