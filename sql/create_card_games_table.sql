-- 创建扑克牌游戏表
CREATE TABLE IF NOT EXISTS card_games (
    game_id VARCHAR(100) PRIMARY KEY,
    chat_id BIGINT NOT NULL,
    creator_id VARCHAR(50) NOT NULL,
    creator_name VARCHAR(100),
    opponent_id VARCHAR(50),
    opponent_name VARCHAR(100),
    amount INT NOT NULL,
    creator_card VARCHAR(10),
    opponent_card VARCHAR(10),
    winner_id VARCHAR(50),
    status VARCHAR(20) DEFAULT 'waiting', -- waiting, playing, finished
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    finished_at TIMESTAMP
);

-- 创建索引
CREATE INDEX IF NOT EXISTS idx_card_games_chat_id ON card_games(chat_id);
CREATE INDEX IF NOT EXISTS idx_card_games_status ON card_games(status);
CREATE INDEX IF NOT EXISTS idx_card_games_creator_id ON card_games(creator_id);
