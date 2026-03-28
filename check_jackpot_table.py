#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查jackpot_pool表的结构
"""

import pymysql
from config import DB_CONFIG

def check_jackpot_table():
    """检查jackpot_pool表的结构"""
    try:
        # 连接数据库
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],  # test数据库
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        print("✅ 连接数据库成功")
        
        # 检查jackpot_pool表结构
        print("\n📋 jackpot_pool表字段结构:")
        cursor.execute("DESCRIBE jackpot_pool")
        fields = cursor.fetchall()
        # 打印表头
        print("+----------------------+------------------+------+-----+-------------------+-------------------+")
        print("| Field                | Type             | Null | Key | Default           | Extra             |")
        print("+----------------------+------------------+------+-----+-------------------+-------------------+")
        # 打印字段信息
        for field in fields:
            field_name = field['Field']
            field_type = field['Type']
            null = 'YES' if field['Null'] else 'NO'
            key = field['Key'] if field['Key'] else ''
            default = field['Default'] if field['Default'] is not None else 'None'
            extra = field['Extra'] if field['Extra'] else ''
            print(f"| {field_name:20} | {field_type:16} | {null:4} | {key:3} | {default:17} | {extra:17} |")
        print("+----------------------+------------------+------+-----+-------------------+-------------------+")
        
        # 检查jackpot_pool表中的数据
        print("\n📋 jackpot_pool表数据:")
        cursor.execute("SELECT * FROM jackpot_pool")
        data = cursor.fetchall()
        if data:
            for row in data:
                print(row)
        else:
            print("  表中无数据")
        
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.open:
            conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    print("开始检查jackpot_pool表结构...")
    check_jackpot_table()
