import pymysql
from config import DB_CONFIG

# 连接数据库
conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor()

# 查看余额表结构
print("余额表结构:")
cursor.execute('DESCRIBE balances')
for row in cursor.fetchall():
    print(row)

# 查看余额数据
print("\n余额数据:")
cursor.execute('SELECT * FROM balances')
rows = cursor.fetchall()
for row in rows:
    print(row)

# 关闭连接
conn.close()
print("\n查询完成")