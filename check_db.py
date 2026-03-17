import pymysql
from config import DB_CONFIG

# 连接数据库
conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor()

# 查看users表结构
print("Users表结构:")
cursor.execute('DESCRIBE users')
for row in cursor.fetchall():
    print(row)

# 查看是否有数据
print("\nUsers表数据:")
cursor.execute('SELECT * FROM users LIMIT 5')
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(row)
else:
    print("暂无数据")

# 关闭连接
conn.close()
print("\n数据库检查完成")