#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
将测试数据库 game_db_test 复制到正式数据库 game_db
"""

import pymysql
from config import DB_CONFIG

def get_db_connection(db_name):
    """获取数据库连接"""
    try:
        config = DB_CONFIG.copy()
        config['database'] = db_name
        conn = pymysql.connect(**config)
        return conn
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def get_all_tables(conn):
    """获取数据库中的所有表"""
    try:
        with conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = [row[0] for row in cursor.fetchall()]
        return tables
    except Exception as e:
        print(f"获取表列表失败: {e}")
        return []

def drop_all_tables(conn, tables):
    """删除所有表"""
    try:
        with conn.cursor() as cursor:
            # 禁用外键检查
            cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
            
            for table in tables:
                cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
                print(f"删除表: {table}")
            
            # 启用外键检查
            cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
            conn.commit()
        return True
    except Exception as e:
        print(f"删除表失败: {e}")
        conn.rollback()
        return False

def copy_tables(source_conn, target_conn):
    """复制表结构和数据"""
    try:
        # 获取源数据库的所有表
        source_tables = get_all_tables(source_conn)
        if not source_tables:
            print("源数据库没有表")
            return False
        
        # 删除目标数据库的所有表
        target_tables = get_all_tables(target_conn)
        if target_tables:
            if not drop_all_tables(target_conn, target_tables):
                return False
        
        with source_conn.cursor() as source_cursor, target_conn.cursor() as target_cursor:
            for table in source_tables:
                print(f"\n复制表: {table}")
                
                # 获取表结构
                source_cursor.execute(f"SHOW CREATE TABLE `{table}`")
                create_table_sql = source_cursor.fetchone()[1]
                
                # 在目标数据库创建表
                target_cursor.execute(create_table_sql)
                print(f"  ✅ 创建表结构")
                
                # 获取数据
                source_cursor.execute(f"SELECT * FROM `{table}`")
                rows = source_cursor.fetchall()
                
                if rows:
                    # 获取列名
                    source_cursor.execute(f"SHOW COLUMNS FROM `{table}`")
                    columns = [row[0] for row in source_cursor.fetchall()]
                    column_str = ', '.join([f"`{col}`" for col in columns])
                    placeholders = ', '.join(['%s'] * len(columns))
                    
                    # 插入数据
                    insert_sql = f"INSERT INTO `{table}` ({column_str}) VALUES ({placeholders})"
                    target_cursor.executemany(insert_sql, rows)
                    print(f"  ✅ 插入 {len(rows)} 条数据")
                else:
                    print(f"  ✅ 表为空，跳过数据复制")
        
        target_conn.commit()
        return True
    except Exception as e:
        print(f"复制表失败: {e}")
        import traceback
        print(traceback.format_exc())
        target_conn.rollback()
        return False

def main():
    """主函数"""
    print("开始复制数据库...")
    print(f"源数据库: game_db_test")
    print(f"目标数据库: game_db")
    print("=" * 50)
    
    # 连接源数据库
    source_conn = get_db_connection('game_db_test')
    if not source_conn:
        return
    
    # 连接目标数据库
    target_conn = get_db_connection('game_db')
    if not target_conn:
        source_conn.close()
        return
    
    try:
        # 复制表
        if copy_tables(source_conn, target_conn):
            print("\n" + "=" * 50)
            print("✅ 数据库复制成功！")
        else:
            print("\n" + "=" * 50)
            print("❌ 数据库复制失败！")
    finally:
        # 关闭连接
        source_conn.close()
        target_conn.close()
        print("数据库连接已关闭")

if __name__ == "__main__":
    main()
