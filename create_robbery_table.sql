-- 创建打劫记录表
CREATE TABLE IF NOT EXISTS robbery_records (
    id INT AUTO_INCREMENT PRIMARY KEY,
    user_id VARCHAR(255) NOT NULL UNIQUE COMMENT 'emos用户ID',
    username VARCHAR(255) COMMENT '用户名称',
    robbery_count INT DEFAULT 0 COMMENT '今日打劫次数',
    robbery_date DATE NOT NULL COMMENT '日期',
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_user_id (user_id),
    INDEX idx_date (robbery_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci COMMENT='打劫记录表';
