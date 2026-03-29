from config import DB_CONFIG
import pymysql

order_no = '20260330041040payXxtZD'

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
    
    # 查询这个订单
    print(f"=== 查询 platform_order_no = '{order_no}' ===")
    cursor.execute("SELECT * FROM recharge_orders WHERE platform_order_no = %s", (order_no,))
    result = cursor.fetchone()
    if result:
        print(f"✅ 找到订单:")
        print(f"  id: {result['id']}")
        print(f"  order_no: {result['order_no']}")
        print(f"  platform_order_no: {result['platform_order_no']}")
        print(f"  user_id: {result['user_id']}")
        print(f"  username: {result['username']}")
        print(f"  carrot_amount: {result['carrot_amount']}")
        print(f"  game_coin_amount: {result['game_coin_amount']}")
        print(f"  status: {result['status']}")
        print(f"  created_at: {result['created_at']}")
    else:
        print("❌ 订单未找到")
    
    # 查询最近的5个订单
    print("\n=== 最近的5个订单 ===")
    cursor.execute("SELECT order_no, platform_order_no, username, status, created_at FROM recharge_orders ORDER BY created_at DESC LIMIT 5")
    for row in cursor.fetchall():
        print(f"订单号: {row['order_no']}, 平台订单号: {row['platform_order_no']}, 用户名: {row['username']}, 状态: {row['status']}, 创建时间: {row['created_at']}")
    
    conn.close()
except Exception as e:
    print(f"错误: {e}")
    import traceback
    traceback.print_exc()
