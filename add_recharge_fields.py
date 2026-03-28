#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
为users表添加累计充值金额字段
"""

import pymysql
from config import DB_CONFIG

def add_recharge_fields():
    """为users表添加累计充值金额字段"""
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
        print("✅ 连接test数据库成功")
        
        # 开始事务
        conn.begin()
        
        # 为users表添加累计充值金额字段
        try:
            # 检查字段是否已存在
            cursor.execute("DESCRIBE users")
            fields = cursor.fetchall()
            field_names = [field['Field'] for field in fields]
            
            if 'total_recharge' not in field_names:
                # 添加累计充值金额字段
                cursor.execute("ALTER TABLE users ADD COLUMN total_recharge DECIMAL(10,2) DEFAULT 0")
                print("✅ 为users表添加total_recharge字段成功")
            else:
                print("ℹ️ users表已经有total_recharge字段")
        except Exception as e:
            print(f"❌ 为users表添加字段失败: {e}")
            conn.rollback()
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
    print("开始为users表添加累计充值金额字段...")
    add_recharge_fields()
