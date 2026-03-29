#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
检查数据库表结构
"""

from app.database.db import get_db_connection

def check_table_structure():
    """检查数据库表结构"""
    print("开始检查数据库表结构...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ 无法获取数据库连接")
        return
    
    try:
        cursor = conn.cursor()
        
        # 检查 user_streaks 表结构
        print("\n=== user_streaks 表结构 ===")
        cursor.execute("DESCRIBE user_streaks")
        rows = cursor.fetchall()
        for row in rows:
            print(f"  {row['Field']}: {row['Type']} {row['Null']}")
        
        # 检查 user_tags 表结构
        print("\n=== user_tags 表结构 ===")
        cursor.execute("DESCRIBE user_tags")
        rows = cursor.fetchall()
        for row in rows:
            print(f"  {row['Field']}: {row['Type']} {row['Null']}")
        
        # 检查 users 表结构
        print("\n=== users 表结构 ===")
        cursor.execute("DESCRIBE users")
        rows = cursor.fetchall()
        for row in rows:
            print(f"  {row['Field']}: {row['Type']} {row['Null']}")
        
        # 检查 user_streaks 表中的数据
        print("\n=== user_streaks 表数据 ===")
        cursor.execute("SELECT * FROM user_streaks")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  user_id: {row['user_id']}, telegram_id: {row['telegram_id']}, game_type: {row['game_type']}, win_streak: {row['win_streak']}")
        else:
            print("  表中没有数据")
        
        # 检查 user_tags 表中的数据
        print("\n=== user_tags 表数据 ===")
        cursor.execute("SELECT * FROM user_tags")
        rows = cursor.fetchall()
        if rows:
            for row in rows:
                print(f"  user_id: {row['user_id']}, telegram_id: {row['telegram_id']}, tag_name: {row['tag_name']}, tag_level: {row['tag_level']}")
        else:
            print("  表中没有数据")
            
    except Exception as e:
        print(f"❌ 检查数据库表结构失败: {e}")
        import traceback
        print(traceback.format_exc())
    finally:
        conn.close()

if __name__ == "__main__":
    check_table_structure()
