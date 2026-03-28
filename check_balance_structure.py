#!/usr/bin/env python3
# 检查balance表结构

from app.database import get_db_connection

def check_balance_structure():
    """检查balance表结构"""
    print("开始检查balance表结构...")
    
    connection = get_db_connection()
    if not connection:
        print("❌ 数据库连接失败")
        return
    
    try:
        with connection.cursor() as cursor:
            # 检查balance表结构
            cursor.execute('DESCRIBE balances')
            print("Balance表结构:")
            for row in cursor.fetchall():
                print(row)
            
            # 检查balance表中的数据
            cursor.execute('SELECT * FROM balances')
            print("\nBalance表数据:")
            for row in cursor.fetchall():
                print(row)
                
    except Exception as e:
        print(f"❌ 检查过程中出错: {e}")
    finally:
        connection.close()

if __name__ == "__main__":
    check_balance_structure()
