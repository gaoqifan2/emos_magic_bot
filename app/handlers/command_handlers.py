from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from app.database import get_balance, update_balance, add_user, add_game_record, ensure_user_exists, get_last_checkin, update_checkin_time
from app.database.jackpot import get_jackpot_pool, add_to_jackpot_pool, reset_jackpot_pool, record_jackpot_win
from app.database.user_score import get_user_score, add_user_score, reset_user_score, get_user_level
from app.database.user_streaks import get_user_streak, update_user_streak, add_user_tag
from app.utils.helpers import check_balance, process_daily_checkin
from app.config import BOT_USERNAME, user_tokens, save_token_to_db, get_user_info, Config, API_BASE_URL, DEFAULT_GROUP_CHAT_ID
import logging
import httpx
import random

# 21点游戏牌相关定义
SUITS = ['♠️', '♥️', '♣️', '♦️']
VALUES = ['A', '2', '3', '4', '5', '6', '7', '8', '9', '10', 'J', 'Q', 'K']

def get_blackjack_card():
    """获取一张21点游戏的牌"""
    suit = random.choice(SUITS)
    value_idx = random.randint(0, 12)
    value = VALUES[value_idx]
    if value == 'A':
        point = 1
    elif value in ['J', 'Q', 'K']:
        point = 10
    else:
        point = int(value)
    return {'value': value, 'point': point, 'suit': suit}

def format_blackjack_card(card):
    """格式化显示一张21点游戏的牌"""
    return f"{card['suit']}{card['value']}"

def format_blackjack_cards(cards):
    """格式化显示多张21点游戏的牌"""
    return ' '.join([format_blackjack_card(card) for card in cards])

def calculate_blackjack_score(cards):
    """计算21点游戏的牌点数"""
    score = sum([card['point'] for card in cards])
    has_ace = any([card['value'] == 'A' for card in cards])
    if has_ace and score + 10 <= 21:
        score += 10
    return score

# 配置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)


async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /start 命令"""
    user = update.effective_user
    user_id = user.id
    
    logger.info(f"用户 {user_id} 发送 /start 命令")
    
    # 检查是否是CallbackQuery类型的更新
    if update.callback_query:
        # 通过按钮回调调用，直接显示游戏菜单
        logger.info("通过按钮回调调用start_handler，显示游戏菜单")
        # 检查用户是否已登录（是否有token）
        is_logged_in = False
        # 首先检查telegram_id是否在user_tokens中
        if user_id in user_tokens:
            is_logged_in = True
        else:
            # 遍历user_tokens，查找可能的匹配
            for key, info in user_tokens.items():
                if isinstance(info, dict) and (info.get('username') == user.username or info.get('first_name') == user.first_name):
                    is_logged_in = True
                    break
        
        # 创建按钮菜单，根据登录状态决定是否显示授权登录按钮
        if is_logged_in:
            # 已登录，隐藏授权登录按钮
            keyboard = [
                [InlineKeyboardButton("🎮 游戏厅", callback_data='games'),
                 InlineKeyboardButton("💰 余额", callback_data='balance'),
                 InlineKeyboardButton("📅 每日签到", callback_data='daily')],
                [InlineKeyboardButton("💸 充值", callback_data='recharge'),
                 InlineKeyboardButton("💎 提现", callback_data='withdraw'),
                 InlineKeyboardButton("📝 游戏规则", callback_data='help')],
                [InlineKeyboardButton("🔙 返回", callback_data='back')]
            ]
        else:
            # 未登录，显示授权登录按钮
            keyboard = [
                [InlineKeyboardButton("🔐 登录授权", callback_data='login'),
                 InlineKeyboardButton("🎮 游戏厅", callback_data='games'),
                 InlineKeyboardButton("📝 游戏规则", callback_data='help')],
                [InlineKeyboardButton("💰 余额", callback_data='balance'),
                 InlineKeyboardButton("📅 每日签到", callback_data='daily'),
                 InlineKeyboardButton("🔙 返回", callback_data='back')]
            ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 编辑回调消息
        await update.callback_query.edit_message_text(
            "点击下方按钮选择游戏或功能：\n",
            reply_markup=reply_markup
        )
        return
    
    # 正常的Message类型更新
    text = update.message.text
    logger.info(f"完整的start命令文本: {text}")
    
    # 处理登录授权逻辑
    if context.args:
        start_param = context.args[0]
        
        # 处理链接登录请求
        if start_param.startswith('link_'):
            # 解析参数：link_[user_id]-[bot_name]-[operation]
            parts = start_param.split('-', 2)
            if len(parts) >= 2:
                unique_id = parts[0].split('_', 1)[1]  # 获取唯一标识符
                bot_name = parts[1]  # 获取机器人名称
                operation = parts[2] if len(parts) == 3 else None  # 获取操作状态
                
                # 生成授权链接
                # 格式：https://t.me/emospg_bot?start=link_[token]-[bot_username]-[operation]
                # 使用固定的token作为唯一标识符
                unique_id = "e0E446ZE6s"
                if operation:
                    auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_name}-{operation}"
                else:
                    auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_name}"
                
                # 创建授权按钮
                keyboard = [
                    [InlineKeyboardButton("🔐 授权登录", url=auth_link)],
                    [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                await update.message.reply_text(
                    "请点击下方按钮授权登录，以使用完整的游戏功能：\n" 
                    "登录后可以获得更多游戏福利和特权！",
                    reply_markup=reply_markup
                )
                return
    
    # 显示欢迎消息和菜单
    welcome_message = (
        f"欢迎使用 Emos 魔法机器人！\n\n"
        f"我是你的游戏助手，为你提供各种有趣的游戏和功能。\n\n"
        f"点击下方按钮开始探索："
    )
    
    # 创建初始菜单按钮
    keyboard = [
        [InlineKeyboardButton("🎮 游戏厅", callback_data='games'),
         InlineKeyboardButton("💰 余额", callback_data='balance'),
         InlineKeyboardButton("📅 每日签到", callback_data='daily')],
        [InlineKeyboardButton("💸 充值", callback_data='recharge'),
         InlineKeyboardButton("💎 提现", callback_data='withdraw'),
         InlineKeyboardButton("📝 游戏规则", callback_data='help')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    await update.message.reply_text(welcome_message, reply_markup=reply_markup)


async def balance_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理余额查询"""
    user_id = update.effective_user.id
    
    # 检查用户是否已登录
    if user_id not in user_tokens:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否是CallbackQuery类型的更新
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再查看余额：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再查看余额：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 获取用户信息
    user_info = user_tokens[user_id]
    
    # 从 user_info 中获取用户信息
    # 注意：user_info应该是字典格式，包含user_id字段
    if isinstance(user_info, dict):
        user_id_str = user_info.get('user_id', user_id)
        username = user_info.get('username', update.effective_user.username)
    else:
        # 如果是字符串，说明登录不完整，提示用户重新登录
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text("❌ 登录信息不完整，请重新登录！")
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text("❌ 登录信息不完整，请重新登录！")
        return
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id_str,
        'token': user_info if isinstance(user_info, str) else user_info.get('token', ''),
        'username': username,
        'first_name': update.effective_user.first_name,
        'last_name': update.effective_user.last_name,
        'telegram_id': user_id
    }
    add_user(user_id_str, user_data)
    
    # 获取余额
    balance = get_balance(user_id_str)
    
    # 获取用户积分和等级
    score = get_user_score(user_id_str)
    level = get_user_level(score)
    
    # 获取连续签到天数
    streak = get_user_streak(user_id_str, user_id)
    
    # 构建余额消息
    balance_message = (
        f"💰 您的余额\n\n"
        f"游戏币：{balance} 🪙\n"
        f"积分：{score} 分\n"
        f"等级：{level} 级\n"
        f"连续签到：{streak} 天\n\n"
        f"💡 每日签到可获得游戏币和积分！\n"
        f"💡 参与游戏可以获得更多积分！"
    )
    
    # 创建返回按钮
    keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 检查是否是CallbackQuery类型的更新
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            balance_message,
            reply_markup=reply_markup
        )
    elif hasattr(update, 'message') and update.message:
        await update.message.reply_text(
            balance_message,
            reply_markup=reply_markup
        )


async def guess_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理 /guess 命令"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否是CallbackQuery类型的更新
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_info 中获取用户信息
    # 注意：user_info可能是字符串（token）或字典
    if isinstance(user_info, dict):
        user_id = user_info.get('user_id', telegram_id)
        token = user_info.get('token', '')
        username = user_info.get('username', user.username)
    else:
        # 如果是字符串，使用telegram_id作为user_id
        user_id = telegram_id
        token = user_info
        username = user.username
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id,
        'token': token,
        'username': username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'telegram_id': telegram_id
    }
    add_user(user_id, user_data)
    
    # 新用户初始余额为0，无需额外添加
    
    # 检查是否有参数
    if len(context.args) == 2:
        # 直接处理参数
        await process_guess(update, context, context.args[0], context.args[1])
    else:
        # 没有参数或参数不全，提示完整指令
        await update.message.reply_text(
            "🎲 猜大小游戏\n\n"
            "请输入完整命令，例如：\n"
            "`/guess 10 大` 或 `/guess 10 小`\n\n"
            "直接复制：`/guess 10 大`",
            parse_mode='Markdown'
        )


async def process_guess(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: str, guess: str):
    """处理猜大小游戏的逻辑"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "您还未绑定账号，请先绑定后再玩游戏：\n" 
            "绑定后可以获得更多游戏功能和福利！",
            reply_markup=reply_markup
        )
        return
    
    # 从 user_info 中获取用户信息
    if isinstance(user_info, dict):
        user_id_str = user_info.get('user_id', telegram_id)
        username = user_info.get('username', '用户')
    else:
        # 如果是字符串，使用telegram_id作为user_id
        user_id_str = telegram_id
        username = '用户'
    
    # 获取数据库中的用户ID（自增ID）
    # 优先使用 telegram_id 查询，因为这才是最可靠的标识
    local_user_id = None
    from app.database import get_db_connection
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                result = cursor.fetchone()
                if result:
                    local_user_id = result['id'] if isinstance(result, dict) else result[0]
        finally:
            conn.close()
    
    # 如果找不到，尝试使用 user_id 查询
    if not local_user_id:
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id_str,))
                    result = cursor.fetchone()
                    if result:
                        local_user_id = result['id'] if isinstance(result, dict) else result[0]
            finally:
                conn.close()
    
    # 检查金额是否有效
    try:
        amount = int(amount)
        if amount <= 0:
            await update.message.reply_text("下注金额必须大于0")
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字")
        return
    
    # 检查猜测是否有效
    if guess not in ['大', '小']:
        await update.message.reply_text("猜测必须是「大」或「小」")
        return
    
    # 检查余额
    balance = get_balance(user_id_str)
    if balance < amount:
        await update.message.reply_text(f"游戏币不足！当前余额：{balance}")
        return
    
    # 生成随机结果（1-6）
    import random
    dice = random.randint(1, 6)
    
    # 判断大小
    if dice in [1, 2, 3]:
        result = "小"
    else:
        result = "大"
    
    # 计算结果
    if guess == result:
        # 赢了，获得下注金额
        win_amount = amount
        update_balance(user_id_str, win_amount)
        new_balance = get_balance(user_id_str)
        result_message = (
            f"🎮 猜大小游戏结果\n\n"
            f"您选择：{guess}\n"
            f"🎲 骰子点数：{dice} ({result})\n\n"
            f"🎉 恭喜您赢了！\n"
            f"获得：{win_amount} 🪙\n"
            f"当前余额：{new_balance} 🪙"
        )
        # 记录游戏结果
        add_game_record(user_id_str, 'guess', amount, 'win', win_amount, username)
        # 添加积分
        add_user_score(user_id_str, 1)
    else:
        # 输了，扣除下注金额
        update_balance(user_id_str, -amount)
        new_balance = get_balance(user_id_str)
        result_message = (
            f"🎮 猜大小游戏结果\n\n"
            f"您选择：{guess}\n"
            f"🎲 骰子点数：{dice} ({result})\n\n"
            f"😢 很遗憾，您输了！\n"
            f"扣除：{amount} 🪙\n"
            f"当前余额：{new_balance} 🪙"
        )
        # 记录游戏结果
        add_game_record(user_id_str, 'guess', amount, 'lose', -amount, username)
    
    # 发送结果
    await update.message.reply_text(result_message)


async def slot_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理老虎机游戏"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否是CallbackQuery类型的更新
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_info 中获取用户信息
    # 注意：user_info可能是字符串（token）或字典
    if isinstance(user_info, dict):
        user_id = user_info.get('user_id', telegram_id)
        username = user_info.get('username', user.username)
    else:
        # 如果是字符串，使用telegram_id作为user_id
        user_id = telegram_id
        username = user.username
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id,
        'token': user_info if isinstance(user_info, str) else user_info.get('token', ''),
        'username': username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'telegram_id': telegram_id
    }
    add_user(user_id, user_data)
    
    # 检查是否有参数
    if len(context.args) == 1:
        # 直接处理参数
        await process_slot(update, context, context.args[0])
    else:
        # 没有参数，提示完整指令
        await update.message.reply_text(
            "🎰 老虎机游戏\n\n"
            "请输入完整命令，例如：\n"
            "`/slot 10`\n\n"
            "直接复制：`/slot 10`",
            parse_mode='Markdown'
        )


async def process_slot(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: str):
    """处理老虎机游戏的逻辑"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "您还未绑定账号，请先绑定后再玩游戏：\n" 
            "绑定后可以获得更多游戏功能和福利！",
            reply_markup=reply_markup
        )
        return
    
    # 从 user_info 中获取用户信息
    if isinstance(user_info, dict):
        user_id_str = user_info.get('user_id', telegram_id)
        username = user_info.get('username', '用户')
    else:
        # 如果是字符串，使用telegram_id作为user_id
        user_id_str = telegram_id
        username = '用户'
    
    # 获取数据库中的用户ID（自增ID）
    # 优先使用 telegram_id 查询，因为这才是最可靠的标识
    local_user_id = None
    from app.database import get_db_connection
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                result = cursor.fetchone()
                if result:
                    local_user_id = result['id'] if isinstance(result, dict) else result[0]
        finally:
            conn.close()
    
    # 如果找不到，尝试使用 user_id 查询
    if not local_user_id:
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id_str,))
                    result = cursor.fetchone()
                    if result:
                        local_user_id = result['id'] if isinstance(result, dict) else result[0]
            finally:
                conn.close()
    
    # 检查金额是否有效
    try:
        amount = int(amount)
        if amount <= 0:
            await update.message.reply_text("下注金额必须大于0")
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字")
        return
    
    # 检查余额
    balance = get_balance(user_id_str)
    if balance < amount:
        await update.message.reply_text(f"游戏币不足！当前余额：{balance}")
        return
    
    # 使用Telegram官方的老虎机功能
    # 发送老虎机消息
    dice_message = await update.message.reply_dice(emoji="🎰")
    
    # 等待老虎机结果
    import asyncio
    await asyncio.sleep(3)  # 等待3秒让老虎机完全停止
    
    # 获取老虎机结果
    dice_value = dice_message.dice.value
    
    # 根据老虎机结果计算中奖情况
    # Telegram的老虎机返回值：1-64，不同值代表不同的组合
    # 使用位运算映射到三个槽位的图标
    is_win = False
    win_amount = -amount  # 默认输
    result = ""
    reels = ["🍇", "🍇", "🍇"]  # 默认值，防止索引错误
    
    # 图标映射 - 根据用户反馈调整
    # 正确的图标顺序：BAR、葡萄、柠檬、7
    icons = ["BAR", "🍇", "🍋", "7️⃣"]
    
    # 正常情况：使用位运算计算三个槽位的图标
    value = dice_value - 1
    
    # 计算三个槽位的图标索引
    left_icon = icons[((value) & 3) % 4]
    right_icon = icons[((value >> 2) & 3) % 4]
    center_icon = icons[((value >> 4) & 3) % 4]
    
    reels = [left_icon, right_icon, center_icon]
    
    # 检查是否中奖
    if left_icon == center_icon == right_icon:
        is_win = True
        win_amount = amount * 2  # 三个相同：固定2倍
        result = f"{left_icon} {right_icon} {center_icon} - 三个相同！赔率 2 倍！"
        # 抽水10%
        if amount > 0:
            from app.database.jackpot import add_to_jackpot_pool
            add_to_jackpot_pool(amount * 0.05)  # 5%进入奖池
            # 5%给服务器利润（通过其他方式处理）
    elif (left_icon == "7️⃣" and right_icon == "BAR" and center_icon == "7️⃣"):
        # 特殊组合：7-BAR-7
        is_win = True
        win_amount = amount * 5  # JACKPOT赔率：5倍
        result = f"{left_icon} {right_icon} {center_icon} - JACKPOT大奖！赔率 5 倍！"
        # 抽水10%
        if amount > 0:
            from app.database.jackpot import add_to_jackpot_pool
            add_to_jackpot_pool(amount * 0.05)  # 5%进入奖池
            # 5%给服务器利润（通过其他方式处理）
    elif (left_icon == right_icon) or (left_icon == center_icon) or (right_icon == center_icon):
        # 两个相同
        is_win = True
        win_amount = amount * 0.4  # 两个相同：0.4倍
        result = f"{left_icon} {right_icon} {center_icon} - 两个相同！赔率 0.4 倍！"
        # 抽水10%
        if amount > 0:
            from app.database.jackpot import add_to_jackpot_pool
            add_to_jackpot_pool(amount * 0.05)  # 5%进入奖池
            # 5%给服务器利润（通过其他方式处理）
    else:
        # 全不同
        result = f"{left_icon} {right_icon} {center_icon} - 全不同！"
        # 输了，向奖池添加少量金额
        from app.database.jackpot import add_to_jackpot_pool
        add_to_jackpot_pool(amount * 0.1)  # 每次下注的10%进入奖池
    
    # 处理余额更新
    if is_win and win_amount > 0:
        # 处理JACKPOT奖池
        if (left_icon == "7️⃣" and center_icon == "BAR" and right_icon == "7️⃣"):
            # 从奖池中扣除JACKPOT金额
            from app.database.jackpot import get_jackpot_pool, set_jackpot_pool
            jackpot_amount = get_jackpot_pool()
            if jackpot_amount > 0:
                # 奖池金额作为额外奖励
                jackpot_bonus = min(jackpot_amount, amount * 5)  # 最多额外5倍
                win_amount += jackpot_bonus
                set_jackpot_pool(jackpot_amount - jackpot_bonus)  # 从奖池中扣除
                result += f"\n🎊 奖池奖励：{int(jackpot_bonus)} 🪙"
        
        update_balance(user_id_str, win_amount)
        new_balance = get_balance(user_id_str)
        
        # 获取当前奖池金额
        from app.database.jackpot import get_jackpot_pool
        jackpot_amount = get_jackpot_pool()
        
        result_message = (
            f"🎰 老虎机游戏结果\n\n"
            f"{reels[0]} {reels[1]} {reels[2]}\n\n"
            f"{result}\n"
            f"获得：{int(win_amount)} 🪙\n"
            f"当前余额：{new_balance} 🪙\n"
            f"🎊 当前奖池：{int(jackpot_amount)} 🪙\n\n"
            f"🎮 游戏规则：\n"
            f"  - 两个相同：赢0.4倍（抽水10%）\n"
            f"  - 三个相同：赢2倍（抽水10%）\n"
            f"  - 7️⃣-BAR-7️⃣：触发Jackpot大奖！5倍 + 奖池\n"
            f"  - 全不同：输\n\n"
            f"💰 抽水规则：\n"
            f"  - 所有中奖情况都扣除10%\n"
            f"  - 5%给服务器利润，5%注入Jackpot奖池"
        )
        # 记录游戏结果
        add_game_record(user_id_str, 'slot', amount, 'win', int(win_amount), username)
        # 添加积分
        add_user_score(user_id_str, 2)
    else:
        # 输了
        update_balance(user_id_str, -amount)
        
        new_balance = get_balance(user_id_str)
        
        # 获取当前奖池金额
        from app.database.jackpot import get_jackpot_pool
        jackpot_amount = get_jackpot_pool()
        
        result_message = (
            f"🎰 老虎机游戏结果\n\n"
            f"{reels[0]} {reels[1]} {reels[2]}\n\n"
            f"{result}\n"
            f"扣除：{amount} 🪙\n"
            f"当前余额：{new_balance} 🪙\n"
            f"🎊 当前奖池：{int(jackpot_amount)} 🪙\n\n"
            f"🎮 游戏规则：\n"
            f"  - 两个相同：赢0.4倍（抽水10%）\n"
            f"  - 三个相同：赢2倍（抽水10%）\n"
            f"  - 7️⃣-BAR-7️⃣：触发Jackpot大奖！5倍 + 奖池\n"
            f"  - 全不同：输\n\n"
            f"💰 抽水规则：\n"
            f"  - 所有中奖情况都扣除10%\n"
            f"  - 5%给服务器利润，5%注入Jackpot奖池"
        )
        # 记录游戏结果
        add_game_record(user_id_str, 'slot', amount, 'lose', 0, username)
        # 添加积分
        add_user_score(user_id_str, 1)
    
    # 发送结果消息
    await update.message.reply_text(result_message)


async def blackjack_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理21点游戏"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否是CallbackQuery类型的更新
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再玩游戏：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 从 user_info 中获取用户信息
    # 注意：user_info可能是字符串（token）或字典
    if isinstance(user_info, dict):
        user_id = user_info.get('user_id', telegram_id)
        username = user_info.get('username', user.username)
    else:
        # 如果是字符串，使用telegram_id作为user_id
        user_id = telegram_id
        username = user.username
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id,
        'token': user_info if isinstance(user_info, str) else user_info.get('token', ''),
        'username': username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'telegram_id': telegram_id
    }
    add_user(user_id, user_data)
    
    # 检查是否有参数
    if len(context.args) == 1:
        # 直接处理参数
        await process_blackjack(update, context, context.args[0])
    else:
        # 提示用户使用完整指令
        await update.message.reply_text(
            "🃏 21点游戏\n\n"
            "请输入完整命令，例如：`/blackjack 10`\n"
            "输入后游戏将自动开始\n\n"
            "直接复制：`/blackjack 10`",
            parse_mode='Markdown'
        )


async def process_blackjack(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: str):
    """处理21点游戏的逻辑"""
    user = update.effective_user
    telegram_id = user.id
    
    # 检查用户是否已绑定 token
    user_info = None
    # 只基于 telegram_id 进行用户识别
    if telegram_id in user_tokens:
        user_info = user_tokens[telegram_id]
    
    if not user_info:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        await update.message.reply_text(
            "您还未绑定账号，请先绑定后再玩游戏：\n" 
            "绑定后可以获得更多游戏功能和福利！",
            reply_markup=reply_markup
        )
        return
    
    # 从 user_info 中获取用户信息
    if isinstance(user_info, dict):
        user_id_str = user_info.get('user_id', telegram_id)
        username = user_info.get('username', '用户')
    else:
        # 如果是字符串，使用telegram_id作为user_id
        user_id_str = telegram_id
        username = '用户'
    
    # 获取数据库中的用户ID（自增ID）
    # 优先使用 telegram_id 查询，因为这才是最可靠的标识
    local_user_id = None
    from app.database import get_db_connection
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT id FROM users WHERE telegram_id = %s", (telegram_id,))
                result = cursor.fetchone()
                if result:
                    local_user_id = result['id'] if isinstance(result, dict) else result[0]
        finally:
            conn.close()
    
    # 如果找不到，尝试使用 user_id 查询
    if not local_user_id:
        conn = get_db_connection()
        if conn:
            try:
                with conn.cursor() as cursor:
                    cursor.execute("SELECT id FROM users WHERE id = %s", (user_id_str,))
                    result = cursor.fetchone()
                    if result:
                        local_user_id = result['id'] if isinstance(result, dict) else result[0]
            finally:
                conn.close()
    
    # 检查金额是否有效
    try:
        amount = int(amount)
        if amount <= 0:
            await update.message.reply_text("下注金额必须大于0")
            return
    except ValueError:
        await update.message.reply_text("请输入有效的数字")
        return
    
    # 检查余额
    balance = get_balance(user_id_str)
    if balance < amount:
        await update.message.reply_text(f"游戏币不足！当前余额：{balance}")
        return
    
    # 发牌
    player_cards = [get_blackjack_card(), get_blackjack_card()]
    dealer_cards = [get_blackjack_card(), get_blackjack_card()]
    
    # 计算点数
    player_score = calculate_blackjack_score(player_cards)
    dealer_score = calculate_blackjack_score(dealer_cards)
    
    # 显示初始状态
    initial_message = (
        f"🎲 21点游戏\n\n"
        f"您的牌：{format_blackjack_cards(player_cards)} (点数：{player_score})\n"
        f"庄家的牌：{format_blackjack_card(dealer_cards[0])} 🂠\n\n"
        f"下注金额：{amount} 🪙\n\n"
        f"请选择："
    )
    
    # 创建按钮
    keyboard = [
        [InlineKeyboardButton("要牌 (hit)", callback_data=f"hit_{amount}"),
         InlineKeyboardButton("停牌 (stand)", callback_data=f"stand_{amount}")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 存储游戏状态到全局字典
    from main import blackjack_games
    import time
    user_id_key = update.effective_user.id
    blackjack_games[user_id_key] = {
        'player_cards': player_cards,
        'dealer_cards': dealer_cards,
        'amount': amount,
        'user_id': user_id_str,
        'local_user_id': local_user_id,
        'username': username,
        'timestamp': time.time()
    }
    
    await update.message.reply_text(initial_message, reply_markup=reply_markup)


async def hit_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理要牌"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith('hit_'):
        amount = int(data.split('_')[1])
        
        # 获取游戏状态（使用全局字典）
        from main import blackjack_games
        user_id_key = update.effective_user.id
        if user_id_key not in blackjack_games:
            await query.edit_message_text("游戏已结束，请重新开始")
            return
        
        game = blackjack_games[user_id_key]
        player_cards = game['player_cards']
        dealer_cards = game['dealer_cards']
        user_id = game['user_id']
        local_user_id = game['local_user_id']
        username = game.get('username', '用户')
        
        # 要牌
        player_cards.append(get_blackjack_card())
        
        # 更新游戏状态到全局字典
        blackjack_games[user_id_key]['player_cards'] = player_cards
        
        player_score = calculate_blackjack_score(player_cards)
        dealer_score = calculate_blackjack_score(dealer_cards)
        
        # 检查是否爆牌
        if player_score > 21:
            # 爆牌，输了
            update_balance(user_id, -amount)
            new_balance = get_balance(user_id)
            result_message = (
                f"🎲 21点游戏结果\n\n"
                f"您的牌：{format_blackjack_cards(player_cards)} (点数：{player_score})\n"
                f"庄家的牌：{format_blackjack_cards(dealer_cards)} (点数：{dealer_score})\n\n"
                f"💥 您爆牌了！\n"
                f"扣除：{amount} 🪙\n"
                f"当前余额：{new_balance} 🪙"
            )
            # 记录游戏结果
            from app.database import add_game_record
            add_game_record(user_id, 'blackjack', amount, 'lose', -amount, username)
            await query.edit_message_text(result_message)
            del blackjack_games[user_id_key]
        else:
            # 继续游戏
            message = (
                f"🎲 21点游戏\n\n"
                f"您的牌：{format_blackjack_cards(player_cards)} (点数：{player_score})\n"
                f"庄家的牌：{format_blackjack_card(dealer_cards[0])} 🂠\n\n"
                f"下注金额：{amount} 🪙\n\n"
                f"请选择："
            )
            
            keyboard = [
                [InlineKeyboardButton("要牌 (hit)", callback_data=f"hit_{amount}"),
                 InlineKeyboardButton("停牌 (stand)", callback_data=f"stand_{amount}")]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            await query.edit_message_text(message, reply_markup=reply_markup)


async def stand_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理停牌"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    if data.startswith('stand_'):
        amount = int(data.split('_')[1])
        
        # 获取游戏状态（使用全局字典）
        from main import blackjack_games
        user_id_key = update.effective_user.id
        if user_id_key not in blackjack_games:
            await query.edit_message_text("游戏已结束，请重新开始")
            return
        
        game = blackjack_games[user_id_key]
        player_cards = game['player_cards']
        dealer_cards = game['dealer_cards']
        user_id = game['user_id']
        local_user_id = game['local_user_id']
        username = game.get('username', '用户')
        
        player_score = calculate_blackjack_score(player_cards)
        dealer_score = calculate_blackjack_score(dealer_cards)
        
        # 庄家要牌
        while dealer_score < 17:
            dealer_cards.append(get_blackjack_card())
            dealer_score = calculate_blackjack_score(dealer_cards)
        
        # 比较结果
        if dealer_score > 21 or player_score > dealer_score:
            # 玩家赢
            win_amount = amount
            
            # 处理连胜奖励
            from app.database.user_streaks import get_user_streak, update_user_streak, add_user_tag
            streak = get_user_streak(user_id, 'blackjack')
            new_streak = streak + 1
            update_user_streak(user_id, 'blackjack', new_streak)
            
            # 连胜奖励
            bonus = 0
            title = None
            
            if new_streak == 3:
                bonus = 50
            elif new_streak == 5:
                bonus = 100
            elif new_streak == 7:
                bonus = 200
                title = "点王"
                add_user_tag(user_id, title)
            elif new_streak == 8:
                bonus = 50
                title = "不爆狂人"
                add_user_tag(user_id, title)
            elif new_streak == 9:
                bonus = 50
                title = "牌桌幽灵"
                add_user_tag(user_id, title)
            elif new_streak == 10:
                bonus = 50
                title = "天命之子"
                add_user_tag(user_id, title)
            elif new_streak == 11:
                bonus = 50
                title = "庄家克星"
                add_user_tag(user_id, title)
            elif new_streak == 12:
                bonus = 50
                title = "21点魔"
                add_user_tag(user_id, title)
            elif new_streak == 13:
                bonus = 50
                title = "不灭赌徒"
                add_user_tag(user_id, title)
            elif new_streak == 14:
                bonus = 50
                title = "神之一手"
                add_user_tag(user_id, title)
            elif new_streak >= 15:
                bonus = 50
                title = "不败神话"
                add_user_tag(user_id, title)
            
            # 应用奖励
            if bonus > 0:
                win_amount += bonus
                update_balance(user_id, win_amount)
            else:
                update_balance(user_id, win_amount)
            
            new_balance = get_balance(user_id)
            
            # 构建结果消息
            result_message = (
                f"🎲 21点游戏结果\n\n"
                f"您的牌：{format_blackjack_cards(player_cards)} (点数：{player_score})\n"
                f"庄家的牌：{format_blackjack_cards(dealer_cards)} (点数：{dealer_score})\n\n"
            )
            
            if dealer_score > 21:
                result_message += "🎉 庄家爆牌了！您赢了！\n"
            else:
                result_message += "🎉 您赢了！\n"
            
            result_message += f"获得：{win_amount} 🪙\n"
            if bonus > 0:
                result_message += f"连胜奖励：{bonus} 🪙\n"
            result_message += f"当前余额：{new_balance} 🪙\n"
            result_message += f"当前连胜：{new_streak} 局\n"
            
            if title:
                result_message += f"🏆 获得新头衔：{title}\n"
            
            # 记录游戏结果
            from app.database import add_game_record
            add_game_record(user_id, 'blackjack', amount, 'win', win_amount, username)
            # 添加积分
            from app.database.user_score import add_user_score
            add_user_score(user_id, 3)
        elif player_score < dealer_score:
            # 玩家输
            # 重置连胜
            from app.database.user_streaks import update_user_streak
            update_user_streak(user_id, 'blackjack', 0)
            
            update_balance(user_id, -amount)
            new_balance = get_balance(user_id)
            result_message = (
                f"🎲 21点游戏结果\n\n"
                f"您的牌：{format_blackjack_cards(player_cards)} (点数：{player_score})\n"
                f"庄家的牌：{format_blackjack_cards(dealer_cards)} (点数：{dealer_score})\n\n"
                f"😢 您输了！\n"
                f"扣除：{amount} 🪙\n"
                f"当前余额：{new_balance} 🪙"
            )
            # 记录游戏结果
            from app.database import add_game_record
            add_game_record(user_id, 'blackjack', amount, 'lose', -amount, username)
        else:
            # 平局
            # 平局不影响连胜
            result_message = (
                f"🎲 21点游戏结果\n\n"
                f"您的牌：{format_blackjack_cards(player_cards)} (点数：{player_score})\n"
                f"庄家的牌：{format_blackjack_cards(dealer_cards)} (点数：{dealer_score})\n\n"
                f"🤝 平局！\n"
                f"不扣除游戏币\n"
                f"当前余额：{get_balance(user_id)} 🪙"
            )
            # 记录游戏结果
            from app.database import add_game_record
            add_game_record(user_id, 'blackjack', amount, 'draw', 0, username)
        
        await query.edit_message_text(result_message)
        del blackjack_games[user_id_key]


async def daily_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理每日签到"""
    user = update.effective_user
    user_id = user.id
    
    # 检查用户是否已登录
    if user_id not in user_tokens:
        # 生成授权链接
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data='cancel')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # 检查是否是CallbackQuery类型的更新
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "您还未绑定账号，请先绑定后再签到：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text(
                "您还未绑定账号，请先绑定后再签到：\n" 
                "绑定后可以获得更多游戏功能和福利！",
                reply_markup=reply_markup
            )
        return
    
    # 获取用户信息
    user_info = user_tokens[user_id]
    
    # 从 user_info 中获取用户信息
    # 注意：user_info应该是字典格式，包含user_id字段
    if isinstance(user_info, dict):
        user_id_str = user_info.get('user_id', user_id)
        username = user_info.get('username', user.username)
    else:
        # 如果是字符串，说明登录不完整，提示用户重新登录
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text("❌ 登录信息不完整，请重新登录！")
        elif hasattr(update, 'message') and update.message:
            await update.message.reply_text("❌ 登录信息不完整，请重新登录！")
        return
    
    # 检查用户是否存在，不存在则添加
    user_data = {
        'id': user_id_str,
        'token': user_info if isinstance(user_info, str) else user_info.get('token', ''),
        'username': username,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'telegram_id': user_id
    }
    add_user(user_id_str, user_data)
    
    # 处理签到
    result = process_daily_checkin(user_id_str)
    
    # 构建签到消息
    if result['success']:
        sign_message = (
            f"✅ 签到成功！\n\n"
            f"获得游戏币：{result['reward']} 🪙\n"
            f"连续签到：{result['streak']} 天\n\n"
            f"💡 连续签到天数越多，奖励越丰厚！\n"
            f"💡 每天签到都有奖励哦！"
        )
    else:
        sign_message = (
            f"⏰ 您今天已经签到过了！\n\n"
            f"下次签到时间：{result['next_time']}\n\n"
            f"💡 每天签到都有奖励哦！"
        )
    
    # 创建返回按钮
    keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 检查是否是CallbackQuery类型的更新
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            sign_message,
            reply_markup=reply_markup
        )
    elif hasattr(update, 'message') and update.message:
        await update.message.reply_text(
            sign_message,
            reply_markup=reply_markup
        )


async def help_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理帮助命令"""
    help_message = (
        f"📝 游戏规则\n\n"
        f"🎮 猜大小：\n"
        f"  - 命令：/guess 金额 大/小\n"
        f"  - 规则：猜骰子点数，1-3为小，4-6为大\n"
        f"  - 奖励：猜对获得下注金额\n\n"
        f"🎰 老虎机：\n"
        f"  - 命令：/slot 金额\n"
        f"  - 规则：三个相同符号中奖\n"
        f"  - 奖励：777中JACKPOT（10倍），铃铛中5倍，其他中2倍\n\n"
        f"🎲 21点：\n"
        f"  - 命令：/blackjack 金额\n"
        f"  - 规则：接近21点但不超过21点\n"
        f"  - 奖励：赢了获得下注金额\n\n"
        f"📅 每日签到：\n"
        f"  - 命令：/daily\n"
        f"  - 规则：每天可签到一次\n"
        f"  - 奖励：获得游戏币，连续签到奖励更丰厚\n\n"
        f"💰 余额查询：\n"
        f"  - 命令：/balance\n"
        f"  - 功能：查看游戏币、积分和等级\n\n"
        f"💸 充值：\n"
        f"  - 命令：/recharge\n"
        f"  - 功能：使用萝卜兑换游戏币\n\n"
        f"💎 提现：\n"
        f"  - 命令：/withdraw\n"
        f"  - 功能：将游戏币兑换为萝卜\n\n"
        f"💡 提示：\n"
        f"  - 绑定账号后可以获得更多游戏功能\n"
        f"  - 参与游戏可以获得积分，提升等级\n"
        f"  - 等级越高，游戏奖励越丰厚！"
    )
    
    # 创建返回按钮
    keyboard = [[InlineKeyboardButton("🔙 返回", callback_data='back')]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # 检查是否是CallbackQuery类型的更新
    if hasattr(update, 'callback_query') and update.callback_query:
        await update.callback_query.edit_message_text(
            help_message,
            reply_markup=reply_markup
        )
    elif hasattr(update, 'message') and update.message:
        await update.message.reply_text(
            help_message,
            reply_markup=reply_markup
        )


async def withdraw_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """提现专区"""
    user_id = update.effective_user.id
    user_info = user_tokens.get(user_id)
    token = user_info.get('token') if isinstance(user_info, dict) else user_info
    
    if not token:
        # 生成授权链接，添加操作状态参数
        unique_id = "e0E446ZE6s"
        bot_username = BOT_USERNAME
        # 添加操作状态参数，以便绑定后恢复
        auth_link = f"https://t.me/emospg_bot?start=link_{unique_id}-{bot_username}-withdraw"
        
        # 创建绑定提示按钮
        keyboard = [
            [InlineKeyboardButton("🔐 绑定账号", url=auth_link)],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        if hasattr(update, 'callback_query') and update.callback_query:
            await update.callback_query.edit_message_text(
                "❌ 请先登录！发送 /start 登录",
                reply_markup=reply_markup
            )
        else:
            await update.message.reply_text(
                "❌ 请先登录！发送 /start 登录",
                reply_markup=reply_markup
            )
        return
    
    loading = None
    if hasattr(update, 'callback_query') and update.callback_query:
        loading = await update.callback_query.edit_message_text("🔄 正在查询游戏余额...")
    else:
        loading = await update.message.reply_text("🔄 正在查询游戏余额...")
    
    try:
        # 尝试从本地数据库获取游戏余额
        from utils.db_helper import get_user_balance
        local_user_id = context.user_data.get('local_user_id')
        if not local_user_id:
            # 从用户信息中获取本地用户ID
            user_headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient() as client:
                user_response = await client.get(
                    f"{Config.API_BASE_URL}/user",
                    headers=user_headers,
                    timeout=10
                )
            
            if user_response.status_code == 200:
                user_info = user_response.json()
                emos_user_id = user_info.get('user_id')
                username = user_info.get('username')
                from utils.db_helper import ensure_user_exists
                local_user_id = ensure_user_exists(
                    emos_user_id=emos_user_id,
                    token=token,
                    telegram_id=user_id,
                    username=username,
                    first_name=update.effective_user.first_name,
                    last_name=update.effective_user.last_name
                )
                context.user_data['local_user_id'] = local_user_id
                context.user_data['emos_user_id'] = emos_user_id
                context.user_data['username'] = username
        
        # 获取游戏余额（使用emos_user_id）
        from app.database import get_balance
        game_balance = get_balance(emos_user_id)
        
        if game_balance is not None:
            # 获取用户累计充值和提现记录（使用emos_user_id）
            from app.database import get_user_total_recharge, get_user_total_withdraw
            total_recharge = get_user_total_recharge(emos_user_id)
            total_withdraw = get_user_total_withdraw(emos_user_id)
            
            # 计算最大可提现萝卜数（不超过累计充值的3倍）
            max_withdraw_from_recharge = int(total_recharge * 3)
            remaining_withdraw = max_withdraw_from_recharge - total_withdraw
            
            # 计算基于游戏余额的最大可提现萝卜数（11游戏币=1萝卜，包含1%手续费）
            max_carrot_from_balance = game_balance // 11  # 11游戏币=1萝卜
            
            # 检查累计充值3倍的提现限额
            from utils.db_helper import check_withdraw_limits
            limit_check = check_withdraw_limits(emos_user_id, 0)  # 传入0表示检查当前状态
            
            if limit_check['success']:
                # 取游戏余额和累计充值3倍限制中的较小值
                max_carrot = min(
                    max_carrot_from_balance,
                    remaining_withdraw
                )
            else:
                max_carrot = 0
            
            if max_carrot > 0:
                # 计算游戏币
                base_game_coin = max_carrot * 10  # 基础游戏币
                fee_game_coin = max_carrot * 1     # 手续费1游戏币/萝卜
                
                # 计算税费（1%税率）
                tax_rate = 0.01
                tax_carrot = int(max_carrot * tax_rate)  # 税费萝卜数量
                tax_game_coin = tax_carrot * 10  # 税费游戏币数量
                
                total_game_coin = base_game_coin + fee_game_coin + tax_game_coin  # 总扣除游戏币
                after_tax_carrot = max_carrot - tax_carrot  # 税后萝卜数量
            else:
                base_game_coin = 0
                fee_game_coin = 0
                total_game_coin = 0
                tax_carrot = 0
                after_tax_carrot = 0
            
            # 计算建议提现萝卜数
            suggested_carrots = [10, 50, 100, 500]
            valid_suggestions = [carrot for carrot in suggested_carrots if carrot <= max_carrot]
            
            # 提示用户输入提现萝卜数
            message = f"💎 您的游戏余额：{game_balance} 🪙\n"
            message += f"💰 可兑换萝卜：{max_carrot} 萝卜\n"
            message += f"� 税费：{tax_carrot} 萝卜（1%）\n"
            message += f"🎁 税后可兑换：{after_tax_carrot} 萝卜\n"
            message += f"💸 手续费：{fee_game_coin} 🪙\n"
            message += f"🪙 总计扣除：{total_game_coin} 🪙\n\n"
            
            # 显示提现限额信息
            message += "📊 提现限额：\n"
            message += f"• 累计充值：{total_recharge} 萝卜\n"
            message += f"• 累计提现：{total_withdraw} 萝卜\n"
            message += f"• 可提现上限：{max_withdraw_from_recharge} 萝卜（累计充值的3倍）\n"
            message += f"• 剩余可提现：{remaining_withdraw} 萝卜\n"
            message += f"• 实际可提现：{min(after_tax_carrot, remaining_withdraw)} 萝卜\n\n"
            
            message += "请输入您要提现的萝卜数量："
            
            if valid_suggestions:
                message += "\n💡 建议金额："
                message += ", ".join(map(str, valid_suggestions))
            
            # 创建按钮：取消提现
            keyboard = [
                [InlineKeyboardButton("❌ 取消提现", callback_data='games')]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            if hasattr(update, 'callback_query') and update.callback_query:
                await loading.edit_text(message, reply_markup=reply_markup)
            else:
                await loading.edit_text(message, reply_markup=reply_markup)
            
            # 存储当前状态，等待用户输入
            context.user_data['current_operation'] = 'withdraw_amount'
            context.user_data['token'] = token
            context.user_data['game_balance'] = game_balance
            context.user_data['local_user_id'] = local_user_id
            context.user_data['total_recharge'] = total_recharge
            context.user_data['total_withdraw'] = total_withdraw
            context.user_data['remaining_withdraw'] = remaining_withdraw
            # 确保emos_user_id也被保存
            if 'emos_user_id' not in context.user_data:
                from app.database import get_db_connection
                conn = get_db_connection()
                if conn:
                    try:
                        with conn.cursor() as cursor:
                            cursor.execute("SELECT user_id FROM users WHERE id = %s", (local_user_id,))
                            result = cursor.fetchone()
                            if result:
                                emos_user_id = result['user_id'] if isinstance(result, dict) else result[0]
                                context.user_data['emos_user_id'] = emos_user_id
                    finally:
                        conn.close()
        else:
            # 如果本地数据库查询失败，使用默认值
            message = "💎 请输入提现金额（1-5000萝卜）：\n\n"
            message += "📊 提现规则：\n"
            message += "• 11游戏币 = 1萝卜（包含手续费）\n"
            message += "• 提现限额：累计充值的3倍\n"
            message += "• 实际到账为税后金额\n"
            if hasattr(update, 'callback_query') and update.callback_query:
                await loading.edit_text(message)
            else:
                await loading.edit_text(message)
            context.user_data['current_operation'] = 'withdraw_amount'
            context.user_data['token'] = token
            context.user_data['game_balance'] = 50000  # 默认最大值
            context.user_data['local_user_id'] = local_user_id
    except Exception as e:
        # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
        logger.error("查询游戏余额失败")
        # 即使查询失败，也允许用户输入提现金额
        message = "💎 请输入提现金额（1-5000萝卜）：\n\n"
        message += "📊 提现规则：\n"
        message += "• 11游戏币 = 1萝卜（包含手续费）\n"
        message += "• 提现限额：累计充值的3倍\n"
        message += "• 实际到账为税后金额\n"
        if hasattr(update, 'callback_query') and update.callback_query:
            await loading.edit_text(message)
        else:
            await loading.edit_text(message)
        context.user_data['current_operation'] = 'withdraw_amount'
        context.user_data['token'] = token
        context.user_data['game_balance'] = 50000  # 默认最大值
        context.user_data['local_user_id'] = local_user_id


async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理用户输入的消息"""
    user_id = update.effective_user.id
    text = update.message.text.strip()
    
    # 检查是否有等待中的操作
    if 'current_operation' in context.user_data:
        operation = context.user_data['current_operation']
        
        if operation == 'withdraw_amount':
            await process_withdraw(update, context, text)
            return


async def process_withdraw(update: Update, context: ContextTypes.DEFAULT_TYPE, amount: str):
    """处理提现金额"""
    user_id = update.effective_user.id
    token = context.user_data.get('token')
    game_balance = context.user_data.get('game_balance', 0)
    local_user_id = context.user_data.get('local_user_id')
    emos_user_id = context.user_data.get('emos_user_id')
    
    if not token:
        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        return
    
    try:
        carrot_amount = int(amount)
        if 1 <= carrot_amount <= 5000:
            # 计算需要的游戏币数量（10游戏币=1萝卜，1%手续费）
            base_game_coin = carrot_amount * 10
            fee_game_coin = carrot_amount * 1  # 1游戏币/萝卜手续费
            total_game_coin = base_game_coin + fee_game_coin
            
            # 计算税后萝卜数量（1%税率）
            tax_rate = 0.01
            tax_carrot = int(carrot_amount * tax_rate)
            after_tax_carrot = carrot_amount - tax_carrot
            
            # 检查提现限额
            from utils.db_helper import check_withdraw_limits
            limit_check = check_withdraw_limits(emos_user_id, carrot_amount)
            if not limit_check['success']:
                await update.message.reply_text(f"❌ {limit_check['error']}")
                return
            
            if total_game_coin <= game_balance:
                loading = await update.message.reply_text("🔄 正在处理提现...")
                
                try:
                    import httpx
                    import uuid
                    from datetime import datetime
                    from utils.db_helper import create_withdraw_order, update_withdraw_order_status
                    
                    # 生成提现订单号
                    order_no = f"W{datetime.now().strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                    
                    # 1. 创建提现订单
                    # 手续费已从游戏币中扣除，萝卜数量保持不变
                    # 获取用户信息，包括username
                    from app.config import user_tokens
                    user_info_token = user_tokens.get(user_id, {})
                    username = user_info_token.get('username', '') if isinstance(user_info_token, dict) else ''
                    
                    create_withdraw_order(
                        order_no=order_no,
                        emos_user_id=emos_user_id,
                        telegram_user_id=user_id,
                        game_coin_amount=total_game_coin,
                        carrot_amount=carrot_amount,
                        username=username
                    )
                    
                    # 直接使用本地数据库扣除游戏币
                    from app.database import update_balance
                    game_success = update_balance(emos_user_id, -total_game_coin)
                    if game_success:
                        logger.info(f"使用本地数据库扣除游戏币：{total_game_coin}")
                    else:
                        logger.error(f"扣除游戏币失败：{total_game_coin}")
                    
                    if game_success:
                        # 3. 使用服务商token给用户转账萝卜
                        # 获取用户的emos ID
                        user_headers = {"Authorization": f"Bearer {token}"}
                        async with httpx.AsyncClient() as client:
                            user_response = await client.get(
                                f"{Config.API_BASE_URL}/user",
                                headers=user_headers,
                                timeout=10
                            )
                        
                        if user_response.status_code == 200:
                            user_info = user_response.json()
                            user_emos_id = user_info.get('user_id')
                            
                            if user_emos_id:
                                # 使用服务商token转账（税后金额）
                                service_headers = {"Authorization": f"Bearer {Config.SERVICE_PROVIDER_TOKEN}"}
                                transfer_data = {"user_id": user_emos_id, "carrot": after_tax_carrot}
                                async with httpx.AsyncClient() as client:
                                    transfer_response = await client.post(
                                        f"{Config.API_BASE_URL}/pay/transfer",
                                        headers=service_headers,
                                        json=transfer_data,
                                        timeout=10
                                    )
                                
                                if transfer_response.status_code == 200:
                                    # 更新提现订单状态为成功
                                    update_withdraw_order_status(
                                        order_no=order_no,
                                        status='success',
                                        transfer_result=f"转账成功，金额：{after_tax_carrot}萝卜（税前{carrot_amount}萝卜，税费{tax_carrot}萝卜），手续费：{fee_game_coin}游戏币"
                                    )
                                    # 计算剩余游戏币余额
                                    remaining_balance = game_balance - total_game_coin
                                    
                                    # 计算剩余可提现额度
                                    from app.database import get_user_total_recharge, get_user_total_withdraw
                                    total_recharge = get_user_total_recharge(local_user_id)
                                    total_withdraw_after = get_user_total_withdraw(local_user_id)
                                    max_withdraw_limit = int(total_recharge * 3)
                                    remaining_withdraw_limit = max_withdraw_limit - total_withdraw_after
                                    
                                    # 按照游戏厅格式显示
                                    await loading.edit_text(
                                        f"✅ 提现申请成功！\n\n"
                                        f"📋 订单号：`{order_no}`\n"
                                        f"🥕 提现萝卜：{carrot_amount}\n"
                                        f"💼 税费：{tax_carrot} 萝卜（1%）\n"
                                        f"🎁 实际到账：{after_tax_carrot} 萝卜\n"
                                        f"🪙 基础游戏币：{base_game_coin}\n"
                                        f"💸 手续费：{fee_game_coin}\n"
                                        f"💰 扣除游戏币：{total_game_coin}\n"
                                        f"🪙 剩余游戏币：{remaining_balance}\n\n"
                                        f"📊 剩余可提现额度：{remaining_withdraw_limit} 🥕\n"
                                        f"（累计充值{total_recharge} 🥕3倍，已提现{total_withdraw_after} 🥕）",
                                        parse_mode="Markdown"
                                    )
                                    
                                    # 显示返回菜单
                                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                                    keyboard = [
                                        [InlineKeyboardButton("🎮 前往游戏厅", callback_data="games"),
                                         InlineKeyboardButton("💎 继续提现", callback_data="service_withdraw")],
                                        [InlineKeyboardButton("🔙 返回", callback_data="back")]
                                    ]
                                    reply_markup = InlineKeyboardMarkup(keyboard)
                                    await update.message.reply_text("操作完成", reply_markup=reply_markup)
                                else:
                                    # 更新提现订单状态为失败
                                    update_withdraw_order_status(
                                        order_no=order_no,
                                        status='failed',
                                        transfer_result=f"转账失败，状态码：{transfer_response.status_code}"
                                    )
                                    await loading.edit_text(f"❌ 转账失败，状态码：{transfer_response.status_code}\n订单号：\n```\n{order_no}\n```\n", parse_mode="Markdown")
                            else:
                                # 更新提现订单状态为失败
                                update_withdraw_order_status(
                                    order_no=order_no,
                                    status='failed',
                                    transfer_result=f"获取用户信息失败"
                                )
                                await loading.edit_text(f"❌ 获取用户信息失败\n订单号：\n```\n{order_no}\n```\n", parse_mode="Markdown")
                        else:
                            # 更新提现订单状态为失败
                            update_withdraw_order_status(
                                order_no=order_no,
                                status='failed',
                                transfer_result=f"获取用户信息失败，状态码：{user_response.status_code}"
                            )
                            await loading.edit_text(f"❌ 获取用户信息失败，状态码：{user_response.status_code}\n订单号：\n```\n{order_no}\n```\n", parse_mode="Markdown")
                    else:
                        # 更新提现订单状态为失败
                        update_withdraw_order_status(
                            order_no=order_no,
                            status='failed',
                            transfer_result=f"获取用户信息失败，状态码：{user_response.status_code}"
                        )
                        await loading.edit_text(f"❌ 获取用户信息失败，状态码：{user_response.status_code}\n订单号：\n```\n{order_no}\n```\n", parse_mode="Markdown")
                except Exception as e:
                    # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
                    logger.error("提现失败")
                    # 更新提现订单状态为失败
                    update_withdraw_order_status(
                        order_no=order_no,
                        status='failed',
                        transfer_result="提现失败，请稍后重试"
                    )
                    await loading.edit_text(f"❌ 提现失败，请稍后重试\n订单号：\n```\n{order_no}\n```\n", parse_mode="Markdown")
    except ValueError:
        await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
        return 105  # 继续等待金额输入


async def callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理游戏相关的按钮回调
    
    Args:
        update: Telegram更新对象
        context: 上下文对象
    
    Returns:
        bool: 是否处理了回调
    """
    query = update.callback_query
    if not query:
        return False
    
    data = query.data
    
    # 处理游戏相关的回调
    if data == 'games':
        # 显示游戏菜单（包含充值提现）
        keyboard = [
            [InlineKeyboardButton("🎲 猜大小", callback_data='guess'),
             InlineKeyboardButton("✊ 猜拳", callback_data='shoot')],
            [InlineKeyboardButton("🎰 老虎机", callback_data='slot'),
             InlineKeyboardButton("🃏 21点", callback_data='blackjack')],
            [InlineKeyboardButton("💸 充值", callback_data='recharge'),
             InlineKeyboardButton("💎 提现", callback_data='withdraw')],
            [InlineKeyboardButton("🔙 返回", callback_data='back')]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await query.edit_message_text(
            "🎮 游戏厅\n\n请选择游戏或操作：",
            reply_markup=reply_markup
        )
        return True
    elif data == 'balance':
        # 显示余额
        user_id = update.effective_user.id
        user_info = user_tokens.get(user_id)
        if user_info:
            user_id_str = user_info.get('user_id', str(user_id))
            balance = get_balance(user_id_str)
            score = get_user_score(user_id_str)
            level = get_user_level(score)
            streak = get_user_streak(user_id_str, user_id)
            balance_message = (
                f"💰 您的余额\n\n"
                f"游戏币：{balance} 🪙\n"
                f"积分：{score} 分\n"
                f"等级：{level} 级\n"
                f"连续签到：{streak} 天\n\n"
                f"💡 每日签到可获得游戏币和积分！\n"
                f"💡 参与游戏可以获得更多积分！"
            )
            await query.edit_message_text(balance_message)
        else:
            await query.edit_message_text("❌ 请先使用 /start 命令登录！")
        return True
    elif data == 'daily':
        # 处理每日签到
        user_id = update.effective_user.id
        user_info = user_tokens.get(user_id)
        if user_info:
            user_id_str = user_info.get('user_id', str(user_id))
            result = process_daily_checkin(user_id_str, user_id)
            await query.edit_message_text(result)
        else:
            await query.edit_message_text("❌ 请先使用 /start 命令登录！")
        return True
    elif data == 'recharge':
        # 调用服务商的充值功能
        from services.service_main import service_recharge
        await service_recharge(update, context)
        return True
    elif data == 'back':
        # 返回主菜单
        from handlers.common import show_menu
        await show_menu(update, "📱 功能菜单\n\n请选择功能：")
        return True
    elif data == 'withdraw':
        # 调用服务商的提现功能
        from services.service_main import service_withdraw
        await service_withdraw(update, context)
        return True
    elif data == 'guess':
        # 处理猜大小游戏
        await query.edit_message_text("🎲 猜大小游戏\n\n请输入下注金额，例如：`/guess 10`\n\n直接复制：`/guess 10`")
        return True
    elif data == 'shoot':
        # 处理猜拳游戏
        await query.edit_message_text("✊ 猜拳游戏\n\n请输入下注金额，例如：`/shoot 10`\n\n直接复制：`/shoot 10`")
        return True
    elif data == 'slot':
        # 处理老虎机游戏
        await query.edit_message_text("🎰 老虎机游戏\n\n请输入下注金额，例如：`/slot 10`\n\n直接复制：`/slot 10`")
        return True
    elif data == 'blackjack':
        # 处理21点游戏
        await query.edit_message_text("🃏 21点游戏\n\n请输入下注金额，例如：`/blackjack 10`\n\n直接复制：`/blackjack 10`")
        return True
    
    # 处理其他游戏相关的回调
    # 这里可以添加具体的游戏回调处理逻辑
    
    return False