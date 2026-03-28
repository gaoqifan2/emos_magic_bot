# 检查game_db数据库的users表结构

import pymysql
from config import DB_CONFIG

# 连接game_db数据库
config = DB_CONFIG.copy()
config['db'] = 'game_db'

print("开始检查game_db数据库的users表结构...")

try:
    # 连接数据库
    connection = pymysql.connect(**config)
    print("✅ 连接数据库成功")
    
    with connection.cursor() as cursor:
        # 检查表是否存在
        cursor.execute("SHOW TABLES LIKE 'users'")
        table_exists = cursor.fetchone()
        print(f"🔍 users表是否存在: {table_exists is not None}")
        
        if table_exists:
            # 查看表结构
            cursor.execute("DESCRIBE users")
            columns = cursor.fetchall()
            print("\n📋 users表字段结构:")
            print("+----------------------+------------------+------+-----+-------------------+-------------------+")
            print("| Field                | Type             | Null | Key | Default           | Extra             |")
            print("+----------------------+------------------+------+-----+-------------------+-------------------+")
            
            has_current_cycle_score = False
            for column in columns:
                field = column[0]
                type_ = column[1]
                null = column[2]
                key = column[3]
                default = column[4]
                extra = column[5]
                print(f"| {field:20} | {type_:16} | {null:4} | {key:3} | {str(default):17} | {extra:17} |")
                if field == 'current_cycle_score':
                    has_current_cycle_score = True
            
            print("+----------------------+------------------+------+-----+-------------------+-------------------+")
            print(f"\n🔍 current_cycle_score字段是否存在: {has_current_cycle_score}")
        else:
            print("❌ users表不存在")
            
finally:
    # 关闭连接
    if 'connection' in locals():
        connection.close()
        print("\n✅ 数据库连接已关闭")
