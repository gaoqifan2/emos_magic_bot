from utils.db_helper import update_recharge_order_status

# 测试订单状态更新
order_no = "20260318004430payAYz7T"  # 从数据库中获取的订单号
try:
    result = update_recharge_order_status(
        platform_order_no=order_no,
        status='success',
        game_coin_amount=10
    )
    print(f"更新结果: {result}")
    if result:
        print("订单状态更新成功！")
    else:
        print("订单状态更新失败！")
except Exception as e:
    print(f"更新过程中出错: {e}")
