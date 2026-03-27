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
def play_slot_game(bet_amount):
    """
    老虎机游戏
    :param bet_amount: 下注金额
    :return: (是否赢, 结果描述, 赢得金额)
    """
    # 老虎机图案
    symbols = ["🍒", "🔔", "⭐", "💎", "7️⃣"]
    
    # 随机生成三个图案
    reels = [random.choice(symbols) for _ in range(3)]
    
    # 判断中奖情况
    if reels[0] == reels[1] == reels[2]:
        # 三个相同
        is_win = True
        win_amount = bet_amount * 3  # 赢了获得下注金额的3倍
        result = f"{reels[0]} {reels[1]} {reels[2]} - 三个相同！"
    elif reels[0] == reels[1] or reels[1] == reels[2] or reels[0] == reels[2]:
        # 两个相同
        is_win = True
        win_amount = bet_amount * 0.5  # 赢了获得下注金额的0.5倍
        result = f"{reels[0]} {reels[1]} {reels[2]} - 两个相同！"
    else:
        # 全不同
        is_win = False
        win_amount = -bet_amount  # 输了失去下注金额
        result = f"{reels[0]} {reels[1]} {reels[2]} - 全不同！"
    
    return is_win, result, win_amount
