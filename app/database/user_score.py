# 用户贡献分管理模块

from app.database.db import get_db_connection
from utils.http_client import http_client

def get_user_score(telegram_id):
    """获取用户的当前贡献分"""
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT current_cycle_score 
                FROM users 
                WHERE telegram_id = %s
            ''', (telegram_id,))
            result = cursor.fetchone()
            return result['current_cycle_score'] if result else 0
    except Exception as e:
        print(f"获取用户贡献分失败: {e}")
        return 0
    finally:
        connection.close()

def add_user_score(telegram_id, score):
    """增加用户的贡献分"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE users 
                SET current_cycle_score = current_cycle_score + %s
                WHERE telegram_id = %s
            ''', (score, telegram_id))
            connection.commit()
            return True
    except Exception as e:
        print(f"增加用户贡献分失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def reset_user_score(telegram_id):
    """重置用户的贡献分（中奖后）"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE users 
                SET current_cycle_score = 0
                WHERE telegram_id = %s
            ''', (telegram_id,))
            connection.commit()
            return True
    except Exception as e:
        print(f"重置用户贡献分失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def get_user_level(score):
    """根据贡献分获取用户等级"""
    if score >= 50000:
        return "王者", 100, 1.0  # 100倍，100%奖池
    elif score >= 30000:
        return "大师", 80, 0.8   # 80倍，80%奖池
    elif score >= 20000:
        return "宗师", 60, 0.6   # 60倍，60%奖池
    elif score >= 10000:
        return "钻石", 50, 0.5   # 50倍，50%奖池
    elif score >= 5000:
        return "黄金", 30, 0.3   # 30倍，30%奖池
    elif score >= 1000:
        return "白银", 20, 0.2   # 20倍，20%奖池
    else:
        return "青铜", 10, 0.1    # 10倍，10%奖池
