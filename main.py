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