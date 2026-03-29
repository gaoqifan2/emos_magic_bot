#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
清空测试数据库所有表的数据
"""

import pymysql
from config import DB_CONFIG

def clear_database():
    """清空数据库所有表"""
    try:
        # 连接数据库
        connection = pymysql.connect(
            host=DB_CONFIG["host"],
            port=DB_CONFIG["port"],
            user=DB_CONFIG["user"],
            password=DB_CONFIG["password"],
            database=DB_CONFIG["database"],
            charset=DB_CONFIG["charset"],
            cursorclass=pymysql.cursors.DictCursor
        )
        
        print(f"✅ 连接到数据库: {DB_CONFIG['database']}")
        
        with connection.cursor() as cursor:
            # 获取所有表
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            if not tables:
                print("⚠️ 数据库中没有表")
                return
            
            print(f"\n📋 发现 {len(tables)} 个表:")
            
            # 禁用外键检查
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            # 清空每个表
            for table_info in tables:
                table_name = list(table_info.values())[0]
                print(f"\n🗑️  正在清空表: {table_name}")
                
                # 获取表中的记录数
                cursor.execute(f"SELECT COUNT(*) as count FROM `{table_name}`")
                count = cursor.fetchone()['count']
                print(f"   记录数: {count}")
                
                # 清空表
                cursor.execute(f"TRUNCATE TABLE `{table_name}`")
                print(f"   ✅ 已清空")
            
            # 启用外键检查
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            
            # 提交事务
            connection.commit()
            
            print(f"\n✅ 成功清空 {len(tables)} 个表")
            
    except Exception as e:
        print(f"❌ 错误: {e}")
        import traceback
        traceback.print_exc()
    finally:
        if 'connection' in locals():
            connection.close()
            print("\n🔌 数据库连接已关闭")

if __name__ == "__main__":
    print("=" * 60)
    print("⚠️  警告: 这将清空测试数据库的所有数据!")
    print("=" * 60)
    print(f"\n数据库: {DB_CONFIG['database']}")
    print(f"主机: {DB_CONFIG['host']}")
    print("\n" + "=" * 60)
    print("\n")
    clear_database()
