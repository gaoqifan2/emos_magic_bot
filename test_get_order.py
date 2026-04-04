#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
测试 get_recharge_order_by_platform_no 函数
"""

import sys
import os

# 添加项目根目录到Python路径
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from app.database import get_recharge_order_by_platform_no

print("开始测试 get_recharge_order_by_platform_no 函数...")

try:
    # 测试一个已知的平台订单号
    platform_order_no = "TEST20260405002135payTest123"
    print(f"测试平台订单号: {platform_order_no}")
    
    order = get_recharge_order_by_platform_no(platform_order_no)
    print(f"订单: {order}")
    
    print("测试完成")
except Exception as e:
    print(f"测试过程中出错: {e}")
    import traceback
    traceback.print_exc()
