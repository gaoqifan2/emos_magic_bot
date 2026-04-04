"""
游戏规则模块
显示所有游戏的规则说明
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from utils.http_client import http_client
from utils.http_client import http_client

# 游戏规则字典
game_rules = {
    'guess': """
🎲 猜大小游戏 /guess
• 私聊：/guess <金额> <大/小>
• 群聊：回复消息 + /guess <金额> <大/小>
• 规则：4-6为大，1-3为小
• 赔率：1:1（扣除10%服务费）
""",
    'slot': """
🎰 老虎机游戏 /slot
• 私聊：/slot <金额>
• 规则：3个相同图案即中奖
• 赔率：
  - 三个BAR：5倍
  - 三个7️⃣：4倍
  - 三个🍇：3倍
  - 三个🍒：2倍
  - 其他三个相同：1倍
  - 7️⃣-BAR-7️⃣：3倍 + 奖池
  - 两个相同：0.5倍
• 抽水规则：
  - 中奖：扣除15%（10%服务器，5%奖池）
  - 奖池满：扣除10%（全部服务器）
  - 输：10%进入奖池
• 奖池规则：
  - 最高：500 🪙
  - 每日衰减：10%
  - 触发7️⃣-BAR-7️⃣组合获得奖池
""",
    'blackjack': """
🃏 21点游戏 /blackjack
• 私聊：/blackjack <金额>
• 规则：点数接近21点，超过21点爆牌
• 赔率：1:1（黑杰克1.5:1）
""",
    'gameshoot': """
✊ 猜拳游戏 /gameshoot
• 私聊：/gameshoot <金额>
• 群聊：回复消息 + /gameshoot <金额>
• 规则：石头剪刀布
• 赔率：1:1
• 税收：
  - 赢家：扣除10%服务费
  - 平局：双方各扣5%服务费
  - 输家：无额外税收
""",
    'rob': """
🎭 打劫游戏 /rob
• 群聊：回复消息 + /rob <金额>
• 规则：成功率50%
• 成功：抢到金额（扣除10%税）
• 失败：损失输入金额
• 限制：每天最多3次，金额10-10000
""",
    'createguess': """
👥 群聊猜大小 /createguess
• 创建：/createguess <大/小> <金额>
• 下注：/guess_bet <大/小> <金额>
• 规则：多人下注，系统开奖（三个骰子）
• 最低下注：100游戏币
• 开奖规则：
  - 三个骰子总和 4-10 = 小
  - 三个骰子总和 11-17 = 大
• 赔率计算：
  - 输方总金额扣除 10% 服务费
  - 服务费分配：3%给庄家，7%给平台
  - 剩下的 90% 作为奖池，按赢家下注比例分配
  - 所有计算结果向下取整
  - 庄家获得：3%服务费 + 按比例分得的奖池 + 本金
  - 闲家获得：按比例分得的奖池 + 本金
  - 输家失去：本金
• 特殊情况：
  - 所有人都押输：退还所有人本金
  - 所有人都押赢：退还所有人本金
  - 空盘（无玩家参与）：退还庄家本金，收取 1% 空盘费
• 下注时间：5分钟，结束前30秒截止下注
""",
    'cardduel': """
🃏 扑克牌比大小 /cardduel
• 单挑模式：回复对方消息 + /cardduel <金额>
• 群战模式：/cardduel <金额>（任何人可加入）
• 加入：/join 或点击按钮
• 群战规则：
  - 1分钟后自动开始游戏
  - 至少需要2人参与
  - 所有人各抽4张牌比大小
  - 赢家获得所有下注金额
• 牌型大小：炸弹 > 葫芦 > 两对 > 一对 > 高牌
• 点数大小：3 < 4 < 5 < 6 < 7 < 8 < 9 < 10 < J < Q < K < A < 2
• 花色大小：♠️ > ♥️ > ♦️ > ♣️
• 赔率：
  - 单挑：1:1
  - 群战：赢家通吃所有下注
• 税收：赢家扣除10%服务费
""",
    'niuniu': """
🐮 牛牛游戏 /niuniu
• 单挑模式：回复对方消息 + /niuniu <金额>
• 群战模式：/niuniu <金额>（任何人可加入）
• 加入：/join 或点击按钮
• 群战规则：
  - 1分钟后自动开始游戏
  - 至少需要2人参与
  - 所有人各抽5张牌
  - 赢家获得所有下注金额
• 牌型大小：五小牛 > 炸弹牛 > 五花牛 > 四花牛 > 牛牛 > 牛9-牛1 > 无牛
• 点数计算：A=1, 2-10=对应点数, JQK=10
• 赔率：
  - 五小牛：5倍
  - 炸弹牛：4倍
  - 五花牛：3倍
  - 牛牛：2倍
  - 牛9-牛7：1.5倍
  - 牛6-牛4：1倍
  - 牛3-牛1：0.5倍
  - 无牛：0倍
• 税收：赢家扣除5%服务费
"""
}

async def rules_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示游戏规则菜单"""
    # 创建游戏规则菜单
    keyboard = [
        [InlineKeyboardButton("🎲 猜大小", callback_data='rules_guess'),
         InlineKeyboardButton("🎰 老虎机", callback_data='rules_slot')],
        [InlineKeyboardButton("🃏 21点", callback_data='rules_blackjack'),
         InlineKeyboardButton("✊ 猜拳", callback_data='rules_gameshoot')],
        [InlineKeyboardButton("🎭 打劫", callback_data='rules_rob'),
         InlineKeyboardButton("👥 群聊庄家", callback_data='rules_createguess')],
        [InlineKeyboardButton("🃏 扑克牌比大小", callback_data='rules_cardduel'),
         InlineKeyboardButton("🐮 牛牛", callback_data='rules_niuniu')],
        [InlineKeyboardButton("📋 所有规则", callback_data='rules_all')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("🎮 选择游戏查看规则", reply_markup=reply_markup)

async def menu_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """显示游戏菜单"""
    # 创建游戏菜单
    keyboard = [
        [InlineKeyboardButton("🎲 猜大小", callback_data='game_guess'),
         InlineKeyboardButton("🎰 老虎机", callback_data='game_slot')],
        [InlineKeyboardButton("🃏 21点", callback_data='game_blackjack'),
         InlineKeyboardButton("✊ 猜拳", callback_data='game_gameshoot')],
        [InlineKeyboardButton("🎭 打劫", callback_data='game_rob'),
         InlineKeyboardButton("👥 群聊庄家", callback_data='game_createguess')],
        [InlineKeyboardButton("🃏 扑克牌比大小", callback_data='game_cardduel'),
         InlineKeyboardButton("🐮 牛牛", callback_data='game_niuniu')],
        [InlineKeyboardButton("📋 游戏规则", callback_data='rules_menu')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text("🎮 选择游戏开始玩", reply_markup=reply_markup)

async def rules_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理游戏规则回调"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    
    if data == 'rules_all':
        # 显示所有规则
        rules_text = """
🎮 游戏规则说明
━━━━━━━━━━━━━━━━━━

"""
        for game, rule in game_rules.items():
            rules_text += rule + "\n"
        
        rules_text += """
━━━━━━━━━━━━━━━━━━
💡 使用 /balance 查看余额
💡 使用 /help 查看所有命令
"""
        
        await query.edit_message_text(rules_text)
    elif data.startswith('rules_'):
        # 显示指定游戏的规则
        game = data.split('_')[1]
        if game in game_rules:
            await query.edit_message_text(game_rules[game])
        else:
            await query.edit_message_text("❌ 游戏规则不存在")
    elif data == 'rules_menu':
        # 显示规则菜单
        keyboard = [
            [InlineKeyboardButton("🎲 猜大小", callback_data='rules_guess'),
             InlineKeyboardButton("🎰 老虎机", callback_data='rules_slot')],
            [InlineKeyboardButton("🃏 21点", callback_data='rules_blackjack'),
             InlineKeyboardButton("✊ 猜拳", callback_data='rules_gameshoot')],
            [InlineKeyboardButton("🎭 打劫", callback_data='rules_rob'),
             InlineKeyboardButton("👥 群聊庄家", callback_data='rules_createguess')],
            [InlineKeyboardButton("🃏 扑克牌比大小", callback_data='rules_cardduel'),
             InlineKeyboardButton("🐮 牛牛", callback_data='rules_niuniu')],
            [InlineKeyboardButton("📋 所有规则", callback_data='rules_all')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text("🎮 选择游戏查看规则", reply_markup=reply_markup)
    elif data.startswith('game_'):
        # 处理游戏选择
        game = data.split('_')[1]
        game_commands = {
            'guess': '/guess <金额> <大/小>',
            'slot': '/slot <金额>',
            'blackjack': '/blackjack <金额>',
            'gameshoot': '/gameshoot <金额>',
            'rob': '/rob <金额>',
            'createguess': '/createguess <金额> <大/小>',
            'cardduel': '/cardduel <金额>',
            'niuniu': '/niuniu <金额>'
        }
        
        if game in game_commands:
            command = game_commands[game]
            await query.edit_message_text(f"🎮 游戏命令：{command}\n\n请在聊天框中输入命令开始游戏")
        else:
            await query.edit_message_text("❌ 游戏不存在")
