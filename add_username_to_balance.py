#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为balance表添加username字段
"""

import pymysql
from config import DB_CONFIG

def add_username_to_balance():
    """为balance表添加username字段"""
    try:
        # 连接test数据库
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],  # 这是test数据库
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        print("✅ 连接数据库成功")
        
        # 开始事务
        conn.begin()
        
        # 检查balance表是否存在
        cursor.execute("SHOW TABLES LIKE 'balances'")
        if cursor.fetchone():
            # 检查username字段是否已存在
            cursor.execute("DESCRIBE balances")
            fields = cursor.fetchall()
            field_names = [field['Field'] for field in fields]
            
            if 'username' not in field_names:
                # 添加username字段
                try:
                    cursor.execute("ALTER TABLE balances ADD COLUMN username VARCHAR(255) DEFAULT NULL")
                    print("✅ 为balances表添加username字段成功")
                except Exception as e:
                    print(f"❌ 为balances表添加username字段失败: {e}")
                    conn.rollback()
                    return False
            else:
                print("ℹ️ balances表已经有username字段")
        else:
            print("❌ balances表不存在")
            return False
        
        # 提交事务
        conn.commit()
        print("✅ 数据库操作成功")
        
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
        if 'conn' in locals() and conn.open:
            conn.rollback()
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.open:
            conn.close()
        print("✅ 数据库连接已关闭")

if __name__ == "__main__":
    print("开始为balance表添加username字段...")
    add_username_to_balance()
