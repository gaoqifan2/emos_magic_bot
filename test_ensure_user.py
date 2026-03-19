#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
测试 ensure_user_exists 函数
"""

import logging
from utils.db_helper import ensure_user_exists, get_db_connection

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def test_db_connection():
    """测试数据库连接"""
    logger.info("开始测试数据库连接...")
    conn = get_db_connection()
    if conn:
        logger.info("✅ 数据库连接成功！")
        conn.close()
        return True
    else:
        logger.error("❌ 数据库连接失败！")
        return False

def test_ensure_user():
    """测试 ensure_user_exists 函数"""
    logger.info("开始测试 ensure_user_exists 函数...")
    
    # 测试数据
    emos_user_id = "test_user_123"
    token = "test_token_1234567890"
    telegram_id = 123456789
    username = "test_user"
    first_name = "Test"
    last_name = "User"
    
    logger.info(f"测试数据: emos_user_id={emos_user_id}, telegram_id={telegram_id}")
    
    try:
        logger.info("开始调用 ensure_user_exists 函数...")
        # 调用 ensure_user_exists 函数
        local_user_id = ensure_user_exists(
            emos_user_id=emos_user_id,
            token=token,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        
        logger.info(f"✅ ensure_user_exists 函数调用成功，local_user_id={local_user_id}")
        
        # 再次调用，测试更新功能
        logger.info("开始测试更新功能...")
        new_token = "new_test_token_1234567890"
        local_user_id_updated = ensure_user_exists(
            emos_user_id=emos_user_id,
            token=new_token,
            telegram_id=telegram_id,
            username=username,
            first_name=first_name,
            last_name=last_name
        )
        
        logger.info(f"✅ ensure_user_exists 函数更新成功，local_user_id={local_user_id_updated}")
        
        return True
    except Exception as e:
        logger.error(f"❌ ensure_user_exists 函数调用失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    # 先测试数据库连接
    if test_db_connection():
        # 再测试 ensure_user_exists 函数
        test_ensure_user()
    else:
        logger.error("数据库连接失败，无法测试 ensure_user_exists 函数")
