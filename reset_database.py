#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
重置数据库表结构
"""

import pymysql
from config import DB_CONFIG

def reset_database():
    """重置数据库表结构"""
    try:
        # 连接数据库
        conn = pymysql.connect(
            host=DB_CONFIG['host'],
            user=DB_CONFIG['user'],
            password=DB_CONFIG['password'],
            database=DB_CONFIG['database'],
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        print("✅ 连接数据库成功")
        
        # 开始事务
        conn.begin()
        
        # 1. 删除现有表（如果存在）
        tables = ['users', 'recharge_orders', 'withdrawal_records', 'game_records', 'jackpot_pool']
        for table in tables:
            try:
                cursor.execute(f"DROP TABLE IF EXISTS `{table}`")
                print(f"🗑️ 删除表 {table} 成功")
            except Exception as e:
                print(f"⚠️ 删除表 {table} 失败: {e}")
        
        # 2. 创建 users 表
        create_users_table = """
        CREATE TABLE IF NOT EXISTS `users` (
            `id` INT(11) NOT NULL AUTO_INCREMENT,
            `user_id` VARCHAR(50) NOT NULL,
            `telegram_id` BIGINT(20) DEFAULT NULL,
            `token` VARCHAR(255) DEFAULT NULL,
            `username` VARCHAR(255) DEFAULT NULL,
            `first_name` VARCHAR(255) DEFAULT NULL,
            `last_name` VARCHAR(255) DEFAULT NULL,
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            `current_cycle_score` INT(11) DEFAULT 0,
            PRIMARY KEY (`id`),
            UNIQUE KEY `user_id` (`user_id`),
            UNIQUE KEY `telegram_id` (`telegram_id`),
            UNIQUE KEY `token` (`token`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # 3. 创建 recharge_orders 表
        create_recharge_orders_table = """
        CREATE TABLE IF NOT EXISTS `recharge_orders` (
            `id` INT(11) NOT NULL AUTO_INCREMENT,
            `order_id` VARCHAR(100) NOT NULL,
            `user_id` VARCHAR(50) NOT NULL,
            `amount` DECIMAL(10,2) NOT NULL,
            `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `order_id` (`order_id`),
            KEY `user_id` (`user_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # 4. 创建 withdrawal_records 表
        create_withdrawal_records_table = """
        CREATE TABLE IF NOT EXISTS `withdrawal_records` (
            `id` INT(11) NOT NULL AUTO_INCREMENT,
            `record_id` VARCHAR(100) NOT NULL,
            `user_id` VARCHAR(50) NOT NULL,
            `amount` DECIMAL(10,2) NOT NULL,
            `status` VARCHAR(20) NOT NULL DEFAULT 'pending',
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            `updated_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            UNIQUE KEY `record_id` (`record_id`),
            KEY `user_id` (`user_id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # 5. 创建 game_records 表
        create_game_records_table = """
        CREATE TABLE IF NOT EXISTS `game_records` (
            `id` INT(11) NOT NULL AUTO_INCREMENT,
            `user_id` VARCHAR(50) NOT NULL,
            `telegram_id` BIGINT(20) DEFAULT NULL,
            `game_type` VARCHAR(50) NOT NULL,
            `bet_amount` DECIMAL(10,2) NOT NULL,
            `win_amount` DECIMAL(10,2) NOT NULL,
            `result` TEXT,
            `created_at` TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`),
            KEY `user_id` (`user_id`),
            KEY `telegram_id` (`telegram_id`),
            KEY `game_type` (`game_type`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # 6. 创建 jackpot_pool 表
        create_jackpot_pool_table = """
        CREATE TABLE IF NOT EXISTS `jackpot_pool` (
            `id` INT(11) NOT NULL AUTO_INCREMENT,
            `pool_amount` DECIMAL(10,2) NOT NULL DEFAULT 0,
            `last_update` TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
            PRIMARY KEY (`id`)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
        """
        
        # 执行创建表语句
        tables_to_create = [
            ("users", create_users_table),
            ("recharge_orders", create_recharge_orders_table),
            ("withdrawal_records", create_withdrawal_records_table),
            ("game_records", create_game_records_table),
            ("jackpot_pool", create_jackpot_pool_table)
        ]
        
        for table_name, create_sql in tables_to_create:
            try:
                cursor.execute(create_sql)
                print(f"✅ 创建表 {table_name} 成功")
            except Exception as e:
                print(f"❌ 创建表 {table_name} 失败: {e}")
                conn.rollback()
                return False
        
        # 7. 初始化 jackpot_pool 表
        try:
            cursor.execute("INSERT INTO jackpot_pool (pool_amount) VALUES (0)")
            print("✅ 初始化 jackpot_pool 表成功")
        except Exception as e:
            print(f"❌ 初始化 jackpot_pool 表失败: {e}")
            conn.rollback()
            return False
        
        # 提交事务
        conn.commit()
        print("✅ 数据库重置成功")
        
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
    print("开始重置数据库表结构...")
    reset_database()
