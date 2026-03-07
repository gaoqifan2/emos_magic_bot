#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import logging
import sys
import os
from datetime import datetime
from telegram import Update, BotCommand
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    CallbackQueryHandler,
    ConversationHandler,
    filters
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

from config import Config, BOT_COMMANDS
from handlers.common import (
    start, menu_command, help_command, cancel_command,
    button_callback, post_init,
    WAITING_REDPACKET_ID, WAITING_LOTTERY_CANCEL_ID
)
from handlers.redpacket import (
    redpocket_command, redpocket_process, cancel_redpacket,
    WAITING_CARROT, WAITING_NUMBER, WAITING_BLESSING, WAITING_PASSWORD
)
from handlers.redpacket_query import check_redpacket_command, get_redpacket_id
from games.lottery import (
    lottery_command, lottery_process,
    WAITING_LOTTERY_NAME, WAITING_LOTTERY_DESC, WAITING_LOTTERY_START,
    WAITING_LOTTERY_END, WAITING_LOTTERY_AMOUNT, WAITING_LOTTERY_NUMBER,
    WAITING_LOTTERY_RULE_CARROT, WAITING_LOTTERY_RULE_SIGN, WAITING_LOTTERY_PRIZES,
    handle_bodys_choice, get_lottery_bodys, handle_prize_choice
)
from games.lottery_cancel import lottery_cancel_command, get_lottery_cancel_id
from ranks.carrot_rank import rank_carrot_command
from ranks.upload_rank import rank_upload_command
from ranks.playing_rank import playing_command

# 创建 logs 文件夹
if not os.path.exists('logs'):
    os.makedirs('logs')

# 生成日志文件名
log_filename = f"logs/bot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO,
    handlers=[
        logging.StreamHandler(sys.stdout),
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
    
    # 创建应用
    application = Application.builder() \
        .token(Config.BOT_TOKEN) \
        .post_init(post_init) \
        .build()
    
    # ===== 基本命令 =====
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("menu", menu_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    
    # ===== 红包对话 =====
    redpocket_conv = ConversationHandler(
        entry_points=[
            CommandHandler("redpocket", redpocket_command),
            CallbackQueryHandler(redpocket_command, pattern="^menu_redpocket$")
        ],
        states={
            WAITING_CARROT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, redpocket_process),
                MessageHandler(filters.PHOTO, redpocket_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_NUMBER: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, redpocket_process),
                MessageHandler(filters.PHOTO, redpocket_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_BLESSING: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, redpocket_process),
                MessageHandler(filters.PHOTO, redpocket_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
            WAITING_PASSWORD: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, redpocket_process),
                MessageHandler(filters.PHOTO, redpocket_process),
                CallbackQueryHandler(button_callback, pattern="^cancel_operation$")
            ],
        },
        fallbacks=[CommandHandler("cancel", cancel_redpacket)]
    )
    application.add_handler(redpocket_conv)
    
    # ===== 红包查询对话 =====
    redpocket_query_conv = ConversationHandler(
        entry_points=[
            CommandHandler("check_redpacket", check_redpacket_command),
            CallbackQueryHandler(check_redpacket_command, pattern="^menu_check_redpacket$")
        ],
        states={
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
            CommandHandler("lottery", lottery_command),
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
            CommandHandler("lottery_cancel", lottery_cancel_command),
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
    application.add_handler(CommandHandler("playing", playing_command))
    application.add_handler(CommandHandler("rank_carrot", rank_carrot_command))
    application.add_handler(CommandHandler("rank_upload", rank_upload_command))
    
    # 处理用户输入
    async def handle_user_input(update: Update, context: ContextTypes.DEFAULT_TYPE):
        """处理用户输入的信息"""
        user_id = update.effective_user.id
        input_text = update.message.text.strip()
        
        if 'current_operation' in context.user_data:
            operation = context.user_data['current_operation']
            token = context.user_data.get('token')
            
            if operation == 'change_pseudonym':
                # 处理笔名更新
                if token:
                    loading = await update.message.reply_text("🔄 正在更新笔名...")
                    
                    try:
                        import httpx
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
                        logger.error(f"更新笔名失败: {e}")
                        await loading.edit_text("❌ 更新笔名失败，请稍后重试")
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'invite_user':
                # 处理邀请用户
                if token:
                    loading = await update.message.reply_text("🔄 正在邀请用户...")
                    
                    try:
                        import httpx
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
                        logger.error(f"邀请用户失败: {e}")
                        await loading.edit_text("❌ 邀请用户失败，请稍后重试")
                    
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
                                import httpx
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
                                logger.error(f"转赠失败: {e}")
                                await loading.edit_text("❌ 转赠失败，请稍后重试")
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
                            loading = await update.message.reply_text("🔄 正在创建充值订单...")
                            
                            try:
                                import httpx
                                headers = {"Authorization": f"Bearer {token}"}
                                data = {"game_id": "1", "carrot_amount": amount}
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
                                    await loading.edit_text(f"✅ 充值成功！\n兑换游戏币：{game_coin}")
                                else:
                                    await loading.edit_text(f"❌ 充值失败，状态码：{response.status_code}")
                            except Exception as e:
                                logger.error(f"充值失败: {e}")
                                await loading.edit_text("❌ 充值失败，请稍后重试")
                        else:
                            await update.message.reply_text("❌ 充值金额必须在1-50000之间，请重新输入：")
                            return 104  # 继续等待金额输入
                    except ValueError:
                        await update.message.reply_text("❌ 请输入有效的数字，请重新输入：")
                        return 104  # 继续等待金额输入
                    
                    # 清理用户数据
                    context.user_data.clear()
                else:
                    await update.message.reply_text("❌ 请先登录！发送 /start 登录")
            
            elif operation == 'service_withdraw_amount':
                # 处理提现金额输入
                if token:
                    try:
                        amount = int(input_text)
                        if 10 <= amount <= 50000 and amount % 10 == 0:
                            loading = await update.message.reply_text("🔄 正在创建提现订单...")
                            
                            try:
                                import httpx
                                headers = {"Authorization": f"Bearer {token}"}
                                data = {"game_coin_amount": amount}
                                async with httpx.AsyncClient() as client:
                                    response = await client.post(
                                        f"{Config.API_BASE_URL}/game/withdraw",
                                        headers=headers,
                                        json=data,
                                        timeout=10
                                    )
                                
                                if response.status_code == 200:
                                    result = response.json()
                                    carrot_amount = result.get('carrot_amount', 0)
                                    await loading.edit_text(f"✅ 提现成功！\n兑换萝卜：{carrot_amount}")
                                else:
                                    await loading.edit_text(f"❌ 提现失败，状态码：{response.status_code}")
                            except Exception as e:
                                logger.error(f"提现失败: {e}")
                                await loading.edit_text("❌ 提现失败，请稍后重试")
                        else:
                            await update.message.reply_text("❌ 提现金额必须在10-50000之间且为10的倍数，请重新输入：")
                            return 105  # 继续等待金额输入
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
                                logger.error(f"游戏充值失败: {e}")
                                await loading.edit_text("❌ 游戏充值失败，请稍后重试")
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
        
        return ConversationHandler.END
    
    # 添加用户输入处理器
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_input))
    
    # 按钮回调（处理所有未被对话捕获的回调）
    application.add_handler(CallbackQueryHandler(button_callback))
    
    # 打印启动信息
    print("=" * 60)
    print("🤖 机器人启动成功！")
    print("=" * 60)
    print("📱 可用命令：")
    for cmd, desc in BOT_COMMANDS:
        print(f"   /{cmd:<15} - {desc}")
    print("=" * 60)
    print(f"🚀 机器人 @{Config.BOT_USERNAME}")
    print(f"📝 日志文件: {log_filename}")
    print("=" * 60)
    
    logger.info(f"🚀 机器人 @{Config.BOT_USERNAME} 启动成功")
    
    # 启动机器人
    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    main()