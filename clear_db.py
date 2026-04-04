#!/usr/bin/env python3
"""
清空数据库脚本
只清空数据，保留表结构
"""

import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database.db import get_db_connection


def clear_database():
    """清空数据库中的所有数据，保留表结构"""
    connection = get_db_connection()
    if not connection:
        print("数据库连接失败，无法清空数据")
        return False
    
    try:
        with connection.cursor() as cursor:
            # 定义需要清空的表
            tables = [
                'daily_win_records',  # 先清空依赖关系简单的表
                'game_records',
                'checkins',
                'withdrawal_records',
                'recharge_orders',
                'balances',
                'users',
                'jackpot_pool'
            ]
            
            # 清空每个表
            for table in tables:
                try:
                    # 使用 TRUNCATE TABLE 语句清空表数据
                    cursor.execute(f"TRUNCATE TABLE {table}")
                    print(f"成功清空表: {table}")
                except Exception as e:
                    print(f"清空表 {table} 失败: {e}")
                    # 继续处理下一个表，不中断
                    pass
            
            # 重新初始化奖池
            try:
                cursor.execute('INSERT IGNORE INTO jackpot_pool (id, pool_amount) VALUES (1, 0)')
                print("成功重新初始化奖池")
            except Exception as e:
                print(f"初始化奖池失败: {e}")
            
            connection.commit()
            print("\n数据库清空完成，表结构已保留")
            return True
    except Exception as e:
        print(f"清空数据库失败: {e}")
        connection.rollback()
        return False
    finally:
        if connection:
            connection.close()


if __name__ == "__main__":
    print("开始清空数据库...")
    success = clear_database()
    if success:
        print("数据库清空成功！")
    else:
        print("数据库清空失败！")
        sys.exit(1)
