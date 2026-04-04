#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试支付完成链接的处理逻辑
"""

import pymysql
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DB_CONFIG

def get_db_connection():
    """获取数据库连接"""
    try:
        connection = pymysql.connect(
            **DB_CONFIG,
            cursorclass=pymysql.cursors.DictCursor
        )
        return connection
    except Exception as e:
        print(f"数据库连接失败: {e}")
        return None

def add_test_order():
    """添加测试订单"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            # 生成测试订单号
            import uuid
            from datetime import datetime
            order_no = f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}{str(uuid.uuid4())[:8].upper()}"
            platform_order_no = f"TEST{datetime.now().strftime('%Y%m%d%H%M%S')}payTest123"
            
            # 插入测试订单
            cursor.execute('''
                INSERT INTO recharge_orders 
                (order_no, user_id, username, telegram_user_id, carrot_amount, game_coin_amount, 
                 status, platform_order_no, pay_url, created_at, updated_at)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
            ''', (
                order_no, 
                'test_user_id', 
                'test_user', 
                123456789, 
                1, 
                10, 
                'pending', 
                platform_order_no, 
                'https://example.com/pay'
            ))
            
            connection.commit()
            print(f"添加测试订单成功: {order_no}")
            print(f"平台订单号: {platform_order_no}")
            return platform_order_no
    except Exception as e:
        print(f"添加测试订单失败: {e}")
        connection.rollback()
        return None
    finally:
        connection.close()

def check_order_status(platform_order_no):
    """检查订单状态"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT * FROM recharge_orders 
                WHERE platform_order_no = %s
            ''', (platform_order_no,))
            return cursor.fetchone()
    except Exception as e:
        print(f"检查订单状态失败: {e}")
        return None
    finally:
        connection.close()

def check_user_balance(user_id):
    """检查用户余额"""
    connection = get_db_connection()
    if not connection:
        return None
    
    try:
        with connection.cursor() as cursor:
            cursor.execute('''
                SELECT balance FROM balances 
                WHERE user_id = %s
            ''', (user_id,))
            result = cursor.fetchone()
            return result['balance'] if result else 0
    except Exception as e:
        print(f"检查用户余额失败: {e}")
        return None
    finally:
        connection.close()

def simulate_payment_link_click(platform_order_no):
    """模拟点击支付完成链接"""
    print(f"\n模拟点击支付完成链接: emosPayAgree-{platform_order_no}-order123-user123")
    
    # 导入处理函数
    sys.path.append(os.path.dirname(os.path.abspath(__file__)))
    from app.handlers.command_handlers import start_handler
    
    # 模拟Update和Context对象
    class MockUpdate:
        def __init__(self, platform_order_no):
            self.message = self
            self.text = f"/start emosPayAgree-{platform_order_no}-order123-user123"
            self.effective_user = self
            self.id = 123456789
            self.username = "test_user"
            self.first_name = "Test"
            self.last_name = "User"
            # 添加chat属性
            self.chat = self
            self.type = "private"
            # 添加callback_query属性
            self.callback_query = None
        
        async def reply_text(self, text):
            print(f"[Mock] 发送消息: {text}")
            return None
    
    class MockContext:
        def __init__(self):
            self.args = []
            self.user_data = {}
    
    # 解析命令参数
    update = MockUpdate(platform_order_no)
    context = MockContext()
    context.args = update.text.split(' ')[1:]
    
    # 调用处理函数
    import asyncio
    asyncio.run(start_handler(update, context))

def main():
    """主函数"""
    print("=== 测试支付完成链接处理逻辑 ===")
    
    # 步骤1: 添加测试订单
    print("\n步骤1: 添加测试订单")
    platform_order_no = add_test_order()
    if not platform_order_no:
        print("添加测试订单失败，退出测试")
        return
    
    # 步骤2: 检查初始订单状态和用户余额
    print("\n步骤2: 检查初始状态")
    order = check_order_status(platform_order_no)
    if order:
        print(f"初始订单状态: {order['status']}")
    else:
        print("获取订单状态失败")
    
    balance = check_user_balance('test_user_id')
    print(f"初始用户余额: {balance} 🪙")
    
    # 步骤3: 第一次点击支付完成链接
    print("\n步骤3: 第一次点击支付完成链接")
    simulate_payment_link_click(platform_order_no)
    
    # 步骤4: 检查订单状态和用户余额
    print("\n步骤4: 检查第一次点击后的状态")
    order = check_order_status(platform_order_no)
    if order:
        print(f"订单状态: {order['status']}")
    else:
        print("获取订单状态失败")
    
    balance = check_user_balance('test_user_id')
    print(f"用户余额: {balance} 🪙")
    
    # 步骤5: 第二次点击支付完成链接
    print("\n步骤5: 第二次点击支付完成链接")
    simulate_payment_link_click(platform_order_no)
    
    # 步骤6: 检查订单状态和用户余额
    print("\n步骤6: 检查第二次点击后的状态")
    order = check_order_status(platform_order_no)
    if order:
        print(f"订单状态: {order['status']}")
    else:
        print("获取订单状态失败")
    
    balance = check_user_balance('test_user_id')
    print(f"用户余额: {balance} 🪙")
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    main()
