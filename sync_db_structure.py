#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
同步数据库结构脚本
将 game_db_test 的表结构同步到 game_db
"""

import pymysql
import os
from config import DB_CONFIG

# 源数据库配置（测试库）
SOURCE_DB = DB_CONFIG.copy()
SOURCE_DB['database'] = 'game_db_test'

# 目标数据库配置（正式库）
TARGET_DB = DB_CONFIG.copy()
TARGET_DB['database'] = 'game_db'

def get_connection(config):
    """获取数据库连接"""
    try:
        connection = pymysql.connect(
            **config,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        return connection
    except Exception as e:
        print(f"连接数据库失败: {e}")
        return None

def get_table_structures(connection, database):
    """获取数据库中所有表的创建语句"""
    print(f"获取 {database} 中的表结构...")
    structures = {}
    
    try:
        with connection.cursor() as cursor:
            # 获取所有表名
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            
            for table in tables:
                table_name = list(table.values())[0]
                print(f"  获取表 {table_name} 的结构...")
                
                # 获取表的创建语句
                cursor.execute(f"SHOW CREATE TABLE {table_name}")
                result = cursor.fetchone()
                create_statement = result['Create Table']
                
                # 替换表名（如果需要）
                # 这里不需要替换，因为我们要创建相同的表
                structures[table_name] = create_statement
                
    except Exception as e:
        print(f"获取表结构失败: {e}")
    
    return structures

def create_tables(connection, database, structures):
    """在目标数据库中创建表"""
    print(f"在 {database} 中创建表结构...")
    
    try:
        with connection.cursor() as cursor:
            for table_name, create_statement in structures.items():
                print(f"  创建表 {table_name}...")
                
                # 先删除表（如果存在）
                try:
                    cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                except Exception as e:
                    print(f"  删除表 {table_name}失败: {e}")
                
                # 创建表
                try:
                    cursor.execute(create_statement)
                    print(f"  ✅ 表 {table_name} 创建成功")
                except Exception as e:
                    print(f"  ❌ 表 {table_name} 创建失败: {e}")
            
            # 提交事务
            connection.commit()
            print(f"✅ 所有表结构同步完成！")
            
    except Exception as e:
        print(f"创建表失败: {e}")
        connection.rollback()

def main():
    """主函数"""
    print("开始同步数据库结构...")
    print("=" * 60)
    
    # 连接源数据库
    source_conn = get_connection(SOURCE_DB)
    if not source_conn:
        print("❌ 无法连接源数据库")
        return
    
    # 连接目标数据库
    target_conn = get_connection(TARGET_DB)
    if not target_conn:
        print("❌ 无法连接目标数据库")
        source_conn.close()
        return
    
    try:
        # 获取源数据库表结构
        structures = get_table_structures(source_conn, SOURCE_DB['database'])
        
        if not structures:
            print("❌ 未获取到表结构")
            return
        
        print(f"\n获取到 {len(structures)} 个表的结构:")
        for table in structures.keys():
            print(f"  - {table}")
        
        # 在目标数据库中创建表
        create_tables(target_conn, TARGET_DB['database'], structures)
        
    finally:
        # 关闭连接
        if source_conn:
            source_conn.close()
        if target_conn:
            target_conn.close()

if __name__ == "__main__":
    main()
