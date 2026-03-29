import sys
sys.path.insert(0, 'd:\\emos_magic_bot')

from app.database import add_recharge_order, get_db_connection
from datetime import datetime, timedelta, timezone
import logging

# 设置日志
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# 测试数据
order_no = "R20260330TEST001"
platform_order_no = "20260330testpay001"
user_id = "eK98R5PEMs"  # f1negege 的 user_id
username = "f1negege"
telegram_user_id = 7520240928
carrot_amount = 10
game_coin_amount = 100
pay_url = "https://test.com/pay"
beijing_tz = timezone(timedelta(hours=8))
expire_time = datetime.now(beijing_tz) + timedelta(minutes=5)

print("=== 测试插入订单 ===")
print(f"order_no: {order_no}")
print(f"platform_order_no: {platform_order_no}")
print(f"user_id: {user_id}")
print(f"username: {username}")
print(f"telegram_user_id: {telegram_user_id}")
print()

# 尝试插入
result = add_recharge_order(
    order_no=order_no,
    user_id=user_id,
    username=username,
    telegram_user_id=telegram_user_id,
    carrot_amount=carrot_amount,
    game_coin_amount=game_coin_amount,
    platform_order_no=platform_order_no,
    pay_url=pay_url,
    expire_time=expire_time
)

print(f"\n插入结果: {result}")

# 查询是否插入成功
if result:
    print("\n=== 查询刚插入的订单 ===")
    conn = get_db_connection()
    if conn:
        try:
            with conn.cursor() as cursor:
                cursor.execute("SELECT * FROM recharge_orders WHERE order_no = %s", (order_no,))
                row = cursor.fetchone()
                if row:
                    print(f"找到订单: {row}")
                else:
                    print("订单未找到！")
        finally:
            conn.close()
