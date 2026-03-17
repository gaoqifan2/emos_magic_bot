import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import DB_CONFIG
import pymysql

print("=" * 60)
print("测试数据库连接")
print("=" * 60)
print(f"主机: {DB_CONFIG['host']}")
print(f"端口: {DB_CONFIG['port']}")
print(f"用户: {DB_CONFIG['user']}")
print(f"数据库: {DB_CONFIG['database']}")
print("=" * 60)

try:
    conn = pymysql.connect(**DB_CONFIG)
    print("✅ 数据库连接成功！")
    
    with conn.cursor() as cursor:
        # 测试查询
        cursor.execute("SELECT VERSION()")
        version = cursor.fetchone()
        print(f"📊 数据库版本: {version[0]}")
        
        # 查看表
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        print(f"\n📋 数据库中的表 ({len(tables)}个):")
        for table in tables:
            print(f"   - {table[0]}")
        
        # 查看users表结构（如果存在）
        if any('users' in t for t in tables):
            print("\n👤 users表结构:")
            cursor.execute("DESCRIBE users")
            columns = cursor.fetchall()
            for col in columns:
                print(f"   - {col[0]}: {col[1]}")
        
        # 查看recharge_orders表结构（如果存在）
        if any('recharge_orders' in t for t in tables):
            print("\n💰 recharge_orders表结构:")
            cursor.execute("DESCRIBE recharge_orders")
            columns = cursor.fetchall()
            for col in columns:
                print(f"   - {col[0]}: {col[1]}")
    
    conn.close()
    print("\n✅ 所有测试通过！")
    
except Exception as e:
    print(f"\n❌ 数据库连接失败: {e}")
    import traceback
    traceback.print_exc()
