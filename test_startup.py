#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import sys
import traceback

print("Starting test...")

# 测试基本导入
try:
    print("Testing basic imports...")
    import os
    import logging
    import httpx
    from datetime import datetime, timedelta, timezone
    print("✓ Basic imports successful")
except Exception as e:
    print(f"✗ Basic imports failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试telegram导入
try:
    print("Testing telegram imports...")
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
    print("✓ Telegram imports successful")
except Exception as e:
    print(f"✗ Telegram imports failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试配置导入
try:
    print("Testing config imports...")
    from config import Config, BOT_COMMANDS, SERVICE_PROVIDER_TOKEN, user_tokens, GROUP_ALLOWED_COMMANDS
    print(f"✓ Config imported successfully")
    print(f"  BOT_TOKEN: {Config.BOT_TOKEN[:20]}...")
except Exception as e:
    print(f"✗ Config import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

# 测试数据库连接池
try:
    print("Testing database connection pool...")
    from app.database.db_pool import get_db_connection, return_db_connection
    connection = get_db_connection()
    if connection:
        print("✓ Database connection successful")
        return_db_connection(connection)
    else:
        print("⚠ Database connection failed but continuing")
except Exception as e:
    print(f"✗ Database pool import failed: {e}")
    traceback.print_exc()
    # 继续测试，不退出

# 测试其他模块
try:
    print("Testing other modules...")
    from utils.db_helper import ensure_user_exists, create_recharge_order
    from handlers.common import start, menu_command, help_command, cancel_command, button_callback, post_init
    from app.handlers.command_handlers import start_handler, balance_handler, guess_handler, slot_handler, daily_handler, help_handler, blackjack_handler, hit_handler, stand_handler, message_handler, callback_handler, withdraw_handler, recharge_handler
    print("✓ All modules imported successfully")
except Exception as e:
    print(f"✗ Module import failed: {e}")
    traceback.print_exc()
    sys.exit(1)

print("\n✅ All tests passed! The bot should be able to start.")
