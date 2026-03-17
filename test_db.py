import pymysql
from config import DB_CONFIG

print("测试数据库连接...")
try:
    # 连接数据库
    conn = pymysql.connect(**DB_CONFIG)
    print("✅ 数据库连接成功")
    
    cursor = conn.cursor()
    
    # 测试基本查询
    print("\n测试查询数据库版本...")
    cursor.execute('SELECT VERSION()')
    version = cursor.fetchone()
    print(f"数据库版本: {version[0]}")
    
    # 查看数据库中的表
    print("\n查看数据库中的表...")
    cursor.execute('SHOW TABLES')
    tables = cursor.fetchall()
    for table in tables:
        print(f"- {table[0]}")
    
    # 查看users表结构
    print("\n查看users表结构...")
    try:
        cursor.execute('DESCRIBE users')
        for row in cursor.fetchall():
            print(row)
    except Exception as e:
        print(f"查看表结构失败: {e}")
    
    # 关闭连接
    conn.close()
    print("\n✅ 数据库操作完成")
    
except Exception as e:
    print(f"❌ 数据库连接失败: {e}")
