#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
同步balance记录，为users表中存在但balances表中不存在的用户添加默认余额记录
"""

import pymysql
from config import DB_CONFIG

def sync_balance_records():
    """同步balance记录"""
    try:
        # 连接game_db数据库
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            port=DB_CONFIG['port'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database='game_db',  # 正式数据库
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        print("✅ 连接game_db数据库成功")
        
        # 开始事务
        conn.begin()
        
        # 1. 获取users表中的所有用户
        cursor.execute("SELECT id, user_id, username FROM users")
        users = cursor.fetchall()
        print(f"📋 发现 {len(users)} 个用户")
        
        # 2. 获取balances表中的所有记录
        cursor.execute("SELECT user_id FROM balances")
        balance_records = cursor.fetchall()
        existing_user_ids = [record['user_id'] for record in balance_records]
        print(f"📋 已存在 {len(balance_records)} 条余额记录")
        
        # 3. 为缺失的用户添加余额记录
        added_count = 0
        for user in users:
            user_id = user['id']
            username = user['username']
            
            if user_id not in existing_user_ids:
                # 添加默认余额记录
                try:
                    cursor.execute(
                        "INSERT INTO balances (user_id, balance, username) VALUES (%s, %s, %s)",
                        (user_id, 0, username)
                    )
                    added_count += 1
                    print(f"  ✅ 为用户 ID: {user_id}, 用户名: {username} 添加默认余额记录")
                except Exception as e:
                    print(f"  ❌ 为用户 ID: {user_id} 添加余额记录失败: {e}")
                    conn.rollback()
                    return False
        
        # 4. 提交事务
        conn.commit()
        print(f"\n✅ 成功添加 {added_count} 条余额记录")
        
        # 5. 验证结果
        cursor.execute("SELECT COUNT(*) as count FROM balances")
        final_count = cursor.fetchone()['count']
        print(f"📋 最终余额记录数: {final_count}")
        
        if final_count == len(users):
            print("✅ 所有用户都有对应的余额记录")
        else:
            print(f"⚠️ 仍有 {len(users) - final_count} 个用户缺少余额记录")
        
    except Exception as e:
        print(f"❌ 数据库操作失败: {e}")
        if 'conn' in locals() and conn.open:
            conn.rollback()
        return False
    finally:
        if 'cursor' in locals():
            cursor.close()
        if 'conn' in locals() and conn.open:
            conn.close()
        print("✅ 数据库连接已关闭")

if __name__ == "__main__":
    print("开始同步balance记录...")
    sync_balance_records()
