import pymysql
from config import DB_CONFIG

# 连接数据库
conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor()

# 查看所有订单信息
print("所有订单信息:")
cursor.execute('SELECT id, order_no, user_id, telegram_user_id, carrot_amount, status FROM recharge_orders')
rows = cursor.fetchall()
for row in rows:
    print(row)

# 查看用户信息
print("\n用户信息:")
cursor.execute('SELECT id, user_id, telegram_id, username FROM users')
rows = cursor.fetchall()
for row in rows:
    print(row)

# 关闭连接
conn.close()
print("\n查询完成")