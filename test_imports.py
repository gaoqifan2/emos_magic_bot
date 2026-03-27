#!/usr/bin/env python3
# 测试导入是否正常

print("开始测试导入...")

try:
    import logging
    print("✓ logging 导入成功")
except Exception as e:
    print(f"✗ logging 导入失败: {e}")

try:
    import sys
    print("✓ sys 导入成功")
except Exception as e:
    print(f"✗ sys 导入失败: {e}")

try:
    import os
    print("✓ os 导入成功")
except Exception as e:
    print(f"✗ os 导入失败: {e}")

try:
    import httpx
    print("✓ httpx 导入成功")
except Exception as e:
    print(f"✗ httpx 导入失败: {e}")

try:
    from datetime import datetime, timedelta, timezone
    print("✓ datetime 导入成功")
except Exception as e:
    print(f"✗ datetime 导入失败: {e}")

try:
    # 测试 imghdr 兼容模块
    sys.modules['imghdr'] = __import__('utils.imghdr_compat')
    import imghdr
    print("✓ imghdr 兼容模块导入成功")
except Exception as e:
    print(f"✗ imghdr 兼容模块导入失败: {e}")

try:
    from telegram import Update, BotCommand, InlineKeyboardButton, InlineKeyboardMarkup
    print("✓ telegram 导入成功")
except Exception as e:
    print(f"✗ telegram 导入失败: {e}")

try:
    from telegram.ext import (
        Application,
        CommandHandler,
        MessageHandler,
        CallbackQueryHandler,
        ConversationHandler,
        filters,
        ContextTypes
    )
    print("✓ telegram.ext 导入成功")
except Exception as e:
    print(f"✗ telegram.ext 导入失败: {e}")

try:
    from config import Config, BOT_COMMANDS, SERVICE_PROVIDER_TOKEN, user_tokens, GROUP_ALLOWED_COMMANDS
    print("✓ config 导入成功")
except Exception as e:
    print(f"✗ config 导入失败: {e}")

try:
    from utils.db_helper import ensure_user_exists, create_recharge_order
    print("✓ utils.db_helper 导入成功")
except Exception as e:
    print(f"✗ utils.db_helper 导入失败: {e}")

try:
    from handlers.common import (
        start, menu_command, help_command, cancel_command,
        button_callback, post_init,
        WAITING_REDPACKET_ID, WAITING_LOTTERY_CANCEL_ID
    )
    print("✓ handlers.common 导入成功")
except Exception as e:
    print(f"✗ handlers.common 导入失败: {e}")

print("\n测试完成!")