#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
修改 users 表的 user_id 列类型为字符串
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

def modify_user_id_column():
    """修改 users 表的 user_id 列类型为字符串"""
    logger.info("开始修改 users 表的 user_id 列类型...")
    
    try:
        # 连接数据库
        conn = pymysql.connect(**DB_CONFIG)
        logger.info("✅ 数据库连接成功！")
        
        with conn.cursor() as cursor:
            # 先添加一个临时列
            cursor.execute("ALTER TABLE users ADD COLUMN user_id_str varchar(255) DEFAULT NULL COMMENT '用户ID（字符串）'")
            conn.commit()
            logger.info("✅ 成功添加临时列 user_id_str！")
            
            # 然后修改 user_id 列的类型
            cursor.execute("ALTER TABLE users MODIFY COLUMN user_id varchar(255) DEFAULT NULL COMMENT '用户ID'")
            conn.commit()
            logger.info("✅ 成功修改 user_id 列类型为 varchar(255)！")
            
            # 删除临时列
            cursor.execute("ALTER TABLE users DROP COLUMN user_id_str")
            conn.commit()
            logger.info("✅ 成功删除临时列 user_id_str！")
        
        conn.close()
        logger.info("✅ 操作完成！")
        return True
    except Exception as e:
        logger.error(f"❌ 修改 user_id 列类型失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return False

if __name__ == "__main__":
    modify_user_id_column()
