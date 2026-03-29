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

# 修复balance表的username字段
def fix_balance_username():
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        cursor = connection.cursor()
        
        # 1. 清理旧的自增id格式的balance记录
        print('清理旧的自增id格式的balance记录...')
        cursor.execute('DELETE FROM balances WHERE user_id REGEXP "^[0-9]+$"')
        deleted = cursor.rowcount
        print(f'删除了 {deleted} 条旧记录')
        
        # 2. 修复users表中的username为None的问题
        print('\n修复users表中的username为None的问题...')
        cursor.execute('UPDATE users SET username = "" WHERE username IS NULL OR username = "None"')
        updated_users = cursor.rowcount
        print(f'更新了 {updated_users} 条用户记录')
        
        # 3. 同步balance表的username字段
        print('\n同步balance表的username字段...')
        cursor.execute('''
            UPDATE balances b
            JOIN users u ON b.user_id = u.user_id
            SET b.username = u.username
            WHERE b.username IS NULL OR b.username = "None"
        ''')
        updated_balances = cursor.rowcount
        print(f'更新了 {updated_balances} 条balance记录')
        
        # 4. 检查结果
        print('\n=== 修复后的balance表数据 ===')
        cursor.execute('SELECT * FROM balances')
        rows = cursor.fetchall()
        
        if rows:
            for row in rows:
                print(f'  user_id: {row["user_id"]}, balance: {row["balance"]}, username: {row["username"] if row["username"] else "NULL"}')
        else:
            print('  表中没有数据')
        
        connection.commit()
        print('\n修复完成！')
        
    except Exception as e:
        print(f"修复过程中出错: {e}")
        connection.rollback()
    finally:
        connection.close()

if __name__ == "__main__":
    fix_balance_username()