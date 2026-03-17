import pymysql
from config import DB_CONFIG

print("检查数据库结构...")
try:
    # 连接数据库
    conn = pymysql.connect(**DB_CONFIG)
    print("✅ 数据库连接成功")
    
    cursor = conn.cursor()
    
    # 查看recharge_orders表结构
    print("\nRecharge_orders表结构:")
    cursor.execute('DESCRIBE recharge_orders')
    for row in cursor.fetchall():
        print(row)
    
    # 查看provider_config表结构
    print("\nProvider_config表结构:")
    cursor.execute('DESCRIBE provider_config')
    for row in cursor.fetchall():
        print(row)
    
    # 查看是否有数据
    print("\nRecharge_orders表数据:")
    cursor.execute('SELECT * FROM recharge_orders LIMIT 3')
    rows = cursor.fetchall()
    if rows:
        for row in rows:
            print(row)
    else:
        print("暂无数据")
    
    # 关闭连接
    conn.close()
    print("\n✅ 数据库检查完成")
    
except Exception as e:
    print(f"❌ 数据库操作失败: {e}")
