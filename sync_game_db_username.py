#!/usr/bin/env python3
# 同步game_db数据库中的balance表username字段

import pymysql
from config import DB_CONFIG

def sync_game_db_username():
    """同步game_db数据库中的balance表username字段"""
    print("开始同步game_db数据库中的balance表username字段...")
    
    # 复制DB_CONFIG并修改数据库名称
    config = DB_CONFIG.copy()
    config['database'] = 'game_db'
    
    try:
        connection = pymysql.connect(
            **config,
            cursorclass=pymysql.cursors.DictCursor
        )
        print("✅ 成功连接到game_db数据库")
        
        with connection.cursor() as cursor:
            # 从users表获取所有用户信息
            cursor.execute('SELECT id, username FROM users')
            users = cursor.fetchall()
            
            print(f"找到 {len(users)} 个用户")
            
            for user in users:
                user_id = user['id']
                username = user['username']
                
                print(f"同步用户 {user_id} 的username: {username}")
                
                # 检查balance表中是否存在该用户的记录
                cursor.execute('SELECT * FROM balances WHERE user_id = %s', (user_id,))
                balance_result = cursor.fetchone()
                
                if balance_result:
                    # 如果存在，更新username
                    cursor.execute('UPDATE balances SET username = %s WHERE user_id = %s', (username, user_id))
                    print(f"✅ 更新用户 {user_id} 的balance记录")
                else:
                    # 如果不存在，创建新记录
                    cursor.execute('INSERT INTO balances (user_id, balance, username) VALUES (%s, %s, %s)', (user_id, 0, username))
                    print(f"✅ 为用户 {user_id} 创建balance记录")
            
            connection.commit()
            print(f"🎉 成功同步 {len(users)} 个用户的username到game_db数据库的balance表")
            
    except Exception as e:
        print(f"❌ 同步过程中出错: {e}")
    finally:
        if 'connection' in locals() and connection:
            connection.close()
            print("数据库连接已关闭")

def check_game_db_balance():
    """检查game_db数据库中balance表的状态"""
    print("\n检查game_db数据库中balance表的状态...")
    
    # 复制DB_CONFIG并修改数据库名称
    config = DB_CONFIG.copy()
    config['database'] = 'game_db'
    
    try:
        connection = pymysql.connect(
            **config,
            cursorclass=pymysql.cursors.DictCursor
        )
        print("✅ 成功连接到game_db数据库")
        
        with connection.cursor() as cursor:
            # 检查balance表中的数据
            cursor.execute('SELECT * FROM balances')
            balances = cursor.fetchall()
            
            print(f"balance表中有 {len(balances)} 条记录")
            for balance in balances:
                print(f"user_id: {balance['user_id']}, balance: {balance['balance']}, username: {balance['username']}")
                
    except Exception as e:
        print(f"❌ 检查过程中出错: {e}")
    finally:
        if 'connection' in locals() and connection:
            connection.close()
            print("数据库连接已关闭")

if __name__ == "__main__":
    # 检查game_db数据库中balance表的状态
    check_game_db_balance()
    
    # 同步game_db数据库中的balance表username字段
    sync_game_db_username()
    
    # 再次检查game_db数据库中balance表的状态
    check_game_db_balance()
