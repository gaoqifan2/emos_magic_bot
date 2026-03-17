import pymysql
from config import DB_CONFIG

# 连接数据库
conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor()

# 查看recharge_orders表结构
print("Recharge_orders表结构:")
cursor.execute('DESCRIBE recharge_orders')
for row in cursor.fetchall():
    print(row)

# 查看recharge_orders表数据
print("\nRecharge_orders表数据:")
cursor.execute('SELECT * FROM recharge_orders LIMIT 10')
rows = cursor.fetchall()
if rows:
    for row in rows:
        print(row)
else:
    print("暂无数据")

# 关闭连接
conn.close()
print("\n数据库检查完成")