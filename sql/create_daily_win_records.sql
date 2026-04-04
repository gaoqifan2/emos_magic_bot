-- 每日赢取记录表
-- 用于限制用户每天从AI游戏赢取的金额

CREATE TABLE IF NOT EXISTS daily_win_records (
    user_id VARCHAR(50) PRIMARY KEY,
    username VARCHAR(100),
    win_amount INT DEFAULT 0,
    win_date DATE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_win_date (win_date)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
