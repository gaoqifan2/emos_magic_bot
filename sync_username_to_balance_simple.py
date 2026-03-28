#!/usr/bin/env python3
# 同步username到balance表（简化版本）

import pymysql

# 数据库配置
db_config = {
    'host': 'localhost',
    'user': 'root',
    'password': '123456',
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 5
}

def sync_username_to_balance(db_name):
    """同步username到指定数据库的balance表"""
    print(f"开始同步username到 {db_name} 数据库的balance表...")
    
    try:
        # 连接数据库
        connection = pymysql.connect(
            **db_config,
            database=db_name
        )
        print(f"✅ 成功连接到 {db_name} 数据库")
        
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
    finally:
        if 'connection' in locals() and connection:
            connection.close()
            print(f"{db_name} 数据库连接已关闭")

if __name__ == "__main__":
    # 同步到 test 数据库
    sync_username_to_balance('test')
    
    # 同步到 game_db 数据库
    sync_username_to_balance('game_db')
