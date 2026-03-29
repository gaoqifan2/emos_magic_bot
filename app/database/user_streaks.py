#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
用户连胜记录和标签管理模块
"""

from app.database.db import get_db_connection
import logging

logger = logging.getLogger(__name__)


def _get_value(row, index, key):
    """辅助函数：从查询结果中获取值（支持字典和元组）"""
    if row is None:
        return None
    if isinstance(row, dict):
        return row.get(key)
    else:
        return row[index] if index < len(row) else None


def get_user_streak(user_id, telegram_id, game_type='blackjack'):
    """
    获取用户当前连胜次数
    
    Args:
        user_id: 用户ID
        telegram_id: Telegram用户ID
        game_type: 游戏类型
    
    Returns:
        dict: 包含win_streak, max_streak等信息的字典
    """
    conn = get_db_connection()
    if not conn:
        logger.error("无法获取数据库连接")
        return {'win_streak': 0, 'max_streak': 0}
    
    try:
        cursor = conn.cursor()
        
        # 查询连胜记录
        cursor.execute('''
            SELECT win_streak, max_streak, last_win_time
            FROM user_streaks
            WHERE user_id = %s AND game_type = %s
        ''', (user_id, game_type))
        
        result = cursor.fetchone()
        
        if result:
            return {
                'win_streak': _get_value(result, 0, 'win_streak') or 0,
                'max_streak': _get_value(result, 1, 'max_streak') or 0,
                'last_win_time': _get_value(result, 2, 'last_win_time')
            }
        else:
            # 没有记录，返回默认值
            return {'win_streak': 0, 'max_streak': 0, 'last_win_time': None}
            
    except Exception as e:
        logger.error(f"获取连胜记录失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return {'win_streak': 0, 'max_streak': 0}
    finally:
        conn.close()


def update_user_streak(user_id, telegram_id, game_type='blackjack', is_win=True):
    """
    更新用户连胜记录
    
    Args:
        user_id: 用户ID
        telegram_id: Telegram用户ID
        game_type: 游戏类型
        is_win: 是否获胜
    
    Returns:
        int: 当前的连胜次数
    """
    conn = get_db_connection()
    if not conn:
        logger.error("无法获取数据库连接")
        return 0
    
    try:
        cursor = conn.cursor()
        
        logger.info(f"更新连胜记录 - user_id: {user_id} (类型: {type(user_id)}), telegram_id: {telegram_id}, game_type: {game_type}, is_win: {is_win}")
        
        if is_win:
            # 获胜，连胜+1
            sql = '''
                INSERT INTO user_streaks (user_id, telegram_id, game_type, win_streak, max_streak, last_win_time)
                VALUES (%s, %s, %s, 1, 1, NOW())
                ON DUPLICATE KEY UPDATE
                    win_streak = win_streak + 1,
                    max_streak = GREATEST(max_streak, win_streak + 1),
                    last_win_time = NOW(),
                    updated_at = NOW()
            '''
            logger.info(f"执行SQL: {sql}, 参数: {(user_id, telegram_id, game_type)}")
            cursor.execute(sql, (user_id, telegram_id, game_type))
        else:
            # 失败，连胜清零
            sql = '''
                INSERT INTO user_streaks (user_id, telegram_id, game_type, win_streak, max_streak, last_win_time)
                VALUES (%s, %s, %s, 0, 0, NULL)
                ON DUPLICATE KEY UPDATE
                    win_streak = 0,
                    last_win_time = NULL,
                    updated_at = NOW()
            '''
            logger.info(f"执行SQL: {sql}, 参数: {(user_id, telegram_id, game_type)}")
            cursor.execute(sql, (user_id, telegram_id, game_type))
        
        conn.commit()
        logger.info(f"SQL执行成功，影响行数: {cursor.rowcount}")
        
        # 返回当前连胜次数
        cursor.execute('''
            SELECT win_streak FROM user_streaks
            WHERE user_id = %s AND game_type = %s
        ''', (user_id, game_type))
        
        result = cursor.fetchone()
        win_streak = _get_value(result, 0, 'win_streak') if result else 0
        logger.info(f"当前连胜次数: {win_streak}")
        
        # 当用户获得 1 胜时，直接触发 API 给该 TGID 的用户在群里赋予标签
        if is_win and win_streak == 1:
            logger.info(f"用户 {telegram_id} 获得 1 胜，尝试在群里赋予标签")
            try:
                from config import Config, DEFAULT_GROUP_CHAT_ID
                import httpx
                
                # 获取 BOT_TOKEN
                BOT_TOKEN = Config.BOT_TOKEN
                
                # 检查群聊 ID 是否有效
                if not DEFAULT_GROUP_CHAT_ID:
                    logger.warning("DEFAULT_GROUP_CHAT_ID 未设置，跳过标签设置")
                    return win_streak
                
                # 使用 Telegram Bot API 9.5 设置标签
                api_url = f"https://api.telegram.org/bot{BOT_TOKEN}/setChatMemberTag"
                payload = {
                    "chat_id": DEFAULT_GROUP_CHAT_ID,
                    "user_id": telegram_id,
                    "tag": "新手村"  # 使用正确的参数名 tag，而不是 tag_name
                }
                
                response = httpx.post(api_url, json=payload, timeout=10)
                if response.status_code == 200:
                    logger.info(f"成功为用户 {telegram_id} 在群 {DEFAULT_GROUP_CHAT_ID} 中设置标签 '新手村'")
                else:
                    logger.error(f"设置标签失败: {response.status_code} - {response.text}")
                    logger.info("标签设置失败，但游戏流程将继续")
            except Exception as e:
                logger.error(f"触发标签 API 失败: {e}")
                logger.info("标签 API 调用异常，但游戏流程将继续")
        
        return win_streak
        
    except Exception as e:
        logger.error(f"更新连胜记录失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        conn.rollback()
        return 0
    finally:
        conn.close()


def reset_user_streak(user_id, game_type='blackjack'):
    """
    重置用户连胜记录
    
    Args:
        user_id: 用户ID
        game_type: 游戏类型
    """
    conn = get_db_connection()
    if not conn:
        logger.error("无法获取数据库连接")
        return
    
    try:
        cursor = conn.cursor()
        
        cursor.execute('''
            UPDATE user_streaks
            SET win_streak = 0, last_win_time = NULL, updated_at = NOW()
            WHERE user_id = %s AND game_type = %s
        ''', (user_id, game_type))
        
        conn.commit()
        
    except Exception as e:
        logger.error(f"重置连胜记录失败: {e}")
        conn.rollback()
    finally:
        conn.close()


def add_user_tag(user_id, telegram_id, chat_id, tag_name, tag_level=1):
    """
    添加用户标签记录
    
    Args:
        user_id: 用户ID
        telegram_id: Telegram用户ID
        chat_id: 群组ID（可为None）
        tag_name: 标签名称
        tag_level: 标签等级
    
    Returns:
        bool: 是否成功
    """
    conn = get_db_connection()
    if not conn:
        logger.error("无法获取数据库连接")
        return False
    
    try:
        cursor = conn.cursor()
        
        logger.info(f"添加用户标签 - user_id: {user_id}, telegram_id: {telegram_id}, chat_id: {chat_id}, tag_name: {tag_name}, tag_level: {tag_level}")
        
        cursor.execute('''
            INSERT INTO user_tags (user_id, telegram_id, chat_id, tag_name, tag_level, awarded_at)
            VALUES (%s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                tag_level = GREATEST(tag_level, VALUES(tag_level)),
                awarded_at = NOW()
        ''', (user_id, telegram_id, chat_id, tag_name, tag_level))
        
        conn.commit()
        logger.info(f"用户标签添加成功 - user_id: {user_id}, tag_name: {tag_name}")
        return True
        
    except Exception as e:
        logger.error(f"添加用户标签记录失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        conn.rollback()
        return False
    finally:
        conn.close()


def get_user_tags(telegram_id, chat_id=None):
    """
    获取用户标签列表
    
    Args:
        telegram_id: Telegram用户ID
        chat_id: 群组ID（可选，如果不传则返回所有标签）
    
    Returns:
        list: 标签列表
    """
    conn = get_db_connection()
    if not conn:
        logger.error("无法获取数据库连接")
        return []
    
    try:
        cursor = conn.cursor()
        
        if chat_id:
            cursor.execute('''
                SELECT tag_name, tag_level, awarded_at
                FROM user_tags
                WHERE telegram_id = %s AND chat_id = %s
                ORDER BY tag_level DESC, awarded_at DESC
            ''', (telegram_id, chat_id))
        else:
            cursor.execute('''
                SELECT tag_name, tag_level, chat_id, awarded_at
                FROM user_tags
                WHERE telegram_id = %s
                ORDER BY tag_level DESC, awarded_at DESC
            ''', (telegram_id,))
        
        rows = cursor.fetchall()
        # 转换为字典列表
        result = []
        for row in rows:
            if chat_id:
                result.append({
                    'tag_name': _get_value(row, 0, 'tag_name'),
                    'tag_level': _get_value(row, 1, 'tag_level'),
                    'awarded_at': _get_value(row, 2, 'awarded_at')
                })
            else:
                result.append({
                    'tag_name': _get_value(row, 0, 'tag_name'),
                    'tag_level': _get_value(row, 1, 'tag_level'),
                    'chat_id': _get_value(row, 2, 'chat_id'),
                    'awarded_at': _get_value(row, 3, 'awarded_at')
                })
        return result
        
    except Exception as e:
        logger.error(f"获取用户标签失败: {e}")
        import traceback
        logger.error(traceback.format_exc())
        return []
    finally:
        conn.close()


def has_user_tag(telegram_id, chat_id, tag_name):
    """
    检查用户是否有特定标签
    
    Args:
        telegram_id: Telegram用户ID
        chat_id: 群组ID
        tag_name: 标签名称
    
    Returns:
        bool: 是否有该标签
    """
    conn = get_db_connection()
    if not conn:
        logger.error("无法获取数据库连接")
        return False
    
    try:
        cursor = conn.cursor()
        
        cursor.execute('''
            SELECT COUNT(*) FROM user_tags
            WHERE telegram_id = %s AND chat_id = %s AND tag_name = %s
        ''', (telegram_id, chat_id, tag_name))
        
        result = cursor.fetchone()
        count = _get_value(result, 0, 'COUNT(*)') if result else 0
        return count > 0
        
    except Exception as e:
        logger.error(f"检查用户标签失败: {e}")
        return False
    finally:
        conn.close()
