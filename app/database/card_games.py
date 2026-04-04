"""
扑克牌游戏数据库操作模块
"""

from app.database.db import get_db_connection
from datetime import datetime

def create_card_game(game_id, chat_id, creator_id, creator_name, amount):
    """创建新的扑克牌游戏"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                INSERT INTO card_games (game_id, chat_id, creator_id, creator_name, amount, status, created_at)
                VALUES (%s, %s, %s, %s, %s, 'waiting', NOW())
            ''', (game_id, chat_id, creator_id, creator_name, amount))
            connection.commit()
            return True
    except Exception as e:
        print(f"创建扑克牌游戏失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def join_card_game(game_id, opponent_id, opponent_name):
    """加入扑克牌游戏"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE card_games 
                SET opponent_id = %s, opponent_name = %s, status = 'playing'
                WHERE game_id = %s AND status = 'waiting'
            ''', (opponent_id, opponent_name, game_id))
            connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"加入扑克牌游戏失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def get_card_game(game_id):
    """获取游戏信息"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT * FROM card_games WHERE game_id = %s
            ''', (game_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"获取扑克牌游戏失败: {e}")
        return None
    finally:
        connection.close()

def get_waiting_card_game(chat_id, creator_id=None):
    """获取等待中的游戏"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            if creator_id:
                cursor.execute('''
                    SELECT * FROM card_games 
                    WHERE chat_id = %s AND creator_id = %s AND status = 'waiting'
                    ORDER BY created_at DESC LIMIT 1
                ''', (chat_id, creator_id))
            else:
                cursor.execute('''
                    SELECT * FROM card_games 
                    WHERE chat_id = %s AND status = 'waiting'
                    ORDER BY created_at DESC LIMIT 1
                ''', (chat_id,))
            return cursor.fetchone()
    except Exception as e:
        print(f"获取等待中的扑克牌游戏失败: {e}")
        return None
    finally:
        connection.close()

def update_card_game_result(game_id, creator_card, opponent_card, winner_id):
    """更新游戏结果"""
    connection = get_db_connection()
    if not connection:
        return False
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                UPDATE card_games 
                SET creator_card = %s, opponent_card = %s, winner_id = %s, 
                    status = 'finished', finished_at = NOW()
                WHERE game_id = %s
            ''', (creator_card, opponent_card, winner_id, game_id))
            connection.commit()
            return cursor.rowcount > 0
    except Exception as e:
        print(f"更新扑克牌游戏结果失败: {e}")
        connection.rollback()
        return False
    finally:
        connection.close()

def cleanup_old_card_games(hours=24):
    """清理过期的游戏"""
    connection = get_db_connection()
    if not connection:
        return 0
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                DELETE FROM card_games 
                WHERE status = 'waiting' AND created_at < DATE_SUB(NOW(), INTERVAL %s HOUR)
            ''', (hours,))
            deleted_count = cursor.rowcount
            connection.commit()
            return deleted_count
    except Exception as e:
        print(f"清理过期扑克牌游戏失败: {e}")
        connection.rollback()
        return 0
    finally:
        connection.close()
