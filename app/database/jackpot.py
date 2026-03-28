# Jackpot奖池管理模块
# 使用数据库持久化存储，所有玩家共享同一个奖池

from app.database.db import get_db_connection

# 初始奖池金额
INITIAL_JACKPOT = 0

def get_jackpot_pool():
    """获取当前Jackpot奖池金额"""
    connection = get_db_connection()
    if not connection:
        return INITIAL_JACKPOT
    
    try:
        with connection.cursor() as cursor:
            # 查找第一条记录
            cursor.execute('SELECT pool_amount FROM jackpot_pool ORDER BY id LIMIT 1')
            result = cursor.fetchone()
            if result:
                return result['pool_amount']
            else:
                # 如果没有记录，初始化
                cursor.execute(
                    'INSERT INTO jackpot_pool (pool_amount) VALUES (%s)',
                    (INITIAL_JACKPOT,)
                )
                connection.commit()
                return INITIAL_JACKPOT
    except Exception as e:
        print(f"获取Jackpot奖池失败: {e}")
        return INITIAL_JACKPOT
    finally:
        connection.close()

def add_to_jackpot_pool(amount):
    """向Jackpot奖池添加金额（每局抽水）"""
    connection = get_db_connection()
    if not connection:
        return INITIAL_JACKPOT
    
    try:
        with connection.cursor() as cursor:
            # 更新奖池金额
            cursor.execute('''
                UPDATE jackpot_pool 
                SET pool_amount = pool_amount + %s
                ORDER BY id LIMIT 1
            ''', (amount,))
            
            # 获取更新后的金额
            cursor.execute('SELECT pool_amount FROM jackpot_pool ORDER BY id LIMIT 1')
            result = cursor.fetchone()
            connection.commit()
            
            return result['pool_amount'] if result else INITIAL_JACKPOT
    except Exception as e:
        print(f"添加Jackpot奖池金额失败: {e}")
        connection.rollback()
        return INITIAL_JACKPOT
    finally:
        connection.close()

def reset_jackpot_pool():
    """重置Jackpot奖池为初始值（有人中奖后），并重置所有用户的贡献分"""
    connection = get_db_connection()
    if not connection:
        return INITIAL_JACKPOT
    
    try:
        with connection.cursor() as cursor:
            # 开始事务
            # 重置Jackpot奖池
            cursor.execute('''
                UPDATE jackpot_pool 
                SET pool_amount = %s
                ORDER BY id LIMIT 1
            ''', (INITIAL_JACKPOT,))
            
            # 重置所有用户的贡献分
            cursor.execute('''
                UPDATE users 
                SET current_cycle_score = 0
            ''')
            
            # 提交事务
            connection.commit()
            return INITIAL_JACKPOT
    except Exception as e:
        print(f"重置Jackpot奖池失败: {e}")
        connection.rollback()
        return INITIAL_JACKPOT
    finally:
        connection.close()

def record_jackpot_win(telegram_id, win_amount):
    """记录Jackpot中奖信息"""
    # 由于数据库表结构限制，暂不记录详细中奖信息
    # 仅返回成功
    return True

def get_jackpot_stats():
    """获取Jackpot统计信息"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT pool_amount, last_update
                FROM jackpot_pool 
                ORDER BY id LIMIT 1
            ''')
            result = cursor.fetchone()
            return result
    except Exception as e:
        print(f"获取Jackpot统计失败: {e}")
        return None
    finally:
        connection.close()

def set_jackpot_pool(amount):
    """设置Jackpot奖池为指定金额（管理员手动调整）"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE jackpot_pool 
                SET pool_amount = %s
                ORDER BY id LIMIT 1
            ''', (amount,))
            connection.commit()
            return True
    except Exception as e:
        print(f"设置Jackpot奖池失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()
