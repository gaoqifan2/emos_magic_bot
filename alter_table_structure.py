#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修改数据库表结构
"""

from app.database.db import get_db_connection

def alter_table_structure():
    """修改数据库表结构"""
    print("开始修改数据库表结构...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ 无法获取数据库连接")
        return
    
    try:
        cursor = conn.cursor()
        
        # 修改 user_streaks 表的 user_id 字段类型
        print("\n修改 user_streaks 表的 user_id 字段类型...")
        try:
            # 先删除唯一索引
            cursor.execute("ALTER TABLE user_streaks DROP INDEX unique_user_game")
            print("  ✅ 删除唯一索引 unique_user_game")
        except Exception as e:
            print(f"  ⚠️ 删除唯一索引失败（可能不存在）: {e}")
        
        try:
            # 修改字段类型
            cursor.execute("ALTER TABLE user_streaks MODIFY COLUMN user_id VARCHAR(50) NOT NULL COMMENT '关联users表的user_id（字符串格式）'")
            print("  ✅ 修改 user_id 字段为 VARCHAR(50)")
        except Exception as e:
            print(f"  ❌ 修改字段类型失败: {e}")
        
        try:
            # 重新创建唯一索引
            cursor.execute("ALTER TABLE user_streaks ADD UNIQUE KEY unique_user_game (user_id, game_type)")
            print("  ✅ 重新创建唯一索引 unique_user_game")
        except Exception as e:
            print(f"  ⚠️ 创建唯一索引失败: {e}")
        
        try:
            # 添加 user_id 索引
            cursor.execute("CREATE INDEX idx_user_id ON user_streaks(user_id)")
            print("  ✅ 添加 user_id 索引")
        except Exception as e:
            print(f"  ⚠️ 添加索引失败（可能已存在）: {e}")
        
        # 修改 daily_checkins 表的 user_id 字段类型
        print("\n修改 daily_checkins 表的 user_id 字段类型...")
        try:
            cursor.execute("ALTER TABLE daily_checkins MODIFY COLUMN user_id VARCHAR(50) PRIMARY KEY COMMENT '关联users表的user_id（字符串格式）'")
            print("  ✅ 修改 user_id 字段为 VARCHAR(50)")
        except Exception as e:
            print(f"  ❌ 修改字段类型失败: {e}")
        
        try:
            # 添加 user_id 索引
            cursor.execute("CREATE INDEX idx_user_id ON daily_checkins(user_id)")
            print("  ✅ 添加 user_id 索引")
        except Exception as e:
            print(f"  ⚠️ 添加索引失败（可能已存在）: {e}")
        
        # 修改 game_records 表的 user_id 字段类型
        print("\n修改 game_records 表的 user_id 字段类型...")
        try:
            cursor.execute("ALTER TABLE game_records MODIFY COLUMN user_id VARCHAR(50) NOT NULL COMMENT '关联users表的user_id（字符串格式）'")
            print("  ✅ 修改 user_id 字段为 VARCHAR(50)")
        except Exception as e:
            print(f"  ❌ 修改字段类型失败: {e}")
        
        try:
            # 添加 user_id 索引
            cursor.execute("CREATE INDEX idx_user_id ON game_records(user_id)")
            print("  ✅ 添加 user_id 索引")
        except Exception as e:
            print(f"  ⚠️ 添加索引失败（可能已存在）: {e}")
        
        # 修改 recharge_orders 表的 user_id 字段类型
        print("\n修改 recharge_orders 表的 user_id 字段类型...")
        try:
            cursor.execute("ALTER TABLE recharge_orders MODIFY COLUMN user_id VARCHAR(50) NOT NULL COMMENT '关联users表的user_id（字符串格式）'")
            print("  ✅ 修改 user_id 字段为 VARCHAR(50)")
        except Exception as e:
            print(f"  ❌ 修改字段类型失败: {e}")
        
        try:
            # 添加 user_id 索引
            cursor.execute("CREATE INDEX idx_user_id ON recharge_orders(user_id)")
            print("  ✅ 添加 user_id 索引")
        except Exception as e:
            print(f"  ⚠️ 添加索引失败（可能已存在）: {e}")
        
        # 修改 withdraw_orders 表的 user_id 字段类型
        print("\n修改 withdraw_orders 表的 user_id 字段类型...")
        try:
            cursor.execute("ALTER TABLE withdraw_orders MODIFY COLUMN user_id VARCHAR(50) NOT NULL COMMENT '关联users表的user_id（字符串格式）'")
            print("  ✅ 修改 user_id 字段为 VARCHAR(50)")
        except Exception as e:
            print(f"  ❌ 修改字段类型失败: {e}")
        
        try:
            # 添加 user_id 索引
            cursor.execute("CREATE INDEX idx_user_id ON withdraw_orders(user_id)")
            print("  ✅ 添加 user_id 索引")
        except Exception as e:
            print(f"  ⚠️ 添加索引失败（可能已存在）: {e}")
        
        conn.commit()
        print("\n✅ 数据库表结构修改完成")
        
    except Exception as e:
        print(f"❌ 修改数据库表结构失败: {e}")
        import traceback
        print(traceback.format_exc())
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    alter_table_structure()
