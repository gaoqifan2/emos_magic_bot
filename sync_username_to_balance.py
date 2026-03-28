import pymysql

def sync_username():
    try:
        # 连接到正式数据库
        conn = pymysql.connect(
            host='66.235.105.125',
            port=3306,
            user='root',
            password='H_fans200109~',
            db='game_db',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        
        print("=== Syncing username from users to balances ===")
        
        # 获取所有用户信息
        cursor.execute('SELECT id, username FROM users WHERE username IS NOT NULL')
        users = cursor.fetchall()
        
        print(f"Found {len(users)} users with username")
        
        # 同步每个用户的username到balance表
        updated_count = 0
        for user in users:
            user_id = user['id']
            username = user['username']
            
            # 更新balance表的username
            cursor.execute(
                'UPDATE balances SET username = %s WHERE user_id = %s',
                (username, user_id)
            )
            
            if cursor.rowcount > 0:
                print(f"✓ Updated user {user_id}: {username}")
                updated_count += 1
            else:
                # 如果balance记录不存在，创建一个
                cursor.execute(
                    'INSERT INTO balances (user_id, balance, username) VALUES (%s, %s, %s)',
                    (user_id, 0, username)
                )
                print(f"✓ Created balance record for user {user_id}: {username}")
                updated_count += 1
        
        conn.commit()
        print(f"\n=== Sync completed ===")
        print(f"Updated {updated_count} balance records")
        
        # 验证同步结果
        print("\n=== Verifying sync results ===")
        cursor.execute('SELECT u.id, u.username as user_username, b.username as balance_username FROM users u LEFT JOIN balances b ON u.id = b.user_id WHERE u.username IS NOT NULL')
        results = cursor.fetchall()
        
        for result in results:
            user_id = result['id']
            user_username = result['user_username']
            balance_username = result['balance_username']
            
            if user_username == balance_username:
                print(f"✓ User {user_id}: {user_username} (synchronized)")
            else:
                print(f"✗ User {user_id}: user={user_username}, balance={balance_username} (not synchronized)")
        
    except Exception as e:
        print(f"Error: {e}")
        import traceback
        print(f"Error stack: {traceback.format_exc()}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    sync_username()
