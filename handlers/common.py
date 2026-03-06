import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, BotCommand
from telegram.ext import ContextTypes, ConversationHandler, Application

from config import Config, BOT_COMMANDS, user_tokens

logger = logging.getLogger(__name__)

# 对话状态
WAITING_REDPACKET_ID = 20
WAITING_LOTTERY_CANCEL_ID = 21

async def post_init(application: Application) -> None:
    """机器人启动后执行的钩子函数"""
    commands = [BotCommand(cmd, desc) for cmd, desc in BOT_COMMANDS]
    await application.bot.set_my_commands(commands)
    logger.info("✅ 机器人命令菜单已设置")

def add_cancel_button(keyboard=None):
    """添加取消按钮"""
    if keyboard is None:
        keyboard = []
    # 确保 keyboard 是可变的列表
    if not isinstance(keyboard, list):
        keyboard = []
    keyboard.append([InlineKeyboardButton("❌ 取消", callback_data="cancel_operation")])
    return keyboard

async def cancel_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理取消按钮回调"""
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("✅ 操作已取消")
    # 清理用户数据
    context.user_data.clear()
    return ConversationHandler.END

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理/start命令 - 登录"""
    user_id = update.effective_user.id
    
    logger.info(f"用户 {user_id} 发送 /start 命令")
    
    text = update.message.text
    if text.startswith('/start emosLinkAgree-'):
        token = text.replace('/start emosLinkAgree-', '').strip()
        logger.info(f"收到授权Token: {token}")
        user_tokens[user_id] = token
        await show_menu(update, "✅ 授权成功！\n\n欢迎使用综合机器人，请选择功能：")
        return
    
    if user_id in user_tokens:
        await show_menu(update, "👋 欢迎回来！\n\n请选择功能：")
    else:
        auth_link = f"https://t.me/emospg_bot?start=link_e0E446ZE6s-{Config.BOT_USERNAME}"
        keyboard = [
            [InlineKeyboardButton("🔐 一键登录", url=auth_link)],
            [InlineKeyboardButton("❌ 取消", callback_data="cancel_operation")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        await update.message.reply_text(
            "👋 欢迎使用综合机器人！\n\n使用前请先登录EMOS账号：",
            reply_markup=reply_markup
        )

async def menu_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """处理/menu命令"""
    user_id = update.effective_user.id
    if user_id not in user_tokens:
        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        return
    await show_menu(update, "📱 功能菜单\n\n请选择功能：")

async def show_menu(update, message_text: str):
    """显示主菜单"""
    keyboard = [
        [InlineKeyboardButton("🧧 红包功能", callback_data="menu_redpacket_main")],
        [InlineKeyboardButton("🎲 抽奖功能", callback_data="menu_lottery_main")],
        [InlineKeyboardButton("🏆 排行榜", callback_data="menu_rank_main")],
        [InlineKeyboardButton("❓ 帮助", callback_data="help")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(message_text, reply_markup=reply_markup)
    else:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)

async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """处理所有按钮回调"""
    query = update.callback_query
    await query.answer()
    
    data = query.data
    logger.info(f"按钮回调: {data}")
    
    if data == "cancel_operation":
        return await cancel_callback(update, context)
    
    # 处理返回主菜单
    if data == "back_to_main":
        await show_menu(update, "📱 功能菜单\n\n请选择功能：")
        return
    
    # 红包二级菜单
    if data == "menu_redpacket_main":
        await show_redpacket_menu(update, context)
        return
    
    # 抽奖二级菜单
    if data == "menu_lottery_main":
        await show_lottery_menu(update, context)
        return
    
    # 排行榜二级菜单
    if data == "menu_rank_main":
        await show_rank_menu(update, context)
        return
    
    # 处理具体的功能按钮
    if data == "menu_redpocket":
        from handlers.redpacket import redpocket_command
        return await redpocket_command(update, context)
    
    elif data == "menu_check_redpacket":
        from handlers.redpacket_query import check_redpacket_command
        return await check_redpacket_command(update, context)
    
    elif data == "menu_lottery":
        from games.lottery import lottery_command
        return await lottery_command(update, context)
    
    elif data == "menu_lottery_cancel":
        from games.lottery_cancel import lottery_cancel_command
        return await lottery_cancel_command(update, context)
    
    elif data == "menu_rank_carrot":
        from ranks.carrot_rank import rank_carrot_command
        await rank_carrot_command(update, context)
    
    elif data == "menu_rank_upload":
        from ranks.upload_rank import rank_upload_command
        await rank_upload_command(update, context)
    
    elif data == "menu_playing":
        from ranks.playing_rank import playing_command
        await playing_command(update, context)
    
    elif data == "help":
        await help_command(update, context)
    
    elif data in ["add_more_prizes", "finish_prizes"]:
        from games.lottery import handle_prize_choice
        return await handle_prize_choice(update, context)

async def show_redpacket_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """红包二级菜单"""
    keyboard = [
        [InlineKeyboardButton("🧧 创建红包", callback_data="menu_redpocket")],
        [InlineKeyboardButton("📊 查询红包记录", callback_data="menu_check_redpacket")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "🧧 红包功能\n\n请选择操作：",
        reply_markup=reply_markup
    )

async def show_lottery_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """抽奖二级菜单"""
    keyboard = [
        [InlineKeyboardButton("🎲 创建抽奖", callback_data="menu_lottery")],
        [InlineKeyboardButton("❌ 取消抽奖", callback_data="menu_lottery_cancel")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "🎲 抽奖功能\n\n请选择操作：",
        reply_markup=reply_markup
    )

async def show_rank_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """排行榜二级菜单"""
    keyboard = [
        [InlineKeyboardButton("🥕 萝卜排行榜", callback_data="menu_rank_carrot")],
        [InlineKeyboardButton("📤 上传量排行榜", callback_data="menu_rank_upload")],
        [InlineKeyboardButton("🎬 正在播放", callback_data="menu_playing")],
        [InlineKeyboardButton("🔙 返回主菜单", callback_data="back_to_main")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.callback_query.edit_message_text(
        "🏆 排行榜\n\n请选择类型：",
        reply_markup=reply_markup
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """帮助命令"""
    help_text = (
        "📖 **使用帮助**\n\n"
        "**红包功能**\n"
        "• /redpocket - 创建红包\n"
        "• /check_redpacket - 查询红包记录\n\n"
        "**抽奖功能**\n"
        "• /lottery - 创建抽奖\n"
        "• /lottery_cancel - 取消抽奖\n\n"
        "**排行榜**\n"
        "• /rank_carrot - 萝卜排行榜\n"
        "• /rank_upload - 上传排行榜\n"
        "• /playing - 正在播放\n\n"
        "**其他**\n"
        "• /menu - 打开菜单\n"
        "• /cancel - 取消当前操作"
    )
    
    if isinstance(update, Update) and update.message:
        await update.message.reply_text(help_text, parse_mode="Markdown")
    else:
        await update.callback_query.edit_message_text(help_text, parse_mode="Markdown")

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """取消操作"""
    await update.message.reply_text("✅ 操作已取消")
    context.user_data.clear()
    return ConversationHandler.END

async def return_to_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """返回主菜单"""
    if update.callback_query:
        await update.callback_query.answer()
        await show_menu(update, "📱 功能菜单\n\n请选择功能：")
    else:
        await show_menu(update, "📱 功能菜单\n\n请选择功能：")
    return ConversationHandler.END