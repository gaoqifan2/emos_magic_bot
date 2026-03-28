import logging
import pymysql
from typing import Optional, Dict, Any
from datetime import datetime

from config import DB_CONFIG

logger = logging.getLogger(__name__)

def get_db_connection():
    """获取数据库连接"""
    try:
        conn = pymysql.connect(**DB_CONFIG)
        return conn
    except Exception as e:
        logger.error(f"数据库连接失败: {e}")
        return None

def ensure_user_exists(emos_user_id: str, token: str, telegram_id: Optional[int] = None, username: Optional[str] = None, 
                      first_name: Optional[str] = None, last_name: Optional[str] = None) -> Optional[int]:
    """确保用户存在，如果不存在则创建
    
    Returns:
        用户ID（本地数据库的id）
    """
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as cursor:
            # 检查用户是否存在
            if telegram_id:
                cursor.execute("SELECT id FROM users WHERE user_id = %s OR telegram_id = %s", (emos_user_id, telegram_id))
            else:
                cursor.execute("SELECT id FROM users WHERE user_id = %s", (emos_user_id,))
            result = cursor.fetchone()
            
            if result:
                user_id = result[0]
                # 更新用户信息
                cursor.execute(
                    "UPDATE users SET token = %s, telegram_id = %s, username = %s, first_name = %s, last_name = %s WHERE id = %s",
                    (token, telegram_id, username, first_name, last_name, user_id)
                )
                conn.commit()
                return user_id
            else:
                # 创建新用户
                cursor.execute(
                    "INSERT INTO users (user_id, telegram_id, token, username, first_name, last_name) VALUES (%s, %s, %s, %s, %s, %s)",
                    (emos_user_id, telegram_id, token, username, first_name, last_name)
                )
                user_id = cursor.lastrowid
                
                # 创建余额记录
                cursor.execute(
                    "INSERT INTO balances (user_id, balance, username) VALUES (%s, 0, %s)",
                    (user_id, username)
                )
                
                conn.commit()
                return user_id
    except Exception as e:
        logger.error(f"操作用户失败: {e}")
        conn.rollback()
        return None
    finally:
        conn.close()

def create_recharge_order(order_no: str, local_user_id: int, telegram_user_id: int, 
                         carrot_amount: int, platform_order_no: Optional[str] = None,
                         pay_url: Optional[str] = None, expire_time: Optional[datetime] = None) -> bool:
    """创建充值订单"""
    logger.info(f"开始创建充值订单: order_no={order_no}, platform_order_no={platform_order_no}")
    conn = get_db_connection()
    if not conn:
        logger.error("数据库连接失败")
        return False
    
    try:
        with conn.cursor() as cursor:
            logger.info(f"执行SQL插入: order_no={order_no}, platform_order_no={platform_order_no}, user_id={local_user_id}")
            cursor.execute(
                """INSERT INTO recharge_orders 
                   (order_no, user_id, telegram_user_id, carrot_amount, game_coin_amount, 
                    status, platform_order_no, pay_url, expire_time, created_at, updated_at)
                   VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())""",
                (order_no, local_user_id, telegram_user_id, carrot_amount, 
                 carrot_amount * 10, 'pending', platform_order_no, pay_url, expire_time)
            )
            logger.info(f"SQL执行成功，影响行数: {cursor.rowcount}")
            conn.commit()
            logger.info(f"事务提交成功")
            logger.info(f"充值订单已创建: {order_no}, platform_order_no={platform_order_no}")
            return True
    except Exception as e:
        logger.error(f"创建充值订单失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        conn.rollback()
        return False
    finally:
        if conn:
            conn.close()
            logger.info("数据库连接已关闭")

def update_recharge_order_status(platform_order_no: str, status: str, 
                                game_coin_amount: Optional[int] = None) -> bool:
    """更新充值订单状态"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            if game_coin_amount is not None:
                cursor.execute(
                    """UPDATE recharge_orders 
                       SET status = %s, game_coin_amount = %s 
                       WHERE platform_order_no = %s""",
                    (status, game_coin_amount, platform_order_no)
                )
            else:
                cursor.execute(
                    "UPDATE recharge_orders SET status = %s WHERE platform_order_no = %s",
                    (status, platform_order_no)
                )
            
            # 如果订单成功，更新用户余额
            if status == 'success' and game_coin_amount is not None:
                cursor.execute(
                    """SELECT user_id FROM recharge_orders WHERE platform_order_no = %s""",
                    (platform_order_no,)
                )
                result = cursor.fetchone()
                if result:
                    user_id = result[0]
                    cursor.execute(
                        """UPDATE balances 
                           SET balance = balance + %s 
                           WHERE user_id = %s""",
                        (game_coin_amount, user_id)
                    )
            
            conn.commit()
            logger.info(f"充值订单状态已更新: {platform_order_no} -> {status}")
            return True
    except Exception as e:
        logger.error(f"更新充值订单失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def get_user_by_telegram_id(telegram_user_id: int) -> Optional[Dict[str, Any]]:
    """根据Telegram用户ID获取用户信息"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                """SELECT u.*, b.balance 
                   FROM users u 
                   LEFT JOIN balances b ON u.id = b.user_id 
                   WHERE u.id IN (
                       SELECT user_id FROM recharge_orders 
                       WHERE telegram_user_id = %s 
                       LIMIT 1
                   )""",
                (telegram_user_id,)
            )
            return cursor.fetchone()
    except Exception as e:
        logger.error(f"查询用户失败: {e}")
        return None
    finally:
        conn.close()

def get_order_by_platform_no(platform_order_no: str) -> Optional[Dict[str, Any]]:
    """根据平台订单号获取订单信息"""
    logger.info(f"开始查询订单: platform_order_no={platform_order_no}")
    conn = get_db_connection()
    if not conn:
        logger.error("数据库连接失败")
        return None
    
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            logger.info(f"执行SQL查询: SELECT * FROM recharge_orders WHERE platform_order_no = '{platform_order_no}'")
            cursor.execute(
                "SELECT * FROM recharge_orders WHERE platform_order_no = %s",
                (platform_order_no,)
            )
            result = cursor.fetchone()
            if result:
                logger.info(f"✅ 订单找到: {result}")
            else:
                logger.info(f"❌ 订单未找到: platform_order_no={platform_order_no}")
            return result
    except Exception as e:
        logger.error(f"查询订单失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return None
    finally:
        if conn:
            conn.close()
            logger.info("数据库连接已关闭")

def get_pending_orders() -> list:
    """获取所有待处理订单"""
    conn = get_db_connection()
    if not conn:
        return []
    
    try:
        with conn.cursor(pymysql.cursors.DictCursor) as cursor:
            cursor.execute(
                "SELECT id, order_no, user_id, telegram_user_id, carrot_amount as amount, platform_order_no FROM recharge_orders WHERE status = 'pending'"
            )
            orders = cursor.fetchall()
            logger.info(f"查询到 {len(orders)} 个待处理订单")
            for order in orders:
                logger.info(f"待处理订单: ID={order['id']}, 平台订单号={order['platform_order_no']}, 金额={order['amount']}")
            return orders
    except Exception as e:
        logger.error(f"查询待处理订单失败: {e}")
        return []
    finally:
        conn.close()

def get_user_token(user_id: int) -> Optional[str]:
    """根据用户ID获取用户token"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT token FROM users WHERE id = %s",
                (user_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"获取用户token失败: {e}")
        return None
    finally:
        conn.close()

def get_user_balance(user_id: int) -> Optional[int]:
    """根据用户ID获取游戏余额"""
    conn = get_db_connection()
    if not conn:
        return None
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                "SELECT balance FROM balances WHERE user_id = %s",
                (user_id,)
            )
            result = cursor.fetchone()
            return result[0] if result else None
    except Exception as e:
        logger.error(f"获取用户余额失败: {e}")
        return None
    finally:
        conn.close()

def create_withdraw_order(order_no: str, user_id: int, telegram_user_id: int, 
                        game_coin_amount: int, carrot_amount: int) -> bool:
    """创建提现订单"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            cursor.execute(
                """INSERT INTO withdraw_orders 
                   (order_no, user_id, telegram_user_id, game_coin_amount, 
                    carrot_amount, status)
                   VALUES (%s, %s, %s, %s, %s, %s)""",
                (order_no, user_id, telegram_user_id, game_coin_amount, 
                 carrot_amount, 'pending')
            )
            conn.commit()
            logger.info(f"提现订单已创建: {order_no}")
            return True
    except Exception as e:
        logger.error(f"创建提现订单失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def update_withdraw_order_status(order_no: str, status: str, 
                               transfer_result: Optional[str] = None) -> bool:
    """更新提现订单状态"""
    conn = get_db_connection()
    if not conn:
        return False
    
    try:
        with conn.cursor() as cursor:
            if transfer_result:
                cursor.execute(
                    """UPDATE withdraw_orders 
                       SET status = %s, transfer_result = %s 
                       WHERE order_no = %s""",
                    (status, transfer_result, order_no)
                )
            else:
                cursor.execute(
                    "UPDATE withdraw_orders SET status = %s WHERE order_no = %s",
                    (status, order_no)
                )
            
            # 如果订单成功，更新用户余额
            if status == 'success':
                cursor.execute(
                    """SELECT user_id, game_coin_amount FROM withdraw_orders 
                       WHERE order_no = %s""",
                    (order_no,)
                )
                result = cursor.fetchone()
                if result:
                    user_id = result[0]
                    game_coin_amount = result[1]
                    cursor.execute(
                        """UPDATE balances 
                           SET balance = balance - %s 
                           WHERE user_id = %s""",
                        (game_coin_amount, user_id)
                    )
            
            conn.commit()
            logger.info(f"提现订单状态已更新: {order_no} -> {status}")
            return True
    except Exception as e:
        logger.error(f"更新提现订单失败: {e}")
        conn.rollback()
        return False
    finally:
        conn.close()

def check_withdraw_limits(user_id: int, carrot_amount: int) -> Dict[str, Any]:
    """检查用户提现限额
    
    Args:
        user_id: 用户ID
        carrot_amount: 提现萝卜数量
    
    Returns:
        dict: 包含限额检查结果的字典
    """
    from config import WITHDRAW_LIMITS
    from datetime import datetime, timedelta
    
    conn = get_db_connection()
    if not conn:
        return {"success": False, "error": "数据库连接失败"}
    
    try:
        with conn.cursor() as cursor:
            # 获取今日开始时间
            today = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            # 获取本月开始时间
            month_start = today.replace(day=1)
            
            # 查询今日提现总额
            cursor.execute(
                """SELECT COALESCE(SUM(carrot_amount), 0) FROM withdraw_orders 
                   WHERE user_id = %s AND status = 'success' AND created_at >= %s""",
                (user_id, today)
            )
            daily_total = cursor.fetchone()[0]
            
            # 查询本月提现总额
            cursor.execute(
                """SELECT COALESCE(SUM(carrot_amount), 0) FROM withdraw_orders 
                   WHERE user_id = %s AND status = 'success' AND created_at >= %s""",
                (user_id, month_start)
            )
            monthly_total = cursor.fetchone()[0]
            
            # 查询终身提现总额
            cursor.execute(
                """SELECT COALESCE(SUM(carrot_amount), 0) FROM withdraw_orders 
                   WHERE user_id = %s AND status = 'success'""",
                (user_id,)
            )
            lifetime_total = cursor.fetchone()[0]
            
            # 检查限额
            if daily_total + carrot_amount > WITHDRAW_LIMITS['daily']:
                return {
                    "success": False, 
                    "error": f"每日提现限额为{WITHDRAW_LIMITS['daily']}萝卜，今日已提现{daily_total}萝卜，无法再提现{carrot_amount}萝卜"
                }
            
            if monthly_total + carrot_amount > WITHDRAW_LIMITS['monthly']:
                return {
                    "success": False, 
                    "error": f"每月提现限额为{WITHDRAW_LIMITS['monthly']}萝卜，本月已提现{monthly_total}萝卜，无法再提现{carrot_amount}萝卜"
                }
            
            if lifetime_total + carrot_amount > WITHDRAW_LIMITS['lifetime']:
                return {
                    "success": False, 
                    "error": f"终身提现限额为{WITHDRAW_LIMITS['lifetime']}萝卜，已累计提现{lifetime_total}萝卜，无法再提现{carrot_amount}萝卜"
                }
            
            return {
                "success": True, 
                "daily_total": daily_total, 
                "monthly_total": monthly_total, 
                "lifetime_total": lifetime_total,
                "daily_limit": WITHDRAW_LIMITS['daily'],
                "monthly_limit": WITHDRAW_LIMITS['monthly'],
                "lifetime_limit": WITHDRAW_LIMITS['lifetime']
            }
    except Exception as e:
        logger.error(f"检查提现限额失败: {e}")
        return {"success": False, "error": "检查限额失败"}
    finally:
        conn.close()
