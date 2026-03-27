import mysql.connector

# 连接数据库
cnx = mysql.connector.connect(
    host='66.235.105.125',
    port=3306,
    user='root',
    password='H_fans200109~',
    database='game_db_test'
)
cursor = cnx.cursor(dictionary=True)

# 查询用户记录
print('用户记录:')
cursor.execute('SELECT * FROM users LIMIT 5')
for row in cursor:
    print(row)

# 查询充值订单
print('\n充值订单:')
cursor.execute('SELECT * FROM recharge_orders LIMIT 5')
for row in cursor:
    print(row)

# 查询提现记录
print('\n提现记录:')
cursor.execute('SELECT * FROM withdrawal_records LIMIT 5')
for row in cursor:
    print(row)

# 关闭连接
cursor.close()
cnx.close()
