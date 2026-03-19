#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
检查数据库表结构
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

def check_db_structure():
    """检查数据库表结构"""
    logger.info("开始检查数据库表结构...")
    
    try:
        # 连接数据库
        conn = pymysql.connect(**DB_CONFIG)
        logger.info("✅ 数据库连接成功！")
        
        with conn.cursor() as cursor:
            # 检查 users 表结构
            logger.info("检查 users 表结构...")
            cursor.execute("DESCRIBE users")
            users_columns = cursor.fetchall()
            logger.info("users 表列信息:")
            for column in users_columns:
                logger.info(f"  {column[0]} - {column[1]} - {column[2]}")
            
            # 检查 balances 表结构
            logger.info("检查 balances 表结构...")
            cursor.execute("DESCRIBE balances")
            balances_columns = cursor.fetchall()
            logger.info("balances 表列信息:")
            for column in balances_columns:
                logger.info(f"  {column[0]} - {column[1]} - {column[2]}")
        
        conn.close()
        logger.info("✅ 数据库表结构检查完成！")
        return True
    except Exception as e:
        logger.error(f"❌ 检查数据库表结构失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    check_db_structure()
