#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
创建每日赢取记录表
"""

import pymysql
from config import DB_CONFIG


def create_daily_win_records_table():
    """创建每日赢取记录表"""
    try:
        # 连接数据库
        connection = pymysql.connect(**DB_CONFIG)
        cursor = connection.cursor()
        
        # 创建表
        sql = """
        CREATE TABLE IF NOT EXISTS daily_win_records (
            user_id VARCHAR(50) PRIMARY KEY,
            username VARCHAR(100),
            win_amount INT DEFAULT 0,
            win_date DATE,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            INDEX idx_win_date (win_date)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """
        
        cursor.execute(sql)
        connection.commit()
        
        print("✅ 成功创建 daily_win_records 表")
        
    except Exception as e:
        print(f"❌ 创建表失败: {e}")
    finally:
        if 'connection' in locals():
            connection.close()


if __name__ == "__main__":
    create_daily_win_records_table()
