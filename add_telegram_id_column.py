#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
向 users 表添加 telegram_id 列
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

def add_telegram_id_column():
    """向 users 表添加 telegram_id 列"""
    logger.info("开始向 users 表添加 telegram_id 列...")
    
    try:
        # 连接数据库
        conn = pymysql.connect(**DB_CONFIG)
        logger.info("✅ 数据库连接成功！")
        
        with conn.cursor() as cursor:
            # 检查 users 表是否已有 telegram_id 列
            cursor.execute("DESCRIBE users")
            columns = [column[0] for column in cursor.fetchall()]
            
            if 'telegram_id' not in columns:
                # 添加 telegram_id 列
                cursor.execute("ALTER TABLE users ADD COLUMN telegram_id bigint(20) DEFAULT NULL COMMENT 'Telegram用户ID'")
                conn.commit()
                logger.info("✅ 成功向 users 表添加 telegram_id 列！")
            else:
                logger.info("ℹ️ users 表已经有 telegram_id 列，无需添加")
        
        conn.close()
        logger.info("✅ 操作完成！")
        return True
    except Exception as e:
        logger.error(f"❌ 添加 telegram_id 列失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    add_telegram_id_column()
