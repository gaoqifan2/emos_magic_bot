#!/usr/bin/env python3
# 同步用户数据到balance表

from app.database import get_db_connection


def sync_user_to_balance():
    """同步用户数据到balance表，确保所有用户都有对应的balance记录"""
    print("开始同步用户数据到balance表...")
    
    connection = get_db_connection()
    if not connection:
        print("❌ 数据库连接失败，无法同步")
        return
    
    try:
        with connection.cursor() as cursor:
            # 检查所有用户是否都有对应的balance记录
            cursor.execute('''
                SELECT u.id, u.user_id, u.first_name 
                FROM users u
                LEFT JOIN balances b ON u.id = b.user_id
                WHERE b.user_id IS NULL
            ''')
            users_without_balance = cursor.fetchall()
            
            if users_without_balance:
                print(f"发现 {len(users_without_balance)} 个用户没有balance记录，正在创建...")
                for user in users_without_balance:
                    user_id = user['id']
                    user_emos_id = user['user_id']
                    user_name = user['first_name']
                    
                    # 为用户创建balance记录，默认余额为0
                    cursor.execute('''
                        INSERT INTO balances (user_id, balance, username) 
                        VALUES (%s, %s, %s)
                    ''', (user_id, 0, user_name))
                    
                    print(f"✅ 为用户 {user_name} (ID: {user_emos_id}) 创建了balance记录")
                
                connection.commit()
                print(f"🎉 成功为 {len(users_without_balance)} 个用户创建了balance记录")
            else:
                print("✅ 所有用户都已有balance记录，无需同步")
                
    except Exception as e:
        print(f"❌ 同步过程中出错: {e}")
        connection.rollback()
    finally:
        connection.close()
        print("数据库连接已关闭")


if __name__ == "__main__":
    sync_user_to_balance()
