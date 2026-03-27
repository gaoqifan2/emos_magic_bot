from app.database import get_db_connection

# 连接数据库
connection = get_db_connection()
if connection:
    try:
        with connection.cursor() as cursor:
            # 查询用户记录
            print('用户记录:')
            cursor.execute('SELECT * FROM users LIMIT 5')
            # 获取列名
            columns = [desc[0] for desc in cursor.description]
            # 打印结果
            for row in cursor:
                row_dict = dict(zip(columns, row))
                print(row_dict)
            
            # 查询充值订单
            print('\n充值订单:')
            cursor.execute('SELECT * FROM recharge_orders LIMIT 5')
            columns = [desc[0] for desc in cursor.description]
            for row in cursor:
                row_dict = dict(zip(columns, row))
                print(row_dict)
            
            # 查询提现记录
            print('\n提现记录:')
            cursor.execute('SELECT * FROM withdrawal_records LIMIT 5')
            columns = [desc[0] for desc in cursor.description]
            for row in cursor:
                row_dict = dict(zip(columns, row))
                print(row_dict)
    finally:
        connection.close()
else:
    print('无法连接到数据库')
