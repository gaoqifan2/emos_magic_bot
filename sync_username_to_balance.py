#!/usr/bin/env python3
# 同步username到balance表

import pymysql
from config import DB_CONFIG

def get_db_connection_db(db_name):
    """获取指定数据库的连接"""
    try:
        # 复制DB_CONFIG并修改数据库名称
        config = DB_CONFIG.copy()
        config['database'] = db_name
        connection = pymysql.connect(
            **config,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        return connection
    except Exception as e:
        print(f"连接 {db_name} 数据库失败: {e}")
        return None

def sync_username_to_balance():
    """同步username到balance表"""
    print("开始同步username到balance表...")
    
    # 同步到 test 数据库
    print("\n===== 同步到 test 数据库 =====")
    sync_to_database('test')
    
    # 同步到 game_db 数据库
    print("\n===== 同步到 game_db 数据库 =====")
    sync_to_database('game_db')

def sync_to_database(db_name):
    """同步到指定数据库"""
    connection = get_db_connection_db(db_name)
    if not connection:
        print(f"❌ {db_name} 数据库连接失败，无法同步")
        return
    
    try:
        with connection.cursor() as cursor:
            # 获取所有用户信息
            cursor.execute('SELECT id, username FROM users')
            users = cursor.fetchall()
            
            print(f"找到 {len(users)} 个用户")
            
            for user in users:
                user_id = user['id']
                username = user['username']
                
                print(f"同步用户 {user_id} 的username: {username}")
                
                # 更新balance表中的username
                cursor.execute('''
                    UPDATE balances 
                    SET username = %s 
                    WHERE user_id = %s
                ''', (username, user_id))
            
            connection.commit()
            print(f"🎉 成功同步 {len(users)} 个用户的username到 {db_name} 数据库的balance表")
            
    except Exception as e:
        print(f"❌ 同步过程中出错: {e}")
        connection.rollback()
    finally:
        connection.close()
        print(f"{db_name} 数据库连接已关闭")

if __name__ == "__main__":
    sync_username_to_balance()
