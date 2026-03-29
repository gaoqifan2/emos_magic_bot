#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
修复数据库表结构，处理外键约束
"""

from app.database.db import get_db_connection

def fix_table_structure():
    """修复数据库表结构"""
    print("开始修复数据库表结构...")
    
    conn = get_db_connection()
    if not conn:
        print("❌ 无法获取数据库连接")
        return
    
    try:
        cursor = conn.cursor()
        
        # 禁用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 0")
        print("✅ 禁用外键检查")
        
        # 重新创建 user_streaks 表
        print("\n重新创建 user_streaks 表...")
        try:
            # 删除旧表
            cursor.execute("DROP TABLE IF EXISTS user_streaks")
            print("  ✅ 删除旧表 user_streaks")
            
            # 创建新表
            cursor.execute('''
                CREATE TABLE user_streaks (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
                    user_id VARCHAR(50) NOT NULL COMMENT '关联users表的user_id（字符串格式）',
                    telegram_id BIGINT NOT NULL COMMENT 'Telegram用户ID',
                    game_type VARCHAR(50) NOT NULL COMMENT '游戏类型：blackjack/slot等',
                    win_streak INT DEFAULT 0 COMMENT '当前连胜次数',
                    max_streak INT DEFAULT 0 COMMENT '历史最高连胜',
                    last_win_time TIMESTAMP NULL COMMENT '上次胜利时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    UNIQUE KEY unique_user_game (user_id, game_type),
                    INDEX idx_telegram_id (telegram_id),
                    INDEX idx_game_type (game_type),
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户连胜记录表'
            ''')
            print("  ✅ 创建新表 user_streaks")
        except Exception as e:
            print(f"  ❌ 重新创建 user_streaks 表失败: {e}")
        
        # 重新创建 daily_checkins 表
        print("\n重新创建 daily_checkins 表...")
        try:
            # 删除旧表
            cursor.execute("DROP TABLE IF EXISTS daily_checkins")
            print("  ✅ 删除旧表 daily_checkins")
            
            # 创建新表
            cursor.execute('''
                CREATE TABLE daily_checkins (
                    user_id VARCHAR(50) PRIMARY KEY COMMENT '关联users表的user_id（字符串格式）',
                    last_checkin TIMESTAMP NOT NULL COMMENT '上次签到时间',
                    checkin_streak INT DEFAULT 1 COMMENT '连续签到天数',
                    total_checkins INT DEFAULT 1 COMMENT '总签到次数',
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日签到表'
            ''')
            print("  ✅ 创建新表 daily_checkins")
        except Exception as e:
            print(f"  ❌ 重新创建 daily_checkins 表失败: {e}")
        
        # 重新创建 withdraw_orders 表
        print("\n重新创建 withdraw_orders 表...")
        try:
            # 删除旧表
            cursor.execute("DROP TABLE IF EXISTS withdraw_orders")
            print("  ✅ 删除旧表 withdraw_orders")
            
            # 创建新表
            cursor.execute('''
                CREATE TABLE withdraw_orders (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '提现订单ID',
                    order_no VARCHAR(100) UNIQUE NOT NULL COMMENT '提现订单号',
                    user_id VARCHAR(50) NOT NULL COMMENT '关联users表的user_id（字符串格式）',
                    telegram_user_id BIGINT NOT NULL COMMENT 'Telegram用户ID',
                    game_coin_amount INT NOT NULL COMMENT '提现游戏币数量',
                    carrot_amount INT NOT NULL COMMENT '获得萝卜数量',
                    status VARCHAR(20) DEFAULT 'pending' COMMENT '订单状态：pending(待处理)/processing(处理中)/success(成功)/failed(失败)',
                    transfer_result TEXT COMMENT '转账结果信息',
                    admin_note TEXT COMMENT '管理员备注',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_status (status),
                    INDEX idx_telegram_user (telegram_user_id),
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提现订单表'
            ''')
            print("  ✅ 创建新表 withdraw_orders")
        except Exception as e:
            print(f"  ❌ 重新创建 withdraw_orders 表失败: {e}")
        
        # 重新创建 game_records 表
        print("\n重新创建 game_records 表...")
        try:
            # 删除旧表
            cursor.execute("DROP TABLE IF EXISTS game_records")
            print("  ✅ 删除旧表 game_records")
            
            # 创建新表
            cursor.execute('''
                CREATE TABLE game_records (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
                    user_id VARCHAR(50) NOT NULL COMMENT '关联users表的user_id（字符串格式）',
                    username VARCHAR(255) COMMENT '用户名',
                    game_type VARCHAR(50) NOT NULL COMMENT '游戏类型：dice/slot/coinflip等',
                    bet_amount INT NOT NULL COMMENT '下注金额',
                    result VARCHAR(50) NOT NULL COMMENT '游戏结果：win/lose/draw',
                    win_amount INT NOT NULL COMMENT '赢得的金额（负数表示输）',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '游戏时间',
                    INDEX idx_user_created (user_id, created_at),
                    INDEX idx_game_type (game_type),
                    INDEX idx_username (username),
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='游戏记录表'
            ''')
            print("  ✅ 创建新表 game_records")
        except Exception as e:
            print(f"  ❌ 重新创建 game_records 表失败: {e}")
        
        # 重新创建 recharge_orders 表
        print("\n重新创建 recharge_orders 表...")
        try:
            # 删除旧表
            cursor.execute("DROP TABLE IF EXISTS recharge_orders")
            print("  ✅ 删除旧表 recharge_orders")
            
            # 创建新表
            cursor.execute('''
                CREATE TABLE recharge_orders (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '订单ID',
                    order_no VARCHAR(100) UNIQUE NOT NULL COMMENT '平台内部订单号',
                    user_id VARCHAR(50) NOT NULL COMMENT '关联users表的user_id（字符串格式）',
                    telegram_user_id BIGINT NOT NULL COMMENT 'Telegram用户ID，方便查询',
                    carrot_amount INT NOT NULL COMMENT '充值萝卜数量（1-50000）',
                    game_coin_amount INT NOT NULL COMMENT '获得游戏币数量',
                    status VARCHAR(20) DEFAULT 'pending' COMMENT '订单状态：pending(待支付)/success(成功)/failed(失败)/closed(已关闭)',
                    platform_order_no VARCHAR(255) COMMENT '支付平台返回的订单号',
                    pay_url TEXT COMMENT '支付链接',
                    qrcode TEXT COMMENT '支付二维码',
                    expire_time TIMESTAMP NULL COMMENT '订单过期时间',
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    INDEX idx_status (status),
                    INDEX idx_telegram_user (telegram_user_id),
                    INDEX idx_platform_no (platform_order_no),
                    INDEX idx_created (created_at),
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='充值订单表'
            ''')
            print("  ✅ 创建新表 recharge_orders")
        except Exception as e:
            print(f"  ❌ 重新创建 recharge_orders 表失败: {e}")
        
        # 重新创建 user_tags 表
        print("\n重新创建 user_tags 表...")
        try:
            # 删除旧表
            cursor.execute("DROP TABLE IF EXISTS user_tags")
            print("  ✅ 删除旧表 user_tags")
            
            # 创建新表，确保 chat_id 允许为 NULL
            cursor.execute('''
                CREATE TABLE user_tags (
                    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
                    user_id VARCHAR(50) NOT NULL COMMENT '关联users表的user_id（字符串格式）',
                    telegram_id BIGINT NOT NULL COMMENT 'Telegram用户ID',
                    chat_id BIGINT NULL COMMENT '群组ID（可为NULL）',
                    tag_name VARCHAR(100) NOT NULL COMMENT '标签名称',
                    tag_level INT DEFAULT 1 COMMENT '标签等级',
                    awarded_at TIMESTAMP NOT NULL COMMENT '获得时间',
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
                    UNIQUE KEY unique_user_chat_tag (user_id, chat_id, tag_name),
                    INDEX idx_telegram_id (telegram_id),
                    INDEX idx_chat_id (chat_id),
                    INDEX idx_tag_name (tag_name),
                    INDEX idx_user_id (user_id)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户标签表'
            ''')
            print("  ✅ 创建新表 user_tags")
        except Exception as e:
            print(f"  ❌ 重新创建 user_tags 表失败: {e}")
        
        # 启用外键检查
        cursor.execute("SET FOREIGN_KEY_CHECKS = 1")
        print("✅ 启用外键检查")
        
        conn.commit()
        print("\n✅ 数据库表结构修复完成")
        
    except Exception as e:
        print(f"❌ 修复数据库表结构失败: {e}")
        import traceback
        print(traceback.format_exc())
        conn.rollback()
    finally:
        conn.close()

if __name__ == "__main__":
    fix_table_structure()
