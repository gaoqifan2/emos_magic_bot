from app.database import get_db_connection

# 连接数据库
connection = get_db_connection()
if connection:
    try:
        with connection.cursor(dictionary=True) as cursor:
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
    finally:
        connection.close()
else:
    print('无法连接到数据库')
