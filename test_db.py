#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""测试数据库连接"""

import time
import sys

print("=" * 50)
print("数据库连接测试")
print("=" * 50)

try:
    print("正在导入模块...")
    from app.database.db import get_db_connection
    from config import DB_CONFIG
    
    print(f"数据库配置:")
    print(f"  主机: {DB_CONFIG.get('host')}")
    print(f"  端口: {DB_CONFIG.get('port', 3306)}")
    print(f"  数据库: {DB_CONFIG.get('database')}")
    print(f"  用户: {DB_CONFIG.get('user')}")
    
    print("\n正在连接数据库...")
    start = time.time()
    conn = get_db_connection()
    elapsed = time.time() - start
    
    if conn:
        print(f"✅ 数据库连接成功！耗时: {elapsed:.2f}秒")
        
        # 测试查询
        print("\n测试查询...")
        with conn.cursor() as cursor:
            cursor.execute("SELECT 1 as test")
            result = cursor.fetchone()
            print(f"查询结果: {result}")
        
        conn.close()
        print("✅ 数据库测试通过！")
    else:
        print(f"❌ 数据库连接失败！耗时: {elapsed:.2f}秒")
        sys.exit(1)
        
except Exception as e:
    print(f"❌ 发生错误: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)
