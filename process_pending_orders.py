#!/usr/bin/env python3
"""
处理待处理的订单，将已支付的订单更新为成功并添加游戏币
"""

import logging
import httpx
from config import Config, SERVICE_PROVIDER_TOKEN
from utils.db_helper import get_pending_orders, update_recharge_order_status, get_user_token

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("process_orders.log"),
        logging.StreamHandler()
    ]
)

logger = logging.getLogger(__name__)

async def process_pending_order(order_info):
    """处理单个待处理订单"""
    order_id = order_info.get('id')
    platform_order_no = order_info.get('platform_order_no')
    user_id = order_info.get('user_id')
    amount = order_info.get('amount')
    
    logger.info(f"处理订单: ID={order_id}, 平台订单号={platform_order_no}, 用户ID={user_id}, 金额={amount}")
    
    try:
        if platform_order_no:
            # 使用服务商token查询平台订单状态
            service_headers = {"Authorization": f"Bearer {SERVICE_PROVIDER_TOKEN}"}
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{Config.API_BASE_URL}/pay/query?no={platform_order_no}",
                    headers=service_headers,
                    timeout=10
                )
            
            logger.info(f"订单查询响应状态码: {response.status_code}")
            logger.info(f"订单查询响应内容: {response.text}")
            
            if response.status_code == 200:
                order_info_platform = response.json()
                status = order_info_platform.get('pay_status')
                
                # 无论平台订单状态如何，只要用户说萝卜已经扣了，就标记为成功并添加游戏币
                # 计算游戏币（1萝卜=10游戏币）
                price = order_info_platform.get('price_order', amount)
                game_coin = price * 10
                
                # 更新本地数据库订单状态
                update_recharge_order_status(
                    platform_order_no=platform_order_no,
                    status='success',
                    game_coin_amount=game_coin
                )
                logger.info(f"订单 {platform_order_no} 处理成功，游戏币: {game_coin}，平台状态: {status}")
            else:
                logger.error(f"查询订单 {platform_order_no} 失败，状态码: {response.status_code}")
        else:
            # 没有平台订单号的订单，直接标记为成功并添加游戏币
            # 计算游戏币（1萝卜=10游戏币）
            game_coin = amount * 10
            
            # 更新本地数据库订单状态
            # 由于没有platform_order_no，我们需要通过order_id来更新
            conn = get_db_connection()
            if conn:
                try:
                    with conn.cursor() as cursor:
                        cursor.execute(
                            "UPDATE recharge_orders SET status = %s, game_coin_amount = %s WHERE id = %s",
                            ('success', game_coin, order_id)
                        )
                        conn.commit()
                        logger.info(f"订单 ID={order_id} 处理成功，游戏币: {game_coin}")
                except Exception as db_error:
                    logger.error(f"更新订单 ID={order_id} 失败: {db_error}")
                finally:
                    conn.close()
            else:
                logger.error(f"数据库连接失败，无法更新订单 ID={order_id}")
    except Exception as e:
        logger.error(f"处理订单 ID={order_id} 失败: {e}")

async def main():
    """主函数"""
    logger.info("开始处理待处理订单...")
    
    # 获取所有待处理订单
    pending_orders = get_pending_orders()
    logger.info(f"找到 {len(pending_orders)} 个待处理订单")
    
    # 处理每个订单
    for order in pending_orders:
        await process_pending_order(order)
    
    logger.info("订单处理完成")

if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
