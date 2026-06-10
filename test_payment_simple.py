#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
简单测试支付完成链接的处理逻辑
"""

import pymysql
import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from config import DB_CONFIG
from app.database import get_recharge_order_by_platform_no, update_recharge_order_status, get_balance

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
            platform_order_no = f"TEST{datetime.now().strftime('%Y%m%d%H%M%S%f')}payTest123"
            
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

def cleanup_test_orders():
    """清理测试订单"""
    connection = get_db_connection()
    if not connection:
        return
    
    try:
        with connection.cursor() as cursor:
            # 删除所有测试订单
            cursor.execute('DELETE FROM recharge_orders WHERE order_no LIKE %s', ('TEST%',))
            connection.commit()
            print("清理测试订单成功")
    except Exception as e:
        print(f"清理测试订单失败: {e}")
        connection.rollback()
    finally:
        connection.close()

def check_order_status(platform_order_no):
    """检查订单状态"""
    print(f"检查订单状态，平台订单号: {platform_order_no}")
    try:
        order = get_recharge_order_by_platform_no(platform_order_no)
        if order:
            print(f"订单状态: {order['status']}")
            print(f"用户ID: {order['user_id']}")
            print(f"游戏币数量: {order['game_coin_amount']}")
        else:
            print("获取订单状态失败")
    except Exception as e:
        print(f"检查订单状态时出错: {e}")

def check_user_balance(user_id):
    """检查用户余额"""
    balance = get_balance(user_id)
    print(f"用户余额: {balance} 🪙")
    return balance

def simulate_payment_link_click(platform_order_no):
    """模拟点击支付完成链接"""
    print(f"\n模拟点击支付完成链接: emosPayAgree-{platform_order_no}-order123-user123")
    
    # 检查订单是否已经处理过
    order = get_recharge_order_by_platform_no(platform_order_no)
    
    if order:
        if order['status'] == 'success':
            # 订单已经处理过，不给加余额
            print("❌ 该订单已经处理过，请勿重复点击链接！")
            return False
        else:
            # 订单未处理过，处理支付结果
            game_coin_amount = order['game_coin_amount']
            result = update_recharge_order_status(platform_order_no, 'success', game_coin_amount)
            
            if result:
                # 显示支付成功消息
                emos_user_id = order['user_id']
                carrot_amount = order['carrot_amount']
                new_balance = get_balance(emos_user_id)
                
                print(f"🎉 支付成功！")
                print(f"订单号：{platform_order_no}")
                print(f"充值金额：{carrot_amount} 萝卜")
                print(f"获得游戏币：{game_coin_amount} 🪙")
                print(f"当前余额：{new_balance} 🪙")
                return True
            else:
                print("❌ 处理支付结果失败！")
                return False
    else:
        # 订单不存在
        print("❌ 订单不存在，请检查链接是否正确！")
        return False

def main():
    """主函数"""
    print("=== 测试支付完成链接处理逻辑 ===")
    
    # 清理之前的测试订单
    print("\n清理之前的测试订单")
    cleanup_test_orders()
    
    # 步骤1: 添加测试订单
    print("\n步骤1: 添加测试订单")
    platform_order_no = add_test_order()
    if not platform_order_no:
        print("添加测试订单失败，退出测试")
        return
    
    # 步骤2: 检查初始订单状态和用户余额
    print("\n步骤2: 检查初始状态")
    check_order_status(platform_order_no)
    check_user_balance('test_user_id')
    
    # 步骤3: 第一次点击支付完成链接
    print("\n步骤3: 第一次点击支付完成链接")
    simulate_payment_link_click(platform_order_no)
    
    # 步骤4: 检查订单状态和用户余额
    print("\n步骤4: 检查第一次点击后的状态")
    check_order_status(platform_order_no)
    check_user_balance('test_user_id')
    
    # 步骤5: 第二次点击支付完成链接
    print("\n步骤5: 第二次点击支付完成链接")
    simulate_payment_link_click(platform_order_no)
    
    # 步骤6: 检查订单状态和用户余额
    print("\n步骤6: 检查第二次点击后的状态")
    check_order_status(platform_order_no)
    check_user_balance('test_user_id')
    
    print("\n=== 测试完成 ===")

if __name__ == "__main__":
    print("开始测试...")
    # 重定向输出到文件
    import sys
    original_stdout = sys.stdout
    with open('test_payment_output.txt', 'w', encoding='utf-8') as f:
        sys.stdout = f
        try:
            main()
            print("测试完成")
        except Exception as e:
            print(f"测试过程中出错: {e}")
            import traceback
            traceback.print_exc()
        finally:
            sys.stdout = original_stdout
    print("测试完成，输出已保存到 test_payment_output.txt")
    # 读取并显示输出文件内容
    with open('test_payment_output.txt', 'r', encoding='utf-8') as f:
        print("\n测试输出:")
        print(f.read())
