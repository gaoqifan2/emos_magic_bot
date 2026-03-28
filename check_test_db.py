#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查test数据库的结构
"""

import pymysql
from config import DB_CONFIG

def check_test_db():
    """检查test数据库的结构"""
    try:
        # 连接test数据库
        print(f"尝试连接数据库: {DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}")
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
        
        # 检查数据库中的表
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"\n📋 test数据库中的表:")
        for table in tables:
            table_name = list(table.values())[0]
            print(f"  - {table_name}")
        
        # 检查users表结构
        if any('users' in list(table.values())[0] for table in tables):
            print("\n📋 users表字段结构:")
            cursor.execute("DESCRIBE users")
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
        
        # 检查其他表结构
        for table in tables:
            table_name = list(table.values())[0]
            if table_name != 'users':
                print(f"\n📋 {table_name}表字段结构:")
                cursor.execute(f"DESCRIBE {table_name}")
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
        
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.open:
            conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    print("开始检查test数据库结构...")
    check_test_db()
