import pymysql
from config import DB_CONFIG

# 连接数据库
conn = pymysql.connect(**DB_CONFIG)
cursor = conn.cursor()

try:
    # 添加telegram_id字段
    print("添加telegram_id字段...")
    cursor.execute('ALTER TABLE users ADD COLUMN telegram_id BIGINT UNIQUE COMMENT "Telegram用户ID"')
    
    # 添加索引
    print("添加telegram_id索引...")
    cursor.execute('CREATE INDEX idx_telegram_id ON users(telegram_id)')
    
    conn.commit()
    print("\n数据库表结构更新成功！")
    
    # 查看更新后的表结构
    print("\n更新后的Users表结构:")
    cursor.execute('DESCRIBE users')
    for row in cursor.fetchall():
        print(row)
        
except Exception as e:
    print(f"错误: {e}")
    conn.rollback()
finally:
    # 关闭连接
    conn.close()
    print("\n数据库操作完成")