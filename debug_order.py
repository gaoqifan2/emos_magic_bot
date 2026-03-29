from config import DB_CONFIG
import pymysql

order_no = '20260330035538payt5INR'

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
    
    # 查询 platform_order_no
    print(f"=== 查询 platform_order_no = '{order_no}' ===")
    cursor.execute("SELECT * FROM recharge_orders WHERE platform_order_no = %s", (order_no,))
    result = cursor.fetchone()
    if result:
        print(f"找到订单: {result}")
    else:
        print("未找到订单")
    
    # 查询 order_no
    print(f"\n=== 查询 order_no = '{order_no}' ===")
    cursor.execute("SELECT * FROM recharge_orders WHERE order_no = %s", (order_no,))
    result = cursor.fetchone()
    if result:
        print(f"找到订单: {result}")
    else:
        print("未找到订单")
    
    # 查询最近的10个订单
    print("\n=== 最近的10个订单 ===")
    cursor.execute("SELECT order_no, platform_order_no, status, created_at FROM recharge_orders ORDER BY created_at DESC LIMIT 10")
    for row in cursor.fetchall():
        print(f"order_no: {row['order_no']}, platform_order_no: {row['platform_order_no']}, status: {row['status']}, created_at: {row['created_at']}")
    
    conn.close()
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
