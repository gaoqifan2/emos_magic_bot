"""
扑克牌比大小游戏模块
支持两种模式：
1. 单挑模式：回复某人，只有被邀请者能加入
2. 群战模式：不回复任何人，群里任何人都能加入，1分钟后自动开始
"""

import random
import asyncio
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from datetime import datetime, timedelta

# 存储进行中的群战游戏
# 格式: {chat_id: {'game_id': str, 'players': {user_id: {'emos_id': str, 'name': str, 'card': tuple}}, 'amount': int, 'start_time': datetime, 'message': message}}
group_card_games = {}

# 扑克牌定义（斗地主规则）
SUITS = ['♠️', '♥️', '♦️', '♣️']
RANKS = ['3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K', 'A', '2']

# 点数映射（斗地主规则：3最小，2最大）
RANK_VALUES = {
    '3': 3, '4': 4, '5': 5, '6': 6, '7': 7, '8': 8, '9': 9, '10': 10,
    'J': 11, 'Q': 12, 'K': 13, 'A': 14, '2': 15
}

# 花色映射
SUIT_VALUES = {
    '♠️': 4, '♥️': 3, '♦️': 2, '♣️': 1
}

def draw_cards():
    """抽4张牌"""
    cards = []
    while len(cards) < 4:
        suit = random.choice(SUITS)
        rank = random.choice(RANKS)
        card = (suit, rank)
        if card not in cards:  # 避免重复牌
            cards.append(card)
    return cards

def compare_hands(hand1, hand2):
    """
    比较两手牌的大小（4张牌，斗地主规则）
    规则：
    1. 炸弹（4张相同点数）最大
    2. 葫芦（3+1）
    3. 两对
    4. 一对
    5. 高牌（按最大牌比较）
    返回: 1表示hand1大, -1表示hand2大, 0表示平局
    """
    def get_hand_type(hand):
        """获取牌型"""
        ranks = [card[1] for card in hand]
        rank_counts = {}
        for rank in ranks:
            rank_counts[rank] = rank_counts.get(rank, 0) + 1
        
        counts = sorted(rank_counts.values(), reverse=True)
        
        if counts == [4]:
            return (5, max([RANK_VALUES[rank] for rank in ranks]))  # 炸弹
        elif counts == [3, 1]:
            # 葫芦：找到3张的牌
            triple_rank = [rank for rank, count in rank_counts.items() if count == 3][0]
            return (4, RANK_VALUES[triple_rank])
        elif counts == [2, 2]:
            # 两对：取较大的对子
            pair_ranks = [RANK_VALUES[rank] for rank, count in rank_counts.items() if count == 2]
            pair_ranks.sort(reverse=True)
            return (3, pair_ranks[0], pair_ranks[1])
        elif counts == [2, 1, 1]:
            # 一对：取对子
            pair_rank = [rank for rank, count in rank_counts.items() if count == 2][0]
            return (2, RANK_VALUES[pair_rank])
        else:
            # 高牌：取最大的牌
            max_rank = max([RANK_VALUES[rank] for rank in ranks])
            return (1, max_rank)
    
    type1 = get_hand_type(hand1)
    type2 = get_hand_type(hand2)
    
    if type1 > type2:
        return 1
    elif type1 < type2:
        return -1
    else:
        # 牌型相同，比较花色（仅高牌时）
        if type1[0] == 1:
            max_card1 = max(hand1, key=lambda card: (RANK_VALUES[card[1]], SUIT_VALUES[card[0]]))
            max_card2 = max(hand2, key=lambda card: (RANK_VALUES[card[1]], SUIT_VALUES[card[0]]))
            suit1 = SUIT_VALUES[max_card1[0]]
            suit2 = SUIT_VALUES[max_card2[0]]
            if suit1 > suit2:
                return 1
            elif suit1 < suit2:
                return -1
        return 0

def format_hand(hand):
    """格式化显示手牌"""
    return ' '.join([f"{card[0]}{card[1]}" for card in hand])

# ===== 牛牛游戏相关函数 =====

def draw_niuniu_cards():
    """抽5张牌（牛牛游戏）"""
    cards = []
    while len(cards) < 5:
        suit = random.choice(SUITS)
        rank = random.choice(RANKS)
        card = (suit, rank)
        if card not in cards:  # 避免重复牌
            cards.append(card)
    return cards

def get_card_point(card):
    """获取牌的点数"""
    rank = card[1]
    if rank in ['J', 'Q', 'K']:
        return 10
    elif rank == 'A':
        return 1
    else:
        return int(rank)

def calculate_niuniu(cards):
    """
    计算牛牛牌型
    返回：(牌型名称, 牛的大小, 最大牌)
    """
    points = [get_card_point(card) for card in cards]
    total_point = sum(points)
    
    # 检查五小牛
    if all(point < 5 for point in points) and total_point <= 10:
        return ("五小牛", 10, max(cards, key=lambda x: (RANK_VALUES[x[1]], SUIT_VALUES[x[0]])))
    
    # 检查炸弹牛
    ranks = [card[1] for card in cards]
    rank_counts = {}
    for rank in ranks:
        rank_counts[rank] = rank_counts.get(rank, 0) + 1
    if 4 in rank_counts.values():
        return ("炸弹牛", 9, max(cards, key=lambda x: (RANK_VALUES[x[1]], SUIT_VALUES[x[0]])))
    
    # 检查五花牛
    if all(rank in ['J', 'Q', 'K'] for rank in ranks):
        return ("五花牛", 8, max(cards, key=lambda x: (RANK_VALUES[x[1]], SUIT_VALUES[x[0]])))
    
    # 检查四花牛
    jqk_count = sum(1 for rank in ranks if rank in ['J', 'Q', 'K'])
    if jqk_count == 4:
        return ("四花牛", 7, max(cards, key=lambda x: (RANK_VALUES[x[1]], SUIT_VALUES[x[0]])))
    
    # 寻找3张牌和为10的倍数
    has_niu = False
    niu_value = 0
    for i in range(5):
        for j in range(i+1, 5):
            for k in range(j+1, 5):
                if (points[i] + points[j] + points[k]) % 10 == 0:
                    has_niu = True
                    remaining = sum(points) - (points[i] + points[j] + points[k])
                    niu_value = remaining % 10
                    if niu_value == 0:
                        niu_value = 10  # 牛牛
                    break
            if has_niu:
                break
        if has_niu:
            break
    
    if has_niu:
        if niu_value == 10:
            return ("牛牛", 6, max(cards, key=lambda x: (RANK_VALUES[x[1]], SUIT_VALUES[x[0]])))
        else:
            return (f"牛{niu_value}", niu_value, max(cards, key=lambda x: (RANK_VALUES[x[1]], SUIT_VALUES[x[0]])))
    else:
        return ("无牛", 0, max(cards, key=lambda x: (RANK_VALUES[x[1]], SUIT_VALUES[x[0]])))

def compare_niuniu(hand1, hand2):
    """
    比较两手牛牛牌的大小
    返回: 1表示hand1大, -1表示hand2大, 0表示平局
    """
    type1, value1, max_card1 = calculate_niuniu(hand1)
    type2, value2, max_card2 = calculate_niuniu(hand2)
    
    if value1 > value2:
        return 1
    elif value1 < value2:
        return -1
    else:
        # 牌型相同，比较最大牌
        max_rank1 = RANK_VALUES[max_card1[1]]
        max_rank2 = RANK_VALUES[max_card2[1]]
        if max_rank1 > max_rank2:
            return 1
        elif max_rank1 < max_rank2:
            return -1
        else:
            # 最大牌点数相同，比较花色
            max_suit1 = SUIT_VALUES[max_card1[0]]
            max_suit2 = SUIT_VALUES[max_card2[0]]
            if max_suit1 > max_suit2:
                return 1
            elif max_suit1 < max_suit2:
                return -1
            else:
                return 0

def get_niuniu_odds(card_type):
    """获取牛牛赔率"""
    odds_map = {
        "五小牛": 5,
        "炸弹牛": 4,
        "五花牛": 3,
        "牛牛": 2,
        "牛9": 1.5,
        "牛8": 1.5,
        "牛7": 1.5,
        "牛6": 1,
        "牛5": 1,
        "牛4": 1,
        "牛3": 0.5,
        "牛2": 0.5,
        "牛1": 0.5,
        "无牛": 0
    }
    return odds_map.get(card_type, 0)

# 存储进行中的牛牛群战游戏
# 格式: {chat_id: {'game_id': str, 'players': {user_id: {'emos_id': str, 'name': str, 'card': tuple}}, 'amount': int, 'start_time': datetime, 'message': message}}  
niuniu_group_games = {}

async def niuniu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """创建牛牛游戏"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # 检查是否在群聊中
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ 此游戏只能在群聊中进行！")
        return
    
    # 获取参数
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ 请输入下注金额！\n\n"
            "使用方法：\n"
            "• 单挑模式：回复对方消息 + `/niuniu <金额>`\n"
            "• 群战模式：`/niuniu <金额>`（任何人可加入）\n"
            "例如：`/niuniu 100`\n\n"
            "直接复制：`/niuniu 100`",
            parse_mode='Markdown'
        )
        return
    
    try:
        amount = int(args[0])
        if amount <= 0:
            await update.message.reply_text("❌ 下注金额必须大于0！")
            return
    except ValueError:
        await update.message.reply_text("❌ 请输入有效的数字！")
        return
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user.id not in user_tokens:
        await update.message.reply_text("❌ 请先使用 /start 命令登录！")
        return
    
    # 获取用户ID
    user_info = user_tokens[user.id]
    user_emos_id = user_info.get('user_id', str(user.id))
    
    # 检查余额
    from app.database import get_balance
    user_balance = get_balance(user_emos_id)
    if user_balance < amount:
        await update.message.reply_text(f"❌ 您的游戏币不足！当前余额：{user_balance} 🪙")
        return
    
    # 判断游戏模式
    if update.message.reply_to_message:
        # ===== 单挑模式 =====
        opponent = update.message.reply_to_message.from_user
        opponent_id = opponent.id
        
        # 不能和自己对战
        if opponent_id == user.id:
            await update.message.reply_text("❌ 不能和自己对战！")
            return
        
        if opponent_id not in user_tokens:
            await update.message.reply_text("❌ 对方未登录游戏系统！")
            return
        
        opponent_info = user_tokens[opponent_id]
        opponent_emos_id = opponent_info.get('user_id', str(opponent_id))
        
        # 检查对方余额
        opponent_balance = get_balance(opponent_emos_id)
        if opponent_balance < amount:
            await update.message.reply_text(f"❌ 对方的游戏币不足！对方余额：{opponent_balance} 🪙")
            return
        
        # 开始游戏
        user_cards = draw_niuniu_cards()
        opponent_cards = draw_niuniu_cards()
        
        # 计算牌型
        user_type, user_value, _ = calculate_niuniu(user_cards)
        opponent_type, opponent_value, _ = calculate_niuniu(opponent_cards)
        
        # 比较大小
        result = compare_niuniu(user_cards, opponent_cards)
        
        # 处理结果
        from app.database import update_balance, add_game_record
        
        user_name = user_info.get('username', user.first_name)
        opponent_name = opponent_info.get('username', opponent.first_name)
        
        if result > 0:
            # 用户赢
            odds = get_niuniu_odds(user_type)
            win_amount = int(amount * odds)
            service_fee = int(win_amount * 0.05)  # 抽水5%
            net_win = win_amount - service_fee
            
            # 更新余额
            update_balance(user_emos_id, net_win)
            update_balance(opponent_emos_id, -amount)
            
            # 添加游戏记录
            add_game_record(user_emos_id, 'niuniu', amount, 'win', net_win, user_name)
            add_game_record(opponent_emos_id, 'niuniu', amount, 'lose', -amount, opponent_name)
            
            # 获取最新余额
            user_balance = get_balance(user_emos_id)
            opponent_balance = get_balance(opponent_emos_id)
            
            result_text = (
                f"🐮 牛牛游戏结果\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 {user_name}：{format_hand(user_cards)} → {user_type}\n"
                f"👤 {opponent_name}：{format_hand(opponent_cards)} → {opponent_type}\n\n"
                f"🎉 {user_name} 获胜！\n\n"
                f"💰 {user_name}：\n"
                f"  下注：{amount} 🪙\n"
                f"  赔率：{odds}倍\n"
                f"  赢得：{win_amount} 🪙\n"
                f"  服务费：{service_fee} 🪙\n"
                f"  实际获得：{net_win} 🪙\n"
                f"  当前余额：{user_balance} 🪙\n\n"
                f"💸 {opponent_name}：\n"
                f"  失去：{amount} 🪙\n"
                f"  当前余额：{opponent_balance} 🪙"
            )
            
        elif result < 0:
            # 对手赢
            odds = get_niuniu_odds(opponent_type)
            win_amount = int(amount * odds)
            service_fee = int(win_amount * 0.05)  # 抽水5%
            net_win = win_amount - service_fee
            
            # 更新余额
            update_balance(opponent_emos_id, net_win)
            update_balance(user_emos_id, -amount)
            
            # 添加游戏记录
            add_game_record(opponent_emos_id, 'niuniu', amount, 'win', net_win, opponent_name)
            add_game_record(user_emos_id, 'niuniu', amount, 'lose', -amount, user_name)
            
            # 获取最新余额
            user_balance = get_balance(user_emos_id)
            opponent_balance = get_balance(opponent_emos_id)
            
            result_text = (
                f"🐮 牛牛游戏结果\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 {user_name}：{format_hand(user_cards)} → {user_type}\n"
                f"👤 {opponent_name}：{format_hand(opponent_cards)} → {opponent_type}\n\n"
                f"🎉 {opponent_name} 获胜！\n\n"
                f"💰 {opponent_name}：\n"
                f"  下注：{amount} 🪙\n"
                f"  赔率：{odds}倍\n"
                f"  赢得：{win_amount} 🪙\n"
                f"  服务费：{service_fee} 🪙\n"
                f"  实际获得：{net_win} 🪙\n"
                f"  当前余额：{opponent_balance} 🪙\n\n"
                f"💸 {user_name}：\n"
                f"  失去：{amount} 🪙\n"
                f"  当前余额：{user_balance} 🪙"
            )
            
        else:
            # 平局
            # 添加游戏记录
            add_game_record(user_emos_id, 'niuniu', amount, 'draw', 0, user_name)
            add_game_record(opponent_emos_id, 'niuniu', amount, 'draw', 0, opponent_name)
            
            # 获取最新余额
            user_balance = get_balance(user_emos_id)
            opponent_balance = get_balance(opponent_emos_id)
            
            result_text = (
                f"🐮 牛牛游戏结果\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 {user_name}：{format_hand(user_cards)} → {user_type}\n"
                f"👤 {opponent_name}：{format_hand(opponent_cards)} → {opponent_type}\n\n"
                f"🤝 平局！\n\n"
                f"👤 {user_name} 当前余额：{user_balance} 🪙\n"
                f"👤 {opponent_name} 当前余额：{opponent_balance} 🪙"
            )
        
        await update.message.reply_text(result_text)
        
    else:
        # ===== 群战模式 =====
        # 检查是否已有进行中的游戏
        if chat_id in niuniu_group_games:
            await update.message.reply_text("❌ 当前群聊已有进行中的牛牛游戏！")
            return
        
        # 创建游戏ID
        game_id = f"niuniu_group_{chat_id}_{int(datetime.now().timestamp())}"
        
        # 存储游戏信息
        niuniu_group_games[chat_id] = {
            'game_id': game_id,
            'creator_id': user_emos_id,
            'creator_name': user_info.get('username', user.first_name),
            'players': {
                user.id: {
                    'emos_id': user_emos_id,
                    'name': user_info.get('username', user.first_name),
                    'card': None
                }
            },
            'amount': amount,
            'start_time': datetime.now(),
            'message': None
        }
        
        # 发送游戏邀请
        keyboard = [[InlineKeyboardButton("🎮 加入游戏", callback_data=f"join_niuniu_group_{chat_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = await update.message.reply_text(
            f"🐮 牛牛游戏 - 群战模式\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 创建者：{user_info.get('username', user.first_name)}\n"
            f"💰 下注金额：{amount} 🪙\n"
            f"⏱️ 开始时间：1分钟后自动开始\n"
            f"👥 当前参与：1人\n\n"
            f"📋 游戏规则：\n"
            f"  • 所有人各抽5张牌\n"
            f"  • 牌型大小：五小牛 > 炸弹牛 > 五花牛 > 四花牛 > 牛牛 > 牛9-牛1 > 无牛\n"
            f"  • 点数计算：A=1, 2-10=对应点数, JQK=10\n"
            f"  • 赢家获得所有下注金额\n"
            f"  • 赢家扣除5%服务费\n\n"
            f"💡 任何人都可以点击按钮加入游戏！",
            reply_markup=reply_markup
        )
        
        niuniu_group_games[chat_id]['message'] = message
        
        # 启动倒计时任务
        asyncio.create_task(start_niuniu_group_game_countdown(chat_id, context))

async def start_niuniu_group_game_countdown(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """牛牛群战模式倒计时"""
    await asyncio.sleep(60)  # 等待1分钟
    
    if chat_id not in niuniu_group_games:
        return
    
    game = niuniu_group_games[chat_id]
    players = game['players']
    
    if len(players) < 2:
        # 人数不足，取消游戏
        message = game['message']
        await message.edit_text(
            f"🐮 牛牛游戏 - 群战模式\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"❌ 游戏取消！\n"
            f"原因：参与人数不足（至少需要2人）\n"
            f"当前参与：{len(players)}人\n"
            f"━━━━━━━━━━━━━━━━━━"
        )
        del niuniu_group_games[chat_id]
        return
    
    # 开始游戏，给每个人发牌
    player_cards = {}
    for user_id, player_info in players.items():
        cards = draw_niuniu_cards()
        player_info['card'] = cards
        player_cards[user_id] = {
            'name': player_info['name'],
            'emos_id': player_info['emos_id'],
            'card': cards,
            'type': calculate_niuniu(cards)
        }
    
    # 找出最大的牌
    winner_id = None
    winner_cards = None
    winner_name = None
    winner_type = None
    
    for user_id, player_data in player_cards.items():
        if winner_id is None:
            winner_id = user_id
            winner_cards = player_data['card']
            winner_name = player_data['name']
            winner_type = player_data['type']
        else:
            result = compare_niuniu(player_data['card'], winner_cards)
            if result > 0:
                winner_id = user_id
                winner_cards = player_data['card']
                winner_name = player_data['name']
                winner_type = player_data['type']
    
    # 计算奖金
    total_amount = game['amount'] * len(players)
    odds = get_niuniu_odds(winner_type[0])
    
    # 输家数量
    loser_count = len(players) - 1
    
    # 每个输家的损失 = 下注金额 × 赔率
    each_loser_loss = int(game['amount'] * odds)
    
    # 总输家损失
    total_loser_loss = each_loser_loss * loser_count
    
    # 服务费：总输家损失的10%
    service_fee = int(total_loser_loss * 0.10)
    
    # 赢家获得 = 总输家损失 - 服务费
    net_win = total_loser_loss - service_fee
    
    # 总奖池 = 所有玩家的下注总和
    # 输家每人损失：下注金额 × 赔率
    # 赢家获得：总输家损失 × 90%
    # 服务费：总输家损失 × 10%
    
    # 更新余额
    from app.database import update_balance, add_game_record, get_balance
    
    # 赢家获得奖金
    winner_emos_id = player_cards[winner_id]['emos_id']
    update_balance(winner_emos_id, net_win)
    add_game_record(winner_emos_id, 'niuniu_group', game['amount'], 'win', net_win, winner_name)
    
    # 其他玩家扣除下注
    for user_id, player_data in player_cards.items():
        if user_id != winner_id:
            update_balance(player_data['emos_id'], -each_loser_loss)
            add_game_record(player_data['emos_id'], 'niuniu_group', each_loser_loss, 'lose', -each_loser_loss, player_data['name'])
    
    # 生成结果文本
    result_text = (
        f"🐮 牛牛游戏 - 群战结果\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 参与人数：{len(players)}人\n"
        f"💰 总奖池：{total_amount} 🪙\n"
        f"🎰 牌型：{winner_type[0]} (赔率：{odds}倍)\n\n"
    )
    
    # 显示每个人的牌
    for user_id, player_data in player_cards.items():
        cards_str = format_hand(player_data['card'])
        card_type, _, _ = player_data['type']
        if user_id == winner_id:
            result_text += f"👑 {player_data['name']}：{cards_str} → {card_type} 🏆\n"
        else:
            result_text += f"👤 {player_data['name']}：{cards_str} → {card_type}\n"
    
    # 显示赢家信息
    winner_balance = get_balance(winner_emos_id)
    
    # 收集所有玩家的余额变化
    balance_changes = []
    for user_id, player_data in player_cards.items():
        player_balance = get_balance(player_data['emos_id'])
        if user_id == winner_id:
            change = net_win
            balance_changes.append(f"  • 🏆 {player_data['name']}：{player_balance - change} → {player_balance} 🪙 (+{change} 🪙)")
        else:
            change = -each_loser_loss
            balance_changes.append(f"  • 👤 {player_data['name']}：{player_balance - change} → {player_balance} 🪙 ({change} 🪙)")
    
    result_text += (
        f"\n🎉 {winner_name} 获胜！\n\n"
        f"💰 奖金明细：\n"
        f"  • 总奖池：{total_amount} 🪙\n"
        f"  • 赔率：{odds}倍\n"
        f"  • 每个输家损失：{each_loser_loss} 🪙\n"
        f"  • 总输家损失：{total_loser_loss} 🪙\n"
        f"  • 服务费：{service_fee} 🪙 (10%)\n"
        f"  • 实际获得：{net_win} 🪙\n"
        f"  • 赢家余额：{winner_balance} 🪙\n\n"
        f"📊 余额变动：\n"
        f"{'\n'.join(balance_changes)}"
    )
    
    # 更新消息
    message = game['message']
    await message.edit_text(result_text)
    
    # 清理游戏数据
    del niuniu_group_games[chat_id]

async def join_niuniu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """加入牛牛游戏"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # 检查是否在群聊中
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ 此游戏只能在群聊中进行！")
        return
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user.id not in user_tokens:
        await update.message.reply_text("❌ 请先使用 /start 命令登录！")
        return
    
    # 获取用户ID
    user_info = user_tokens[user.id]
    user_emos_id = user_info.get('user_id', str(user.id))
    
    # 检查是否有群战游戏
    if chat_id in niuniu_group_games:
        # ===== 加入群战模式 =====
        game = niuniu_group_games[chat_id]
        
        # 检查是否已加入
        if user.id in game['players']:
            await update.message.reply_text("❌ 您已经加入了这个游戏！")
            return
        
        # 检查余额
        from app.database import get_balance
        user_balance = get_balance(user_emos_id)
        if user_balance < game['amount']:
            await update.message.reply_text(f"❌ 您的游戏币不足！当前余额：{user_balance} 🪙")
            return
        
        # 加入游戏
        game['players'][user.id] = {
            'emos_id': user_emos_id,
            'name': user_info.get('username', user.first_name),
            'card': None
        }
        
        # 更新消息
        remaining_time = 60 - int((datetime.now() - game['start_time']).total_seconds())
        if remaining_time < 0:
            remaining_time = 0
        
        keyboard = [[InlineKeyboardButton("🎮 加入游戏", callback_data=f"join_niuniu_group_{chat_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await game['message'].edit_text(
            f"🐮 牛牛游戏 - 群战模式\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 创建者：{game['creator_name']}\n"
            f"💰 下注金额：{game['amount']} 🪙\n"
            f"⏱️ 开始时间：{remaining_time}秒后自动开始\n"
            f"👥 当前参与：{len(game['players'])}人\n\n"
            f"📋 游戏规则：\n"
            f"  • 所有人各抽5张牌\n"
            f"  • 牌型大小：五小牛 > 炸弹牛 > 五花牛 > 四花牛 > 牛牛 > 牛9-牛1 > 无牛\n"
            f"  • 点数计算：A=1, 2-10=对应点数, JQK=10\n"
            f"  • 赢家获得所有下注金额\n"
            f"  • 赢家扣除5%服务费\n\n"
            f"💡 任何人都可以点击按钮加入游戏！",
            reply_markup=reply_markup
        )
        
        await update.message.reply_text(f"✅ 您已成功加入牛牛游戏！当前参与人数：{len(game['players'])}人")
        return
    else:
        await update.message.reply_text("❌ 当前没有等待中的牛牛游戏！")
        return

async def niuniu_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理牛牛游戏的按钮回调"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    chat_id = update.effective_chat.id
    
    if data.startswith('join_niuniu_group_'):
        # 加入牛牛群战游戏
        chat_id = int(data.split('_')[-1])
        
        # 检查用户是否已登录
        from app.config import user_tokens
        if user.id not in user_tokens:
            await query.answer("请先使用 /start 命令登录！", show_alert=True)
            return
        
        user_info = user_tokens[user.id]
        user_emos_id = user_info.get('user_id', str(user.id))
        
        if chat_id in niuniu_group_games:
            game = niuniu_group_games[chat_id]
            
            # 检查是否已加入
            if user.id in game['players']:
                await query.answer("您已经加入了这个游戏！", show_alert=True)
                return
            
            # 检查余额
            from app.database import get_balance
            user_balance = get_balance(user_emos_id)
            if user_balance < game['amount']:
                await query.answer(f"您的游戏币不足！当前余额：{user_balance} 🪙", show_alert=True)
                return
            
            # 加入游戏
            game['players'][user.id] = {
                'emos_id': user_emos_id,
                'name': user_info.get('username', user.first_name),
                'card': None
            }
            
            # 更新消息
            remaining_time = 60 - int((datetime.now() - game['start_time']).total_seconds())
            if remaining_time < 0:
                remaining_time = 0
            
            keyboard = [[InlineKeyboardButton("🎮 加入游戏", callback_data=f"join_niuniu_group_{chat_id}")]]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await game['message'].edit_text(
                f"🐮 牛牛游戏 - 群战模式\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 创建者：{game['creator_name']}\n"
                f"💰 下注金额：{game['amount']} 🪙\n"
                f"⏱️ 开始时间：{remaining_time}秒后自动开始\n"
                f"👥 当前参与：{len(game['players'])}人\n\n"
                f"📋 游戏规则：\n"
                f"  • 所有人各抽5张牌\n"
                f"  • 牌型大小：五小牛 > 炸弹牛 > 五花牛 > 四花牛 > 牛牛 > 牛9-牛1 > 无牛\n"
                f"  • 点数计算：A=1, 2-10=对应点数, JQK=10\n"
                f"  • 赢家获得所有下注金额\n"
                f"  • 赢家扣除5%服务费\n\n"
                f"💡 任何人都可以点击按钮加入游戏！",
                reply_markup=reply_markup
            )
            
            await query.answer(f"您已成功加入游戏！当前参与人数：{len(game['players'])}人")
        else:
            await query.answer("游戏已结束或不存在！", show_alert=True)
    
    await query.answer()

async def cardduel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """创建扑克牌比大小游戏"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # 检查是否在群聊中
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ 此游戏只能在群聊中进行！")
        return
    
    # 获取参数
    args = context.args
    if not args:
        await update.message.reply_text(
            "❌ 请输入下注金额！\n\n"
            "使用方法：\n"
            "• 单挑模式：回复对方消息 + `/cardduel <金额>`\n"
            "• 群战模式：`/cardduel <金额>`（任何人可加入）\n"
            "例如：`/cardduel 100`\n\n"
            "直接复制：`/cardduel 100`",
            parse_mode='Markdown'
        )
        return
    
    try:
        amount = int(args[0])
        if amount <= 0:
            await update.message.reply_text("❌ 下注金额必须大于0！")
            return
    except ValueError:
        await update.message.reply_text("❌ 请输入有效的数字！")
        return
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user.id not in user_tokens:
        await update.message.reply_text("❌ 请先使用 /start 命令登录！")
        return
    
    # 获取用户ID
    user_info = user_tokens[user.id]
    user_emos_id = user_info.get('user_id', str(user.id))
    
    # 检查余额
    from app.database import get_balance
    user_balance = get_balance(user_emos_id)
    if user_balance < amount:
        await update.message.reply_text(f"❌ 您的游戏币不足！当前余额：{user_balance} 🪙")
        return
    
    # 判断游戏模式
    if update.message.reply_to_message:
        # ===== 单挑模式 =====
        opponent = update.message.reply_to_message.from_user
        opponent_id = opponent.id
        
        # 不能和自己对战
        if opponent_id == user.id:
            await update.message.reply_text("❌ 不能和自己对战！")
            return
        
        if opponent_id not in user_tokens:
            await update.message.reply_text("❌ 对方未登录游戏系统！")
            return
        
        opponent_info = user_tokens[opponent_id]
        opponent_emos_id = opponent_info.get('user_id', str(opponent_id))
        
        # 检查对方余额
        opponent_balance = get_balance(opponent_emos_id)
        if opponent_balance < amount:
            await update.message.reply_text(f"❌ 对方的游戏币不足！对方余额：{opponent_balance} 🪙")
            return
        
        # 创建游戏ID
        game_id = f"card_duel_{chat_id}_{int(datetime.now().timestamp())}"
        
        # 保存到数据库
        from app.database.card_games import create_card_game
        success = create_card_game(
            game_id=game_id,
            chat_id=chat_id,
            creator_id=user_emos_id,
            creator_name=user_info.get('username', user.first_name),
            amount=amount
        )
        
        if not success:
            await update.message.reply_text("❌ 创建游戏失败，请重试！")
            return
        
        # 发送游戏邀请
        keyboard = [[InlineKeyboardButton("🎮 加入游戏", callback_data=f"join_card_duel_{game_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            f"🃏 扑克牌比大小 - 单挑模式\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 创建者：{user_info.get('username', user.first_name)}\n"
            f"🎯 挑战对象：{opponent_info.get('username', opponent.first_name)}\n"
            f"💰 下注金额：{amount} 🪙\n\n"
            f"📋 游戏规则：\n"
            f"  • 双方各抽4张牌比大小\n"
            f"  • 牌型大小：炸弹 > 葫芦 > 两对 > 一对 > 高牌\n"
            f"  • 点数大小：3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A < 2\n"
            f"  • 花色大小：♠️ > ♥️ > ♦️ > ♣️\n"
            f"  • 赢家获得对方下注金额\n"
            f"  • 赢家扣除10%服务费\n\n"
            f"⏳ 等待 {opponent_info.get('username', opponent.first_name)} 加入...\n\n"
            f"💡 {opponent_info.get('username', opponent.first_name)} 请点击下方按钮加入游戏",
            reply_markup=reply_markup
        )
    else:
        # ===== 群战模式 =====
        # 检查是否已有进行中的游戏
        if chat_id in group_card_games:
            await update.message.reply_text("❌ 当前群聊已有进行中的扑克牌游戏！")
            return
        
        # 创建游戏ID
        game_id = f"card_group_{chat_id}_{int(datetime.now().timestamp())}"
        
        # 存储游戏信息
        group_card_games[chat_id] = {
            'game_id': game_id,
            'creator_id': user_emos_id,
            'creator_name': user_info.get('username', user.first_name),
            'players': {
                user.id: {
                    'emos_id': user_emos_id,
                    'name': user_info.get('username', user.first_name),
                    'card': None
                }
            },
            'amount': amount,
            'start_time': datetime.now(),
            'message': None
        }
        
        # 发送游戏邀请
        keyboard = [[InlineKeyboardButton("🎮 加入游戏", callback_data=f"join_card_group_{chat_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        message = await update.message.reply_text(
            f"🃏 扑克牌比大小 - 群战模式\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 创建者：{user_info.get('username', user.first_name)}\n"
            f"💰 下注金额：{amount} 🪙\n"
            f"⏱️ 开始时间：1分钟后自动开始\n"
            f"👥 当前参与：1人\n\n"
            f"📋 游戏规则：\n"
            f"  • 所有人各抽4张牌比大小\n"
            f"  • 牌型大小：炸弹 > 葫芦 > 两对 > 一对 > 高牌\n"
            f"  • 点数大小：3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A < 2\n"
            f"  • 花色大小：♠️ > ♥️ > ♦️ > ♣️\n"
            f"  • 赢家获得所有下注金额\n"
            f"  • 赢家扣除10%服务费\n\n"
            f"💡 任何人都可以点击按钮加入游戏！",
            reply_markup=reply_markup
        )
        
        group_card_games[chat_id]['message'] = message
        
        # 启动倒计时任务
        asyncio.create_task(start_group_card_game_countdown(chat_id, context))

async def start_group_card_game_countdown(chat_id: int, context: ContextTypes.DEFAULT_TYPE):
    """群战模式倒计时"""
    await asyncio.sleep(60)  # 等待1分钟
    
    if chat_id not in group_card_games:
        return
    
    game = group_card_games[chat_id]
    players = game['players']
    
    if len(players) < 2:
        # 人数不足，取消游戏
        message = game['message']
        await message.edit_text(
            f"🃏 扑克牌比大小 - 群战模式\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"❌ 游戏取消！\n"
            f"原因：参与人数不足（至少需要2人）\n\n"
            f"👥 实际参与：{len(players)}人"
        )
        del group_card_games[chat_id]
        return
    
    # 开始游戏，给每个人发牌
    player_cards = {}
    for user_id, player_info in players.items():
        cards = draw_cards()
        player_info['card'] = cards
        player_cards[user_id] = {
            'name': player_info['name'],
            'emos_id': player_info['emos_id'],
            'card': cards
        }
    
    # 找出最大的牌
    winner_id = None
    winner_cards = None
    winner_name = None
    
    for user_id, player_data in player_cards.items():
        if winner_id is None:
            winner_id = user_id
            winner_cards = player_data['card']
            winner_name = player_data['name']
        else:
            result = compare_hands(player_data['card'], winner_cards)
            if result > 0:
                winner_id = user_id
                winner_cards = player_data['card']
                winner_name = player_data['name']
    
    # 计算奖金
    total_amount = game['amount'] * len(players)
    service_fee = int(total_amount * 0.1)
    net_win = total_amount - service_fee
    
    # 更新余额
    from app.database import update_balance, add_game_record, get_balance
    
    # 赢家获得奖金
    winner_emos_id = player_cards[winner_id]['emos_id']
    update_balance(winner_emos_id, net_win)
    add_game_record(winner_emos_id, 'cardduel_group', game['amount'], 'win', net_win, winner_name)
    
    # 其他玩家扣除下注
    for user_id, player_data in player_cards.items():
        if user_id != winner_id:
            update_balance(player_data['emos_id'], -game['amount'])
            add_game_record(player_data['emos_id'], 'cardduel_group', game['amount'], 'lose', -game['amount'], player_data['name'])
    
    # 生成结果文本
    result_text = (
        f"🃏 扑克牌比大小 - 群战结果\n"
        f"━━━━━━━━━━━━━━━━━━\n\n"
        f"👥 参与人数：{len(players)}人\n"
        f"💰 总奖池：{total_amount} 🪙\n\n"
    )
    
    # 显示每个人的牌
    for user_id, player_data in player_cards.items():
        cards_str = format_hand(player_data['card'])
        if user_id == winner_id:
            result_text += f"👑 {player_data['name']}：{cards_str} 🏆\n"
        else:
            result_text += f"👤 {player_data['name']}：{cards_str}\n"
    
    # 显示赢家信息
    winner_balance = get_balance(winner_emos_id)
    
    # 收集所有玩家的余额变化
    balance_changes = []
    for user_id, player_data in player_cards.items():
        player_balance = get_balance(player_data['emos_id'])
        if user_id == winner_id:
            change = net_win
            balance_changes.append(f"  • 🏆 {player_data['name']}：{player_balance - change} → {player_balance} 🪙 (+{change} 🪙)")
        else:
            change = -game['amount']
            balance_changes.append(f"  • 👤 {player_data['name']}：{player_balance - change} → {player_balance} 🪙 ({change} 🪙)")
    
    result_text += (
        f"\n🎉 {winner_name} 获胜！\n\n"
        f"💰 奖金明细：\n"
        f"  • 总奖池：{total_amount} 🪙\n"
        f"  • 服务费：{service_fee} 🪙\n"
        f"  • 实际获得：{net_win} 🪙\n"
        f"  • 赢家余额：{winner_balance} 🪙\n\n"
        f"📊 余额变动：\n"
        f"{'\n'.join(balance_changes)}"
    )
    
    # 更新消息
    message = game['message']
    await message.edit_text(result_text)
    
    # 清理游戏数据
    del group_card_games[chat_id]

async def join_cardduel_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """加入扑克牌比大小游戏"""
    user = update.effective_user
    chat_id = update.effective_chat.id
    
    # 检查是否在群聊中
    if update.message.chat.type not in ['group', 'supergroup']:
        await update.message.reply_text("❌ 此游戏只能在群聊中进行！")
        return
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user.id not in user_tokens:
        await update.message.reply_text("❌ 请先使用 /start 命令登录！")
        return
    
    # 获取用户ID
    user_info = user_tokens[user.id]
    user_emos_id = user_info.get('user_id', str(user.id))
    
    # 检查是否有群战游戏
    if chat_id in group_card_games:
        # ===== 加入群战模式 =====
        game = group_card_games[chat_id]
        
        # 检查是否已加入
        if user.id in game['players']:
            await update.message.reply_text("❌ 您已经加入了这个游戏！")
            return
        
        # 检查余额
        from app.database import get_balance
        user_balance = get_balance(user_emos_id)
        if user_balance < game['amount']:
            await update.message.reply_text(f"❌ 您的游戏币不足！当前余额：{user_balance} 🪙")
            return
        
        # 加入游戏
        game['players'][user.id] = {
            'emos_id': user_emos_id,
            'name': user_info.get('username', user.first_name),
            'card': None
        }
        
        # 更新消息
        remaining_time = 60 - int((datetime.now() - game['start_time']).total_seconds())
        if remaining_time < 0:
            remaining_time = 0
        
        keyboard = [[InlineKeyboardButton("🎮 加入游戏", callback_data=f"join_card_group_{chat_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await game['message'].edit_text(
            f"🃏 扑克牌比大小 - 群战模式\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 创建者：{game['creator_name']}\n"
            f"💰 下注金额：{game['amount']} 🪙\n"
            f"⏱️ 开始时间：{remaining_time}秒后自动开始\n"
            f"👥 当前参与：{len(game['players'])}人\n\n"
            f"📋 游戏规则：\n"
            f"  • 所有人各抽4张牌比大小\n"
            f"  • 牌型大小：炸弹 > 葫芦 > 两对 > 一对 > 高牌\n"
            f"  • 点数大小：3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A < 2\n"
            f"  • 花色大小：♠️ > ♥️ > ♦️ > ♣️\n"
            f"  • 赢家获得所有下注金额\n"
            f"  • 赢家扣除10%服务费\n\n"
            f"💡 任何人都可以点击按钮加入游戏！",
            reply_markup=reply_markup
        )
        
        await update.message.reply_text(f"✅ 您已成功加入游戏！当前参与人数：{len(game['players'])}人")
        return
    
    # ===== 加入单挑模式 =====
    # 查找等待中的游戏
    from app.database.card_games import get_waiting_card_game, join_card_game, update_card_game_result
    
    game = get_waiting_card_game(chat_id)
    
    if not game:
        await update.message.reply_text("❌ 当前没有等待中的游戏！")
        return
    
    # 检查是否是创建者自己加入
    if game['creator_id'] == user_emos_id:
        await update.message.reply_text("❌ 您不能加入自己创建的游戏！")
        return
    
    # 检查余额
    from app.database import get_balance
    user_balance = get_balance(user_emos_id)
    if user_balance < game['amount']:
        await update.message.reply_text(f"❌ 您的游戏币不足！当前余额：{user_balance} 🪙")
        return
    
    # 加入游戏
    success = join_card_game(game['game_id'], user_emos_id, user_info.get('username', user.first_name))
    if not success:
        await update.message.reply_text("❌ 加入游戏失败，游戏可能已开始或已结束！")
        return
    
    # 开始游戏，抽牌
    creator_cards = draw_cards()
    opponent_cards = draw_cards()
    
    # 比较大小
    result = compare_hands(creator_cards, opponent_cards)
    
    # 处理结果
    from app.database import update_balance, add_game_record
    
    amount = game['amount']
    creator_name = game['creator_name']
    opponent_name = user_info.get('username', user.first_name)
    
    if result > 0:
        # 创建者赢
        winner_id = game['creator_id']
        win_amount = amount
        service_fee = int(win_amount * 0.1)
        net_win = win_amount - service_fee
        
        # 更新余额
        update_balance(game['creator_id'], net_win)
        update_balance(user_emos_id, -amount)
        
        # 保存结果
        update_card_game_result(game['game_id'], format_hand(creator_cards), format_hand(opponent_cards), winner_id)
        
        # 添加游戏记录
        add_game_record(game['creator_id'], 'cardduel', amount, 'win', net_win, creator_name)
        add_game_record(user_emos_id, 'cardduel', amount, 'lose', -amount, opponent_name)
        
        # 获取最新余额
        creator_balance = get_balance(game['creator_id'])
        opponent_balance = get_balance(user_emos_id)
        
        result_text = (
            f"🃏 扑克牌比大小结果\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 {creator_name}：{format_hand(creator_cards)}\n"
            f"👤 {opponent_name}：{format_hand(opponent_cards)}\n\n"
            f"🎉 {creator_name} 获胜！\n\n"
            f"💰 {creator_name}：\n"
            f"  赢得：{win_amount} 🪙\n"
            f"  服务费：{service_fee} 🪙\n"
            f"  实际获得：{net_win} 🪙\n"
            f"  当前余额：{creator_balance} 🪙\n\n"
            f"💸 {opponent_name}：\n"
            f"  失去：{amount} 🪙\n"
            f"  当前余额：{opponent_balance} 🪙"
        )
        
    elif result < 0:
        # 挑战者赢
        winner_id = user_emos_id
        win_amount = amount
        service_fee = int(win_amount * 0.1)
        net_win = win_amount - service_fee
        
        # 更新余额
        update_balance(user_emos_id, net_win)
        update_balance(game['creator_id'], -amount)
        
        # 保存结果
        update_card_game_result(game['game_id'], format_hand(creator_cards), format_hand(opponent_cards), winner_id)
        
        # 添加游戏记录
        add_game_record(user_emos_id, 'cardduel', amount, 'win', net_win, opponent_name)
        add_game_record(game['creator_id'], 'cardduel', amount, 'lose', -amount, creator_name)
        
        # 获取最新余额
        creator_balance = get_balance(game['creator_id'])
        opponent_balance = get_balance(user_emos_id)
        
        result_text = (
            f"🃏 扑克牌比大小结果\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 {creator_name}：{format_hand(creator_cards)}\n"
            f"👤 {opponent_name}：{format_hand(opponent_cards)}\n\n"
            f"🎉 {opponent_name} 获胜！\n\n"
            f"💰 {opponent_name}：\n"
            f"  赢得：{win_amount} 🪙\n"
            f"  服务费：{service_fee} 🪙\n"
            f"  实际获得：{net_win} 🪙\n"
            f"  当前余额：{opponent_balance} 🪙\n\n"
            f"💸 {creator_name}：\n"
            f"  失去：{amount} 🪙\n"
            f"  当前余额：{creator_balance} 🪙"
        )
        
    else:
        # 平局
        winner_id = None
        
        # 保存结果
        update_card_game_result(game['game_id'], format_hand(creator_cards), format_hand(opponent_cards), winner_id)
        
        # 添加游戏记录
        add_game_record(game['creator_id'], 'cardduel', amount, 'draw', 0, creator_name)
        add_game_record(user_emos_id, 'cardduel', amount, 'draw', 0, opponent_name)
        
        # 获取最新余额
        creator_balance = get_balance(game['creator_id'])
        opponent_balance = get_balance(user_emos_id)
        
        result_text = (
            f"🃏 扑克牌比大小结果\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 {creator_name}：{format_hand(creator_cards)}\n"
            f"👤 {opponent_name}：{format_hand(opponent_cards)}\n\n"
            f"🤝 平局！\n\n"
            f"👤 {creator_name} 当前余额：{creator_balance} 🪙\n"
            f"👤 {opponent_name} 当前余额：{opponent_balance} 🪙"
        )
    
    await update.message.reply_text(result_text)

async def cardduel_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理扑克牌游戏的按钮回调"""
    query = update.callback_query
    user = query.from_user
    data = query.data
    
    # 检查用户是否已登录
    from app.config import user_tokens
    if user.id not in user_tokens:
        await query.answer("请先使用 /start 命令登录！", show_alert=True)
        return
    
    # 获取用户ID
    user_info = user_tokens[user.id]
    user_emos_id = user_info.get('user_id', str(user.id))
    
    if data.startswith("join_card_duel_"):
        # ===== 单挑模式加入 =====
        game_id = data.replace("join_card_duel_", "")
        
        # 获取游戏信息
        from app.database.card_games import get_card_game, join_card_game, update_card_game_result
        game = get_card_game(game_id)
        
        if not game:
            await query.answer("游戏不存在或已结束！", show_alert=True)
            return
        
        if game['status'] != 'waiting':
            await query.answer("游戏已经开始或已结束！", show_alert=True)
            return
        
        # 检查是否是创建者自己加入
        if game['creator_id'] == user_emos_id:
            await query.answer("您不能加入自己创建的游戏！", show_alert=True)
            return
        
        # 检查余额
        from app.database import get_balance
        user_balance = get_balance(user_emos_id)
        if user_balance < game['amount']:
            await query.answer(f"游戏币不足！当前余额：{user_balance} 🪙", show_alert=True)
            return
        
        # 加入游戏
        success = join_card_game(game_id, user_emos_id, user_info.get('username', user.first_name))
        if not success:
            await query.answer("加入游戏失败！", show_alert=True)
            return
        
        await query.answer("加入成功！正在发牌...")
        
        # 开始游戏，抽牌
        creator_card = draw_card()
        opponent_card = draw_card()
        
        # 比较大小
        result = compare_cards(creator_card, opponent_card)
        
        # 处理结果
        from app.database import update_balance, add_game_record
        
        amount = game['amount']
        creator_name = game['creator_name']
        opponent_name = user_info.get('username', user.first_name)
        
        if result > 0:
            # 创建者赢
            winner_id = game['creator_id']
            win_amount = amount
            service_fee = int(win_amount * 0.1)
            net_win = win_amount - service_fee
            
            # 更新余额
            update_balance(game['creator_id'], net_win)
            update_balance(user_emos_id, -amount)
            
            # 保存结果
            update_card_game_result(game_id, format_card(creator_card), format_card(opponent_card), winner_id)
            
            # 添加游戏记录
            add_game_record(game['creator_id'], 'cardduel', amount, 'win', net_win, creator_name)
            add_game_record(user_emos_id, 'cardduel', amount, 'lose', -amount, opponent_name)
            
            # 获取最新余额
            creator_balance = get_balance(game['creator_id'])
            opponent_balance = get_balance(user_emos_id)
            
            result_text = (
                f"🃏 扑克牌比大小结果\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 {creator_name}：{format_card(creator_card)}\n"
                f"👤 {opponent_name}：{format_card(opponent_card)}\n\n"
                f"🎉 {creator_name} 获胜！\n\n"
                f"💰 {creator_name}：\n"
                f"  赢得：{win_amount} 🪙\n"
                f"  服务费：{service_fee} 🪙\n"
                f"  实际获得：{net_win} 🪙\n"
                f"  当前余额：{creator_balance} 🪙\n\n"
                f"💸 {opponent_name}：\n"
                f"  失去：{amount} 🪙\n"
                f"  当前余额：{opponent_balance} 🪙"
            )
            
        elif result < 0:
            # 挑战者赢
            winner_id = user_emos_id
            win_amount = amount
            service_fee = int(win_amount * 0.1)
            net_win = win_amount - service_fee
            
            # 更新余额
            update_balance(user_emos_id, net_win)
            update_balance(game['creator_id'], -amount)
            
            # 保存结果
            update_card_game_result(game_id, format_card(creator_card), format_card(opponent_card), winner_id)
            
            # 添加游戏记录
            add_game_record(user_emos_id, 'cardduel', amount, 'win', net_win, opponent_name)
            add_game_record(game['creator_id'], 'cardduel', amount, 'lose', -amount, creator_name)
            
            # 获取最新余额
            creator_balance = get_balance(game['creator_id'])
            opponent_balance = get_balance(user_emos_id)
            
            result_text = (
                f"🃏 扑克牌比大小结果\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 {creator_name}：{format_card(creator_card)}\n"
                f"👤 {opponent_name}：{format_card(opponent_card)}\n\n"
                f"🎉 {opponent_name} 获胜！\n\n"
                f"💰 {opponent_name}：\n"
                f"  赢得：{win_amount} 🪙\n"
                f"  服务费：{service_fee} 🪙\n"
                f"  实际获得：{net_win} 🪙\n"
                f"  当前余额：{opponent_balance} 🪙\n\n"
                f"💸 {creator_name}：\n"
                f"  失去：{amount} 🪙\n"
                f"  当前余额：{creator_balance} 🪙"
            )
            
        else:
            # 平局
            winner_id = None
            
            # 保存结果
            update_card_game_result(game_id, format_card(creator_card), format_card(opponent_card), winner_id)
            
            # 添加游戏记录
            add_game_record(game['creator_id'], 'cardduel', amount, 'draw', 0, creator_name)
            add_game_record(user_emos_id, 'cardduel', amount, 'draw', 0, opponent_name)
            
            # 获取最新余额
            creator_balance = get_balance(game['creator_id'])
            opponent_balance = get_balance(user_emos_id)
            
            result_text = (
                f"🃏 扑克牌比大小结果\n"
                f"━━━━━━━━━━━━━━━━━━\n\n"
                f"👤 {creator_name}：{format_card(creator_card)}\n"
                f"👤 {opponent_name}：{format_card(opponent_card)}\n\n"
                f"🤝 平局！\n\n"
                f"👤 {creator_name} 当前余额：{creator_balance} 🪙\n"
                f"👤 {opponent_name} 当前余额：{opponent_balance} 🪙"
            )
        
        await query.edit_message_text(result_text)
    
    elif data.startswith("join_card_group_"):
        # ===== 群战模式加入 =====
        chat_id = int(data.replace("join_card_group_", ""))
        
        if chat_id not in group_card_games:
            await query.answer("游戏不存在或已结束！", show_alert=True)
            return
        
        game = group_card_games[chat_id]
        
        # 检查是否已加入
        if user.id in game['players']:
            await query.answer("您已经加入了这个游戏！", show_alert=True)
            return
        
        # 检查余额
        from app.database import get_balance
        user_balance = get_balance(user_emos_id)
        if user_balance < game['amount']:
            await query.answer(f"游戏币不足！当前余额：{user_balance} 🪙", show_alert=True)
            return
        
        # 加入游戏
        game['players'][user.id] = {
            'emos_id': user_emos_id,
            'name': user_info.get('username', user.first_name),
            'card': None
        }
        
        await query.answer(f"加入成功！当前参与人数：{len(game['players'])}人")
        
        # 更新消息
        remaining_time = 60 - int((datetime.now() - game['start_time']).total_seconds())
        if remaining_time < 0:
            remaining_time = 0
        
        keyboard = [[InlineKeyboardButton("🎮 加入游戏", callback_data=f"join_card_group_{chat_id}")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await game['message'].edit_text(
            f"🃏 扑克牌比大小 - 群战模式\n"
            f"━━━━━━━━━━━━━━━━━━\n\n"
            f"👤 创建者：{game['creator_name']}\n"
            f"💰 下注金额：{game['amount']} 🪙\n"
            f"⏱️ 开始时间：{remaining_time}秒后自动开始\n"
            f"👥 当前参与：{len(game['players'])}人\n\n"
            f"📋 游戏规则：\n"
            f"  • 所有人各抽一张牌比大小\n"
            f"  • A最大，2最小\n"
            f"  • 点数相同比花色：♠️>♥️>♦️>♣️\n"
            f"  • 赢家获得所有下注金额\n"
            f"  • 赢家扣除10%服务费\n\n"
            f"💡 任何人都可以点击按钮加入游戏！",
            reply_markup=reply_markup
        )
