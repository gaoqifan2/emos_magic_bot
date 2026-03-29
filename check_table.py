from config import DB_CONFIG
import pymysql

try:
    conn = pymysql.connect(
        host=DB_CONFIG['host'],
        port=DB_CONFIG['port'],
        user=DB_CONFIG['user'],
        password=DB_CONFIG['password'],
        database=DB_CONFIG['database'],
        charset=DB_CONFIG['charset'],
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()
    cursor.execute('DESCRIBE recharge_orders')
    print("=== recharge_orders 表结构 ===")
    for col in cursor.fetchall():
        print(f"{col['Field']:20} {col['Type']}")
    
    print("\n=== 最近的充值订单 ===")
    cursor.execute('SELECT order_no, platform_order_no, username, created_at FROM recharge_orders ORDER BY created_at DESC LIMIT 5')
    for row in cursor.fetchall():
        print(f"订单号: {row['order_no']}, 平台订单号: {row['platform_order_no']}, 用户名: {row['username']}, 创建时间: {row['created_at']}")
    
    conn.close()
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
