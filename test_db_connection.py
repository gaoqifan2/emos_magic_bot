#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试数据库连接
"""

import pymysql
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DB_CONFIG

def test_db_connection():
    """测试数据库连接"""
    print("=== 测试数据库连接 ===")
    
    try:
        # 尝试连接数据库
        connection = pymysql.connect(
            **DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor
        )
        print("✅ 数据库连接成功")
        
        # 测试执行SQL语句
        with connection.cursor() as cursor:
            cursor.execute('SELECT 1')
            result = cursor.fetchone()
            print(f"✅ SQL执行成功: {result}")
        
        # 测试查询充值订单表
        with connection.cursor() as cursor:
            cursor.execute('SELECT * FROM recharge_orders LIMIT 1')
            result = cursor.fetchone()
            if result:
                print("✅ 充值订单表查询成功")
                print(f"订单号: {result.get('order_no')}")
                print(f"状态: {result.get('status')}")
            else:
                print("⚠️  充值订单表为空")
        
        # 关闭连接
        connection.close()
        print("✅ 数据库连接测试完成")
        return True
    except Exception as e:
        print(f"❌ 数据库连接失败: {e}")
        return False

if __name__ == "__main__":
    test_db_connection()
