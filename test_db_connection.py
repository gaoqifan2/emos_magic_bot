#!/usr/bin/env python3
# 测试数据库连接

import pymysql

# 数据库配置
db_config = {
    'host': '66.235.105.125',
    'port': 3306,
    'user': 'root',
    'password': 'H_fans200109~',
    'cursorclass': pymysql.cursors.DictCursor,
    'connect_timeout': 10
}

def test_db_connection(db_name):
    """测试数据库连接"""
    print(f"测试连接到 {db_name} 数据库...")
    
    try:
        # 连接数据库
        connection = pymysql.connect(
            **db_config,
            database=db_name
        )
        print(f"✅ 成功连接到 {db_name} 数据库")
        
        # 获取表列表
        with connection.cursor() as cursor:
            cursor.execute("SHOW TABLES")
            tables = cursor.fetchall()
            table_names = [table[f'Tables_in_{db_name}'] for table in tables]
            print(f"找到 {len(table_names)} 个表：{table_names}")
        
        connection.close()
        return True
    except Exception as e:
        print(f"❌ 连接过程中出错: {e}")
        return False

if __name__ == "__main__":
    # 测试连接到 game_db_test
    test_db_connection('game_db_test')
    
    # 测试连接到 game_db
    test_db_connection('game_db')
