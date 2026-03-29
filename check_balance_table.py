import mysql.connector

# 连接数据库
cnx = mysql.connector.connect(
    host='localhost',
    user='root',
    password='Aa123456!',
    database='game_db'
)

cursor = cnx.cursor()

# 检查表结构
print('=== balances 表结构 ===')
cursor.execute('DESCRIBE balances')
for row in cursor:
    print(f'  {row[0]}: {row[1]} {"YES" if row[2] == "YES" else "NO"}')

# 检查表数据
print('\n=== balances 表数据 ===')
cursor.execute('SELECT * FROM balances LIMIT 10')
for row in cursor:
    print(f'  user_id: {row[0]}, balance: {row[1]}, username: {row[2] if row[2] else "NULL"}')

cursor.close()
cnx.close()