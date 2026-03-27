#!/usr/bin/env python3
# 测试基本的导入和初始化

print("开始测试基本导入和初始化...")

try:
    # 测试基本导入
    import logging
    import sys
    import os
    from datetime import datetime, timedelta, timezone
    
    print("✓ 基本模块导入成功")
    
    # 测试config导入
    from config import Config, BOT_COMMANDS, SERVICE_PROVIDER_TOKEN, user_tokens, GROUP_ALLOWED_COMMANDS
    print("✓ config 导入成功")
    print(f"  BOT_USERNAME: {Config.BOT_USERNAME}")
    print(f"  API_BASE_URL: {Config.API_BASE_URL}")
    
    # 测试数据库初始化
    from app.database import init_db
    print("✓ app.database 导入成功")
    
    # 测试utils.db_helper导入
    from utils.db_helper import ensure_user_exists, create_recharge_order
    print("✓ utils.db_helper 导入成功")
    
    # 测试handlers.common导入
    from handlers.common import (
        start, menu_command, help_command, cancel_command,
        button_callback, post_init,
        WAITING_REDPACKET_ID, WAITING_LOTTERY_CANCEL_ID
    )
    print("✓ handlers.common 导入成功")
    
    # 测试app.config导入
    from app.config import load_tokens_from_db, save_token_to_db, get_user_info
    print("✓ app.config 导入成功")
    
    print("\n所有导入测试通过！")
    
    # 测试数据库初始化
    print("\n测试数据库初始化...")
    try:
        init_db()
        print("✓ 数据库初始化成功")
    except Exception as e:
        print(f"✗ 数据库初始化失败: {e}")
        import traceback
        traceback.print_exc()
    
    # 测试加载tokens
    print("\n测试加载tokens...")
    try:
        load_tokens_from_db()
        print("✓ 加载tokens成功")
    except Exception as e:
        print(f"✗ 加载tokens失败: {e}")
        import traceback
        traceback.print_exc()
        
    print("\n测试完成!")
    
except Exception as e:
    print(f"✗ 测试失败: {e}")
    import traceback
    traceback.print_exc()