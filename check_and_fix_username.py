import pymysql
from config import DB_CONFIG

# 连接数据库
def get_db_connection():
    try:
        connection = pymysql.connect(
            **DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor,
            connect_timeout=5
        )
        return connection
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

# 检查并修复username字段
def check_and_fix():
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        cursor = connection.cursor()
        
        # 检查users表
        print('=== users 表数据 ===')
        cursor.execute('SELECT user_id, username FROM users')
        users = cursor.fetchall()
        for user in users:
            print(f'  user_id: {user["user_id"]}, username: "{user["username"]}"')
        
        # 检查balance表
        print('\n=== balance 表数据 ===')
        cursor.execute('SELECT user_id, username FROM balances')
        balances = cursor.fetchall()
        for balance in balances:
            print(f'  user_id: {balance["user_id"]}, username: "{balance["username"]}"')
        
        # 修复balance表的username
        print('\n修复balance表的username...')
        for user in users:
            user_id = user["user_id"]
            username = user["username"]
            
            # 更新balance表
            cursor.execute(
                'UPDATE balances SET username = %s WHERE user_id = %s',
                (username, user_id)
            )
            print(f'  更新 user_id={user_id} 的 username 为 "{username}"')
        
        connection.commit()
        
        # 再次检查结果
        print('\n=== 修复后的balance表数据 ===')
        cursor.execute('SELECT user_id, username FROM balances')
        balances = cursor.fetchall()
        for balance in balances:
            print(f'  user_id: {balance["user_id"]}, username: "{balance["username"]}"')
        
        print('\n修复完成！')
        
    except Exception as e:
        print(f"修复过程中出错: {e}")
        connection.rollback()
    finally:
        connection.close()

if __name__ == "__main__":
    check_and_fix()