#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
初始化数据库表结构
"""

import pymysql
from config import DB_CONFIG

def init_database():
    """初始化数据库表结构"""
    print("开始初始化数据库...")
    
    try:
        # 连接数据库
        connection = pymysql.connect(
            **DB_CONFIG,
            connect_timeout=10
        )
        print("✅ 数据库连接成功")
        
        try:
            with connection.cursor() as cursor:
                # 读取并执行 SQL 文件
                with open('create_database.sql', 'r', encoding='utf-8') as f:
                    sql_script = f.read()
                
                # 执行 SQL 脚本
                print("执行数据库初始化脚本...")
                for statement in sql_script.split(';'):
                    statement = statement.strip()
                    if statement:
                        try:
                            cursor.execute(statement)
                            print(f"  ✅ 执行: {statement[:100]}...")
                        except Exception as e:
                            print(f"  ⚠️  执行失败: {statement[:100]}...")
                            print(f"     错误: {e}")
                
                connection.commit()
                print("✅ 数据库初始化完成")
                
                # 显示创建的表
                print("\n创建的表:")
                cursor.execute("SHOW TABLES")
                tables = cursor.fetchall()
                for table in tables:
                    print(f"  - {table[0]}")
                    
        finally:
            connection.close()
            print("✅ 数据库连接已关闭")
            
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        print("提示: 请确保数据库服务正在运行，并且 DB_CONFIG 配置正确")

if __name__ == "__main__":
    init_database()
