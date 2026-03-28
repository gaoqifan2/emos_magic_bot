import pymysql

def check_database():
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
        
        print("=== Checking users table ===")
        # 检查users表结构
        cursor.execute('DESCRIBE users')
        print("Users table structure:")
        for row in cursor.fetchall():
            print(row)
        
        # 检查users表数据
        cursor.execute('SELECT id, user_id, username, first_name FROM users')
        print("\nUsers data:")
        users = cursor.fetchall()
        for row in users:
            print(row)
        
        print("\n=== Checking balances table ===")
        # 检查balances表结构
        cursor.execute('DESCRIBE balances')
        print("Balances table structure:")
        for row in cursor.fetchall():
            print(row)
        
        # 检查balances表数据
        cursor.execute('SELECT user_id, username, balance FROM balances')
        print("\nBalances data:")
        balances = cursor.fetchall()
        for row in balances:
            print(row)
        
        # 检查username同步情况
        print("\n=== Checking username synchronization ===")
        for user in users:
            user_id = user['id']
            user_username = user['username']
            
            # 查找对应的balance记录
            for balance in balances:
                if balance['user_id'] == user_id:
                    balance_username = balance['username']
                    if user_username == balance_username:
                        print(f"✓ User {user_id}: username synchronized - {user_username}")
                    else:
                        print(f"✗ User {user_id}: username NOT synchronized - user: {user_username}, balance: {balance_username}")
                    break
        
    except Exception as e:
        print(f"Error: {e}")
    finally:
        if 'conn' in locals():
            conn.close()

if __name__ == "__main__":
    check_database()
