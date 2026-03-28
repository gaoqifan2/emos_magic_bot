# 同步数据库结构到game_db，仅同步结构，不同步数据

import pymysql
from config import DB_CONFIG

# 源数据库配置（当前使用的数据库）
source_config = DB_CONFIG

# 目标数据库配置（game_db）
target_config = DB_CONFIG.copy()
target_config['db'] = 'game_db'

def get_table_structures(connection):
    """获取数据库中所有表的结构"""
    structures = {}
    with connection.cursor() as cursor:
        # 获取所有表名
        cursor.execute("SHOW TABLES")
        tables = cursor.fetchall()
        
        for table in tables:
            table_name = table[0]  # 使用元组索引获取表名
            # 获取表结构
            cursor.execute(f"SHOW CREATE TABLE {table_name}")
            create_table_result = cursor.fetchone()
            create_table_sql = create_table_result[1]  # 使用索引获取CREATE TABLE语句
            structures[table_name] = create_table_sql
    return structures

def sync_structures(source_config, target_config):
    """同步数据库结构"""
    print("开始同步数据库结构...")
    
    # 连接源数据库
    source_conn = None
    target_conn = None
    
    try:
        # 连接源数据库
        source_conn = pymysql.connect(**source_config)
        print("✅ 连接源数据库成功")
        
        # 连接目标数据库
        target_conn = pymysql.connect(**target_config)
        print("✅ 连接目标数据库成功")
        
        # 获取源数据库表结构
        source_structures = get_table_structures(source_conn)
        print(f"✅ 获取到 {len(source_structures)} 个表结构")
        
        # 同步结构到目标数据库
        with target_conn.cursor() as cursor:
            for table_name, create_sql in source_structures.items():
                try:
                    if table_name == 'users':
                        # 对于users表，使用ALTER TABLE添加缺失的字段
                        # 首先检查表是否存在
                        cursor.execute("SHOW TABLES LIKE 'users'")
                        if cursor.fetchone():
                            # 表存在，检查并添加缺失的字段
                            # 检查current_cycle_score字段
                            cursor.execute("SHOW COLUMNS FROM users LIKE 'current_cycle_score'")
                            if not cursor.fetchone():
                                cursor.execute("ALTER TABLE users ADD COLUMN current_cycle_score INT DEFAULT 0 COMMENT '当前周期贡献分（每下注1币增加1分，中奖后归零）'")
                                print("✅ 为users表添加current_cycle_score字段")
                            print(f"✅ 同步表结构: {table_name}")
                        else:
                            # 表不存在，直接创建
                            cursor.execute(create_sql)
                            print(f"✅ 创建表结构: {table_name}")
                    else:
                        # 其他表直接删除并重建
                        cursor.execute(f"DROP TABLE IF EXISTS {table_name}")
                        cursor.execute(create_sql)
                        print(f"✅ 同步表结构: {table_name}")
                except Exception as e:
                    print(f"❌ 同步表结构失败: {table_name}, 错误: {e}")
            
            # 提交事务
            target_conn.commit()
        
        print("\n🎉 数据库结构同步完成！")
        
    except Exception as e:
        print(f"❌ 同步失败: {e}")
    finally:
        # 关闭连接
        if source_conn:
            source_conn.close()
        if target_conn:
            target_conn.close()

if __name__ == "__main__":
    sync_structures(source_config, target_config)
