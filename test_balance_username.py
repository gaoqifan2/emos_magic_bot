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

# 检查balance表数据
def check_balance_table():
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        cursor = connection.cursor()
        
        # 检查表结构
        print('=== balances 表结构 ===')
        cursor.execute('DESCRIBE balances')
        for row in cursor:
            print(f'  {row["Field"]}: {row["Type"]} {row["Null"]}')
        
        # 检查表数据
        print('\n=== balances 表数据 ===')
        cursor.execute('SELECT * FROM balances')
        rows = cursor.fetchall()
        
        if rows:
            for row in rows:
                print(f'  user_id: {row["user_id"]}, balance: {row["balance"]}, username: {row["username"] if row["username"] else "NULL"}')
        else:
            print('  表中没有数据')
        
        # 检查users表数据
        print('\n=== users 表数据 ===')
        cursor.execute('SELECT user_id, username, telegram_id FROM users')
        user_rows = cursor.fetchall()
        
        if user_rows:
            for row in user_rows:
                print(f'  user_id: {row["user_id"]}, username: {row["username"]}, telegram_id: {row["telegram_id"]}')
        else:
            print('  表中没有数据')
            
    finally:
        connection.close()

if __name__ == "__main__":
    check_balance_table()