import pymysql
import logging
from config import DB_CONFIG

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def get_db_connection():
    """获取数据库连接"""
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
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None

def verify_recharge_orders():
    """验证recharge_orders表结构"""
    conn = get_db_connection()
    if not conn:
        return
    
    try:
        with conn.cursor() as cursor:
            print("\n=== recharge_orders 表结构 ===")
            cursor.execute("DESCRIBE recharge_orders")
            columns = cursor.fetchall()
            for col in columns:
                print(f"{col['Field']:20} {col['Type']:20} {col['Null']:10} {col['Key']:10} {col['Default']} {col['Extra']}")
            
            print("\n=== recharge_orders 最新数据 ===")
            cursor.execute("SELECT * FROM recharge_orders ORDER BY created_at DESC LIMIT 5")
            orders = cursor.fetchall()
            for order in orders:
                print(f"\n订单号: {order.get('order_no')}")
                print(f"用户ID: {order.get('user_id')}")
                print(f"用户名: {order.get('username')}")
                print(f"充值萝卜: {order.get('carrot_amount')}")
                print(f"状态: {order.get('status')}")
                print(f"创建时间: {order.get('created_at')}")
            
    except Exception as e:
        logger.error(f"验证失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
    finally:
        conn.close()

if __name__ == "__main__":
    verify_recharge_orders()
