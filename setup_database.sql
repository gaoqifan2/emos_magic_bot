-- =====================================================
-- 数据库创建脚本
-- 请在VPS上直接执行此脚本
-- =====================================================

-- 创建数据库（如果不存在）
CREATE DATABASE IF NOT EXISTS game_db 
CHARACTER SET utf8mb4 
COLLATE utf8mb4_unicode_ci;

-- 使用 game_db 数据库
USE game_db;

-- 1. users（用户表）
CREATE TABLE IF NOT EXISTS users (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '自增主键，内部使用',
    user_id VARCHAR(50) UNIQUE NOT NULL COMMENT '用户emosid，格式：e开头s结尾（如：e0E446ZE6s）',
    telegram_id BIGINT UNIQUE COMMENT 'Telegram用户ID',
    token VARCHAR(255) UNIQUE COMMENT '用户令牌，格式：1047_开头的字符串',
    username VARCHAR(255) COMMENT '登录用户名',
    first_name VARCHAR(255) COMMENT 'Telegram名字',
    last_name VARCHAR(255) COMMENT 'Telegram姓氏',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '注册时间',
    INDEX idx_user_id (user_id),
    INDEX idx_telegram_id (telegram_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户信息表';

-- 2. balances（余额表）
CREATE TABLE IF NOT EXISTS balances (
    user_id INT PRIMARY KEY COMMENT '关联users表的id',
    balance INT DEFAULT 0 COMMENT '游戏币余额（默认0币）',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '最后更新时间',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='用户余额表';

-- 3. daily_checkins（签到表）
CREATE TABLE IF NOT EXISTS daily_checkins (
    user_id INT PRIMARY KEY COMMENT '关联users表的id',
    last_checkin TIMESTAMP NOT NULL COMMENT '上次签到时间',
    checkin_streak INT DEFAULT 1 COMMENT '连续签到天数',
    total_checkins INT DEFAULT 1 COMMENT '总签到次数',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='每日签到表';

-- 4. game_records（游戏记录表）
CREATE TABLE IF NOT EXISTS game_records (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '记录ID',
    user_id INT NOT NULL COMMENT '关联users表的id',
    game_type VARCHAR(50) NOT NULL COMMENT '游戏类型：dice/slot/coinflip等',
    bet_amount INT NOT NULL COMMENT '下注金额',
    result VARCHAR(50) NOT NULL COMMENT '游戏结果：win/lose/draw',
    win_amount INT NOT NULL COMMENT '赢得的金额（负数表示输）',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '游戏时间',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_created (user_id, created_at),
    INDEX idx_game_type (game_type)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='游戏记录表';

-- 5. recharge_orders（充值订单表）
CREATE TABLE IF NOT EXISTS recharge_orders (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '订单ID',
    order_no VARCHAR(100) UNIQUE NOT NULL COMMENT '平台内部订单号',
    user_id INT NOT NULL COMMENT '关联users表的id',
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
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_status (status),
    INDEX idx_telegram_user (telegram_user_id),
    INDEX idx_platform_no (platform_order_no),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='充值订单表';

-- 6. withdraw_orders（提现订单表）
CREATE TABLE IF NOT EXISTS withdraw_orders (
    id INT AUTO_INCREMENT PRIMARY KEY COMMENT '提现订单ID',
    order_no VARCHAR(100) UNIQUE NOT NULL COMMENT '提现订单号',
    user_id INT NOT NULL COMMENT '关联users表的id',
    telegram_user_id BIGINT NOT NULL COMMENT 'Telegram用户ID',
    game_coin_amount INT NOT NULL COMMENT '提现游戏币数量',
    carrot_amount INT NOT NULL COMMENT '获得萝卜数量',
    status VARCHAR(20) DEFAULT 'pending' COMMENT '订单状态：pending(待处理)/processing(处理中)/success(成功)/failed(失败)',
    transfer_result TEXT COMMENT '转账结果信息',
    admin_note TEXT COMMENT '管理员备注',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_status (status),
    INDEX idx_telegram_user (telegram_user_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='提现订单表';

-- 7. provider_config（服务商配置表）
CREATE TABLE IF NOT EXISTS provider_config (
    id INT PRIMARY KEY DEFAULT 1 COMMENT '固定为1，单行配置',
    provider_name VARCHAR(255) NOT NULL COMMENT '服务商名称',
    provider_description TEXT COMMENT '服务商描述',
    notify_url VARCHAR(500) COMMENT '回调地址',
    api_key VARCHAR(255) COMMENT 'API密钥',
    api_secret VARCHAR(255) COMMENT 'API密钥',
    is_active BOOLEAN DEFAULT TRUE COMMENT '是否启用',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP COMMENT '更新时间',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP COMMENT '创建时间'
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='服务商配置表';

-- 初始化服务商配置
INSERT INTO provider_config (id, provider_name, is_active) 
VALUES (1, 'emosMagicBox_bot', TRUE)
ON DUPLICATE KEY UPDATE 
    provider_name = VALUES(provider_name),
    is_active = VALUES(is_active);

-- 显示创建的表
SHOW TABLES;

-- 显示每个表的结构
DESCRIBE users;
DESCRIBE balances;
DESCRIBE daily_checkins;
DESCRIBE game_records;
DESCRIBE recharge_orders;
DESCRIBE withdraw_orders;
DESCRIBE provider_config;

-- 显示服务商配置
SELECT * FROM provider_config;