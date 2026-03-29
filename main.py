#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
import os
import httpx
from datetime import datetime, timedelta, timezone

# 兼容 Python 3.12+，替换已被移除的 imghdr 模块
sys.modules['imghdr'] = __import__('utils.imghdr_compat')

# 北京时间 UTC+8
beijing_tz = timezone(timedelta(hours=8))

from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters,
    ContextTypes
)

# 确保只有一个实例运行
def ensure_single_instance():
    """确保只有一个实例运行"""
    lock_file = 'bot.lock'
    
    # 检查锁文件是否存在
    if os.path.exists(lock_file):
        try:
            # 尝试读取锁文件中的进程ID
            with open(lock_file, 'r') as f:
                pid = f.read().strip()
            
            # 检查进程是否存在
            if sys.platform == 'win32':
                # Windows 平台
                import ctypes
                kernel32 = ctypes.windll.kernel32
                process = kernel32.OpenProcess(0x100000, False, int(pid))
                if process:
                    kernel32.CloseHandle(process)
                    print("另一个机器人实例已在运行，请先关闭它")
                    sys.exit(1)
            else:
                # 其他平台
                import subprocess
                try:
                    subprocess.check_call(['kill', '-0', pid])
                    print("另一个机器人实例已在运行，请先关闭它")
                    sys.exit(1)
                except subprocess.CalledProcessError:
                    pass
        except:
            pass
    
    # 创建或更新锁文件
    with open(lock_file, 'w') as f:
        f.write(str(os.getpid()))

# 确保在程序退出时删除锁文件
import atexit

def cleanup():
    """程序退出时清理"""
    lock_file = 'bot.lock'
    if os.path.exists(lock_file):
        try:
            os.remove(lock_file)
        except:
            pass

atexit.register(cleanup)

from config import Config, BOT_COMMANDS, SERVICE_PROVIDER_TOKEN, user_tokens, GROUP_ALLOWED_COMMANDS
from utils.db_helper import ensure_user_exists, create_recharge_order
from handlers.common import (
    start, menu_command, help_command, cancel_command,
    button_callback, post_init,
    WAITING_REDPACKET_ID, WAITING_LOTTERY_CANCEL_ID
)

# 群聊命令过滤装饰器
from functools import wraps
from telegram import Update
from telegram.ext import ContextTypes

def group_command_filter(func):
    """群聊命令过滤装饰器"""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        # 检查是否是群聊
        if update.message and update.message.chat.type in ['group', 'supergroup']:
            # 获取命令名称，处理带@机器人用户名的情况
            command_part = update.message.text.split(' ')[0].lstrip('/')
            # 移除@机器人用户名部分
            command = command_part.split('@')[0]
            # 检查命令是否在允许列表中
            if command not in GROUP_ALLOWED_COMMANDS:
                # 群聊中不允许的命令，不执行
                logger.info(f"群聊中拒绝执行命令: /{command_part}")
                return
        # 执行原函数
        return await func(update, context)
    return wrapper

from handlers.redpacket import (
    redpocket_command, handle_type, handle_carrot, handle_number, handle_blessing, 
    handle_password, handle_media, create_redpacket, cancel_redpacket,
    WAITING_TYPE, WAITING_CARROT, WAITING_NUMBER, WAITING_BLESSING, WAITING_PASSWORD, WAITING_MEDIA
)
from app.handlers.command_handlers import (
    start_handler, balance_handler, guess_handler, slot_handler, daily_handler, help_handler, 
    blackjack_handler, hit_handler, stand_handler, message_handler, callback_handler, withdraw_handler
)
from handlers.redpacket_query import WAITING_QUERY_TYPE
from handlers.redpacket_query import check_redpacket_command, get_redpacket_id, handle_query_type
from games.lottery import (
    lottery_command, lottery_process,
    WAITING_LOTTERY_NAME, WAITING_LOTTERY_DESC, WAITING_LOTTERY_START,
    WAITING_LOTTERY_END, WAITING_LOTTERY_AMOUNT, WAITING_LOTTERY_NUMBER,
    WAITING_LOTTERY_RULE_CARROT, WAITING_LOTTERY_RULE_SIGN, WAITING_LOTTERY_PRIZES,
    handle_bodys_choice, get_lottery_bodys, handle_prize_choice, handle_end_time_choice
)
from games.lottery_cancel import lottery_cancel_command, get_lottery_cancel_id
from ranks.carrot_rank import rank_carrot_command
from ranks.upload_rank import rank_upload_command
from ranks.playing_rank import playing_command

# 创建 logs 文件夹
if not os.path.exists('logs'):
    os.makedirs('logs')

# 生成日志文件名
log_filename = f"logs/bot_{datetime.now(beijing_tz).strftime('%Y%m%d_%H%M%S')}.log"

# 设置日志
try:
    sys.stdout.reconfigure(encoding='utf-8')
except (AttributeError, OSError):
    pass

console_handler = logging.StreamHandler(sys.stdout)
console_handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))

logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        console_handler,
        logging.FileHandler(log_filename, encoding='utf-8')
    ]
)
logger = logging.getLogger(__name__)

logger.info(f"日志文件: {log_filename}")
logger.info("=" * 60)

def main() -> None:
    """主函数"""
    # 确保只有一个实例运行
    ensure_single_instance()
    
    logger.info("正在启动机器人...")
    
    # 初始化游戏数据库
    logger.info("初始化游戏数据库...")
    from app.database import init_db
    init_db()
    
    # 加载游戏用户token
    logger.info("加载游戏用户token...")
    from app.config import load_tokens_from_db
    load_tokens_from_db()
    
    # 创建应用
    application = Application.builder() \
        .token(Config.BOT_TOKEN) \
        .post_init(post_init) \
        .build()
    
    # ===== 基本命令 =====
    application.add_handler(CommandHandler("start", group_command_filter(start)))
    application.add_handler(CommandHandler("menu", group_command_filter(menu_command)))
    application.add_handler(CommandHandler("help", group_command_filter(help_command)))
    application.add_handler(CommandHandler("cancel", group_command_filter(cancel_command)))
    
    # ===== 游戏命令 =====
    application.add_handler(CommandHandler("game", group_command_filter(start_handler)))
    application.add_handler(CommandHandler("balance", group_command_filter(balance_handler)))
    application.add_handler(CommandHandler("guess", group_command_filter(guess_handler)))
    application.add_handler(CommandHandler("slot", group_command_filter(slot_handler)))
    application.add_handler(CommandHandler("blackjack", group_command_filter(blackjack_handler)))
    application.add_handler(CommandHandler("hit", group_command_filter(hit_handler)))
    application.add_handler(CommandHandler("stand", group_command_filter(stand_handler)))
    application.add_handler(CommandHandler("daily", group_command_filter(daily_handler)))
    application.add_handler(CommandHandler("withdraw", group_command_filter(withdraw_handler)))
    
    # ===== 红包对话 =====
    redpocket_conv = ConversationHandler(
        entry_points=[
            CommandHandler("redpocket", group_command_filter(redpocket_command)),
            CallbackQueryHandler(redpocket_command, pattern="^menu_redpocket$")
        ],
        states={
            WAITING_TYPE: [
                CallbackQueryHandler(handle_type, pattern="^(type_|image_no_password|image_with_password|audio_no_password|audio_with_password|back_)"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_CARROT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_carrot),
                MessageHandler(filters.PHOTO, handle_media),
                MessageHandler(filters.VOICE, handle_media),
                MessageHandler(filters.AUDIO, handle_media),
                MessageHandler(filters.Document.ALL, handle_media),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_number),
                MessageHandler(filters.PHOTO, handle_media),
                MessageHandler(filters.VOICE, handle_media),
                MessageHandler(filters.AUDIO, handle_media),
                MessageHandler(filters.Document.ALL, handle_media),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_BLESSING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_blessing),
                MessageHandler(filters.PHOTO, handle_media),
                MessageHandler(filters.VOICE, handle_media),
                MessageHandler(filters.AUDIO, handle_media),
                MessageHandler(filters.Document.ALL, handle_media),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, handle_password),
                MessageHandler(filters.PHOTO, handle_media),
                MessageHandler(filters.VOICE, handle_media),
                MessageHandler(filters.AUDIO, handle_media),
                MessageHandler(filters.Document.ALL, handle_media),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_MEDIA: [
                MessageHandler(filters.PHOTO, handle_media),
                MessageHandler(filters.VOICE, handle_media),
                MessageHandler(filters.AUDIO, handle_media),
                MessageHandler(filters.Document.ALL, handle_media),
                CallbackQueryHandler(handle_type, pattern="^back_"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_redpacket)]
    )
    application.add_handler(redpocket_conv)
    
    # ===== 红包查询对话 =====
    redpocket_query_conv = ConversationHandler(
        entry_points=[
            CommandHandler("check_redpacket", group_command_filter(check_redpacket_command)),
            CallbackQueryHandler(check_redpacket_command, pattern="^menu_check_redpacket$")
        ],
        states={
            WAITING_QUERY_TYPE: [
                CallbackQueryHandler(handle_query_type, pattern="^(my_redpackets|input_id)$"),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_REDPACKET_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_redpacket_id),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    application.add_handler(redpocket_query_conv)
    
    # ===== 抽奖对话 =====
    lottery_conv = ConversationHandler(
        entry_points=[
            CommandHandler("lottery", group_command_filter(lottery_command)),
            CallbackQueryHandler(lottery_command, pattern="^menu_lottery$")
        ],
        states={
            WAITING_LOTTERY_NAME: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_DESC: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_START: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_END: [
                CallbackQueryHandler(handle_end_time_choice, pattern="^end_time_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_RULE_CARROT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_RULE_SIGN: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_LOTTERY_PRIZES: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, lottery_process),
                CallbackQueryHandler(handle_bodys_choice, pattern="^need_bodys_"),
                CallbackQueryHandler(handle_prize_choice, pattern="^(add_more_prizes|finish_prizes)$"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_lottery_bodys),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    application.add_handler(lottery_conv)
    
    # ===== 取消抽奖对话 =====
    lottery_cancel_conv = ConversationHandler(
        entry_points=[
            CommandHandler("lottery_cancel", group_command_filter(lottery_cancel_command)),
            CallbackQueryHandler(lottery_cancel_command, pattern="^menu_lottery_cancel$")
        ],
        states={
            WAITING_LOTTERY_CANCEL_ID: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, get_lottery_cancel_id),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_command)]
    )
    application.add_handler(lottery_cancel_conv)
    
    # ===== 排行榜命令 =====
    application.add_handler(CommandHandler("playing", group_command_filter(playing_command)))
    application.add_handler(CommandHandler("rank_carrot", group_command_filter(rank_carrot_command)))
    application.add_handler(CommandHandler("rank_upload", group_command_filter(rank_upload_command)))
    
    # 处理用户输入
    async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理用户输入的信息"""
        user_id = update.effective_user.id
        input_text = update.message.text.strip()
        
        # 首先检查是否有游戏状态需要处理
        # 检查是否在等待猜大小游戏的输入
        if 'awaiting_guess' in context.user_data and context.user_data['awaiting_guess']:
            from app.handlers.command_handlers import process_guess
            parts = input_text.split()
            if len(parts) == 2:
                amount, guess = parts
                await process_guess(update, context, amount, guess)
            else:
                await update.message.reply_text("请输入正确的格式，例如：10 大")
            context.user_data['awaiting_guess'] = False
            return
        
        # 检查是否在等待老虎机游戏的输入
        if 'awaiting_slot' in context.user_data and context.user_data['awaiting_slot']:
            from app.handlers.command_handlers import process_slot
            await process_slot(update, context, input_text)
            context.user_data['awaiting_slot'] = False
            return
        
        # 检查是否在等待21点游戏的输入
        if 'awaiting_blackjack' in context.user_data and context.user_data['awaiting_blackjack']:
            from app.handlers.command_handlers import process_blackjack
            await process_blackjack(update, context, input_text)
            context.user_data['awaiting_blackjack'] = False
            return

        # 检查是否有游戏厅相关的文本输入需要处理（充值、提现等）
        if 'current_operation' in context.user_data and context.user_data['current_operation'] in ['recharge_amount', 'withdraw_amount']:
            from app.handlers.command_handlers import message_handler as game_message_handler
            # 调用游戏厅的消息处理器处理充值或提现
            await game_message_handler(update, context)
            return

        if 'current_operation' in context.user_data:
                operation = context.user_data['current_operation']
                user_id = update.effective_user.id
                token = None
                print(f"DEBUG: user_id={user_id}")
                print(f"DEBUG: user_tokens type={type(user_tokens)}")
                print(f"DEBUG: user_tokens keys={list(user_tokens.keys())}")
                try:
                    # 优先从context.user_data中获取token
                    if 'token' in context.user_data:
                        token = context.user_data.get('token')
                        print(f"DEBUG: token from context={token[:20]}..." if token else "DEBUG: token is None from context")
                    # 如果context中没有token，从user_tokens中获取
                    elif user_id in user_tokens:
                        user_info = user_tokens[user_id]
                        print(f"DEBUG: user_info type={type(user_info)}")
                        if isinstance(user_info, dict):
                            token = user_info.get('token')
                            print(f"DEBUG: token from dict={token[:20]}..." if token else "DEBUG: token is None from dict")
                        else:
                            token = user_info
                            print(f"DEBUG: token from string={token[:20]}..." if token else "DEBUG: token is None from string")
                    print(f"DEBUG: final token={token[:20]}..." if token else "DEBUG: final token is None")
                except Exception as e:
                    print(f"DEBUG: Token获取异常: {type(e).__name__}: {e}")
                    token = None
                
                if operation == 'change_pseudonym':
                    # 处理笔名更新
                    if token:
                        loading = await update.message.reply_text("🔄 正在更新笔名...")
                        
                        try:
                            headers = {"Authorization": f"Bearer {token}"}
                            async with httpx.AsyncClient() as client:
                                response = await client.put(
                                    f"{Config.API_BASE_URL}/user/pseudonym?name={input_text}",
                                    headers=headers,
                                    timeout=10
                                )
                            
                            if response.status_code == 200:
                                await loading.edit_text(f"✅ 笔名更新成功！新笔名为：{input_text}")
                            else:
                                await loading.edit_text(f"❌ 更新笔名失败，状态码：{response.status_code}")
                        except Exception as e:
                            # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
                            logger.error("更新笔名失败")
                            await loading.edit_text("❌ 更新笔名失败，请稍后重试")
                        
                        # 显示返回菜单
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        keyboard = [[InlineKeyboardButton("🔙 返回个人信息", callback_data="menu_user_main")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text("操作完成", reply_markup=reply_markup)
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'invite_user':
                    # 处理邀请用户
                    if token:
                        loading = await update.message.reply_text("🔄 正在邀请用户...")
                        
                        try:
                            headers = {"Authorization": f"Bearer {token}"}
                            data = {"invite_user_id": input_text}
                            async with httpx.AsyncClient() as client:
                                response = await client.post(
                                    f"{Config.API_BASE_URL}/invite",
                                    headers=headers,
                                    json=data,
                                    timeout=10
                                )
                            
                            if response.status_code == 200:
                                result = response.json()
                                remaining = result.get('invite_remaining', 0)
                                await loading.edit_text(f"✅ 邀请成功！剩余邀请次数：{remaining}")
                            else:
                                await loading.edit_text(f"❌ 邀请失败，状态码：{response.status_code}")
                        except Exception as e:
                            # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
                            logger.error("邀请用户失败")
                            await loading.edit_text("❌ 邀请用户失败，请稍后重试")
                        
                        # 显示返回菜单
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        keyboard = [[InlineKeyboardButton("🔙 返回个人信息", callback_data="menu_user_main")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text("操作完成", reply_markup=reply_markup)
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'transfer_user_id':
                    # 处理转赠用户ID输入
                    if token:
                        # 存储对方用户ID
                        context.user_data['target_user_id'] = input_text
                        # 提示用户输入转赠金额
                        await update.message.reply_text("💸 请输入转赠萝卜数量（2-6000之间）：")
                        # 更新操作状态
                        context.user_data['current_operation'] = 'transfer_amount'
                        return 103  # 继续等待金额输入
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'transfer_amount':
                    # 处理转赠金额输入
                    if token:
                        target_user_id = context.user_data.get('target_user_id')
                        try:
                            amount = int(input_text)
                            if 2 <= amount <= 6000:
                                loading = await update.message.reply_text("🔄 正在转赠...")
                                
                                try:
                                    headers = {"Authorization": f"Bearer {token}"}
                                    data = {"user_id": target_user_id, "carrot": amount}
                                    async with httpx.AsyncClient() as client:
                                        response = await client.put(
                                            f"{Config.API_BASE_URL}/carrot/transfer",
                                            headers=headers,
                                            json=data,
                                            timeout=10
                                        )
                                    
                                    if response.status_code == 200:
                                        result = response.json()
                                        remaining = result.get('carrot', 0)
                                        await loading.edit_text(f"✅ 转赠成功！\n剩余萝卜：{remaining}")
                                    else:
                                        await loading.edit_text(f"❌ 转赠失败，状态码：{response.status_code}")
                                except Exception as e:
                                    # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
                                    logger.error("转赠失败")
                                    await loading.edit_text("❌ 转赠失败，请稍后重试")
                                
                                # 显示返回菜单
                                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                                keyboard = [[InlineKeyboardButton("🔙 返回转账菜单", callback_data="menu_transfer_main")]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                await update.message.reply_text("操作完成", reply_markup=reply_markup)
                            else:
                                await update.message.reply_text("❌ 转赠金额必须在2-6000之间，请重新输入：")
                                return 103  # 继续等待金额输入
                        except ValueError:
                            await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                            return 103  # 继续等待金额输入
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_recharge_amount':
                    # 处理充值金额输入
                    if token:
                        try:
                            amount = int(input_text)
                            if 1 <= amount <= 50000:
                                # 检查充值限制
                                from config import RECHARGE_LIMITS
                                from app.database import get_recharge_history
                                from datetime import datetime, timedelta
                                import httpx
                                
                                # 获取用户信息
                                user_headers = {"Authorization": f"Bearer {token}"}
                                async with httpx.AsyncClient() as client:
                                    user_response = await client.get(
                                        f"{Config.API_BASE_URL}/user",
                                        headers=user_headers,
                                        timeout=10
                                    )
                                
                                if user_response.status_code == 200:
                                    user_data = user_response.json()
                                    emos_user_id = user_data.get('user_id')
                                    
                                    # 获取用户充值历史
                                    recharge_history = get_recharge_history(emos_user_id)
                                    
                                    # 计算各时间段的充值总额
                                    today = datetime.now().date()
                                    this_month = today.month
                                    this_year = today.year
                                    
                                    daily_recharge = 0
                                    monthly_recharge = 0
                                    
                                    for record in recharge_history:
                                        record_date = record['created_at'].date()
                                        record_amount = record['carrot_amount']
                                        
                                        # 累计本月充值
                                        if record_date.month == this_month and record_date.year == this_year:
                                            monthly_recharge += record_amount
                                        
                                        # 累计今日充值
                                        if record_date == today:
                                            daily_recharge += record_amount
                                    
                                    # 检查累计充值限额
                                    from app.database import get_user_total_recharge
                                    total_recharge = get_user_total_recharge(emos_user_id)
                                    max_total_recharge = 100  # 累计充值限额为100萝卜
                                    
                                    if total_recharge + amount > max_total_recharge:
                                        remaining_recharge = max_total_recharge - total_recharge
                                        await update.message.reply_text(f"累计充值已达上限！累计已充值 {total_recharge} 萝卜，最多可充值 {max_total_recharge} 萝卜，还可充值 {remaining_recharge} 萝卜")
                                        return
                                    
                                    # 检查充值限制
                                    if daily_recharge + amount > RECHARGE_LIMITS['daily']:
                                        await update.message.reply_text(f"今日充值已达上限！今日已充值 {daily_recharge} 萝卜，最多可充值 {RECHARGE_LIMITS['daily']} 萝卜")
                                        return
                                    
                                    if monthly_recharge + amount > RECHARGE_LIMITS['monthly']:
                                        await update.message.reply_text(f"本月充值已达上限！本月已充值 {monthly_recharge} 萝卜，最多可充值 {RECHARGE_LIMITS['monthly']} 萝卜")
                                        return
                                else:
                                    await update.message.reply_text("❌ 获取用户信息失败，请稍后重试")
                                    return
                                
                                loading = await update.message.reply_text("🔄 正在创建支付订单...")
                                
                                try:
                                    import uuid
                                    import json
                                    from datetime import datetime
                                    
                                    # 生成唯一参数
                                    param = str(uuid.uuid4())[:8]
                                    
                                    # 调用创建订单API（使用服务商token）
                                    headers = {
                                        "Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}",
                                        "Content-Type": "application/json; charset=utf-8"
                                    }
                                    data = {
                                        "pay_way": "telegram_bot",
                                        "price": amount,
                                        "name": f"游戏币充值 {amount}萝卜",
                                        "param": param,
                                        "callback_telegram_bot_name": Config.BOT_USERNAME
                                    }
                                    
                                    logger.info(f"创建支付订单: {data}")
                                    
                                    json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
                                    
                                    async with httpx.AsyncClient() as client:
                                        response = await client.post(
                                            f"{Config.API_BASE_URL}/pay/create",
                                            headers=headers,
                                            content=json_data,
                                            timeout=10
                                        )
                                    
                                    logger.info(f"支付订单API响应状态码: {response.status_code}")
                                    logger.info(f"支付订单API响应内容: {response.text}")
                                    
                                    if response.status_code == 200:
                                        result = response.json()
                                        pay_url = result.get('pay_url')
                                        order_no = result.get('no')
                                        expired = result.get('expired')
                                        
                                        if pay_url:
                                            # 先获取用户信息，保存到本地数据库
                                            try:
                                                user_headers = {"Authorization": f"Bearer {token}"}
                                                async with httpx.AsyncClient() as client:
                                                    user_response = await client.get(
                                                        f"{Config.API_BASE_URL}/user",
                                                        headers=user_headers,
                                                        timeout=10
                                                    )
                                                
                                                if user_response.status_code == 200:
                                                    user_data = user_response.json()
                                                    emos_user_id = user_data.get('user_id')
                                                    username = user_data.get('username')
                                                    
                                                    # 确保用户在本地数据库中存在
                                                    local_user_id = ensure_user_exists(
                                                        emos_user_id=emos_user_id,
                                                        token=token,
                                                        telegram_id=user_id,
                                                        username=username,
                                                        first_name=update.effective_user.first_name,
                                                        last_name=update.effective_user.last_name
                                                    )
                                                    
                                                    if local_user_id:
                                                        # 生成本地订单号
                                                        local_order_no = f"R{datetime.now(beijing_tz).strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                                                        
                                                        # 解析过期时间
                                                        expire_time = None
                                                        if expired:
                                                            try:
                                                                expire_time = datetime.strptime(expired, '%Y-%m-%d %H:%M:%S')
                                                            except Exception as e:
                                                                logger.error(f"解析过期时间失败: {e}")
                                                        
                                                        # 保存订单到本地数据库
                                                        logger.info(f"开始创建充值订单: local_order_no={local_order_no}, platform_order_no={order_no}, emos_user_id={emos_user_id}, username={username}")
                                                        success = create_recharge_order(
                                                            order_no=local_order_no,
                                                            emos_user_id=emos_user_id,
                                                            username=username,
                                                            telegram_user_id=user_id,
                                                            carrot_amount=amount,
                                                            platform_order_no=order_no,
                                                            pay_url=pay_url,
                                                            expire_time=expire_time
                                                        )
                                                        if success:
                                                            logger.info(f"订单已保存到本地数据库: {local_order_no}")
                                                        else:
                                                            logger.error(f"订单保存到本地数据库失败: {local_order_no}")
                                            except Exception as db_error:
                                                logger.error(f"保存订单到本地数据库失败: {db_error}")
                                            
                                            # 存储订单信息
                                            context.user_data['recharge_order'] = {
                                                'order_no': order_no,
                                                'amount': amount,
                                                'param': param,
                                                'token': token
                                            }
                                            
                                            message = f"📋 充值订单已创建\n\n"
                                            message += f"订单号：\n```\n{order_no}\n```\n"
                                            message += f"充值金额：{amount} 🥕\n"
                                            message += f"预计兑换：{amount * 10} 🎮\n"
                                            message += f"过期时间：{expired}\n\n"
                                            message += "请点击下方按钮完成支付："
                                            
                                            from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                                            keyboard = [
                                                [InlineKeyboardButton("💳 去支付", url=pay_url)],
                                                [InlineKeyboardButton("❌ 取消", callback_data="cancel_recharge")]
                                            ]
                                            reply_markup = InlineKeyboardMarkup(keyboard)
                                            await loading.edit_text(message, reply_markup=reply_markup, parse_mode="Markdown")
                                        else:
                                            await loading.edit_text("❌ 创建订单失败，没有返回支付链接")
                                    else:
                                        await loading.edit_text(f"❌ 创建订单失败，状态码：{response.status_code}\n响应：{response.text}")
                                except Exception as e:
                                    # 记录详细的错误信息
                                    logger.error(f"创建支付订单失败: {type(e).__name__}: {e}")
                                    import traceback
                                    logger.error(f"错误堆栈: {traceback.format_exc()}")
                                    await loading.edit_text(f"❌ 创建订单失败: {type(e).__name__}: {e}")
                            else:
                                await update.message.reply_text("❌ 充值金额必须在1-50000之间，请重新输入：")
                                return 104  # 继续等待金额输入
                        except ValueError:
                            await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                            return 104  # 继续等待金额输入
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_withdraw_amount':
                    # 处理提现萝卜数量输入
                    if token:
                        try:
                            carrot_amount = int(input_text)
                            game_balance = context.user_data.get('game_balance', 0)
                            local_user_id = context.user_data.get('local_user_id')
                            user_id = update.effective_user.id
                            
                            # 计算需要的游戏币数量（10游戏币=1萝卜）
                            # 1%手续费
                            base_game_coin = carrot_amount * 10
                            fee_game_coin = int(base_game_coin * 0.01)
                            amount = base_game_coin + fee_game_coin
                            # 计算税后萝卜数量（假设税率为0%）
                            tax_rate = 0
                            tax_carrot = int(carrot_amount * tax_rate)
                            after_tax_carrot = carrot_amount - tax_carrot
                            
                            # 检查提现限额
                            from utils.db_helper import check_withdraw_limits
                            limit_check = check_withdraw_limits(local_user_id, carrot_amount)
                            if not limit_check['success']:
                                await update.message.reply_text(f"❌ {limit_check['error']}")
                                return
                            
                            if 1 <= carrot_amount <= 5000 and amount <= game_balance:
                                loading = await update.message.reply_text("🔄 正在处理提现...")
                                
                                try:
                                    import httpx
                                    import uuid
                                    from datetime import datetime
                                    from utils.db_helper import create_withdraw_order, update_withdraw_order_status
                                    
                                    # 生成提现订单号
                                    order_no = f"W{datetime.now(beijing_tz).strftime('%Y%m%d')}{str(uuid.uuid4())[:8].upper()}"
                                    
                                    # 1. 创建提现订单
                                    # 手续费已从游戏币中扣除，萝卜数量保持不变
                                    create_withdraw_order(
                                        order_no=order_no,
                                        user_id=local_user_id,
                                        telegram_user_id=user_id,
                                        game_coin_amount=amount,
                                        carrot_amount=carrot_amount
                                    )
                                    
                                    # 直接使用本地数据库扣除游戏币（withdraw API不存在）
                                    game_success = True
                                    logger.info(f"使用本地数据库扣除游戏币：{amount}")
                                    
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
                                                # 使用服务商token转账
                                                service_headers = {"Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}"}
                                                transfer_data = {"user_id": user_emos_id, "carrot": carrot_amount}
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
                                                        transfer_result=f"转账成功，金额：{carrot_amount}萝卜，手续费：{fee_game_coin}游戏币"
                                                    )
                                                    # 计算剩余游戏币余额
                                                    remaining_balance = game_balance - amount
                                                    await loading.edit_text(f"✅ 提现成功！\n\n订单号：\n```\n{order_no}\n```\n🪙 游戏币扣除：{amount}\n🥕 兑换萝卜：{carrot_amount}\n💸 手续费：{fee_game_coin} 🪙\n💼 税费：{tax_carrot}萝卜\n💰 实际到账（税后）：{after_tax_carrot}萝卜\n🪙 剩余游戏币：{remaining_balance} 🪙\n已转入您的账号", parse_mode="Markdown")
                                                    
                                                    # 显示返回菜单
                                                    from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                                                    keyboard = [[InlineKeyboardButton("🔙 返回游戏厅", callback_data="games")]]
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
                                                    transfer_result="获取用户信息失败"
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
                                            transfer_result=f"游戏币扣除失败，状态码：{game_response.status_code}"
                                        )
                                        await loading.edit_text(f"❌ 游戏币扣除失败，状态码：{game_response.status_code}\n订单号：\n```\n{order_no}\n```\n", parse_mode="Markdown")
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
                            else:
                                if amount > game_balance:
                                    max_carrot = game_balance // 10
                                    await update.message.reply_text(f"❌ 提现萝卜数不能超过可兑换上限（{max_carrot}萝卜），请重新输入：")
                                else:
                                    await update.message.reply_text("❌ 提现萝卜数量必须在1-5000之间，请重新输入：")
                                return 104  # 继续等待金额输入
                        except ValueError:
                            await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                            return 105  # 继续等待金额输入
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_game_recharge_amount':
                    # 处理游戏充值金额输入
                    if token:
                        game_id = context.user_data.get('game_id')
                        try:
                            amount = int(input_text)
                            if 1 <= amount <= 50000:
                                loading = await update.message.reply_text("🔄 正在创建游戏充值订单...")
                                
                                try:
                                    import httpx
                                    headers = {"Authorization": f"Bearer {token}"}
                                    data = {"game_id": game_id, "carrot_amount": amount}
                                    async with httpx.AsyncClient() as client:
                                        response = await client.post(
                                            f"{Config.API_BASE_URL}/game/recharge",
                                            headers=headers,
                                            json=data,
                                            timeout=10
                                        )
                                    
                                    if response.status_code == 200:
                                        result = response.json()
                                        game_coin = result.get('game_coin', 0)
                                        await loading.edit_text(f"✅ 游戏充值成功！\n兑换游戏币：{game_coin}")
                                    else:
                                        await loading.edit_text(f"❌ 游戏充值失败，状态码：{response.status_code}")
                                except Exception as e:
                                    # 直接记录固定的错误信息，避免尝试编码包含emoji的异常信息
                                    logger.error("游戏充值失败")
                                    await loading.edit_text("❌ 游戏充值失败，请稍后重试")
                                
                                # 显示返回菜单
                                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                                keyboard = [[InlineKeyboardButton("🔙 返回游戏厅", callback_data="games")]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                await update.message.reply_text("操作完成", reply_markup=reply_markup)
                            else:
                                await update.message.reply_text("❌ 充值金额必须在1-50000之间，请重新输入：")
                                return 106  # 继续等待金额输入
                        except ValueError:
                            await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                            return 106  # 继续等待金额输入
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_apply_name':
                    # 处理服务商名称输入
                    if token:
                        # 存储服务商名称
                        context.user_data['service_name'] = input_text
                        # 提示用户输入服务商描述
                        await update.message.reply_text("🏢 请输入服务商描述（200字以内）：")
                        # 更新操作状态
                        context.user_data['current_operation'] = 'service_apply_description'
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_apply_description':
                    # 处理服务商描述输入
                    if token:
                        service_name = context.user_data.get('service_name')
                        service_description = input_text
                        
                        loading = await update.message.reply_text("🔄 正在申请成为服务商...")
                        
                        try:
                            import httpx
                            import json
                            print(f"DEBUG: Creating headers with token length={len(token) if token else 0}")
                            headers = {
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json; charset=utf-8"
                            }
                            print(f"DEBUG: Headers created successfully")
                            data = {"name": service_name, "description": service_description}
                            
                            print(f"DEBUG: Request data: name={service_name}, description={service_description}")
                            
                            logger.info(f"申请服务商请求: name={service_name[:20]}, description={service_description[:50]}")
                            logger.info(f"API地址: {Config.API_BASE_URL}/pay/apply")
                            
                            json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
                            print(f"DEBUG: JSON data encoded successfully, length={len(json_data)}")
                            
                            async with httpx.AsyncClient() as client:
                                print(f"DEBUG: Sending API request...")
                                response = await client.post(
                                    f"{Config.API_BASE_URL}/pay/apply",
                                    headers=headers,
                                    content=json_data,
                                    timeout=10
                                )
                            print(f"DEBUG: API request completed, status={response.status_code}")
                            
                            try:
                                status_code = response.status_code
                                print(f"DEBUG: Response status code={status_code}")
                                logger.info(f"申请服务商响应状态码: {status_code}")
                            except Exception as e:
                                print(f"DEBUG: Status code logging error: {e}")
                            
                            # 避免在日志中直接记录可能包含emoji的响应内容
                            try:
                                response_text = response.text
                                # 安全处理响应内容，避免编码错误
                                safe_text = response_text.encode('utf-8', errors='replace').decode('utf-8')
                                print(f"DEBUG: Safe response text={safe_text[:100]}...")
                                logger.info(f"申请服务商响应内容: {safe_text[:200]}")
                            except Exception as e:
                                print(f"DEBUG: Error processing response text: {type(e).__name__}: {e}")
                                logger.info("申请服务商响应内容: [无法处理的响应]")
                            
                            if response.status_code == 200:
                                # API返回200表示成功，可能没有响应体
                                await loading.edit_text("✅ 申请成功！请等待审核结果")
                            else:
                                try:
                                    error_text = response.text[:200] if response.text else "无响应内容"
                                    # 安全处理错误文本
                                    safe_error = error_text.encode('utf-8', errors='replace').decode('utf-8')
                                    print(f"DEBUG: Safe error text={safe_error[:100]}...")
                                    logger.error(f"申请服务商API返回错误: 状态码={response.status_code}")
                                    await loading.edit_text(f"❌ 申请失败，状态码：{response.status_code}\n{safe_error}")
                                except Exception as e:
                                    print(f"DEBUG: Error processing error text: {type(e).__name__}: {e}")
                                    logger.error(f"申请服务商API返回错误: 状态码={response.status_code} [无法处理的响应]")
                                    await loading.edit_text(f"❌ 申请失败，状态码：{response.status_code}\n[响应内容无法显示]")
                        except httpx.HTTPStatusError as e:
                            print(f"DEBUG: HTTPStatusError: {e}")
                            logger.error(f"申请服务商HTTP错误: {e.response.status_code}")
                            await loading.edit_text(f"❌ 申请失败，HTTP错误：{e.response.status_code}")
                        except httpx.RequestError as e:
                            print(f"DEBUG: RequestError: {e}")
                            logger.error(f"申请服务商请求错误: {type(e).__name__}")
                            await loading.edit_text("❌ 申请失败，网络请求错误，请检查网络连接")
                        except UnicodeEncodeError as e:
                            print(f"DEBUG: UnicodeEncodeError: {e}")
                            print(f"DEBUG: Error details: {e.encode}")
                            # 记录异常类型但不记录可能包含emoji的消息
                            logger.error(f"申请服务商发生异常: UnicodeEncodeError")
                            await loading.edit_text("❌ 申请失败，请稍后重试")
                        except Exception as e:
                            print(f"DEBUG: Other exception: {type(e).__name__}: {e}")
                            # 记录异常类型但不记录可能包含emoji的消息
                            logger.error(f"申请服务商发生异常: {type(e).__name__}")
                            await loading.edit_text("❌ 申请失败，请稍后重试")
                        
                        # 显示返回菜单
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        keyboard = [[InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text("操作完成", reply_markup=reply_markup)
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_update_name':
                    # 处理服务商名称输入
                    if token:
                        # 存储服务商名称
                        context.user_data['service_name'] = input_text
                        # 提示用户输入服务商描述
                        await update.message.reply_text("🏢 请输入服务商描述（200字以内）：")
                        # 更新操作状态
                        context.user_data['current_operation'] = 'service_update_description'
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_update_description':
                    # 处理服务商描述输入
                    if token:
                        service_name = context.user_data.get('service_name')
                        service_description = input_text
                        # 提示用户输入回调地址
                        await update.message.reply_text("🏢 请输入回调地址（可为空）：")
                        # 更新操作状态
                        context.user_data['current_operation'] = 'service_update_notify_url'
                        context.user_data['service_name'] = service_name
                        context.user_data['service_description'] = service_description
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_update_notify_url':
                    # 处理服务商回调地址输入
                    if token:
                        service_name = context.user_data.get('service_name')
                        service_description = context.user_data.get('service_description')
                        service_notify_url = input_text if input_text else None
                        
                        loading = await update.message.reply_text("🔄 正在更新服务商信息...")
                        
                        try:
                            import httpx
                            import json
                            headers = {
                                "Authorization": f"Bearer {token}",
                                "Content-Type": "application/json; charset=utf-8"
                            }
                            data = {"name": service_name, "description": service_description, "notify_url": service_notify_url}
                            json_data = json.dumps(data, ensure_ascii=False).encode('utf-8')
                            async with httpx.AsyncClient() as client:
                                response = await client.post(
                                    f"{Config.API_BASE_URL}/pay/update",
                                    headers=headers,
                                    content=json_data,
                                    timeout=10
                                )
                            
                            if response.status_code == 200:
                                await loading.edit_text("✅ 更新成功！")
                            else:
                                await loading.edit_text(f"❌ 更新失败，状态码：{response.status_code}")
                        except Exception as e:
                            logger.error(f"更新服务商信息失败: {e}")
                            await loading.edit_text("❌ 更新失败，请稍后重试")
                        
                        # 显示返回菜单
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        keyboard = [[InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text("操作完成", reply_markup=reply_markup)
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_fund_transfer_user_id':
                    # 处理转账用户ID输入
                    if token:
                        # 存储对方用户ID
                        context.user_data['target_user_id'] = input_text
                        # 提示用户输入转账金额
                        await update.message.reply_text("💸 请输入转账萝卜数量（1-50000之间）：")
                        # 更新操作状态
                        context.user_data['current_operation'] = 'service_fund_transfer_amount'
                        return 107  # 继续等待金额输入
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_fund_transfer_amount':
                    # 处理转账金额输入
                    if token:
                        target_user_id = context.user_data.get('target_user_id')
                        try:
                            amount = int(input_text)
                            if 1 <= amount <= 50000:
                                # 再次验证用户是否为服务商
                                is_service = False
                                try:
                                    import httpx
                                    headers = {"Authorization": f"Bearer {token}"}
                                    async with httpx.AsyncClient() as client:
                                        response = await client.get(
                                            f"{Config.API_BASE_URL}/pay/base",
                                            headers=headers,
                                            timeout=10
                                        )
                                    
                                    if response.status_code == 200:
                                        service_info = response.json()
                                        status = service_info.get('status')
                                        if status == 'pass':
                                            is_service = True
                                        else:
                                            is_service = False
                                    else:
                                        is_service = False
                                except Exception as e:
                                    logger.error("检查服务商状态失败")
                                    is_service = False
                                
                                if not is_service:
                                    await update.message.reply_text("❌ 只有服务商才能使用此功能！")
                                    # 清理用户数据
                                    context.user_data.clear()
                                    return
                                
                                loading = await update.message.reply_text("🔄 正在转账...")
                                
                                try:
                                    import httpx
                                    headers = {"Authorization": f"Bearer {token}"}
                                    data = {"user_id": target_user_id, "carrot": amount}
                                    async with httpx.AsyncClient() as client:
                                        response = await client.post(
                                            f"{Config.API_BASE_URL}/pay/transfer",
                                            headers=headers,
                                            json=data,
                                            timeout=10
                                        )
                                    
                                    if response.status_code == 200:
                                        result = response.json()
                                        deduct = result.get('deduct', 0)
                                        carrot = result.get('carrot', 0)
                                        await loading.edit_text(f"✅ 转账成功！\n消耗萝卜：{deduct}\n剩余萝卜：{carrot}")
                                    else:
                                        await loading.edit_text(f"❌ 转账失败，状态码：{response.status_code}")
                                except Exception as e:
                                    logger.error(f"转账失败: {e}")
                                    await loading.edit_text("❌ 转账失败，请稍后重试")
                                
                                # 显示返回菜单
                                from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                                keyboard = [[InlineKeyboardButton("🔙 返回服务商菜单", callback_data="menu_service")]]
                                reply_markup = InlineKeyboardMarkup(keyboard)
                                await update.message.reply_text("操作完成", reply_markup=reply_markup)
                            else:
                                await update.message.reply_text("❌ 转账金额必须在1-50000之间，请重新输入：")
                                return 107  # 继续等待金额输入
                        except ValueError:
                            await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                            return 107  # 继续等待金额输入
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_pay_create_amount':
                    # 处理创建订单金额输入
                    if token:
                        try:
                            amount = int(input_text)
                            if 1 <= amount <= 50000:
                                # 提示用户输入商品名称
                                await update.message.reply_text("💳 请输入商品名称（100字以内）：")
                                # 更新操作状态
                                context.user_data['current_operation'] = 'service_pay_create_name'
                                context.user_data['amount'] = amount
                            else:
                                await update.message.reply_text("❌ 订单金额必须在1-50000之间，请重新输入：")
                                return 108  # 继续等待金额输入
                        except ValueError:
                            await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                            return 108  # 继续等待金额输入
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_pay_create_name':
                    # 处理创建订单商品名称输入
                    if token:
                        amount = context.user_data.get('amount')
                        name = input_text
                        # 提示用户选择支付方式
                        keyboard = [
                            [InlineKeyboardButton("🤖 Telegram机器人支付", callback_data="service_pay_create_telegram_bot")],
                            [InlineKeyboardButton("🌐 网页支付", callback_data="service_pay_create_web")]
                        ]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text("💳 请选择支付方式：", reply_markup=reply_markup)
                        # 存储数据
                        context.user_data['amount'] = amount
                        context.user_data['name'] = name
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_pay_query_no':
                    # 处理查询订单号输入
                    if token:
                        order_no = input_text
                        loading = await update.message.reply_text("🔄 正在查询订单...")
                        
                        try:
                            import httpx
                            headers = {"Authorization": f"Bearer {token}"}
                            async with httpx.AsyncClient() as client:
                                response = await client.get(
                                    f"{Config.API_BASE_URL}/pay/query?no={order_no}",
                                    headers=headers,
                                    timeout=10
                                )
                            
                            logger.info(f"订单查询响应状态码: {response.status_code}")
                            logger.info(f"订单查询响应内容: {response.text}")
                            
                            if response.status_code == 200:
                                order_info = response.json()
                                message = f"📋 订单信息\n\n"
                                message += f"订单号：{order_info.get('no', '未知')}\n"
                                message += f"状态：{order_info.get('pay_status', '未知')}\n"
                                message += f"金额：{order_info.get('price_order', 0)} 萝卜\n"
                                message += f"商品名称：{order_info.get('order_name', '未知')}\n"
                                message += f"支付时间：{order_info.get('time_payed', '未知')}\n"
                                await loading.edit_text(message)
                            elif response.status_code == 404:
                                # 订单不存在，先检查本地数据库
                                from utils.db_helper import get_order_by_platform_no
                                order_info_db = get_order_by_platform_no(order_no)
                                if not order_info_db:
                                    # 尝试在order_no字段中查询
                                    from utils.db_helper import get_db_connection
                                    conn = get_db_connection()
                                    if conn:
                                        try:
                                            import pymysql
                                            with conn.cursor(pymysql.cursors.DictCursor) as cursor:
                                                cursor.execute(
                                                    "SELECT * FROM recharge_orders WHERE order_no = %s",
                                                    (order_no,)
                                                )
                                                order_info_db = cursor.fetchone()
                                        finally:
                                            conn.close()
                                
                                if order_info_db:
                                    message = f"📋 本地订单信息\n\n"
                                    message += f"订单号：{order_info_db.get('order_no')}\n"
                                    message += f"平台订单号：{order_info_db.get('platform_order_no', '未知')}\n"
                                    message += f"状态：{order_info_db.get('status')}\n"
                                    message += f"萝卜数量：{order_info_db.get('carrot_amount')}\n"
                                    message += f"游戏币数量：{order_info_db.get('game_coin_amount')}\n"
                                    message += f"创建时间：{order_info_db.get('created_at')}\n"
                                    await loading.edit_text(message)
                                else:
                                    await loading.edit_text("❌ 订单不存在，请检查订单号是否正确")
                            else:
                                await loading.edit_text(f"❌ 查询失败，状态码：{response.status_code}")
                        except Exception as e:
                            logger.error(f"查询订单失败: {e}")
                            await loading.edit_text("❌ 查询失败，请稍后重试")
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_pay_close_no':
                    # 处理关闭订单号输入
                    if token:
                        order_no = input_text
                        loading = await update.message.reply_text("🔄 正在关闭订单...")
                        
                        try:
                            import httpx
                            headers = {"Authorization": f"Bearer {token}"}
                            async with httpx.AsyncClient() as client:
                                response = await client.put(
                                    f"{Config.API_BASE_URL}/pay/close?no={order_no}",
                                    headers=headers,
                                    timeout=10
                                )
                            
                            if response.status_code == 200:
                                await loading.edit_text("✅ 订单关闭成功！")
                            else:
                                await loading.edit_text(f"❌ 关闭失败，状态码：{response.status_code}")
                        except Exception as e:
                            logger.error(f"关闭订单失败: {e}")
                            await loading.edit_text("❌ 关闭失败，请稍后重试")
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'service_lottery_win_id':
                    # 处理查询中奖列表
                    if token:
                        lottery_id = input_text
                        loading = await update.message.reply_text("🔄 正在查询中奖列表...")
                        
                        try:
                            import httpx
                            headers = {"Authorization": f"Bearer {token}"}
                            async with httpx.AsyncClient() as client:
                                response = await client.get(
                                    f"{Config.API_BASE_URL}/lottery/win?lottery_id={lottery_id}",
                                    headers=headers,
                                    timeout=10
                                )
                            
                            if response.status_code == 200:
                                win_data = response.json()
                                message = "🏆 中奖列表\n\n"
                                message += f"抽奖ID：`#{lottery_id}`\n"
                                message += f"结束时间：{win_data.get('time_end', '未知')}\n"
                                message += f"抽奖价格：{win_data.get('amount', 0)}\n"
                                
                                users = win_data.get('users', [])
                                winning_count = len(users)
                                message += f"中奖个数：{winning_count}\n\n"
                                
                                if users:
                                    message += "中奖名单：\n"
                                    for i, user in enumerate(users, 1):
                                        username = user.get('user_username', user.get('username', '未知'))
                                        user_id = user.get('user_id', '未知')
                                        join_index = user.get('join_index', '未知')
                                        message += f"{i}. `{username}` (id:`{user_id}`) 中奖号码：`{join_index}`\n"
                                else:
                                    message += "暂无中奖用户\n"
                                
                                await loading.edit_text(message, parse_mode="Markdown")
                            else:
                                await loading.edit_text(f"❌ 查询失败，状态码：{response.status_code}", parse_mode="Markdown")
                        except Exception as e:
                            logger.error(f"查询中奖列表失败: {e}")
                            await loading.edit_text("❌ 查询失败，请稍后重试", parse_mode="Markdown")
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'revoke_invite':
                    # 处理撤销邀请
                    if token:
                        target_user_id = input_text
                        loading = await update.message.reply_text("🔄 正在撤销邀请...")
                        
                        try:
                            import httpx
                            headers = {"Authorization": f"Bearer {token}"}
                            data = {"user_id": target_user_id}
                            async with httpx.AsyncClient() as client:
                                response = await client.post(
                                    f"{Config.API_BASE_URL}/invite/revoke",
                                    headers=headers,
                                    json=data,
                                    timeout=10
                                )
                            
                            if response.status_code == 200:
                                result = response.json()
                                remaining = result.get('invite_remaining', 0)
                                await loading.edit_text(f"✅ 撤销邀请成功！剩余邀请次数：{remaining}")
                            else:
                                await loading.edit_text(f"❌ 撤销邀请失败，状态码：{response.status_code}")
                        except Exception as e:
                            logger.error(f"撤销邀请失败: {e}")
                            await loading.edit_text("❌ 撤销邀请失败，请稍后重试")
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
                
                elif operation == 'custom_password':
                    # 处理自定义密码
                    if token:
                        custom_password = input_text
                        loading = await update.message.reply_text("🔄 正在设置自定义密码...")
                        
                        try:
                            import httpx
                            headers = {"Authorization": f"Bearer {token}"}
                            async with httpx.AsyncClient() as client:
                                response = await client.put(
                                    f"{Config.API_BASE_URL}/emya/resetPassword?password={custom_password}",
                                    headers=headers,
                                    timeout=10
                                )
                            
                            if response.status_code == 204:
                                await loading.edit_text("✅ 自定义密码设置成功！")
                            else:
                                await loading.edit_text(f"❌ 设置密码失败，状态码：{response.status_code}")
                        except Exception as e:
                            logger.error(f"设置自定义密码失败: {e}")
                            await loading.edit_text("❌ 设置密码失败，请稍后重试")
                        
                        # 显示返回菜单
                        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
                        keyboard = [[InlineKeyboardButton("🔙 返回密码管理", callback_data="menu_password_management")]]
                        reply_markup = InlineKeyboardMarkup(keyboard)
                        await update.message.reply_text("操作完成", reply_markup=reply_markup)
                        
                        # 清理用户数据
                        context.user_data.clear()
                    else:
                        await update.message.reply_text("❌ 请先登录！发送 /start 登录")
        
        return
    
    # 添加用户输入处理器（包含游戏消息处理）
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))
    
    # 按钮回调（处理所有未被对话捕获的回调）
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # 打印启动信息
    print("=" * 60)
    print("机器人启动成功！")
    print("=" * 60)
    print("可用命令：")
    for cmd, desc in BOT_COMMANDS:
        print(f"   /{cmd:<15} - {desc}")
    print("=" * 60)
    print(f"机器人 @{Config.BOT_USERNAME}")
    print(f"日志文件: {log_filename}")
    print("=" * 60)
    
    logger.info(f"机器人 @{Config.BOT_USERNAME} 启动成功")
    
    # 启动机器人
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()