#!/usr/bin/env python3
# 从game_db_test同步数据库结构到game_db

import pymysql

# 数据库配置
db_config = {
    'host': '66.235.105.125',
    'port': 3306,
    'user': 'root',
    'password': 'H_fans200109~',
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 10
}

def get_table_structure(connection, table_name):
    """获取表结构"""
    with connection.cursor() as cursor:
        cursor.execute(f"SHOW CREATE TABLE {table_name}")
        result = cursor.fetchone()
        return result['Create Table']

def sync_db_structure():
    """同步数据库结构"""
    print("开始从game_db_test同步数据库结构到game_db...")
    
    try:
        # 连接源数据库 game_db_test
        source_conn = pymysql.connect(
            **db_config,
            database='game_db_test'
        )
        print("✅ 成功连接到 game_db_test 数据库")
        
        # 连接目标数据库 game_db
        target_conn = pymysql.connect(
            **db_config,
            database='game_db'
        )
        print("✅ 成功连接到 game_db 数据库")
        
        # 获取源数据库中的所有表
        with source_conn.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            table_names = [table['Tables_in_game_db_test'] for table in tables]
        
        print(f"找到 {len(table_names)} 个表：{table_names}")
        
        # 同步每个表的结构
        for table_name in table_names:
            print(f"\n同步表结构: {table_name}")
            
            # 获取表结构
            create_table_sql = get_table_structure(source_conn, table_name)
            
            # 在目标数据库中创建或替换表
            with target_conn.cursor() as cursor:
                # 先删除表（如果存在）
                cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                # 创建新表
                cursor.execute(create_table_sql)
                print(f"✅ 同步表结构: {table_name} 成功")
        
        target_conn.commit()
        print("\n🎉 数据库结构同步完成！")
        
    except Exception as e:
        print(f"❌ 同步过程中出错: {e}")
    finally:
        if 'source_conn' in locals() and source_conn:
            source_conn.close()
        if 'target_conn' in locals() and target_conn:
            target_conn.close()
        print("数据库连接已关闭")

def fix_balance_username():
    """修复balance表中的username字段"""
    print("\n开始修复balance表中的username字段...")
    
    try:
        # 连接数据库
        connection = pymysql.connect(
            **db_config,
            database='game_db'
        )
        print("✅ 成功连接到 game_db 数据库")
        
        with connection.cursor() as cursor:
            # 从users表获取username并更新到balance表
            cursor.execute('''
                UPDATE balances b
                JOIN users u ON b.user_id = u.id
                SET b.username = u.username
                WHERE b.username IS NULL
            ''')
            
            affected_rows = cursor.rowcount
            print(f"✅ 修复了 {affected_rows} 条记录的username字段")
        
        connection.commit()
        print("🎉 balance表username字段修复完成！")
        
    except Exception as e:
        print(f"❌ 修复过程中出错: {e}")
    finally:
        if 'connection' in locals() and connection:
            connection.close()
        print("数据库连接已关闭")

if __name__ == "__main__":
    # 同步数据库结构
    sync_db_structure()
    
    # 修复balance表中的username字段
    fix_balance_username()
