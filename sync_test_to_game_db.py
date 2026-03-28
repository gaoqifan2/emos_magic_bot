#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将test数据库结构同步到game_db数据库
"""

import pymysql
from config import DB_CONFIG

def sync_test_to_game_db():
    """将test数据库结构同步到game_db数据库"""
    try:
        # 连接test数据库（源数据库）
        source_conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],  # 这是test数据库
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        source_cursor = source_conn.cursor()
        print("✅ 连接test数据库成功")
        
        # 连接game_db数据库（目标数据库）
        target_conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database='game_db',  # 这是正式数据库
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        target_cursor = target_conn.cursor()
        print("✅ 连接game_db数据库成功")
        
        # 开始事务
        target_conn.begin()
        
        # 1. 获取test数据库中的所有表
        source_cursor.execute("SHOW TABLES")
        tables = source_cursor.fetchall()
        table_names = [list(table.values())[0] for table in tables]
        print(f"\n📋 test数据库中的表: {table_names}")
        
        # 2. 同步每个表的结构
        for table_name in table_names:
            print(f"\n🔄 同步表: {table_name}")
            
            if table_name == 'users':
                # 对于users表，使用ALTER TABLE来同步结构
                try:
                    # 获取test数据库中users表的字段
                    source_cursor.execute("DESCRIBE users")
                    source_fields = source_cursor.fetchall()
                    source_field_names = [field['Field'] for field in source_fields]
                    
                    # 获取game_db数据库中users表的字段
                    target_cursor.execute("DESCRIBE users")
                    target_fields = target_cursor.fetchall()
                    target_field_names = [field['Field'] for field in target_fields]
                    
                    # 检查并添加缺失的字段
                    for field in source_fields:
                        field_name = field['Field']
                        if field_name not in target_field_names:
                            # 构建添加字段的SQL
                            field_type = field['Type']
                            null = 'NULL' if field['Null'] == 'YES' else 'NOT NULL'
                            default = f"DEFAULT {field['Default']}" if field['Default'] is not None else ''
                            extra = field['Extra'] if field['Extra'] else ''
                            
                            alter_sql = f"ALTER TABLE users ADD COLUMN `{field_name}` {field_type} {null} {default} {extra}"
                            # 移除多余的空格
                            alter_sql = ' '.join(alter_sql.split())
                            
                            target_cursor.execute(alter_sql)
                            print(f"  ✅ 为game_db中的users表添加字段: {field_name}")
                    
                    print(f"  ✅ 同步game_db中的users表结构成功")
                except Exception as e:
                    print(f"  ❌ 同步game_db中的users表结构失败: {e}")
                    target_conn.rollback()
                    return False
            else:
                # 对于其他表，使用删除再创建的方式
                # 获取表的创建语句
                source_cursor.execute(f"SHOW CREATE TABLE `{table_name}`")
                create_table_result = source_cursor.fetchone()
                create_table_sql = create_table_result['Create Table']
                
                # 先删除目标数据库中的表（如果存在）
                try:
                    target_cursor.execute(f"DROP TABLE IF EXISTS `{table_name}`")
                    print(f"  🗑️ 删除game_db中的{table_name}表成功")
                except Exception as e:
                    print(f"  ⚠️ 删除game_db中的{table_name}表失败: {e}")
                
                # 在目标数据库中创建表
                try:
                    target_cursor.execute(create_table_sql)
                    print(f"  ✅ 在game_db中创建{table_name}表成功")
                except Exception as e:
                    print(f"  ❌ 在game_db中创建{table_name}表失败: {e}")
                    target_conn.rollback()
                    return False
        
        # 3. 同步jackpot_pool的初始数据
        try:
            # 检查test数据库中jackpot_pool是否有数据
            source_cursor.execute("SELECT * FROM jackpot_pool")
            jackpot_data = source_cursor.fetchall()
            
            if jackpot_data:
                # 清空目标数据库中的jackpot_pool
                target_cursor.execute("DELETE FROM jackpot_pool")
                # 插入初始数据
                for data in jackpot_data:
                    target_cursor.execute(
                        "INSERT INTO jackpot_pool (pool_amount) VALUES (%s)",
                        (data['pool_amount'],)
                    )
                print("  ✅ 同步jackpot_pool初始数据成功")
            else:
                # 如果test数据库中没有数据，插入默认值
                target_cursor.execute("INSERT INTO jackpot_pool (pool_amount) VALUES (0)")
                print("  ✅ 初始化jackpot_pool默认数据成功")
        except Exception as e:
            print(f"  ❌ 同步jackpot_pool数据失败: {e}")
            target_conn.rollback()
            return False
        
        # 提交事务
        target_conn.commit()
        print("\n✅ 数据库结构同步成功")
        
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
        if 'target_conn' in locals() and target_conn.open:
            target_conn.rollback()
        return False
    finally:
        if 'source_cursor' in locals():
            source_cursor.close()
        if 'source_conn' in locals() and source_conn.open:
            source_conn.close()
        if 'target_cursor' in locals():
            target_cursor.close()
        if 'target_conn' in locals() and target_conn.open:
            target_conn.close()
        print("\n✅ 数据库连接已关闭")

if __name__ == "__main__":
    print("开始将test数据库结构同步到game_db数据库...")
    sync_test_to_game_db()
