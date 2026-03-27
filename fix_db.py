import pymysql
from config import DB_CONFIG

# 连接到MySQL数据库
def fix_database():
    print("开始修复数据库字段类型...")
    try:
        # 建立数据库连接
        connection = pymysql.connect(
            **DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor
        )
        print("✅ 数据库连接成功")
        
        with connection.cursor() as cursor:
            # 查看当前表结构
            print("\n查看当前users表结构:")
            cursor.execute('DESCRIBE users')
            result = cursor.fetchall()
            for row in result:
                print(f"{row['Field']}: {row['Type']} - {row['Null']} - {row['Key']} - {row['Default']} - {row['Extra']}")
            
            # 修改token字段类型为VARCHAR
            print("\n修改token字段类型为VARCHAR(255)...")
            cursor.execute('ALTER TABLE users MODIFY token VARCHAR(255)')
            print("✅ token字段类型修改成功")
            
            # 检查username字段类型
            print("\n检查username字段类型...")
            cursor.execute('DESCRIBE users')
            result = cursor.fetchall()
            for row in result:
                if row['Field'] == 'username':
                    print(f"当前username字段类型: {row['Type']}")
                    if row['Type'] != 'varchar(255)':
                        print("修改username字段类型为VARCHAR(255)...")
                        cursor.execute('ALTER TABLE users MODIFY username VARCHAR(255)')
                        print("✅ username字段类型修改成功")
                    else:
                        print("username字段类型已经是VARCHAR(255)，无需修改")
            
            # 查看修改后的表结构
            print("\n修改后的users表结构:")
            cursor.execute('DESCRIBE users')
            result = cursor.fetchall()
            for row in result:
                print(f"{row['Field']}: {row['Type']} - {row['Null']} - {row['Key']} - {row['Default']} - {row['Extra']}")
        
        connection.commit()
        print("\n✅ 数据库修复完成")
        
    except Exception as e:
        print(f"❌ 数据库修复失败: {e}")
    finally:
        if 'connection' in locals():
            connection.close()

if __name__ == "__main__":
    fix_database()
