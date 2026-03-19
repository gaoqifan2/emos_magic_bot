#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
简单测试数据库操作
"""

import logging
import pymysql
from config import DB_CONFIG

# 设置日志
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

def simple_test():
    """简单测试数据库操作"""
    logger.info("开始简单测试数据库操作...")
    
    try:
        # 连接数据库
        conn = pymysql.connect(**DB_CONFIG)
        logger.info("✅ 数据库连接成功！")
        
        with conn.cursor() as cursor:
            # 插入测试用户
            test_user_id = "test_user_123"
            test_telegram_id = 123456789
            test_token = "test_token_1234567890"
            test_username = "test_user"
            
            logger.info(f"尝试插入测试用户: user_id={test_user_id}, telegram_id={test_telegram_id}")
            
            # 检查用户是否存在
            cursor.execute("SELECT id FROM users WHERE user_id = %s OR telegram_id = %s", (test_user_id, test_telegram_id))
            result = cursor.fetchone()
            
            if result:
                logger.info(f"用户已存在，ID: {result[0]}")
                # 更新用户信息
                cursor.execute(
                    "UPDATE users SET token = %s, username = %s WHERE id = %s",
                    (test_token, test_username, result[0])
                )
                conn.commit()
                logger.info("✅ 用户信息已更新！")
            else:
                # 创建新用户
                cursor.execute(
                    "INSERT INTO users (user_id, telegram_id, token, username) VALUES (%s, %s, %s, %s)",
                    (test_user_id, test_telegram_id, test_token, test_username)
                )
                user_id = cursor.lastrowid
                conn.commit()
                logger.info(f"✅ 新用户创建成功，ID: {user_id}")
                
                # 创建余额记录
                cursor.execute(
                    "INSERT INTO balances (user_id, balance) VALUES (%s, 0)",
                    (user_id,)
                )
                conn.commit()
                logger.info("✅ 余额记录创建成功！")
            
            # 查询用户信息
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (test_user_id,))
            user_info = cursor.fetchone()
            if user_info:
                logger.info(f"✅ 用户信息查询成功: {user_info}")
            
            # 查询余额信息
            cursor.execute("SELECT * FROM balances WHERE user_id = %s", (user_info[0],))
            balance_info = cursor.fetchone()
            if balance_info:
                logger.info(f"✅ 余额信息查询成功: {balance_info}")
        
        conn.close()
        logger.info("✅ 简单测试完成！")
        return True
    except Exception as e:
        logger.error(f"❌ 测试失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    simple_test()
